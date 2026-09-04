"""Comissoes da Camara na ficha (F-26 / ADR-044).

A ficha dizia quanto o deputado propos e quantas vezes votou. Nao dizia ONDE ele
trabalha — e comissao permanente e' onde a maior parte do trabalho legislativo
acontece de verdade.

Este arquivo protege os tres jeitos de o bloco mentir:

  - chamar filiacao partidaria de comissao (a API chama as duas de "orgao");
  - usar o NOME do tipo, que a Camara nao mantem coerente;
  - dizer que a pessoa foi Presidente o tempo todo quando foi uma vez.
"""

from __future__ import annotations

from ingest.comissoes import (
    CLASSES,
    CLASSES_DE_COLEGIADO,
    PARTIDARIAS,
    _classificar,
)
from scripts.gerar_site import CLASSES_COMISSAO, Candidato
from scripts.render_site import _comissoes, _periodo
from tests.conftest import contem_frase, texto_visivel


def _cand(**kw):
    campos = dict(
        sk="sk-1", sq="70002540001", cod_cargo=6, nome_urna="DEP EXEMPLO",
        nome_completo="DEP EXEMPLO", sg_uf="SP", sigla_partido="PT",
        nome_partido="PT", nr_candidato=1300, coligacao=None, composicao=None,
        federacao=None, situacao="DEFERIDO", url_foto=None, idade=50,
        genero=None, cor_raca=None, grau_instrucao=None, ocupacao=None,
        uf_nascimento=None, bens_total=None, bens_n=None,
        proposta_obrigatoria=False, tem_proposta=False, url_proposta=None,
    )
    campos.update(kw)
    return Candidato(**campos)


COMISSOES = [
    {"classe": "permanente", "sigla": "CCJC",
     "nome": "Comissão de Constituição e Justiça e de Cidadania",
     "tipo": "Comissão permanente", "papel": "Presidente", "vezes": 8,
     "em_curso": True, "a1": 2007, "a2": 2026},
    {"classe": "conselho", "sigla": "COETICA",
     "nome": "Conselho de Ética e Decoro Parlamentar",
     "tipo": "Conselho", "papel": "Titular", "vezes": 2,
     "em_curso": False, "a1": 2015, "a2": 2017},
]


# ── a classificacao vem do CODIGO, nunca do nome ──────────────────────────

def test_o_tipo_15_nao_vira_comissao_e_nao_usa_o_nome_oficial():
    """`codTipoOrgao = 15` chama-se "COORDENADORIA DA MULHER" e agrupa a Bancada
    Negra, a Secretaria de Comunicacao e mais onze. Renderizar o nome como veio
    diria que a Bancada Negra e' a Coordenadoria da Mulher."""
    classe, rotulo = _classificar(15)
    assert classe == "institucional"
    assert classe not in CLASSES_DE_COLEGIADO
    assert "Mulher" not in rotulo


def test_filiacao_partidaria_nunca_e_colegiado():
    """Partido, bloco, lideranca e bancada tambem sao "orgao" na API. Estar no PT
    nao e' ter assento na CCJ."""
    for cod in PARTIDARIAS:
        classe, _ = _classificar(cod)
        assert classe == "partidaria", cod
        assert classe not in CLASSES_DE_COLEGIADO, cod


def test_os_colegiados_de_peso_estao_mapeados():
    assert _classificar(2)[0] == "permanente"      # Comissão Permanente
    assert _classificar(1)[0] == "mesa"            # Comissão Diretora
    assert _classificar(11)[0] == "conselho"       # Conselho (de Ética)
    assert _classificar(4)[0] == "temporaria"      # CPI
    for cod in (1, 2, 4, 11):
        assert _classificar(cod)[0] in CLASSES_DE_COLEGIADO, cod


def test_medida_provisoria_nao_entra_na_lista():
    """Sao 1.393 comissoes de MPV no catalogo e participar delas e' rotina."""
    assert _classificar(9)[0] == "medida_provisoria"
    assert "medida_provisoria" not in CLASSES_DE_COLEGIADO


def test_tipo_ausente_nao_vira_comissao_por_omissao():
    """Orgao que o catalogo nao resolveu fica de fora. Preferir a linha ausente
    a' linha errada."""
    classe, _ = _classificar(None)
    assert classe == "desconhecida"
    assert classe not in CLASSES_DE_COLEGIADO


def test_todo_codigo_mapeado_tem_rotulo_em_portugues():
    for cod, (classe, rotulo) in CLASSES.items():
        assert rotulo and rotulo[0].isupper(), cod
        assert classe.islower(), cod


