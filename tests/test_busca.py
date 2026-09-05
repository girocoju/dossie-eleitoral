"""Buscador da home: um indice por prefixo, e nenhuma ausencia inventada (F-23).

Com 20.162 fichas, um indice unico teria ~1,5 MB — meio minuto num celular em
rede fraca antes de a primeira letra valer alguma coisa. Ele e' quebrado em um
arquivo por prefixo de duas letras, e o navegador baixa UM.

O risco desse desenho nao e' desempenho, e' honestidade: um `fetch` que volta 404
e' indistinguivel de "nao ha' ninguem com esse nome", e a tela diria "nada
encontrado" nos dois casos. Ausencia virando afirmacao e' a Regra 5 ao contrario,
e e' o que a maior parte deste arquivo protege.
"""

from __future__ import annotations

import json
import re
import unicodedata

from scripts.gerar_site import (
    PREFIXO_BUSCA,
    Candidato,
    indice_de_busca,
    normalizar,
    slug,
    termos_de,
)
from scripts.render_site import _busca, _home
from tests.conftest import contem_frase


def _cand(nome="JOSE DA SILVA", sq="70002540001", cod_cargo=6, uf="SP",
          partido="PT", nr=1300):
    return Candidato(
        sk=f"sk-{sq}", sq=sq, cod_cargo=cod_cargo, nome_urna=nome,
        nome_completo=nome, sg_uf=uf, sigla_partido=partido,
        nome_partido=partido, nr_candidato=nr, coligacao=None, composicao=None,
        federacao=None, situacao="Deferido", url_foto=None, idade=44,
        genero=None, cor_raca=None, grau_instrucao=None, ocupacao=None,
        uf_nascimento=None, bens_total=None, bens_n=None,
        proposta_obrigatoria=False, tem_proposta=False, url_proposta=None,
    )


# ── a normalizacao TEM de casar com a do navegador ─────────────────────────

def _como_o_navegador(texto: str) -> str:
    """A mesma coisa que o JavaScript da home faz:

        t.normalize("NFD").replace(/[\\u0300-\\u036f]/g, "").toLowerCase()

    Escrito aqui em Python para que a equivalencia seja CONFERIDA, e nao
    assumida. Divergir faria o navegador pedir um arquivo que nao existe, e a
    tela diria "nada encontrado" para um nome que esta' na base.
    """
    nfd = unicodedata.normalize("NFD", texto)
    return re.sub(r"[̀-ͯ]", "", nfd).lower()


def test_python_e_navegador_normalizam_igual():
    for nome in ("JOSÉ", "CONCEIÇÃO", "ÂNGELA", "MÜLLER", "JOÃO", "ZÉ DA ÓTICA",
                 "MARIA DAS GRAÇAS", "ÍTALO", "NIVALDO JÚNIOR", "AÇÚCAR"):
        assert normalizar(nome) == _como_o_navegador(nome), nome


def test_o_prefixo_do_arquivo_sai_da_mesma_normalizacao():
    """`ÂNGELA` tem de cair no arquivo `an`, que e' onde o navegador vai
    procurar depois de normalizar o que a pessoa digitou."""
    indice = indice_de_busca([_cand(nome="ÂNGELA CONCEIÇÃO")])
    assert set(indice) == {"an", "co", "13"}


# ── o indice ───────────────────────────────────────────────────────────────

def test_a_pessoa_entra_pelo_sobrenome_tambem():
    """Quem procura SILVA nao deveria precisar saber que a pessoa se chama
    JOSE DA SILVA."""
    indice = indice_de_busca([_cand(nome="JOSE DA SILVA")])
    assert "si" in indice
    assert "jo" in indice
    assert indice["si"][0][0] == "JOSE DA SILVA"


def test_o_numero_na_urna_e_um_termo():
    """Quem decide o voto digita o numero."""
    indice = indice_de_busca([_cand(nr=1300)])
    assert "13" in indice


def test_ligacoes_nao_viram_arquivo():
    """`da`, `de`, `do` aparecem em milhares de nomes e ninguem busca por elas.
    Um arquivo `da` teria metade da base dentro."""
    indice = indice_de_busca([_cand(nome="JOSE DA SILVA")])
    assert "da" not in indice


def test_a_ligacao_continua_valendo_na_filtragem():
    """Ela nao ganha arquivo proprio, mas quem digita "jose da silva" casa —
    porque o filtro roda contra o nome inteiro, no navegador."""
    assert termos_de("JOSE DA SILVA") == ["jose", "da", "silva"]


def test_a_mesma_candidatura_entra_uma_vez_por_arquivo():
    """MARIA MARIANA tem dois termos em `ma`; a linha nao pode duplicar."""
    indice = indice_de_busca([_cand(nome="MARIA MARIANA")])
    assert len(indice["ma"]) == 1


