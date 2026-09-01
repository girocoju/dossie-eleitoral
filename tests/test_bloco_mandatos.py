"""A secao "Durante mandatos anteriores" separa por mandato e ordena a trajetoria.

Antes, todos os mandatos caiam numa tabela unica sob um `h2` que nomeava apenas o
mandato da PRIMEIRA linha. Para 57 dos 129 candidatos com este bloco isso era uma
afirmacao falsa: a ficha do Lula trazia 35 linhas de tres mandatos presidenciais
sob "BRASIL, 2023-2026".

Agora: um bloco por mandato, do mais recente para o mais antigo, e os indicadores
em ordem alfabetica DO NOME EXIBIDO dentro de cada um.
"""

from __future__ import annotations

import re
from types import SimpleNamespace

from scripts.render_site import _indicadores


def _linha(cod, indicador, a1, a2, ref1, ref2, ue="BRASIL", cargo=1):
    return {"cod": cod, "indicador": indicador, "unidade": "%", "ue": ue,
            "uf": "BR" if ue == "BRASIL" else "GO",
            "cargo": cargo, "a1": a1, "a2": a2, "ref1": ref1, "ref2": ref2,
            "v1": 1.0, "v2": 2.0, "pct": 10.0, "pct_br": 5.0, "delta": 5.0,
            "incompleta": False}


def _titulos(html):
    return [" ".join(m.split())
            for m in re.findall(r"<h3[^>]*>(.*?)</h3>", html, re.S)]


def _indicadores_por_bloco(html):
    blocos = re.split(r'(?=<h3 style="margin:24px)', html)[1:]
    return [re.findall(r"<tr><td>(.*?)<span", b) for b in blocos]


def test_um_bloco_por_mandato_do_mais_recente_ao_mais_antigo():
    c = SimpleNamespace(indicadores=[
        _linha("PIB", "Produto Interno Bruto", 2003, 2006, 2002, 2006),
        _linha("PIB", "Produto Interno Bruto", 2023, 2026, 2022, 2023),
        _linha("PIB", "Produto Interno Bruto", 2007, 2010, 2006, 2010),
    ])
    titulos = _titulos(_indicadores(c))
    assert len(titulos) == 3, "cada mandato precisa do proprio bloco"
    assert titulos == ["Presidente · BRASIL · 2023–2026",
                       "Presidente · BRASIL · 2007–2010",
                       "Presidente · BRASIL · 2003–2006"]


def test_o_h2_nao_afirma_mais_um_mandato_so():
    c = SimpleNamespace(indicadores=[
        _linha("PIB", "Produto Interno Bruto", 2019, 2022, 2018, 2022, ue="GOIÁS", cargo=3),
        _linha("PIB", "Produto Interno Bruto", 2023, 2026, 2022, 2025, ue="GOIÁS", cargo=3),
    ])
    html = _indicadores(c)
    h2 = re.search(r"<h2>(.*?)</h2>", html, re.S).group(1).strip()
    assert h2 == "Durante mandatos anteriores"
    assert "2019" not in h2 and "2023" not in h2


def test_ordem_alfabetica_e_a_do_nome_EXIBIDO():
    """O glossario renomeia. Ordenar pelo nome do banco daria outra ordem na tela.

    No banco:  Produto Interno Bruto < Populacao residente < Taxa de desocupacao
    Na tela:   Desemprego < PIB do estado < Populacao
    """
    c = SimpleNamespace(indicadores=[
        _linha("PIB", "Produto Interno Bruto a precos correntes", 2019, 2022, 2018, 2022),
        _linha("POPULACAO", "Populacao residente estimada", 2019, 2022, 2018, 2022),
        _linha("DESOCUPACAO", "Taxa de desocupacao", 2019, 2022, 2018, 2022),
    ])
    exibidos = _indicadores_por_bloco(_indicadores(c))[0]
    assert exibidos == ["Desemprego", "PIB do Brasil", "População"], (
        f"ordem na tela saiu {exibidos} — se estiver na ordem do banco, o "
        "leitor ve' uma lista que parece aleatoria")


def test_a_coluna_no_cargo_de_saiu_porque_o_titulo_ja_diz():
    c = SimpleNamespace(indicadores=[
        _linha("PIB", "PIB", 2019, 2022, 2018, 2022, ue="GOIÁS", cargo=3)])
    html = _indicadores(c)
    assert "<th>No cargo de</th>" not in html
    assert "Governador" in html
    cabecalhos = re.findall(r"<th>(.*?)</th>", html)
    assert cabecalhos == ["Indicador", "Janela", "Variação", "Brasil no mesmo período"]


def test_mandato_nacional_nao_compara_o_brasil_com_o_brasil():
    """Numa ficha de presidente o indicador JA' E' o Brasil.

    Medido em 31/08/2026: 76 das 78 linhas presidenciais tinham `variacao_pct`
    identica a `variacao_brasil_pct`, e as outras 2 nao tinham comparador. A
    coluna repetia o mesmo numero — ruido que parece erro.
    """
    c = SimpleNamespace(indicadores=[
        _linha("PIB", "PIB", 2023, 2026, 2022, 2025, ue="BRASIL", cargo=1)])
    cabecalhos = re.findall(r"<th>(.*?)</th>", _indicadores(c))
    assert cabecalhos == ["Indicador", "Janela", "Variação"]
    assert "Brasil no mesmo período" not in _indicadores(c)


def test_o_rotulo_do_pib_segue_o_ente_governado():
    """"PIB do estado" numa ficha de presidente e' rotulo falso sobre dado certo."""
    nacional = SimpleNamespace(indicadores=[
        _linha("PIB", "Produto Interno Bruto", 2023, 2026, 2022, 2025, ue="BRASIL", cargo=1)])
    estadual = SimpleNamespace(indicadores=[
        _linha("PIB", "Produto Interno Bruto", 2019, 2022, 2018, 2022, ue="GOIÁS", cargo=3)])
    assert _indicadores_por_bloco(_indicadores(nacional))[0] == ["PIB do Brasil"]
    assert _indicadores_por_bloco(_indicadores(estadual))[0] == ["PIB do estado"]
    assert "moram no país" in _indicadores(SimpleNamespace(indicadores=[
        _linha("POPULACAO", "Populacao", 2023, 2026, 2022, 2025, cargo=1)]))
    assert "moram no estado" in _indicadores(SimpleNamespace(indicadores=[
        _linha("POPULACAO", "Populacao", 2019, 2022, 2018, 2022, ue="GOIÁS", cargo=3)]))


def test_mandato_sem_valor_nenhum_nao_vira_bloco_vazio():
    vazio = _linha("PIB", "PIB", 2003, 2006, 2002, 2006)
    vazio["v1"] = vazio["v2"] = None
    c = SimpleNamespace(indicadores=[
        _linha("PIB", "PIB", 2019, 2022, 2018, 2022), vazio])
    assert len(_titulos(_indicadores(c))) == 1


def test_sem_indicador_nenhum_a_secao_nao_existe():
    assert _indicadores(SimpleNamespace(indicadores=[])) == ""
