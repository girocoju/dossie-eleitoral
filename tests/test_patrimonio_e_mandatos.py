"""De que o patrimonio e' feito, e o que a ficha NAO pode dizer sobre ele (F-24).

A ficha trazia "R$ 2.221.000, 10 itens". Dois patrimonios do mesmo tamanho podem
ser uma fazenda ou vinte apartamentos, e a diferenca e' o que alguem quer saber.

Este arquivo protege as tres formas de o bloco novo virar afirmacao falsa:

  - publicar o endereco residencial que vem dentro da descricao do bem;
  - transformar a diferenca entre duas declaracoes em "enriqueceu X%";
  - deixar um ano ausente parecer patrimonio zero.
"""

from __future__ import annotations

from scripts.gerar_site import GRUPOS_BEM, Candidato
from scripts.render_site import _bens, _em_exercicio, _ficha, _mandatos, _patrimonio
from tests.conftest import contem_frase, texto_visivel


def _corpo(html: str) -> str:
    """So' o DADO da tabela, sem a prosa em volta.

    As ressalvas dizem, com todas as letras, "contem endereco residencial,
    placa" e "nao medem enriquecimento". Procurar essas palavras no HTML inteiro
    acusaria justamente o texto que existe para proteger o leitor — e um teste
    que reprova a propria correcao empurra para remove-la.
    """
    return texto_visivel(html.split("<tbody>", 1)[-1].split("</tbody>", 1)[0])


def _cand(**kw):
    campos = dict(
        sk="sk-1", sq="70002540001", cod_cargo=6, nome_urna="ANTONIA LUCIA",
        nome_completo="ANTONIA LUCIA SILVA", sg_uf="AC", sigla_partido="PSDB",
        nome_partido="PSDB", nr_candidato=4501, coligacao=None, composicao=None,
        federacao=None, situacao="Deferido", url_foto=None, idade=55,
        genero=None, cor_raca=None, grau_instrucao=None, ocupacao=None,
        uf_nascimento=None, bens_total=4115000.0, bens_n=4,
        proposta_obrigatoria=False, tem_proposta=False, url_proposta=None,
    )
    campos.update(kw)
    return Candidato(**campos)


BENS = [
    {"grupo": "participacoes", "tipo": "Quotas ou quinhões de capital",
     "qt": 2, "valor": 3_920_000.0},
    {"grupo": "moveis", "tipo": "Veículo automotor terrestre", "qt": 2,
     "valor": 195_000.0},
]

SERIE = [
    {"ano": 2026, "valor": 4_115_000.0, "itens": 4, "cargo": 6, "uf": "AC"},
    {"ano": 2022, "valor": 3_290_000.0, "itens": 4, "cargo": 6, "uf": "AC"},
    {"ano": 2018, "valor": 1_610_000.0, "itens": 1, "cargo": 6, "uf": "AC"},
]


# ── o endereco nao pode chegar a' tela ─────────────────────────────────────

def test_a_ficha_nao_tem_onde_receber_a_descricao_do_bem():
    """`ds_bem` traz endereco residencial em 6,8% das linhas de 2026 — um caso
    real: "IMOVEL RESIDENCIAL NA RUA (...), 145, AFOGADOS, RECIFE/PE". A
    Constituicao 0 proibe expor endereco de candidato.

    A protecao e' estrutural: o campo nao existe no mart nem no `Candidato`, e o
    que nao chega ali nao chega a' tela por descuido de quem escrever a proxima
    consulta.
    """
    c = _cand()
    assert not hasattr(c, "bens_descricao")
    assert set(BENS[0]) == {"grupo", "tipo", "qt", "valor"}, \
        "a linha de bem so' carrega tipo, quantidade e valor"
    c.bens = BENS
    corpo = _corpo(_bens(c)).upper()
    for palavra in ("RUA", "AVENIDA", "CEP", "CHASSI", "PLACA", "BAIRRO"):
        assert palavra not in corpo, palavra


def test_a_tela_diz_por_que_a_descricao_nao_esta_la():
    """Omitir sem dizer que omitiu deixa o leitor sem distinguir "nao ha' dado"
    de "esconderam" — a mesma razao do ADR-031."""
    c = _cand()
    c.bens = BENS
    assert contem_frase(_bens(c), "A descrição de cada bem")
    assert contem_frase(_bens(c), "endereço residencial")


# ── o bloco de bens ────────────────────────────────────────────────────────

def test_os_grupos_saem_da_tabela_oficial():
    """A dezena do `cd_tipo_bem` E' o agrupamento da Receita, que o TSE reusa.
    Classificar pelo NOME seria adivinhar (ADR-034)."""
    assert set(GRUPOS_BEM) == {"imoveis", "moveis", "participacoes", "aplicacoes",
                               "creditos", "dinheiro", "fundos", "outros"}


def test_o_bloco_soma_o_grupo_e_detalha_o_tipo():
    c = _cand()
    c.bens = BENS
    t = " ".join(texto_visivel(_bens(c)).split())
    assert "Participação em empresas" in t
    assert "Quotas ou quinhões de capital" in t
    assert "R$ 4.115.000" in t, "o total tem de bater com a soma dos grupos"


def test_sem_bem_declarado_nao_ha_bloco():
    """Regra 5: quem nao declarou nada nao vira uma linha de R$ 0,00."""
    assert _bens(_cand(bens_total=None, bens_n=None)) == ""