def test_a_linha_leva_o_que_a_tela_precisa_para_desambiguar():
    """Vinte mil nomes tem homonimo. Sem cargo, UF, partido e numero, duas
    linhas iguais na tela nao dizem qual e' qual."""
    (linha,) = indice_de_busca([_cand(nome="ANA", uf="BA", partido="PP", nr=4501)])["an"]
    nome, caminho, uf, partido, cargo, nr = linha
    assert nome == "ANA"
    assert caminho == f"{slug('ANA')}-70002540001"
    assert (uf, partido, cargo, nr) == ("BA", "PP", 6, 4501)


def test_o_caminho_do_indice_bate_com_o_da_ficha():
    """O link e' montado no navegador como `/candidato/<caminho>/`. Se ele nao
    for exatamente `Candidato.caminho`, a busca leva a uma pagina que nao
    existe — pior que nao ter busca."""
    c = _cand(nome="JOSÉ MARÍA DA CONCEIÇÃO")
    (linha,) = indice_de_busca([c])["jo"]
    assert f"candidato/{linha[1]}" == c.caminho


def test_prefixo_e_de_duas_letras():
    assert PREFIXO_BUSCA == 2
    for p in indice_de_busca([_cand(nome="ANA CAROLINA")]):
        assert len(p) == 2


def test_termo_de_uma_letra_nao_gera_arquivo():
    indice = indice_de_busca([_cand(nome="J SILVA", nr=None)])
    assert set(indice) == {"si"}


# ── a home ─────────────────────────────────────────────────────────────────

def test_a_home_traz_a_lista_de_prefixos_que_existem():
    """E' ela que deixa o navegador dizer "nao existe" com certeza, em vez de
    dizer isso quando o arquivo apenas nao carregou."""
    html = _busca(["an", "jo", "si"], 20162)
    assert 'new Set(["an","jo","si"])' in html


def test_prefixo_ausente_e_falha_de_rede_sao_frases_diferentes():
    """As duas dizem "nao ha' resultado" para quem olha rapido, e sao coisas
    opostas: uma e' um fato sobre a base, a outra e' o site sem resposta."""
    html = _busca(["jo"], 100)
    assert "Nenhuma candidatura com esse nome ou número." in html
    assert "Não foi possível carregar a busca agora." in html


def test_o_campo_tem_rotulo_de_verdade():
    """Placeholder nao e' rotulo: leitor de tela le' como dica, e alguns nem
    leem. O projeto e' 100% acessivel."""
    html = _busca(["jo"], 100)
    assert '<label for="q"' in html
    assert 'id="q"' in html
    assert 'role="status"' in html and 'aria-live="polite"' in html


def test_a_home_sem_indice_nao_mostra_campo_quebrado():
    """`--limite` e testes geram sem indice; um campo que nao busca nada seria
    pior que campo nenhum."""
    html = _home([], {}, "03/09/2026 19:00")
    assert 'id="q"' not in html


def test_a_home_com_indice_mostra_o_campo():
    html = _home([], {}, "x", prefixos=["jo"], total_fichas=20162)
    assert 'id="q"' in html
    assert contem_frase(html, "Procurar uma candidatura")


def test_a_ordem_dos_resultados_nao_julga_candidato():
    """Constituicao 0.1: nada na tela ordena politico por merito. Aqui a ordem
    e' relevancia de DIGITACAO — quem comeca pelo texto digitado antes de quem
    apenas o contem — e depois alfabetica."""
    html = _busca(["jo"], 100)
    assert 'localeCompare(b[0], "pt-BR")' in html
    assert "startsWith(q)" in html


def test_o_indice_e_json_valido_e_compacto():
    indice = indice_de_busca([_cand(nome=f"NOME {i}", sq=str(i)) for i in range(30)])
    bruto = json.dumps(indice["no"], ensure_ascii=False, separators=(",", ":"))
    assert json.loads(bruto)[0][0].startswith("NOME")
    assert ", " not in bruto, "separador com espaco engorda 20 mil linhas a' toa"


# ── o nome completo ────────────────────────────────────────────────────────

def test_a_pessoa_e_achada_pelo_nome_completo():
    """Nome de urna e' apelido curto. Medido em 03/09/2026: SILVA aparece em 301
    nomes de urna e em 3.322 nomes completos — indexar so' o de urna perderia
    nove em cada dez pessoas que alguem procuraria pelo sobrenome."""
    c = _cand(nome="ZULU")
    c.nome_completo = "JOSE AUGUSTO BERNARDES"
    indice = indice_de_busca([c])
    assert "be" in indice, "BERNARDES tem de virar arquivo"
    assert "au" in indice


