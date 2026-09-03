"""Timeout de download tem de ser TRANSITORIO — o mecanismo inteiro depende disso.

A ADR-022 separa "a fonte esta' de pe', so' nao respondeu agora" de "a fonte
MUDOU". `ingest/common/cli.py` traduz a primeira em codigo 75, que o workflow
trata como aviso, e deixa a segunda derrubar o job.

Em 03/09/2026 o mecanismo estava DESLIGADO para download de arquivo, e ninguem
sabia. `download()` levantava `DownloadError(msg) from last_error`: o `from`
alimenta o traceback, mas quem guarda a causa e' o CONSTRUTOR. Sem ela,
`transitoria` avaliava None e devolvia False — todo timeout virava erro
permanente. Um `<urlopen error timed out>` do INEP derrubou a carga e pulou a
publicacao do site.

`get_texto` e `get_json` sempre passaram a causa. So' `download` nao passava, e e'
justamente ele que o TSE, o INEP e o Tesouro usam.
"""

from __future__ import annotations

import urllib.error

import pytest

from ingest.common.cli import EX_REDE, executar
from ingest.common.http import DownloadError


def _erro(causa):
    return DownloadError("nao foi possivel baixar x", causa)


@pytest.mark.parametrize("causa", [
    urllib.error.URLError(TimeoutError("timed out")),
    TimeoutError("timed out"),
    OSError("connection reset"),
    urllib.error.HTTPError("u", 503, "Service Unavailable", {}, None),
    urllib.error.HTTPError("u", 429, "Too Many Requests", {}, None),
])
def test_fonte_de_pe_que_nao_respondeu_e_transitoria(causa):
    assert _erro(causa).transitoria is True


@pytest.mark.parametrize("codigo", [401, 404, 410])
def test_fonte_que_mudou_de_endereco_e_permanente(codigo):
    """Tratar 404 como instabilidade esconderia o projeto quebrando de verdade."""
    causa = urllib.error.HTTPError("u", codigo, "x", {}, None)
    assert _erro(causa).transitoria is False


def test_sem_causa_nao_e_transitoria():
    """O default seguro: na duvida, falha alto em vez de virar aviso."""
    assert DownloadError("erro sem causa").transitoria is False


def test_executar_traduz_timeout_em_codigo_75():
    """O caminho inteiro, da excecao ao codigo de saida."""
    def falha(_):
        raise _erro(urllib.error.URLError(TimeoutError("timed out")))

    assert executar(falha, None) == EX_REDE


def test_executar_deixa_404_derrubar_o_job():
    def falha(_):
        raise _erro(urllib.error.HTTPError("u", 404, "x", {}, None))

    with pytest.raises(DownloadError):
        executar(falha, None)


def test_o_download_real_anexa_a_causa(monkeypatch, tmp_path):
    """A regressao exata: `download` levantando sem `causa` no construtor."""
    from ingest.common import http

    def sempre_timeout(*a, **k):
        raise urllib.error.URLError(TimeoutError("timed out"))

    monkeypatch.setattr(http, "_abrir", sempre_timeout, raising=False)
    monkeypatch.setattr(http, "BACKOFF_BASE", 0.0)
    monkeypatch.setattr(http.urllib.request, "urlopen", sempre_timeout)

    with pytest.raises(DownloadError) as exc:
        http.download("https://exemplo.gov.br/a.zip", tmp_path / "a.zip")
    assert exc.value.causa is not None, (
        "sem a causa no construtor, `transitoria` devolve False e o timeout "
        "derruba o pipeline")
    assert exc.value.transitoria is True