def test_o_valor_e_dito_como_declarado_e_de_aquisicao():
    c = _cand()
    c.bens = BENS
    assert contem_frase(_bens(c), "declarado pelo candidato")
    assert contem_frase(_bens(c), "de aquisição — não de mercado")


# ── a serie de patrimonio ──────────────────────────────────────────────────

def test_a_serie_nao_calcula_variacao_em_lugar_nenhum():
    """O TSE pede valor de AQUISICAO, os valores sao NOMINAIS e a declaracao e'
    do proprio candidato. Um "+25%" na tela afirmaria crescimento onde pode
    haver queda real, compra ou venda."""
    c = _cand()
    c.patrimonio = SERIE
    corpo = _corpo(_patrimonio(c)).lower()
    for proibido in ("%", "aumento", "cresceu", "enriquec", "variação", "evolução",
                     "+", "→"):
        assert proibido not in corpo, proibido
    # E o titulo do bloco tambem nao promete comparacao.
    assert "evolução" not in _patrimonio(c).lower()


def test_a_serie_diz_as_tres_ressalvas():
    c = _cand()
    c.patrimonio = SERIE
    html = _patrimonio(c)
    assert contem_frase(html, "não medem enriquecimento")
    assert contem_frase(html, "valor de aquisição")
    assert contem_frase(html, "nominais")
    assert contem_frase(html, "declaração do próprio candidato")


def test_ano_ausente_nao_e_patrimonio_zero_e_a_tela_diz_isso():
    """Sem essa frase, o leitor le' a lacuna entre 2018 e 2026 como queda."""
    c = _cand()
    c.patrimonio = SERIE
    assert contem_frase(_patrimonio(c), "não aparece")
    assert contem_frase(_patrimonio(c), "não é patrimônio")


def test_uma_declaracao_sozinha_nao_vira_serie():
    """Uma linha so' nao e' uma serie, e o bloco de bens ja' mostra o total."""
    c = _cand()
    c.patrimonio = SERIE[:1]
    assert _patrimonio(c) == ""


def test_a_serie_mostra_os_anos_em_ordem_decrescente():
    c = _cand()
    c.patrimonio = list(reversed(SERIE))
    t = texto_visivel(_patrimonio(c))
    assert t.index("2026") < t.index("2022") < t.index("2018")


# ── mandatos ───────────────────────────────────────────────────────────────

MANDATOS = [
    {"cargo": "DEPUTADO FEDERAL", "cod": 6, "ue": "ACRE", "uf": "AC",
     "partido": "PSDB", "a1": 2023, "a2": 2027, "em_curso": True, "titular": True},
    {"cargo": "DEPUTADO FEDERAL", "cod": 6, "ue": "ACRE", "uf": "AC",
     "partido": "PSC", "a1": 2011, "a2": 2015, "em_curso": False, "titular": False},
]


def test_mandato_nao_e_candidatura():
    """A trajetoria lista candidaturas, inclusive as perdidas. Este bloco diz o
    que a pessoa chegou a exercer — e a tela precisa dizer a diferenca."""
    c = _cand()
    c.mandatos = MANDATOS
    assert contem_frase(_mandatos(c), "Diferente da trajetória")
    assert contem_frase(_mandatos(c), "inclusive as perdidas")


def test_o_suplente_aparece_como_suplente():
    c = _cand()
    c.mandatos = MANDATOS
    assert "suplente" in _mandatos(c)


def test_a_tela_nao_afirma_saida_antecipada_que_a_fonte_nao_tem():
    """`motivo_fim` e' "nao informado" em 11.771 dos 11.778 mandatos. O periodo
    exibido e' o do CARGO, e dizer isso evita que o leitor entenda que a pessoa
    ficou ate' o fim."""
    c = _cand()
    c.mandatos = MANDATOS
    assert contem_frase(_mandatos(c), "período é o do mandato do cargo")
    assert contem_frase(_mandatos(c), "não publica saída antecipada")


def test_sem_mandato_nao_ha_bloco():
    assert _mandatos(_cand()) == ""


# ── em exercicio ───────────────────────────────────────────────────────────

def test_em_exercicio_diz_de_qual_mandato_sao_os_blocos_abaixo():
    c = _cand()
    c.exercicio = {"casa": "camara", "url": "https://x/dep/1"}
    html = _em_exercicio(c)
    assert contem_frase(html, "em exercício")
    assert contem_frase(html, "Câmara dos Deputados")
    assert contem_frase(html, "são desse mandato")


def test_quem_nao_esta_em_exercicio_nao_ganha_aviso():
    assert _em_exercicio(_cand()) == ""


# ── a ficha inteira ────────────────────────────────────────────────────────

def test_a_ficha_sem_nenhum_dado_novo_nao_ganha_bloco_vazio():
    """Bloco vazio com peso visual de conteudo sugere que falta alguma coisa."""
    html = _ficha(_cand(bens_total=None, bens_n=None), "x")
    for titulo in ("De que é feito o patrimônio",
                   "Patrimônio declarado a cada eleição",
                   "Mandatos exercidos"):
        assert not contem_frase(html, titulo), titulo


def test_a_ficha_completa_traz_os_quatro_blocos():
    c = _cand()
    c.bens, c.patrimonio, c.mandatos = BENS, SERIE, MANDATOS
    c.exercicio = {"casa": "camara", "url": None}
    html = _ficha(c, "x")
    for titulo in ("De que é feito o patrimônio declarado",
                   "Patrimônio declarado a cada eleição",
                   "Mandatos exercidos",
                   "Está em exercício"):
        assert contem_frase(html, titulo), titulo
