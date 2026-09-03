"""Ficha propria para as 19.418 candidaturas proporcionais (F-18 / ADR-040).

Ate' 03/09/2026 quem decidia o voto para deputado tinha listagem e mais nada —
1.126 nomes so' em Sao Paulo, nenhum com endereco proprio para abrir, conferir ou
compartilhar. Era justamente onde uma ficha ajuda MAIS.

O que este arquivo protege sao as tres formas de a mudanca dar errado em
silencio: `CARGOS[6]` estourando, a ficha do deputado herdando texto escrito para
senador, e o link da listagem apontando para um endereco que a ficha nao tem.
"""

from __future__ import annotations

import hashlib
import re

from scripts.gerar_site import CARGOS, PROPORCIONAIS, TODOS_CARGOS, Candidato, slug
from scripts.render_site import (
    CSS,
    CSS_VERSAO,
    _ficha,
    _listagem_proporcional,
    sitemaps,
)
from tests.conftest import contem_frase


def _cand(cod_cargo=6, nome="JOSE DA SILVA", sq="70002540001", uf="SP", **kw):
    campos = dict(
        sk=f"sk-{sq}", sq=sq, cod_cargo=cod_cargo, nome_urna=nome,
        nome_completo="JOSE DA SILVA SANTOS", sg_uf=uf, sigla_partido="PT",
        nome_partido="Partido dos Trabalhadores", nr_candidato=1300,
        coligacao=None, composicao=None, federacao=None, situacao="Deferido",
        url_foto=None, idade=44, genero="MASCULINO", cor_raca="PARDA",
        grau_instrucao="SUPERIOR COMPLETO", ocupacao="ADVOGADO",
        uf_nascimento="SP", bens_total=100000.0, bens_n=2,
        proposta_obrigatoria=False, tem_proposta=False, url_proposta=None,
    )
    campos.update(kw)
    return Candidato(**campos)


# ── o mapa de cargos ────────────────────────────────────────────────────────

def test_todo_cargo_com_ficha_esta_no_mapa():
    """`CARGOS[6]` era KeyError, e KeyError no meio de 19 mil fichas derruba a
    geracao inteira depois de vinte minutos de consulta."""
    assert set(TODOS_CARGOS) == set(CARGOS) | set(PROPORCIONAIS)
    assert TODOS_CARGOS[6] == ("deputado-federal", "Deputado Federal")
    assert TODOS_CARGOS[1][1] == "Presidente"


def test_cargo_chave_aponta_para_a_listagem_de_origem():
    assert _cand(cod_cargo=6).cargo_chave == "deputado-federal"
    assert _cand(cod_cargo=1).cargo_chave == "presidente"
    assert _cand(cod_cargo=7).e_proporcional
    assert not _cand(cod_cargo=5).e_proporcional


# ── a ficha ────────────────────────────────────────────────────────────────

def test_a_ficha_do_deputado_e_gerada_e_volta_para_a_listagem_certa():
    html = _ficha(_cand(), "03/09/2026 19:00")
    assert "JOSE DA SILVA" in html
    assert "/deputado-federal/" in html
    assert contem_frase(html, "Deputado Federal")


def test_a_nota_do_plano_nomeia_o_cargo_da_ficha():
    """Herdado do senador, o texto dizia que Senador e' majoritario na ficha de
    um deputado — leitura possivel: o candidato deixou de entregar algo."""
    dep = _ficha(_cand(cod_cargo=6), "x")
    assert contem_frase(dep, "Deputado Federal não consta da lista")
    assert not contem_frase(dep, "Senador é majoritário")

    est = _ficha(_cand(cod_cargo=7), "x")
    assert contem_frase(est, "Deputado Estadual não consta da lista")


def test_sem_indicador_a_ficha_nao_inventa_bloco():
    """SPEC 2.2: nenhum numero regional atribuido a mandato de deputado. Quem
    nunca teve mandato executivo nao tem linha em `fct_mandato_indicador`."""
    html = _ficha(_cand(), "x")
    assert not contem_frase(html, "Durante mandato")
    assert not contem_frase(html, "Durante Mandato")


def test_o_deputado_que_ja_governou_ve_o_periodo_daquele_mandato():
    """O bloco fala do mandato EXECUTIVO que a pessoa teve, nao do de deputado —
    e' a mesma linha que a ficha de governador mostraria."""
    c = _cand(cod_cargo=6)
    c.indicadores = [{
        "cod": "PIB", "indicador": "PIB", "unidade": "R$", "ue": "São Paulo",
        "uf": "SP", "cargo": 3, "a1": 2015, "a2": 2018, "ref1": 2015,
        "ref2": 2018, "v1": 1.0, "v2": 2.0, "pct": 100.0, "pct_br": 50.0,
        "delta": 50.0, "incompleta": False,
    }]
    assert "São Paulo" in _ficha(c, "x")


# ── o link da listagem ─────────────────────────────────────────────────────

def test_o_link_da_listagem_bate_com_o_endereco_da_ficha():
    """O endereco e' montado em JavaScript a partir de `s` e `sq`. Se `s` nao
    for exatamente o `slug()` do Python, sao 19 mil links quebrados."""
    c = _cand(nome="JOSÉ MARÍA DA CONCEIÇÃO", sq="70002540123")
    assert f"candidato/{slug(c.nome_urna)}-{c.sq}" == c.caminho
    assert c.caminho == "candidato/jose-maria-da-conceicao-70002540123"


