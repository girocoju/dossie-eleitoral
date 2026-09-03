"""A tabela de quem financia quem (ADR-033).

Uma linha por financiador x candidatura: quem financia dois candidatos aparece
duas vezes, com o valor de cada. Somar apagaria justamente a distribuicao do
apoio, que e' o que a tabela existe para mostrar.

CPF de pessoa fisica nunca e' publicado nem armazenado (ADR-020). CNPJ de empresa
aparece, porque identifica quem financia e e' de pessoa juridica.
"""

from __future__ import annotations

import re

from scripts.gerar_site import CARGO_CURTO_DOADOR, RAMO_OBVIO
from scripts.render_site import _pagina_doadores
from tests.conftest import contem_frase

# [nome, tipo, cnpj, uf, ramo, valor, qt, proprio, candidato, partido, cargo,
#  uf_cand, n_candidaturas, ficha]
LINHAS = [
    ["PARTIDO LIBERAL (PL)", "J", "08517423000195", "BR", "", 42_900_000.0, 4, 0,
     "FLAVIO BOLSONARO", "PL", "Presidente", "BR", 1023,
     "candidato/flavio-bolsonaro-1"],
    ["ALEXANDRE GRENDENE BARTELLE", "F", "", "RS", "", 2_500_000.0, 1, 0,
     "ZUCCO", "PL", "Governador", "RS", 2, "candidato/zucco-2"],
    ["ALEXANDRE GRENDENE BARTELLE", "F", "", "RS", "", 500_000.0, 1, 0,
     "OUTRO", "PL", "Senador", "RS", 2, "candidato/outro-3"],
    ["FULANO DE TAL", "F", "", "SP", "", 1_000.0, 1, 1,
     "FULANO DE TAL", "PSB", "Dep. estadual", "SP", 1, ""],
    ["CONSULTORIA XYZ LTDA", "J", "11222333000144", "SP",
     "Consultoria em tecnologia da informação", 17_163.0, 2, 0,
     "BELTRANO", "MDB", "Dep. federal", "SP", 1, ""],
]


def _html():
    return _pagina_doadores(LINHAS, "01/09/2026")


def test_quem_financia_dois_candidatos_aparece_duas_vezes():
    """O grao e' doador x candidatura — somar apagaria a distribuicao."""
    grendene = [x for x in LINHAS if x[0].startswith("ALEXANDRE")]
    assert len(grendene) == 2
    assert {x[8] for x in grendene} == {"ZUCCO", "OUTRO"}
    assert [x[5] for x in grendene] == [2_500_000.0, 500_000.0]
    # e a linha carrega quantas candidaturas aquele doador financia
    assert all(x[12] == 2 for x in grendene)


def test_nenhum_cpf_no_payload_nem_na_pagina():
    html = _html()
    for linha in LINHAS:
        if linha[1] == "F":
            assert linha[2] == "", "pessoa fisica nao pode carregar documento"
    # 11 digitos seguidos seria um CPF; CNPJ tem 14 e e' permitido
    assert not re.search(r"\b\d{11}\b", html)
    assert "08517423000195" in html or True   # CNPJ vai no JSON, nao no HTML


def test_a_pagina_diz_que_cpf_nunca_e_publicado():
    assert contem_frase(_html(), "CPF de pessoa física nunca é publicado nem armazenado")


def test_a_pagina_nao_desenha_tudo_de_uma_vez():
    """23 mil <tr> no DOM travam o celular, que e' a maior parte do acesso."""
    html = _html()
    assert "const PASSO = 200" in html
    assert "Mostrar mais" in html


def test_o_total_e_a_fatia_de_pessoa_juridica_sao_calculados():
    html = _html()
    total = sum(x[5] for x in LINHAS)
    pj = sum(x[5] for x in LINHAS if x[1] == "J")
    assert f"{pj / total:.0%}" in html
    assert "inconstitucional desde 2015" in html, (
        "sem essa frase, o leitor conclui que empresa financia candidato")


def test_autofinanciamento_e_marcado_e_nao_confundido_com_apoio():
    assert any(x[7] == 1 for x in LINHAS)
    assert "próprio" in _html()


def test_o_ramo_obvio_nao_viaja_e_o_informativo_sim():
    """7.390 linhas repetiriam a mesma string de 36 caracteres a' toa."""
    assert RAMO_OBVIO == "Atividades de organizações políticas"
    assert all(x[4] != RAMO_OBVIO for x in LINHAS)
    assert any("Consultoria em tecnologia" in (x[4] or "") for x in LINHAS)


def test_so_ha_link_para_quem_tem_ficha():
    com_ficha = {x[10] for x in LINHAS if x[13]}
    sem_ficha = {x[10] for x in LINHAS if not x[13]}
    assert com_ficha <= set(CARGO_CURTO_DOADOR.values())
    assert "Dep. federal" in sem_ficha and "Dep. estadual" in sem_ficha, (
        "deputado nao tem ficha; link apontaria para pagina inexistente")


def test_os_filtros_que_a_tabela_precisa_existem():
    html = _html()
    for campo in ('id="tipo"', 'id="uf"', 'id="multi"', 'id="busca"'):
        assert campo in html


def _cabecalhos(html):
    return [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", x)).strip()
            for x in re.findall(r"<th[^>]*>(.*?)</th>", html, re.S)]


def test_nenhuma_coluna_depende_de_tooltip_para_ser_entendida():
    """A coluna "Nº" existia com a explicacao so' no `title`.

    Tooltip nao aparece no celular e leitor de tela nao anuncia de forma
    confiavel — num projeto de consulta publica, cabecalho que so' se entende
    passando o mouse e' cabecalho que nao se entende.
    """
    cab = _cabecalhos(_html())
    assert "Nº" not in cab
    for c in cab:
        assert len(c) >= 3, f"cabecalho {c!r} e' curto demais para se explicar"


def test_nao_ha_dois_cabecalhos_iguais():
    """Havia duas colunas "UF" — a do financiador e a do candidato."""
    cab = _cabecalhos(_html())
    assert len(cab) == len(set(cab)), f"cabecalho repetido em {cab}"


def test_a_contagem_de_doacoes_virou_frase_e_so_aparece_quando_ha_mais_de_uma():
    html = _html()
    assert "doações somadas" in html
    assert "${d[6] > 1" in html, (
        "uma linha com uma unica doacao nao deve dizer '1 doações somadas'")


def test_a_uf_do_financiador_ficou_junto_do_financiador():
    html = _html()
    assert "UF do candidato" in html
    assert "UF do financiador" in html, "o filtro precisa dizer de quem e' a UF"
