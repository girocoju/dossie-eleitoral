"""Emendas parlamentares na ficha (F-27 / ADR-046).

Aqui o erro custa mais caro que em qualquer outra tela do projeto: atribuir
milhoes de reais a quem nao propos e' acusacao publicada sobre pessoa real.

Este arquivo protege as quatro formas de isso acontecer:

  - somar anos e publicar um total que nao existe;
  - deixar autor coletivo virar autor pessoal;
  - casar nome ambiguo com a pessoa errada;
  - calar sobre os 17% que a fonte nao atribui a ninguem.
"""

from __future__ import annotations

from ingest.emendas import ANO_NA_URL, COLETIVOS, e_pessoa, normalizar, numero
from scripts.gerar_site import TIPOS_EMENDA, Candidato
from scripts.render_site import _emendas
from tests.conftest import contem_frase, texto_visivel


def _cand(**kw):
    campos = dict(
        sk="sk-1", sq="70002540001", cod_cargo=6, nome_urna="PAULAO",
        nome_completo="PAULAO", sg_uf="AL", sigla_partido="PT", nome_partido="PT",
        nr_candidato=1313, coligacao=None, composicao=None, federacao=None,
        situacao="DEFERIDO", url_foto=None, idade=60, genero=None, cor_raca=None,
        grau_instrucao=None, ocupacao=None, uf_nascimento=None, bens_total=None,
        bens_n=None, proposta_obrigatoria=False, tem_proposta=False,
        url_proposta=None,
    )
    campos.update(kw)
    return Candidato(**campos)


EMENDAS = [
    {"ano": 2026, "tipo": "Emenda Individual - Transferências com Finalidade Definida",
     "qt": 17, "municipios": 12, "ufs": 1,
     "empenhado": 28_732_468.0, "pago": 21_458_011.0, "funcao": "Saúde"},
    {"ano": 2025, "tipo": "Emenda Individual - Transferências com Finalidade Definida",
     "qt": 22, "municipios": 15, "ufs": 1,
     "empenhado": 45_838_660.0, "pago": 30_779_798.0, "funcao": "Saúde"},
    {"ano": 2025, "tipo": "Emenda Individual - Transferências Especiais",
     "qt": 1, "municipios": 1, "ufs": 1,
     "empenhado": 3_400_000.0, "pago": 3_366_000.0, "funcao": "Encargos especiais"},
]


def _corpo(html: str) -> str:
    return texto_visivel(html.split("<tbody>", 1)[-1].split("</tbody>", 1)[0])


# ── um arquivo so', e o ano vem da coluna ──────────────────────────────────

def test_o_ano_no_endereco_nao_filtra_nada():
    """Os treze anos devolvem o MESMO arquivo, byte a byte. A primeira versao
    baixava um por ano e carregava 1.228.019 linhas — treze copias das 94.463.
    Nada falharia: a carga terminaria verde e toda soma sairia multiplicada por
    treze."""
    assert isinstance(ANO_NA_URL, int)


# ── autor coletivo nao e' pessoa ───────────────────────────────────────────

def test_relator_bancada_e_comissao_nao_sao_pessoa():
    """RELATOR GERAL move bilhoes e nao e' de ninguem em particular."""
    for nome in ("RELATOR GERAL", "BANCADA DO RIO DE JANEIRO",
                 "COMISSAO DE FINANCAS", "SEM INFORMACAO"):
        assert not e_pessoa(nome), nome


def test_pessoa_de_verdade_passa():
    for nome in ("ACIR GURGACZ", "JANDIRA FEGHALI", "PAULAO"):
        assert e_pessoa(normalizar(nome)), nome


def test_nome_vazio_nao_e_pessoa():
    assert not e_pessoa("")
    assert not e_pessoa(normalizar(None))


def test_a_lista_de_coletivos_cobre_o_que_a_fonte_usa():
    assert "SEM INFORMA" in COLETIVOS
    assert "RELATOR" in COLETIVOS


# ── o valor ────────────────────────────────────────────────────────────────

def test_o_numero_brasileiro_e_lido_certo():
    """`1.234.567,89` com ponto de milhar e virgula decimal. Ler como float
    americano daria 1,23 — mil vezes menos."""
    assert numero("1.234.567,89") == 1234567.89
    assert numero("241600,00") == 241600.0
    assert numero("") == 0.0
    assert numero("S/I") == 0.0
    assert numero(None) == 0.0


# ── a tela ─────────────────────────────────────────────────────────────────

def test_uma_linha_por_ano_e_nenhum_total():
    """"Moveu R$ 300 milhoes" sem dizer em quantos anos e' um numero grande e
    sem significado."""
    c = _cand()
    c.emendas = EMENDAS
    html = _emendas(c)
    assert contem_frase(html, "Não há total")
    corpo = _corpo(html).lower()
    for proibido in ("total", "soma", "acumulado"):
        assert proibido not in corpo, proibido


def test_empenhado_e_pago_aparecem_separados():
    """Empenhar e' reservar; pagar e' sair da conta. Mostrar so' um seria sempre
    o numero maior, que a campanha preferiria."""
    c = _cand()
    c.emendas = EMENDAS
    html = _emendas(c)
    t = _corpo(html)
    assert "R$ 28.732.468" in t and "R$ 21.458.011" in t
    assert contem_frase(html, "Empenhado não é pago")


def test_a_tela_diz_quanto_a_fonte_nao_atribui_a_ninguem():
    """17% das linhas, R$ 18,5 bi pagos. Um bloco que nao diga isso sugere que a
    lista esta' completa."""
    c = _cand()
    c.emendas = EMENDAS
    html = _emendas(c)
    assert contem_frase(html, "17% das linhas sem autor")
    assert contem_frase(html, "não atribui a ninguém")


def test_a_tela_diz_que_homonimo_fica_de_fora():
    c = _cand()
    c.emendas = EMENDAS
    assert contem_frase(_emendas(c), "não atribuir recurso a quem não propôs")


def test_a_tela_diz_que_emenda_nao_e_obra():
    """Emenda indica destino; quem executa e' o orgao que recebe."""
    c = _cand()
    c.emendas = EMENDAS
    assert contem_frase(_emendas(c), "indicação de destino, não obra entregue")


def test_o_ano_aparece_uma_vez_por_grupo():
    """Repetir 2025 em duas linhas seguidas polui sem informar."""
    c = _cand()
    c.emendas = EMENDAS
    assert _emendas(c).count(">2025<") == 1


def test_sem_emenda_nao_ha_bloco():
    assert _emendas(_cand()) == ""


def test_todo_tipo_da_fonte_tem_rotulo_curto():
    """O nome oficial nao cabe numa coluna."""
    for oficial, curto in TIPOS_EMENDA.items():
        assert len(curto) < len(oficial)
        assert curto[0].isupper()