def test_o_nome_completo_viaja_na_linha_para_o_filtro_poder_ver():
    """Ele poe a linha no arquivo. Se nao estivesse na linha, o navegador
    encontraria pelo indice e descartaria no filtro — "nada encontrado" para
    alguem que esta' na base."""
    c = _cand(nome="ZULU")
    c.nome_completo = "JOSE AUGUSTO BERNARDES"
    (linha,) = indice_de_busca([c])["be"]
    assert linha[6] == "JOSE AUGUSTO BERNARDES"


def test_nome_completo_igual_ao_de_urna_nao_repete_bytes():
    c = _cand(nome="GERALDO ALCKMIN")
    c.nome_completo = "GERALDO ALCKMIN"
    (linha,) = indice_de_busca([c])["ge"]
    assert len(linha) == 6


def test_o_filtro_do_navegador_olha_urna_completo_e_numero():
    html = _busca(["zu"], 100)
    assert 'norm(r[0] + " " + (r[6] ?? "")) + " " + (r[5] ?? "")' in html


def test_a_tela_diz_que_a_busca_cobre_os_dois_nomes():
    """Quem procura por sobrenome e nao acha precisa saber se procurou errado ou
    se a busca nao olha ali."""
    assert contem_frase(_busca(["zu"], 100), "o nome de urna")
    assert contem_frase(_busca(["zu"], 100), "o nome completo declarado ao TSE")


# ── o relatorio em PDF na home (F-28) ──────────────────────────────────────

def test_o_bloco_do_relatorio_so_aparece_se_o_pdf_existir(monkeypatch, tmp_path):
    """Anunciar um download que devolve 404 e' pior que nao anunciar nada.

    O PDF nao e' produzido pelo pipeline — e' um documento escrito. Uma geracao
    feita antes de alguem rodar o relatorio nao pode publicar link quebrado.
    """
    from scripts import render_site

    monkeypatch.setattr(render_site, "ANALISE_ORIGEM", tmp_path / "nao-existe.pdf")
    assert render_site._bloco_analise() == ""
    assert "Baixar o relatório" not in _home([], {}, "x", prefixos=["jo"])

    falso = tmp_path / "analise.pdf"
    falso.write_bytes(b"%PDF-1.4" + b"0" * 400_000)
    monkeypatch.setattr(render_site, "ANALISE_ORIGEM", falso)
    html = render_site._bloco_analise()
    assert "Baixar o relatório" in html
    assert "0,4 MB" in html.replace(".", ",")
    assert 'download' in html


def test_o_link_do_relatorio_usa_o_endereco_publico(monkeypatch, tmp_path):
    from scripts import render_site

    falso = tmp_path / "analise.pdf"
    falso.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(render_site, "ANALISE_ORIGEM", falso)
    assert f"{render_site.BASE_URL}/{render_site.ANALISE_PDF}" in render_site._bloco_analise()


def test_a_chamada_do_relatorio_conta_as_paginas_do_arquivo(monkeypatch, tmp_path):
    """O numero estava escrito na home. O relatorio cresceu de 27 para 29 paginas
    e a home seguiu anunciando 27 — silenciosamente, que e' como todo numero
    escrito a mao envelhece."""
    from scripts import render_site

    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4\n/Type /Page\n/Type /Page\n/Type /Page\n%%EOF")
    monkeypatch.setattr(render_site, "ANALISE_ORIGEM", pdf)
    assert "de 3 páginas" in render_site._bloco_analise()


def test_sem_conseguir_contar_a_frase_sai_sem_numero(monkeypatch, tmp_path):
    """Regra 5: melhor a frase sem o numero que a frase com o numero errado."""
    from scripts import render_site

    pdf = tmp_path / "b.pdf"
    pdf.write_bytes(b"%PDF-1.4 nada aqui parece uma pagina %%EOF")
    monkeypatch.setattr(render_site, "ANALISE_ORIGEM", pdf)
    html = render_site._bloco_analise()
    assert "Um relatório com a leitura" in html
    assert "páginas" not in html


def test_o_tamanho_usa_virgula_decimal(monkeypatch, tmp_path):
    """"0.5 MB" e' separador de outra lingua na home de um site brasileiro."""
    from scripts import render_site

    pdf = tmp_path / "c.pdf"
    pdf.write_bytes(b"%PDF-1.4" + b"0" * 500_000)
    monkeypatch.setattr(render_site, "ANALISE_ORIGEM", pdf)
    html = render_site._bloco_analise()
    assert "0,5 MB" in html
    assert "0.5 MB" not in html
