"""SICONFI — S11. Testes puros sobre a resposta da API, sem rede."""

from __future__ import annotations

from ingest.siconfi import despesa_empenhada, receita_liquida

# Resposta real reduzida — Acre, exercicio 2023, conferida em 28/08/2026.
RECEITA_ITENS = [
    {"cod_conta": "TotalReceitas", "coluna": "Receitas Brutas Realizadas", "valor": 11628569725.84},
    {"cod_conta": "TotalReceitas", "coluna": "Deduções - FUNDEB", "valor": 1449998417.53},
    {"cod_conta": "TotalReceitas", "coluna": "Outras Deduções da Receita", "valor": 26500000.0},
    # linhas de outras contas devem ser ignoradas
    {"cod_conta": "ReceitasExcetoIntraOrcamentarias", "coluna": "Receitas Brutas Realizadas",
     "valor": 11137410342.21},
]

DESPESA_ITENS = [
    {"cod_conta": "TotalDespesas", "coluna": "Despesas Empenhadas", "valor": 10302403421.0},
    {"cod_conta": "TotalDespesas", "coluna": "Despesas Liquidadas", "valor": 9934171128.0},
    {"cod_conta": "TotalDespesas", "coluna": "Despesas Pagas", "valor": 9769534244.0},
]


def test_receita_desconta_as_deducoes():
    """A bruta superestima: a parcela do FUNDEB e' vinculada e sai antes."""
    assert receita_liquida(RECEITA_ITENS) == 11628569725.84 - 1449998417.53 - 26500000.0


def test_receita_ignora_contas_que_nao_sao_o_total():
    """`ReceitasExcetoIntraOrcamentarias` nao pode entrar na conta."""
    assert receita_liquida(RECEITA_ITENS) < 11137410342.21 + 1


def test_receita_tolera_acento_variando():
    """A API devolve com acento e a grafia varia entre exercicios."""
    sem_acento = [
        {"cod_conta": "TotalReceitas", "coluna": "RECEITAS BRUTAS REALIZADAS", "valor": 100.0},
        {"cod_conta": "TotalReceitas", "coluna": "Deducoes - FUNDEB", "valor": 30.0},
    ]
    assert receita_liquida(sem_acento) == 70.0


def test_despesa_usa_empenhada_e_nao_paga():
    """Empenho mede a decisao tomada no exercicio; pagamento pode escorregar."""
    assert despesa_empenhada(DESPESA_ITENS) == 10302403421.0


def test_resultado_do_acre_em_2023_e_deficit():
    """Conferencia de ponta a ponta com o numero real."""
    resultado = receita_liquida(RECEITA_ITENS) - despesa_empenhada(DESPESA_ITENS)
    assert resultado < 0
    assert round(resultado) == -150332113


def test_resposta_vazia_devolve_none():
    assert receita_liquida([]) is None
    assert despesa_empenhada([]) is None
    assert receita_liquida([{"cod_conta": "Outra", "coluna": "X", "valor": 1}]) is None
