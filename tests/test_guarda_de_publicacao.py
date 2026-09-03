"""Publicar nao pode sobrescrever conteudo mais novo com conteudo mais velho.

Em 03/09/2026 uma execucao do CI gerou o site as 02:54 a partir de um commit
ANTERIOR e publicou por cima de uma publicacao manual de 01:41 que ja' trazia a
correcao da metodologia. A mais recente no relogio era a mais velha no conteudo,
e a pagina voltou a afirmar que uma conferencia nao tinha sido feita — no dia em
que ela foi feita e achou um erro de R$ 24 bilhoes.

Por isso o criterio e' LINHAGEM do commit, nao horario.
"""

from __future__ import annotations

import json

import pytest

from scripts.gerar_site import carimbo_de_publicacao
from scripts.publicar import CARIMBO, conferir_regressao


class SessaoFalsa:
    def __init__(self, remoto: dict | None):
        self.remoto = remoto

    def retrbinary(self, comando: str, callback) -> None:
        import ftplib
        if self.remoto is None:
            raise ftplib.error_perm("550 nao existe")
        callback(json.dumps(self.remoto).encode("utf-8"))


def _local(tmp_path, **campos):
    dados = {"gerado_em": "2026-09-03T00:00:00+00:00", "commit": "a" * 40,
             "arvore_suja": "nao"}
    dados.update(campos)
    (tmp_path / CARIMBO).write_text(json.dumps(dados), encoding="utf-8")
    return tmp_path


def test_o_carimbo_traz_commit_e_estado_da_arvore():
    c = carimbo_de_publicacao()
    assert set(c) == {"gerado_em", "commit", "arvore_suja"}
    assert c["arvore_suja"] in ("sim", "nao")


def test_primeira_publicacao_passa(tmp_path):
    conferir_regressao(SessaoFalsa(None), _local(tmp_path), "/")


def test_arvore_suja_nunca_e_bloqueada(tmp_path, monkeypatch):
    """Publicacao manual nao esta' em commit nenhum — nao pode ser barrada.

    Barrar aqui bloquearia justamente a correcao urgente feita a mao.
    """
    import scripts.publicar as pub
    monkeypatch.setattr(pub, "_e_ancestral", lambda *a: True)
    origem = _local(tmp_path, arvore_suja="sim")
    conferir_regressao(SessaoFalsa({"commit": "b" * 40, "arvore_suja": "nao",
                                    "gerado_em": "2026-09-03T02:00:00+00:00"}),
                       origem, "/")


def test_ancestral_e_recusado(tmp_path, monkeypatch):
    """O caso exato do incidente: CI publicando de um commit anterior."""
    import scripts.publicar as pub
    monkeypatch.setattr(pub, "_e_ancestral", lambda commit, de: True)
    with pytest.raises(SystemExit) as exc:
        conferir_regressao(SessaoFalsa({"commit": "b" * 40, "arvore_suja": "nao",
                                        "gerado_em": "2026-09-03T02:54:00+00:00"}),
                           _local(tmp_path), "/")
    assert "ANCESTRAL" in str(exc.value)
    assert "--forcar" in str(exc.value)


def test_forcar_permite_rollback_deliberado(tmp_path, monkeypatch):
    import scripts.publicar as pub
    monkeypatch.setattr(pub, "_e_ancestral", lambda commit, de: True)
    conferir_regressao(SessaoFalsa({"commit": "b" * 40, "arvore_suja": "nao",
                                    "gerado_em": "2026-09-03T02:54:00+00:00"}),
                       _local(tmp_path), "/", forcar=True)


def test_descendente_passa(tmp_path, monkeypatch):
    """O caso normal: publicar algo mais novo que o que esta' la'."""
    import scripts.publicar as pub
    monkeypatch.setattr(pub, "_e_ancestral", lambda commit, de: False)
    conferir_regressao(SessaoFalsa({"commit": "b" * 40, "arvore_suja": "nao",
                                    "gerado_em": "2026-09-02T00:00:00+00:00"}),
                       _local(tmp_path), "/")


def test_sem_saber_comparar_publica_e_avisa(tmp_path, monkeypatch):
    """Clone raso nao conhece o commit remoto — nao pode travar a publicacao."""
    import scripts.publicar as pub
    monkeypatch.setattr(pub, "_e_ancestral", lambda commit, de: None)
    conferir_regressao(SessaoFalsa({"commit": "b" * 40, "arvore_suja": "nao",
                                    "gerado_em": "2026-09-03T02:00:00+00:00"}),
                       _local(tmp_path), "/")
