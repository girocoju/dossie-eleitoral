"""Codigo de saida dos scripts de ingestao.

A pergunta aqui e' uma so': o pipeline diario deve parar por causa DESTA falha?

Errar para o lado tolerante e' o mais perigoso — uma fonte que mudou de endereco
passaria como aviso e a serie pararia de atualizar em silencio, com o site
mostrando dado velho como se fosse novo. Errar para o lado rigoroso custa um job
vermelho, que alguem ve'.
"""

from __future__ import annotations

import urllib.error

import pytest

from ingest.common.cli import EX_REDE, executar
from ingest.common.http import DownloadError


def _erro(causa):
    return DownloadError("nao foi possivel obter https://exemplo/x", causa)


class TestTransitoria:
    @pytest.mark.parametrize("causa", [
        TimeoutError("timed out"),
        urllib.error.URLError(OSError("conexao recusada")),
        urllib.error.HTTPError("u", 503, "Service Unavailable", {}, None),
        urllib.error.HTTPError("u", 502, "Bad Gateway", {}, None),
        urllib.error.HTTPError("u", 429, "Too Many Requests", {}, None),
        urllib.error.HTTPError("u", 500, "Internal Server Error", {}, None),
        OSError("rede fora"),
    ])
    def test_instabilidade_e_transitoria(self, causa):
        assert _erro(causa).transitoria

    @pytest.mark.parametrize("codigo", [404, 403, 410, 401, 400])
    def test_fonte_que_mudou_nao_e_transitoria(self, codigo):
        # 404 significa que o recurso saiu do lugar. Chamar isso de instabilidade
        # esconderia exatamente o caso em que o projeto quebrou de verdade.
        causa = urllib.error.HTTPError("u", codigo, "x", {}, None)
        assert not _erro(causa).transitoria

    def test_http_error_vem_antes_de_url_error(self):
        # HTTPError E' subclasse de URLError. Se a ordem dos `isinstance`
        # inverter, todo 404 vira transitorio e o teste acima passa a mentir.
        assert issubclass(urllib.error.HTTPError, urllib.error.URLError)
        assert not _erro(urllib.error.HTTPError("u", 404, "x", {}, None)).transitoria

    def test_sem_causa_nao_e_transitoria(self):
        # Na duvida, para. E' o lado seguro do erro.
        assert not _erro(None).transitoria


class TestExecutar:
    def test_sucesso_devolve_zero(self):
        assert executar(lambda _: 0, None) == 0

    def test_codigo_do_subcomando_e_preservado(self):
        assert executar(lambda _: 3, None) == 3

    def test_rede_instavel_vira_ex_rede(self):
        def falha(_):
            raise _erro(TimeoutError("timed out"))
        assert executar(falha, None) == EX_REDE
        assert EX_REDE == 75, "o workflow trata exatamente este numero"

    def test_fonte_que_mudou_sobe_como_erro(self):
        def falha(_):
            raise _erro(urllib.error.HTTPError("u", 404, "x", {}, None))
        with pytest.raises(DownloadError):
            executar(falha, None)

    def test_bug_nao_e_confundido_com_rede(self):
        # Qualquer outra excecao passa direto. Um KeyError virando "instabilidade"
        # seria o pior resultado possivel deste modulo.
        def falha(_):
            raise KeyError("coluna sumiu do layout")
        with pytest.raises(KeyError):
            executar(falha, None)


class TestNinguemEngoleACausa:
    """A classificacao so' funciona se a `DownloadError` CHEGAR ate' `executar`.

    Em 29/08/2026 ela nao chegou: `ipeadata` capturava e devolvia `return 1`, e o
    workflow anunciou "nao e' rede" para um timeout. O modulo tinha razao sobre o
    que reportou; a informacao e' que se perdia no caminho.
    """

    def _ipea(self, causa):
        from unittest.mock import patch

        import ingest.ipeadata as ipea
        def morre(*a, **k):
            raise _erro(causa)
        with patch.object(ipea, "coletar", morre):
            return ipea.main(["load", "--somente-verificados", "--target", "local"])

    def test_timeout_do_ipeadata_chega_como_ex_rede(self):
        assert self._ipea(TimeoutError("timed out")) == EX_REDE

    def test_serie_que_saiu_do_ar_derruba(self):
        # 404 NAO pode virar aviso: seria a serie parando de atualizar em
        # silencio, com o site mostrando dado velho como novo.
        with pytest.raises(DownloadError):
            self._ipea(urllib.error.HTTPError("u", 404, "Not Found", {}, None))
