"""So' sobe o que mudou — e o manifesto so' fala depois que tudo chegou (ADR-039).

A F-18 leva o site de 1.013 para mais de 20 mil arquivos. Reenviar tudo todo dia
para trocar mil paginas nao e' so' lento: sao horas de sessao FTP aberta, e cada
hora e' mais chance de a conexao cair no meio.

O que este arquivo protege nao e' a economia — e' a correcao dela. Um manifesto
que afirme o hash de um arquivo que nunca chegou faz a publicacao SEGUINTE pular
justamente esse arquivo, e a pagina errada fica congelada no ar sem nenhum erro
em lugar nenhum.
"""

from __future__ import annotations

import ftplib
import json
from pathlib import Path

import pytest

from scripts.publicar import (
    MANIFESTO,
    _ler_manifesto,
    _orcamento_de_reconexao,
    corpo_do_manifesto,
    enviar,
    enviar_manifesto,
    hashes_locais,
    listar_arquivos,
    ordem_de_envio,
)


class FTPFalso:
    def __init__(self, quebrar_em: set[int] | None = None) -> None:
        self.enviados: list[str] = []
        self.quebrar_em = quebrar_em or set()
        self.n = 0

    def mkd(self, caminho: str) -> None:
        pass

    def rmd(self, caminho: str) -> None:
        raise ftplib.error_perm("550")

    def storbinary(self, cmd: str, f, blocksize: int = 8192) -> None:
        self.n += 1
        if self.n in self.quebrar_em:
            raise ConnectionResetError("caiu")
        f.read()
        self.enviados.append(cmd.removeprefix("STOR "))


def _site(raiz: Path, arquivos: dict[str, str]) -> Path:
    for rel, texto in arquivos.items():
        alvo = raiz / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(texto, encoding="utf-8")
    return raiz


PAGINAS = {
    "index.html": "home",
    "candidato/a-1/index.html": "ficha A",
    "candidato/b-2/index.html": "ficha B",
}


def test_sem_manifesto_anterior_sobe_tudo(tmp_path):
    ftp = FTPFalso()
    n, _ = enviar(ftp, _site(tmp_path, PAGINAS), "", seco=False)
    assert n == 3 and len(ftp.enviados) == 3


def test_o_que_nao_mudou_nao_sobe(tmp_path):
    origem = _site(tmp_path, PAGINAS)
    anterior = hashes_locais(origem, listar_arquivos(origem))

    (origem / "candidato" / "b-2" / "index.html").write_text("ficha B v2",
                                                             encoding="utf-8")
    ftp = FTPFalso()
    n, _ = enviar(ftp, origem, "", seco=False, ja_no_servidor=anterior)
    assert n == 1
    assert ftp.enviados == ["candidato/b-2/index.html"]


def test_arquivo_novo_sobe_mesmo_com_manifesto(tmp_path):
    origem = _site(tmp_path, PAGINAS)
    anterior = hashes_locais(origem, listar_arquivos(origem))
    _site(origem, {"candidato/c-3/index.html": "ficha C"})

    ftp = FTPFalso()
    n, _ = enviar(ftp, origem, "", seco=False, ja_no_servidor=anterior)
    assert n == 1 and ftp.enviados == ["candidato/c-3/index.html"]


def test_manifesto_sem_hash_faz_tudo_subir(tmp_path):
    """Formato v1 — lista de nomes. Sem hash nao ha' como afirmar que o
    conteudo bate, e afirmar sem saber e' o unico erro que nao pode acontecer."""
    origem = _site(tmp_path, PAGINAS)
    v1 = _ler_manifesto(listar_arquivos(origem))
    assert set(v1) == set(PAGINAS)
    assert all(v is None for v in v1.values())

    ftp = FTPFalso()
    n, _ = enviar(ftp, origem, "", seco=False, ja_no_servidor=v1)
    assert n == 3


def test_manifesto_de_formato_estranho_e_ignorado():
    assert _ler_manifesto({"arquivos": ["a", "b"]}) is None
    assert _ler_manifesto("lixo") is None
    assert _ler_manifesto([1, 2, 3]) is None
    assert _ler_manifesto({"versao": 2, "arquivos": {"a.html": "ff"}}) == {"a.html": "ff"}


