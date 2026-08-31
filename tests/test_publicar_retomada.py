"""Queda de conexao no meio da publicacao nao pode matar a publicacao inteira.

Sao 738 arquivos numa sessao FTP unica, aberta por volta de treze minutos. Em
31/08/2026 o servidor cortou a conexao no meio e tudo morreu com
ConnectionResetError, depois de centenas de arquivos ja' terem subido — o site
ficou com metade das paginas novas e metade antigas.

A distincao vem do ADR-022: `error_perm` (5xx) e' problema de verdade e sobe;
conexao cortada e `error_temp` (4xx) sao instabilidade e se resolvem
reconectando e continuando DO MESMO arquivo, sem reenviar o que ja' foi.
"""

from __future__ import annotations

import ftplib

import pytest

from scripts import publicar


class FTPFalso:
    """Sessao de mentira que registra o que subiu e pode quebrar sob encomenda."""

    def __init__(self, quebrar_em: list[int] | None = None,
                 erro: Exception | None = None) -> None:
        self.enviados: list[str] = []
        self.quebrar_em = set(quebrar_em or [])
        self.erro = erro or ConnectionResetError("conexao cortada")
        self.n = 0

    def storbinary(self, comando: str, arquivo, blocksize: int = 0) -> None:
        self.n += 1
        if self.n in self.quebrar_em:
            raise self.erro
        self.enviados.append(comando.removeprefix("STOR "))

    def cwd(self, caminho: str) -> None:
        return None

    def mkd(self, caminho: str) -> None:
        return None

    def rmd(self, caminho: str) -> None:
        # O caso normal: nao existe diretorio ocupando o lugar do arquivo.
        raise ftplib.error_perm("550 nao existe")

    def delete(self, caminho: str) -> None:
        return None

    def close(self) -> None:
        return None

    def quit(self) -> None:
        return None


def _site(tmp_path):
    origem = tmp_path / "site"
    origem.mkdir()
    for nome in ("index.html", "a.html", "b.html", "c.html"):
        (origem / nome).write_text("<html></html>", encoding="utf-8")
    return origem


def test_reconecta_e_continua_do_mesmo_arquivo(tmp_path, monkeypatch):
    monkeypatch.setattr(publicar, "ESPERA_BASE", 0.0)
    sessoes = [FTPFalso(quebrar_em=[2]), FTPFalso()]
    estado = {"i": 0}

    def reconectar():
        estado["i"] += 1
        return sessoes[estado["i"]]

    n, _ = publicar.enviar(sessoes[0], _site(tmp_path), "", seco=False,
                           reconectar=reconectar)

    assert n == 4
    assert estado["i"] == 1, "devia ter reconectado exatamente uma vez"
    subidos = sessoes[0].enviados + sessoes[1].enviados
    assert sorted(subidos) == ["a.html", "b.html", "c.html", "index.html"]
    assert len(subidos) == 4, f"nenhum arquivo pode subir duas vezes: {subidos}"


def test_erro_de_permissao_sobe_sem_reconectar(tmp_path, monkeypatch):
    """`error_perm` e' caminho errado ou permissao negada — tem que falhar alto."""
    monkeypatch.setattr(publicar, "ESPERA_BASE", 0.0)
    sessao = FTPFalso(quebrar_em=[1], erro=ftplib.error_perm("550 nao pode"))
    chamou = {"n": 0}

    def reconectar():
        chamou["n"] += 1
        return FTPFalso()

    with pytest.raises(ftplib.error_perm):
        publicar.enviar(sessao, _site(tmp_path), "", seco=False,
                        reconectar=reconectar)
    assert chamou["n"] == 0, "erro definitivo nao pode virar tentativa de reconexao"


def test_desiste_depois_do_limite_de_tentativas(tmp_path, monkeypatch):
    monkeypatch.setattr(publicar, "ESPERA_BASE", 0.0)

    def reconectar():
        return FTPFalso(quebrar_em=[1])

    with pytest.raises(ConnectionResetError):
        publicar.enviar(FTPFalso(quebrar_em=[1]), _site(tmp_path), "", seco=False,
                        reconectar=reconectar)


def test_sem_reconectar_o_erro_sobe_como_antes(tmp_path):
    """Quem chama sem `reconectar` (o dry-run, os testes antigos) nao muda."""
    with pytest.raises(ConnectionResetError):
        publicar.enviar(FTPFalso(quebrar_em=[1]), _site(tmp_path), "", seco=False)
