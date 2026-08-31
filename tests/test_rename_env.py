"""O nome antigo das variaveis nao pode parar de funcionar sem avisar.

O projeto virou Dossie Eleitoral em 31/08/2026 e o prefixo `RADAR_` virou
`DOSSIE_` (ADR-026). O `.env` da maquina do usuario e os Secrets do GitHub NAO
mudam junto com o codigo — entao o dia da troca e o dia em que os dois nomes
precisam valer.

O caso que estes testes protegem nao e' hipotetico: a primeira versao deste
rename trocou os nomes em `publicar.py` mas deixou a checagem de "variaveis
faltando" lendo `os.environ` direto. Com o `.env` de producao intacto, ela teria
abortado a publicacao dizendo que faltavam host, usuario e senha — todos
definidos, com o nome antigo.
"""

from __future__ import annotations

import os

import pytest

from ingest.common import env as envmod
from ingest.common.env import definida, env


@pytest.fixture(autouse=True)
def _limpo(monkeypatch):
    for chave in ("DOSSIE_TESTE", "RADAR_TESTE"):
        monkeypatch.delenv(chave, raising=False)
    envmod._ja_avisadas.clear()


def test_nome_novo_resolve(monkeypatch):
    monkeypatch.setenv("DOSSIE_TESTE", "novo")
    assert env("DOSSIE_TESTE") == "novo"


def test_nome_antigo_ainda_resolve(monkeypatch):
    monkeypatch.setenv("RADAR_TESTE", "velho")
    assert env("DOSSIE_TESTE") == "velho"
    assert definida("DOSSIE_TESTE")


def test_o_novo_vence_o_antigo(monkeypatch):
    monkeypatch.setenv("RADAR_TESTE", "velho")
    monkeypatch.setenv("DOSSIE_TESTE", "novo")
    assert env("DOSSIE_TESTE") == "novo", (
        "com os dois definidos o nome novo tem que ganhar, senao renomear o .env "
        "nao teria efeito nenhum")


def test_o_fallback_avisa_uma_vez_so(monkeypatch, capsys):
    monkeypatch.setenv("RADAR_TESTE", "velho")
    for _ in range(5):
        env("DOSSIE_TESTE")
    saida = capsys.readouterr().out
    assert saida.count("foi renomeada") == 1, (
        "uma carga le' a mesma variavel dezenas de vezes; aviso repetido vira "
        "ruido e esconde o resto do log")


def test_ausente_devolve_o_default():
    assert env("DOSSIE_TESTE", "padrao") == "padrao"
    assert not definida("DOSSIE_TESTE")


def test_publicar_aceita_o_env_antigo(monkeypatch):
    """A regressao concreta: `_config` checava `os.environ`, sem o fallback."""
    from scripts.publicar import _config

    for chave in list(os.environ):
        if chave.startswith(("RADAR_FTP", "DOSSIE_FTP")):
            monkeypatch.delenv(chave, raising=False)
    monkeypatch.setenv("RADAR_FTP_HOST", "ftp.exemplo.com")
    monkeypatch.setenv("RADAR_FTP_USER", "usuario")
    monkeypatch.setenv("RADAR_FTP_PASSWORD", "senha")

    cfg = _config()
    assert cfg["host"] == "ftp.exemplo.com"
    assert cfg["user"] == "usuario"
