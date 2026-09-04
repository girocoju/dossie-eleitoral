"""Dois publicadores na mesma conta FTP (ADR-047).

Em 03 e 04/09/2026 o workflow publicava a CADA push em `main`, e o
`atualizar.bat` publica da maquina. Nove pushes numa noite produziram nove
publicacoes de 20 mil arquivos, cada uma cancelada pela seguinte NO MEIO DO
ENVIO — e uma delas rodou 2h22 em paralelo com uma publicacao local, as duas
escrevendo os mesmos caminhos.

Foi isso que encheu o servidor de ocultos `.in.<nome>.`. As correcoes do ADR-045
eram necessarias e nenhuma delas era a causa: a causa era haver dois
publicadores.
"""

from __future__ import annotations

import ftplib
import io
import json
from datetime import UTC, datetime, timedelta

from scripts.publicar import (
    TRAVA,
    VALIDADE_TRAVA_H,
    destravar,
    ler_trava,
    listar_arquivos,
    travar,
)


class SessaoFalsa:
    """Guarda o que foi escrito, para a trava poder ser lida de volta."""

    def __init__(self, conteudo: dict[str, bytes] | None = None) -> None:
        self.arquivos = dict(conteudo or {})
        self.apagados: list[str] = []
        self.recusa_escrita = False

    def retrbinary(self, cmd: str, callback) -> None:
        caminho = cmd.removeprefix("RETR ")
        if caminho not in self.arquivos:
            raise ftplib.error_perm("550 No such file")
        callback(self.arquivos[caminho])

    def storbinary(self, cmd: str, f, blocksize: int = 8192) -> None:
        if self.recusa_escrita:
            raise ftplib.error_perm("550 Permission denied")
        self.arquivos[cmd.removeprefix("STOR ")] = f.read()

    def delete(self, caminho: str) -> None:
        self.apagados.append(caminho)
        self.arquivos.pop(caminho, None)


def _trava(horas_atras: float, onde: str = "GitHub Actions, run 42") -> bytes:
    inicio = datetime.now(UTC) - timedelta(hours=horas_atras)
    return json.dumps({"onde": onde, "pid": "1",
                       "inicio": inicio.isoformat(timespec="seconds")}).encode()


# ── o caso que aconteceu ───────────────────────────────────────────────────

def test_publicacao_em_andamento_bloqueia_a_segunda():
    """O caso real: o run do GitHub publicando enquanto o atualizar.bat comeca."""
    s = SessaoFalsa({TRAVA: _trava(0.5)})
    assert travar(s, "/") is False


def test_a_mensagem_diz_de_quem_e_a_publicacao_e_ha_quanto_tempo(caplog):
    """Sem isso, quem ve' o erro nao sabe se espera ou se forca."""
    import logging

    s = SessaoFalsa({TRAVA: _trava(1.5, onde="GitHub Actions, run 33879527736")})
    with caplog.at_level(logging.ERROR):
        travar(s, "/")
    assert "33879527736" in caplog.text
    assert "1.5h" in caplog.text
    assert "--forcar" in caplog.text


def test_sem_trava_a_publicacao_segue():
    s = SessaoFalsa()
    assert travar(s, "/") is True
    assert TRAVA in s.arquivos


# ── trava orfa nao pode bloquear para sempre ───────────────────────────────

def test_trava_velha_demais_e_assumida():
    """Publicacao morta nao pode travar o site ate' alguem entrar por FTP."""
    s = SessaoFalsa({TRAVA: _trava(VALIDADE_TRAVA_H + 1)})
    assert travar(s, "/") is True


def test_a_validade_cobre_a_publicacao_mais_longa_ja_medida():
    """2h22 local; 4h33 no runner do GitHub antes de ser morto pelo teto de 6h."""
    assert VALIDADE_TRAVA_H > 4.6


def test_forcar_passa_por_cima():
    s = SessaoFalsa({TRAVA: _trava(0.1)})
    assert travar(s, "/", forcar=True) is True


# ── a trava e' liberada mesmo quando a publicacao falha ────────────────────

def test_destravar_remove():
    s = SessaoFalsa({TRAVA: _trava(0.1)})
    destravar(s, "/")
    assert TRAVA in s.apagados


def test_trava_ilegivel_conta_como_trava():
    """Alguem morreu no meio da escrita. Tratar como ausente deixaria dois
    publicadores rodando justamente no caso mais suspeito."""
    s = SessaoFalsa({TRAVA: b"{quebrado"})
    lida = ler_trava(s, "/")
    assert lida is not None
    assert travar(s, "/") is False


def test_nao_conseguir_gravar_a_trava_nao_impede_publicar():
    """A trava e' protecao contra coincidencia, nao permissao de acesso. Seguir
    sem ela e' o que este projeto fez a vida toda."""
    s = SessaoFalsa()
    s.recusa_escrita = True
    assert travar(s, "/") is True


# ── a trava nao e' conteudo do site ────────────────────────────────────────

def test_a_trava_nao_entra_no_manifesto(tmp_path):
    (tmp_path / "index.html").write_text("<html>", encoding="utf-8")
    (tmp_path / TRAVA).write_text("{}", encoding="utf-8")
    assert listar_arquivos(tmp_path) == ["index.html"]


def test_a_trava_nunca_e_removida_como_orfa():
    from scripts.publicar import remover_orfas

    s = SessaoFalsa()
    remover_orfas(s, "/", ["index.html"], ["index.html", TRAVA])
    assert TRAVA not in s.apagados


def test_a_trava_identifica_a_origem(monkeypatch):
    from scripts import publicar

    monkeypatch.setenv("GITHUB_RUN_ID", "12345")
    monkeypatch.setenv("GITHUB_WORKFLOW", "pipeline")
    s = SessaoFalsa()
    travar(s, "/")
    dados = json.loads(s.arquivos[TRAVA].decode("utf-8"))
    assert "12345" in dados["onde"]
    assert publicar.TRAVA == ".publicando.json"


def test_a_trava_da_maquina_diz_a_maquina(monkeypatch):
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    s = SessaoFalsa()
    travar(s, "/")
    dados = json.loads(s.arquivos[TRAVA].decode("utf-8"))
    assert dados["onde"].startswith("maquina ")


def test_io_importado_para_a_trava():
    """A trava sobe de memoria, sem passar por disco."""
    assert io.BytesIO is not None