def test_a_listagem_monta_o_link_com_os_campos_que_o_gerador_manda():
    linhas = {"SP": [{"s": "jose-da-silva", "sq": "70002540001",
                      "nome": "JOSE DA SILVA", "nr": 1300, "partido": "PT"}]}
    html = _listagem_proporcional("deputado-federal", "Deputado Federal",
                                  linhas, "x")
    assert "${RAIZ}/candidato/${d.s}-${d.sq}/" in html


def test_a_listagem_nao_diz_mais_que_ficha_propria_nao_existe():
    linhas = {"SP": [{"s": "a", "sq": "1", "nome": "A"}]}
    html = _listagem_proporcional("deputado-federal", "Deputado Federal",
                                  linhas, "x")
    assert not contem_frase(html, "não têm ficha própria")
    assert contem_frase(html, "Clique no nome para abrir a ficha completa")


# ── sitemaps ───────────────────────────────────────────────────────────────

def _urls(xml: str) -> list[str]:
    return re.findall(r"<loc>([^<]+)</loc>", xml)


def test_o_indice_lista_todos_os_sitemaps_e_nenhum_outro():
    fichas = [_cand(cod_cargo=6, sq=f"7000254{i:04d}", uf="SP") for i in range(3)]
    fichas += [_cand(cod_cargo=7, sq=f"8000254{i:04d}", uf="RJ") for i in range(2)]
    fichas += [_cand(cod_cargo=1, sq="10002540001", uf="BR")]

    saida = sitemaps(fichas)
    filhos = {c for c in saida if c != "sitemap.xml"}
    no_indice = {u.rsplit("/", 2)[-2] + "/" + u.rsplit("/", 1)[-1]
                 for u in _urls(saida["sitemap.xml"])}
    assert no_indice == filhos
    assert "sitemap.xml" not in no_indice, "indice apontando para si mesmo e' laco"


def test_cada_ficha_aparece_uma_vez_so_em_todo_o_mapa():
    fichas = [_cand(cod_cargo=6, sq=f"7000254{i:04d}", uf="SP") for i in range(3)]
    fichas += [_cand(cod_cargo=1, sq="10002540001", uf="BR")]
    saida = sitemaps(fichas)
    todas = [u for c, x in saida.items() if c != "sitemap.xml" for u in _urls(x)]
    for c in fichas:
        assert todas.count(c.url) == 1, c.url


def test_proporcional_e_quebrado_por_cargo_e_por_uf():
    """Sao Paulo sozinho tem 1.126 candidaturas a deputado federal: quebrar so'
    por cargo ainda deixaria oito mil URLs num arquivo."""
    fichas = [_cand(cod_cargo=6, sq="1", uf="SP"), _cand(cod_cargo=6, sq="2", uf="RJ"),
              _cand(cod_cargo=7, sq="3", uf="SP")]
    saida = sitemaps(fichas)
    assert "sitemaps/deputado-federal-sp.xml" in saida
    assert "sitemaps/deputado-federal-rj.xml" in saida
    assert "sitemaps/deputado-estadual-sp.xml" in saida
    assert len(_urls(saida["sitemaps/deputado-federal-sp.xml"])) == 1


def test_nenhum_sitemap_passa_do_limite_do_protocolo():
    fichas = [_cand(cod_cargo=6, sq=str(i), uf="SP") for i in range(1200)]
    for caminho, xml in sitemaps(fichas).items():
        assert len(_urls(xml)) <= 50_000, caminho


# ── o CSS saiu de dentro da pagina ─────────────────────────────────────────

def test_o_css_nao_viaja_dentro_de_cada_ficha():
    """9,1 kB embutidos em 19.947 paginas sao 180 MB da mesma folha copiada."""
    html = _ficha(_cand(), "x")
    assert "<style>" not in html
    # Uma regra que so' existe na folha. `var(--ink-3)` aparece em style=""
    # no proprio markup e nao serve de sinal.
    assert ".rodape" not in html, "algum trecho do CSS ficou embutido"
    assert CSS[:40] not in html
    assert f"/dossie.css?v={CSS_VERSAO}" in html


def test_a_impressao_digital_acompanha_o_conteudo_da_folha():
    """Sem ela, CSS novo com HTML novo e o navegador servindo o CSS velho —
    layout quebrado sem nenhum erro visivel."""
    assert CSS_VERSAO == hashlib.sha256(CSS.encode("utf-8")).hexdigest()[:8]
    assert len(CSS_VERSAO) == 8


# ── a nota de 2006 ─────────────────────────────────────────────────────────

def _traj(**kw):
    base = dict(ano=2022, cargo="Deputado Estadual", uf="SC", partido="PT",
                eleito=False, votos=2650, situacao="APTO",
                origem="publicado pelo TSE", turno=1, votos_turno=2650)
    base.update(kw)
    return base


def test_a_nota_de_2006_aparece_quando_ha_resultado_apurado():
    c = _cand()
    c.trajetoria = [_traj(ano=2006, origem="apurado dos votos", eleito=True)]
    assert contem_frase(_ficha(c, "x"), "Sobre a eleição de 2006")


def test_a_nota_de_2006_aparece_quando_falta_resultado():
    c = _cand()
    c.trajetoria = [_traj(eleito=None)]
    assert contem_frase(_ficha(c, "x"), "Sobre a eleição de 2006")


def test_a_nota_de_2006_some_quando_nao_explica_nada_da_tela():
    """1,1 kB sobre eleicao presidencial de 2006 numa ficha de deputado estadual
    cujo unico resultado o TSE publicou. Texto que nao explica o que esta' na
    tela nao ajuda a entender a tela."""
    c = _cand()
    c.trajetoria = [_traj()]
    html = _ficha(c, "x")
    assert not contem_frase(html, "Sobre a eleição de 2006")
    assert contem_frase(html, "Trajetória eleitoral"), "a tabela continua la'"
