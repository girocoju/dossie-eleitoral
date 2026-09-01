"""Catalogo de indicadores, parser do SIDRA e coerencia dos seeds do dbt."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from ingest import ibge_sidra
from ingest.common.indicadores import carregar_catalogo, media_anual
from ingest.common.ufs import POR_COD_IBGE, UFS, sigla_por_cod_ibge

RAIZ = Path(__file__).resolve().parents[1]


# ── catalogo ───────────────────────────────────────────────────────────


def test_catalogo_carrega_e_valida():
    catalogo = carregar_catalogo()
    assert {"PIB", "POPULACAO", "DESOCUPACAO", "HOMICIDIOS"} <= set(catalogo)


def test_todo_indicador_declara_fonte_e_unidade():
    """Constituicao 0.3: fonte em toda visualizacao — logo, em todo indicador."""
    for ind in carregar_catalogo().values():
        assert ind.fonte, f"{ind.cod_indicador} sem fonte"
        assert ind.unidade, f"{ind.cod_indicador} sem unidade"


def test_indicador_verificado_registra_a_data_da_conferencia():
    for ind in carregar_catalogo().values():
        if ind.verificado:
            assert ind.conferido_em, f"{ind.cod_indicador} marcado verificado sem conferido_em"


def test_derivado_e_arquivo_sem_url_nao_sao_ingeriveis():
    """Indicador sem fonte resolvida nao pode ser tentado pela carga.

    O IDHM ocupava esta posicao ate' 28/08/2026, quando passou a vir do Ipeadata.
    Quem ficou sem URL foi o IDEB — ver L-05.
    """
    catalogo = carregar_catalogo()
    assert catalogo["PIB_PER_CAPITA"].ingerivel is False   # nasce no dbt
    assert catalogo["IDHM"].ingerivel is True              # veio para o Ipeadata
    assert catalogo["IDEB"].ingerivel is True              # veio para o INEP
    assert catalogo["PIB"].ingerivel is True

    # A regra em si continua valendo, mesmo sem nenhum indicador a exercendo hoje:
    # `arquivo` sem URL nao pode ser tentado pela carga.
    from ingest.common.indicadores import Indicador

    orfao = Indicador(
        cod_indicador="X", nome="x", fonte="x", unidade="x", periodicidade="anual",
        direcao_desejavel="neutro", ente_medido="territorio",
        provedor="arquivo", verificado=False,
    )
    assert orfao.ingerivel is False


# ── UFs ────────────────────────────────────────────────────────────────


def test_sao_27_ufs_com_codigo_ibge_unico():
    assert len(UFS) == 27
    assert len(POR_COD_IBGE) == 27


@pytest.mark.parametrize(
    ("cod", "esperado"),
    [("11", "RO"), ("35", "SP"), ("53", "DF"), ("1", "BR"), ("99", None), (None, None)],
)
def test_sigla_por_cod_ibge(cod, esperado):
    assert sigla_por_cod_ibge(cod) == esperado


# ── parser do SIDRA ────────────────────────────────────────────────────

CABECALHO_SIDRA = {
    "NC": "Nivel Territorial (Codigo)",
    "NN": "Nivel Territorial",
    "MC": "Unidade de Medida (Codigo)",
    "MN": "Unidade de Medida",
    "V": "Valor",
    "D1C": "Unidade da Federacao (Codigo)",
    "D1N": "Unidade da Federacao",
    "D2C": "Variavel (Codigo)",
    "D2N": "Variavel",
    "D3C": "Ano (Codigo)",
    "D3N": "Ano",
}


def _linha(uf_cod, periodo, valor):
    return {
        "NC": "3", "NN": "Unidade da Federacao", "MC": "40", "MN": "Mil Reais",
        "V": valor, "D1C": uf_cod, "D1N": "x", "D2C": "37", "D2N": "PIB",
        "D3C": periodo, "D3N": periodo,
    }


def test_parse_sidra_mapeia_dimensoes_pelo_rotulo():
    ind = carregar_catalogo()["PIB"]
    payload = [CABECALHO_SIDRA, _linha("11", "2022", "66795454"), _linha("35", "2022", "1000")]
    obs = ibge_sidra.parse_resposta(payload, ind, "http://exemplo")
    assert {(o.sg_uf, o.ano, o.valor) for o in obs} == {
        ("RO", 2022, 66795454.0),
        ("SP", 2022, 1000.0),
    }


@pytest.mark.parametrize("sem_valor", ["-", "..", "...", "X", ""])
def test_parse_sidra_ignora_marcador_de_ausencia(sem_valor):
    """Ausencia vira linha inexistente, nunca zero."""
    ind = carregar_catalogo()["PIB"]
    obs = ibge_sidra.parse_resposta([CABECALHO_SIDRA, _linha("11", "2022", sem_valor)],
                                    ind, "http://exemplo")
    assert obs == []


def _indicador_trimestral():
    """Indicador SINTETICO para exercitar a agregacao trimestral.

    Antes estes testes usavam `carregar_catalogo()["DESOCUPACAO"]`, que era o
    unico com `agregacao: media_anual`. Em 01/09/2026 a desocupacao passou a vir
    da serie ANUAL do IBGE (ADR-030) e os testes quebraram — sem que a maquina de
    agregacao tivesse mudado nada. Teste de maquinaria nao deve depender de qual
    indicador do catalogo por acaso a usa hoje.
    """
    from ingest.common.indicadores import Indicador

    return Indicador(
        cod_indicador="TESTE_TRIMESTRAL", nome="teste", fonte="teste",
        unidade="%", periodicidade="anual", direcao_desejavel="neutro",
        ente_medido="territorio", provedor="sidra", verificado=False,
        parametros={"tabela": 1, "variavel": 1, "niveis": ["n1"],
                    "agregacao": "media_anual", "min_periodos": 4},
    )


def test_parse_sidra_agrega_trimestre_em_ano():
    ind = _indicador_trimestral()
    cabecalho = dict(CABECALHO_SIDRA, D3C="Trimestre (Codigo)", D3N="Trimestre")
    payload = [cabecalho] + [
        _linha("11", f"2024{t:02d}", v) for t, v in ((1, "4.0"), (2, "3.0"), (3, "3.0"), (4, "2.0"))
    ]
    obs = ibge_sidra.parse_resposta(payload, ind, "http://exemplo")
    assert len(obs) == 1
    assert obs[0].ano == 2024
    assert obs[0].valor == pytest.approx(3.0)
    assert obs[0].n_periodos == 4


def test_parse_sidra_descarta_ano_incompleto():
    """Meio ano de PNAD nao vira 'o ano' — o 2026 real tinha so' 2 trimestres."""
    ind = _indicador_trimestral()
    cabecalho = dict(CABECALHO_SIDRA, D3C="Trimestre (Codigo)", D3N="Trimestre")
    payload = [cabecalho, _linha("11", "202601", "5.0"), _linha("11", "202602", "5.0")]
    assert ibge_sidra.parse_resposta(payload, ind, "http://exemplo") == []


def test_parse_sidra_falha_quando_nao_reconhece_as_dimensoes():
    ind = carregar_catalogo()["PIB"]
    with pytest.raises(ibge_sidra.SidraError, match="dimensoes"):
        ibge_sidra.parse_resposta([{"V": "Valor"}, {"V": "1"}], ind, "http://exemplo")


def test_media_anual_respeita_o_minimo():
    assert media_anual([(2024, 1.0), (2024, 3.0)], min_periodos=2) == {2024: (2.0, 2)}
    assert media_anual([(2024, 1.0)], min_periodos=2) == {}


# ── seeds do dbt ───────────────────────────────────────────────────────


def test_seeds_estao_em_dia_com_as_fontes_de_verdade():
    """`ingest/common/ufs.py` e o catalogo nao podem divergir dos CSVs do dbt."""
    resultado = subprocess.run(
        [sys.executable, str(RAIZ / "scripts" / "gerar_seeds.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=RAIZ,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