# ── a tela ─────────────────────────────────────────────────────────────────

def test_a_ficha_mostra_o_colegiado_o_papel_e_o_periodo():
    c = _cand()
    c.comissoes = COMISSOES
    t = " ".join(texto_visivel(_comissoes(c)).split())
    assert "CCJC" in t and "Presidente" in t and "2007–2026" in t
    assert "COETICA" in t and "2015–2017" in t


def test_o_bloco_agrupa_por_natureza_do_colegiado():
    """Em ordem cronologica, "Conselho de Etica" fica perdido entre quinze
    linhas de subcomissao."""
    c = _cand()
    c.comissoes = COMISSOES
    html = _comissoes(c)
    assert contem_frase(html, "Comissões permanentes")
    assert contem_frase(html, "Conselhos e corregedoria")


def test_a_tela_explica_que_o_papel_e_o_de_maior_peso():
    """Sem isso, "Presidente" com periodo de 2007 a 2026 leria como vinte anos
    de presidencia."""
    c = _cand()
    c.comissoes = COMISSOES
    assert contem_frase(_comissoes(c), "o de maior peso que a pessoa teve")


def test_a_tela_diz_que_partido_e_lideranca_ficam_de_fora():
    """Omitir sem dizer que omitiu deixa o leitor sem saber se a lista e'
    completa — a mesma razao do ADR-031."""
    c = _cand()
    c.comissoes = COMISSOES
    assert contem_frase(_comissoes(c), "Filiação a partido, bloco e liderança não entram")


def test_a_tela_explica_por_que_a_mesma_comissao_nao_repete():
    c = _cand()
    c.comissoes = COMISSOES
    assert contem_frase(_comissoes(c), "Uma linha por colegiado, não por designação")


def test_sem_comissao_nao_ha_bloco():
    assert _comissoes(_cand()) == ""


def test_periodo_de_um_ano_so_nao_vira_intervalo():
    assert _periodo(2019, 2019) == "2019"
    assert _periodo(2019, 2023) == "2019–2023"
    assert _periodo(None, None) == "—"
    assert _periodo(2019, None) == "2019"


def test_toda_classe_exibida_tem_rotulo():
    assert set(CLASSES_COMISSAO) == set(CLASSES_DE_COLEGIADO)


# ── paginacao ──────────────────────────────────────────────────────────────

def test_a_pagina_unica_nao_e_suficiente():
    """`itens=200` parece folgado — a maioria dos deputados tem menos de 50
    vinculos. Nao e': o corte cai em cima de quem mais trabalhou.

    Medido em 04/09/2026, antes da correcao:

        Hugo Leal        pagina 1 = 200   total real = 242   perdia 42
        Erika Kokay      pagina 1 = 200   total real = 224   perdia 24
        Jose Rocha       pagina 1 = 200   total real = 217   perdia 17
        Alice Portugal   pagina 1 = 200   total real = 205   perdia  5

    E o que ficava de fora nao era resto: faltavam membros ATUAIS da CCJC, da
    Comissao de Saude, da CFT e da CAPADR.
    """
    from ingest import comissoes
    assert comissoes.POR_PAGINA == 200
    assert comissoes.MAX_PAGINAS >= 2, "sem varias paginas o veterano sai truncado"


def test_a_coleta_pagina_ate_o_fim(monkeypatch):
    """Para de pedir quando a pagina volta menor que o limite — nao na primeira."""
    from ingest import comissoes

    paginas = {1: [{"idOrgao": i} for i in range(200)],
               2: [{"idOrgao": i} for i in range(200, 242)]}
    pedidas = []

    def falso(url):
        n = int(url.split("pagina=")[1].split("&")[0])
        pedidas.append(n)
        return {"dados": paginas.get(n, [])}

    monkeypatch.setattr(comissoes, "_json", falso)
    brutos = comissoes.coletar_brutos([141450])
    assert pedidas == [1, 2], pedidas
    assert len(brutos) == 242


def test_o_laco_tem_teto(monkeypatch):
    """Se a API parar de encurtar a ultima pagina, a coleta nao pode girar para
    sempre."""
    from ingest import comissoes

    monkeypatch.setattr(comissoes, "_json",
                        lambda url: {"dados": [{"idOrgao": 1}] * comissoes.POR_PAGINA})
    brutos = comissoes.coletar_brutos([1])
    assert len(brutos) == comissoes.POR_PAGINA * comissoes.MAX_PAGINAS
