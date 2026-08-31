"""Nenhum recurso sozinho pode segurar a atualizacao por muito tempo.

Seis tentativas com timeout de 120s e backoff ate' 64s chegam a QUATORZE MINUTOS
num unico arquivo. Em 30/08/2026 a API da Camara caiu e o passo das proposicoes
gastou 1h20 tentando dois arquivos — o dobro do que a carga inteira leva quando
tudo funciona.

O teto importa mais agora que a atualizacao roda na maquina do usuario: no
runner, minutos parados passam despercebidos; na tela de alguem, nao.
"""

from __future__ import annotations

import urllib.error
from pathlib import Path
from unittest.mock import patch

import pytest

from ingest.common import http
from ingest.common.http import LIMITE_TOTAL, DownloadError, download, get_json


class RelogioFalso:
    """`time.monotonic` controlado, para medir o teto sem esperar de verdade."""

    def __init__(self, passo: float):
        self.agora = 0.0
        self.passo = passo

    def monotonic(self) -> float:
        return self.agora

    def sleep(self, _segundos: float) -> None:
        # Cada tentativa "gasta" o passo: e' assim que o timeout longo de uma
        # fonte lenta consome o orcamento.
        self.agora += self.passo


def test_o_teto_existe_e_e_curto_o_bastante():
    assert LIMITE_TOTAL <= 600, (
        "acima de dez minutos o teto deixa de proteger: a carga inteira leva "
        "cerca de 45 minutos")


def test_fonte_lenta_nao_consome_as_seis_tentativas(tmp_path: Path):
    """Cada tentativa gasta 100s: o teto corta antes das seis."""
    relogio = RelogioFalso(passo=100.0)
    tentativas = []

    def falha(*_a, **_k):
        tentativas.append(1)
        raise urllib.error.URLError("lento demais")

    with patch.object(http.time, "monotonic", relogio.monotonic), \
         patch.object(http.time, "sleep", relogio.sleep), \
         patch.object(http, "_open", side_effect=falha), \
         pytest.raises(DownloadError):
        download("https://exemplo/grande.zip", tmp_path / "grande.zip")

    assert len(tentativas) < http.MAX_ATTEMPTS, (
        f"gastou as {http.MAX_ATTEMPTS} tentativas apesar do teto")
    # Tolerancia de dois passos: o teto governa o LACO de tentativas, e ha' ainda
    # a pausa entre downloads antes dele (uma constante de poucos segundos na
    # realidade, que o relogio falso infla para 100s) mais a tentativa em curso
    # quando o limite e' cruzado.
    assert relogio.agora <= LIMITE_TOTAL + 2 * relogio.passo, (
        f"gastou {relogio.agora}s, muito alem do teto de {LIMITE_TOTAL}s")


def test_fonte_que_falha_rapido_ainda_tenta_tudo(tmp_path: Path):
    """Host que recusa na hora nao perde tentativa: o teto nao e' atingido.

    O teto e' contra ESPERA, nao contra tentar. Cortar as tentativas de um host
    que responde rapido so' reduziria a chance de pegar uma falha passageira.
    """
    relogio = RelogioFalso(passo=0.1)
    tentativas = []

    def falha(*_a, **_k):
        tentativas.append(1)
        raise urllib.error.URLError("recusada")

    with patch.object(http.time, "monotonic", relogio.monotonic), \
         patch.object(http.time, "sleep", relogio.sleep), \
         patch.object(http, "_open", side_effect=falha), \
         pytest.raises(DownloadError):
        download("https://exemplo/pequeno.zip", tmp_path / "pequeno.zip")

    assert len(tentativas) == http.MAX_ATTEMPTS


def test_get_json_tambem_respeita_o_teto():
    relogio = RelogioFalso(passo=100.0)
    tentativas = []

    def falha(*_a, **_k):
        tentativas.append(1)
        raise urllib.error.URLError("lento demais")

    with patch.object(http.time, "monotonic", relogio.monotonic), \
         patch.object(http.time, "sleep", relogio.sleep), \
         patch.object(http, "_open", side_effect=falha), \
         pytest.raises(DownloadError):
        get_json("https://exemplo/api")

    assert len(tentativas) < http.MAX_ATTEMPTS


def test_a_falha_continua_sendo_DownloadError():
    """O teto muda QUANDO desiste, nao COMO reporta.

    `executar` classifica pela causa (ADR-022); se o teto devolvesse outra
    excecao, uma fonte lenta viraria erro fatal em vez de aviso.
    """
    relogio = RelogioFalso(passo=200.0)
    with patch.object(http.time, "monotonic", relogio.monotonic), \
         patch.object(http.time, "sleep", relogio.sleep), \
         patch.object(http, "_open", side_effect=urllib.error.URLError("x")), \
         pytest.raises(DownloadError) as erro:
        get_json("https://exemplo/api")
    assert erro.value.transitoria, "teto atingido tem que continuar sendo rede"
