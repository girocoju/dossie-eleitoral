"""Proposta de governo — F-14. Testes puros, sem rede."""

from __future__ import annotations

import pytest

from ingest.propostas import (
    CARGOS_COM_PROPOSTA,
    COD_TIPO_PROPOSTA,
    ID_ELEICAO,
    extrair,
    url_pagina_oficial,
)

# Resposta real da API, reduzida — ALAN RICK, governador do AC, em 28/08/2026.
DETALHE = {
    "nomeUrna": "ALAN RICK",
    "arquivos": [
        {"idArquivo": 1, "nome": "certidao TRF1.pdf", "codTipo": "11"},
        {"idArquivo": 2, "nome": "certidao TJ.pdf", "codTipo": "13"},
        {"idArquivo": 3, "nome": "Plano Governo V4.pdf", "codTipo": "5"},
        {"idArquivo": 4, "nome": "PLANO DE GOVERNO.pdf", "codTipo": "5"},
    ],
}


def test_reconhece_a_proposta_e_ignora_certidoes():
    p = extrair(DETALHE, 2026, "AC", "10002532492", 3, "ALAN RICK")
    assert p.tem_proposta is True
    assert p.n_arquivos == 2  # duas propostas, quatro arquivos
    assert p.nome_arquivo == "Plano Governo V4.pdf"


def test_candidato_sem_proposta():
    detalhe = {"arquivos": [{"nome": "certidao.pdf", "codTipo": "11"}]}
    p = extrair(detalhe, 2026, "SP", "123", 3, "FULANO")
    assert p.tem_proposta is False
    assert p.n_arquivos == 0
    assert p.nome_arquivo is None
    # mesmo sem proposta, o link para a fonte existe
    assert p.url_oficial


@pytest.mark.parametrize("detalhe", [None, {}, {"arquivos": None}, {"arquivos": []}])
def test_resposta_vazia_nao_quebra(detalhe):
    """Uma candidatura sem resposta da API nao pode derrubar a carga inteira."""
    p = extrair(detalhe, 2026, "AC", "123", 1, None)
    assert p.tem_proposta is False
    assert p.sk_candidatura == "2026-AC-123"


def test_sk_candidatura_bate_com_a_do_mart():
    p = extrair(DETALHE, 2026, "AC", "10002532492", 3, "ALAN RICK")
    assert p.sk_candidatura == "2026-AC-10002532492"


def test_link_oficial_aponta_para_o_tse():
    url = url_pagina_oficial(2026, "AC", "10002532492")
    assert url.startswith("https://divulgacandcontas.tse.jus.br/divulga/#/candidato/2026/")
    assert str(ID_ELEICAO[2026]) in url
    assert url.endswith("/AC/10002532492")


def test_a_obrigacao_segue_a_lei_e_nao_a_categoria_do_cargo():
    """Lei 9.504/97, art. 11, par. 1o, IX: Prefeito, Governador e Presidente.

    SENADOR e' majoritario mas NAO esta na lista. A medicao de 28/08/2026 confirma:
    0 de 318 senadores tem proposta, contra 193 de 198 governadores. Inclui-lo
    faria a tela acusar 318 pessoas de uma omissao que a lei nunca exigiu delas.
    """
    assert CARGOS_COM_PROPOSTA == (1, 3)
    assert 5 not in CARGOS_COM_PROPOSTA, "senador nao entrega proposta de governo"
    for proporcional in (6, 7, 8):
        assert proporcional not in CARGOS_COM_PROPOSTA


def test_codtipo_da_proposta_e_documentado():
    """Codigo nao documentado pelo TSE, inferido da observacao (ADR-013)."""
    assert COD_TIPO_PROPOSTA == "5"