def test_o_manifesto_nao_sobe_junto_com_as_paginas(tmp_path):
    """A garantia inteira depende disto: enquanto o site sobe, o manifesto que
    esta' no servidor e' o da publicacao ANTERIOR, e ele descreve um site que
    realmente chegou por completo."""
    origem = _site(tmp_path, PAGINAS)
    (origem / MANIFESTO).write_text("{}", encoding="utf-8")
    ftp = FTPFalso()
    enviar(ftp, origem, "", seco=False)
    assert MANIFESTO not in ftp.enviados


def test_o_manifesto_sobe_depois_e_traz_os_hashes(tmp_path):
    origem = _site(tmp_path, PAGINAS)
    ftp = FTPFalso()
    enviar(ftp, origem, "", seco=False)
    hashes = hashes_locais(origem, listar_arquivos(origem))
    assert enviar_manifesto(ftp, "", hashes) is True
    assert ftp.enviados[-1] == MANIFESTO

    lido = json.loads(corpo_do_manifesto(hashes))
    assert set(lido["arquivos"]) == set(PAGINAS)


def test_manifesto_que_nao_sobe_nao_derruba_a_publicacao(tmp_path):
    """O site ja' subiu inteiro. Perder o manifesto custa um envio completo na
    proxima vez — nunca uma pagina errada no ar."""
    origem = _site(tmp_path, PAGINAS)
    ftp = FTPFalso(quebrar_em={1, 2, 3, 4, 5})
    assert enviar_manifesto(ftp, "", hashes_locais(origem, listar_arquivos(origem))) is False


def test_hash_muda_quando_um_byte_muda(tmp_path):
    origem = _site(tmp_path, {"a.html": "x"})
    antes = hashes_locais(origem, ["a.html"])["a.html"]
    (origem / "a.html").write_text("y", encoding="utf-8")
    assert hashes_locais(origem, ["a.html"])["a.html"] != antes


def test_orcamento_de_reconexao_acompanha_o_tamanho_do_site():
    """40 era folga para 738 arquivos e seria teto para 20 mil: o servidor corta
    a cada ~100 arquivos, entao o numero de quedas cresce com o site."""
    assert _orcamento_de_reconexao(738) == 40
    assert _orcamento_de_reconexao(20_000) == 400


@pytest.mark.parametrize("seco", [True, False])
def test_pasta_vazia_continua_falhando(tmp_path, seco):
    with pytest.raises(SystemExit):
        enviar(FTPFalso(), tmp_path, "", seco=seco)


# ── ordem de envio ─────────────────────────────────────────────────────────

def test_o_css_sobe_antes_das_paginas_que_dependem_dele(tmp_path):
    """Em ordem alfabetica `dossie.css` vem DEPOIS de `candidato/`. Na
    publicacao da F-18 isso deixou 20 mil fichas novas no ar apontando para uma
    folha que ainda nao existia: 404 no CSS, site sem estilo, por horas."""
    origem = _site(tmp_path, {**PAGINAS, "dossie.css": "body{}"})
    ftp = FTPFalso()
    enviar(ftp, origem, "", seco=False)
    assert ftp.enviados[0] == "dossie.css"
    assert set(ftp.enviados) == set(PAGINAS) | {"dossie.css"}


def test_a_ordem_nao_perde_nem_duplica_arquivo():
    assert ordem_de_envio(["b.html", "dossie.css", "a.html"]) == [
        "dossie.css", "b.html", "a.html"]
    assert ordem_de_envio(["b.html", "a.html"]) == ["b.html", "a.html"]
    assert ordem_de_envio([]) == []


def test_o_plano_e_anunciado_antes_do_primeiro_envio(tmp_path, caplog):
    """Entre "conectado" e o primeiro lote de 200 havia minutos de silencio —
    baixar o manifesto, ler o disco, calcular hash. Quem olha a tela nao tem
    como distinguir trabalho de travamento."""
    import logging
    origem = _site(tmp_path, PAGINAS)
    anterior = hashes_locais(origem, listar_arquivos(origem))
    (origem / "candidato" / "b-2" / "index.html").write_text("v2", encoding="utf-8")
    with caplog.at_level(logging.INFO):
        enviar(FTPFalso(), origem, "", seco=False, ja_no_servidor=anterior)
    assert "3 arquivos no site: 2 ja' estao no servidor, 1 a enviar" in caplog.text
