"""Atividade do Senado: o filtro de autor principal e a classificacao (F-22).

A L-20 recusava fechar isto sem equivalente ao `proponente` da Camara. Estes
testes guardam as duas coisas que a fechavam: o filtro que separa autoria de
coautoria, e o mapeamento das classes — que veio da lista OFICIAL de siglas, nao
do formato da sigla.
"""

from __future__ import annotations

from ingest.senado import (
    CLASSE_PADRAO,
    CLASSES,
    classe_de,
    extrair_autoria,
    linhas_para_bq,
)


def test_ordem_1_e_autor_principal_e_o_resto_nao():
    """`ordem = 1` e' o equivalente do `proponente = 1` da Camara."""
    indice = {
        1: {"processo_id": 1, "sigla": "PL", "ano": 2024, "autoria": [
            {"codigo_parlamentar": 10, "ordem": 1, "nome_autor": "A"},
            {"codigo_parlamentar": 20, "ordem": 2, "nome_autor": "B"},
        ]},
    }
    linhas = list(linhas_para_bq(indice, {10, 20}))
    por_cod = {x["codigo_parlamentar"]: x for x in linhas}
    assert por_cod[10]["autor_principal"] is True
    assert por_cod[20]["autor_principal"] is False, (
        "coautor contado como autor infla quem assina tudo — era isto que a L-20 "
        "mandava evitar")


def test_senador_fora_da_lista_nao_entra():
    indice = {1: {"processo_id": 1, "sigla": "PL", "ano": 2024, "autoria": [
        {"codigo_parlamentar": 99, "ordem": 1, "nome_autor": "X"}]}}
    assert list(linhas_para_bq(indice, {10})) == []


def test_autoria_sem_parlamentar_e_descartada():
    """Comissao, Executivo, iniciativa popular: nao ha' senador a quem atribuir."""
    detalhe = {"documento": {"autoria": [
        {"autor": "Comissão de Educação", "ordem": 1},
        {"autor": "Fulano", "codigoParlamentar": 5894, "ordem": 2},
    ]}}
    saida = extrair_autoria(detalhe)
    assert [a["codigo_parlamentar"] for a in saida] == [5894]


def test_rqi_nao_e_fiscalizacao():
    """O erro que o mapeamento por formato de sigla teria cometido.

    `RQI` parece "Requerimento de Informacao". A lista oficial do Senado diz
    "Requerimento da Comissao de Servicos de Infraestrutura" — rito de comissao.
    """
    assert classe_de("RQI") == "procedimental"
    assert "RQI" not in CLASSES["fiscalizacao"]


def test_as_classes_normativas_sao_projetos_e_pec():
    for sigla in ("PL", "PLS", "PEC", "PLP", "PDL", "PRS", "MPV"):
        assert classe_de(sigla) == "normativa", sigla


def test_fiscalizacao_so_com_o_que_exige_contas():
    for sigla in ("PFC", "PFS", "RIC", "SIT", "INQ"):
        assert classe_de(sigla) == "fiscalizacao", sigla


def test_requerimento_de_comissao_e_rito():
    for sigla in ("RQS", "REQ", "RQJ", "RRA", "RDH", "RMA", "RCE"):
        assert classe_de(sigla) == CLASSE_PADRAO, sigla


def test_sigla_desconhecida_cai_em_procedimental_e_nao_quebra():
    assert classe_de("XYZ") == CLASSE_PADRAO
    assert classe_de(None) == CLASSE_PADRAO
    assert classe_de("") == CLASSE_PADRAO


def test_nenhuma_sigla_esta_em_duas_classes():
    vistas: dict[str, str] = {}
    for classe, siglas in CLASSES.items():
        for s in siglas:
            assert s not in vistas, f"{s} em {classe} e {vistas[s]}"
            vistas[s] = classe


def test_a_classificacao_e_por_sigla_normalizada():
    assert classe_de(" pl ") == "normativa"
    assert classe_de("pec") == "normativa"


def test_milhar_formata_o_numero_e_nao_a_frase():
    """O bloco da Camara publicava "Rito. homenagem. emenda" desde a F-16.

    A causa era `f"...{n:,}...".replace(",", ".")` aplicado a' linha inteira: a
    troca acertava o separador de milhar e atropelava a virgula do rotulo.
    """
    from scripts.render_site import _milhar

    assert _milhar(1234) == "1.234"
    assert _milhar(999) == "999"
    assert _milhar(1234567) == "1.234.567"
    assert _milhar(None) == "—"


def test_os_rotulos_de_atividade_mantem_as_virgulas():
    from types import SimpleNamespace

    from scripts.render_site import _atividade_senado

    c = SimpleNamespace(atividade_senado=[
        {"classe": "procedimental", "total": 1234, "tramitando": 2,
         "leg": 57, "leg_ini": 2023, "leg_fim": 2026, "a1": 2023, "a2": 2026}])
    html = _atividade_senado(c)
    assert "Rito, homenagem, requerimento de comissão" in html
    assert "Rito. homenagem" not in html
    assert "1.234" in html
