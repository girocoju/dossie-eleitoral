"""Resolucao de layout do TSE — a regra "nao adivinhar" (SPEC 9) como teste."""

from __future__ import annotations

import pytest

from ingest.common.layout import LayoutError, anos_disponiveis, load_layout

# Header real de `consulta_cand_2026_AC.csv`, conferido em 27/08/2026.
HEADER_2026 = [
    "DT_GERACAO", "HH_GERACAO", "ANO_ELEICAO", "CD_TIPO_ELEICAO", "NM_TIPO_ELEICAO",
    "NR_TURNO", "CD_ELEICAO", "DS_ELEICAO", "DT_ELEICAO", "TP_ABRANGENCIA", "SG_UF",
    "SG_UE", "NM_UE", "CD_CARGO", "DS_CARGO", "SQ_CANDIDATO", "NR_CANDIDATO",
    "NM_CANDIDATO", "NM_URNA_CANDIDATO", "NM_SOCIAL_CANDIDATO", "NR_CPF_CANDIDATO",
    "DS_EMAIL", "CD_SITUACAO_CANDIDATURA", "DS_SITUACAO_CANDIDATURA", "TP_AGREMIACAO",
    "NR_PARTIDO", "SG_PARTIDO", "NM_PARTIDO", "NR_FEDERACAO", "NM_FEDERACAO",
    "SG_FEDERACAO", "DS_COMPOSICAO_FEDERACAO", "SQ_COLIGACAO", "NM_COLIGACAO",
    "DS_COMPOSICAO_COLIGACAO", "SG_UF_NASCIMENTO", "DT_NASCIMENTO",
    "NR_TITULO_ELEITORAL_CANDIDATO", "CD_GENERO", "DS_GENERO", "CD_GRAU_INSTRUCAO",
    "DS_GRAU_INSTRUCAO", "CD_ESTADO_CIVIL", "DS_ESTADO_CIVIL", "CD_COR_RACA",
    "DS_COR_RACA", "CD_OCUPACAO", "DS_OCUPACAO", "CD_SIT_TOT_TURNO", "DS_SIT_TOT_TURNO",
]


def test_todos_os_anos_do_escopo_tem_layout():
    assert anos_disponiveis() == [1998, 2002, 2006, 2010, 2014, 2018, 2022, 2026]


def test_ano_sem_layout_falha_com_mensagem_util():
    with pytest.raises(LayoutError, match="sem layout para 2030"):
        load_layout(2030)


def test_heranca_traz_os_datasets_da_base():
    layout = load_layout(2022)
    assert set(layout.datasets) >= {"candidatos", "bens", "vagas", "coligacoes"}


def test_2026_acrescenta_o_complementar():
    assert "complementar" in load_layout(2026).datasets
    assert "complementar" not in load_layout(2022).datasets


class TestResolucaoContraHeaderReal:
    """O layout de 2026 tem de casar com o arquivo que o TSE publicou."""

    def setup_method(self):
        self.ds = load_layout(2026).dataset("candidatos")
        self.resolucao = self.ds.resolve(HEADER_2026)

    def test_resolve_todos_os_obrigatorios(self):
        assert self.resolucao.faltando_obrigatorios == ()
        assert self.resolucao.ok

    def test_campos_que_migraram_para_o_complementar_ficam_nulos(self):
        # em 2026 o TSE moveu estes para consulta_cand_complementar
        for campo in ("st_reeleicao", "vr_despesa_max_campanha", "nr_processo"):
            assert campo in self.resolucao.faltando_opcionais

    def test_colunas_nao_mapeadas_vao_para_extras(self):
        assert "dt_geracao" in self.resolucao.extras
        assert "hh_geracao" in self.resolucao.extras

    def test_dado_pessoal_e_descartado_ou_hasheado(self):
        saida = self.ds.colunas_saida()
        assert "nr_cpf" not in saida
        assert "cpf_hash" in saida
        for sensivel in ("ds_email", "nr_titulo_eleitoral_candidato"):
            assert sensivel in self.ds.descartar


def test_falta_de_obrigatorio_falha_apontando_o_leiame():
    ds = load_layout(2026).dataset("candidatos")
    resolucao = ds.resolve(["ANO_ELEICAO", "SG_UF"])
    assert not resolucao.ok
    with pytest.raises(LayoutError) as erro:
        ds.exige(resolucao)
    mensagem = str(erro.value)
    assert "sq_candidato" in mensagem
    assert "leiame" in mensagem
    assert "tse_2026.yml" in mensagem


def test_alias_ignora_caixa_acento_e_aspas():
    ds = load_layout(2026).dataset("candidatos")
    resolucao = ds.resolve(['"ano_eleicao"', "Sq_Candidato", "SG_UF", "CD_CARGO",
                            "NR_TURNO", "NM_CANDIDATO", "SG_PARTIDO", "CD_SIT_TOT_TURNO"])
    assert resolucao.ok


def test_regex_casa_unidade_eleitoral_mas_nunca_o_consolidado():
    """O `_BRASIL` do pacote e' um consolidado de todas as UFs.

    Le-lo junto com os arquivos por UF duplica cada candidatura — foi o que
    aconteceu em 27/08/2026: 41.530 linhas para 20.765 candidaturas reais.
    """
    padrao = load_layout(2026).dataset("candidatos").compila_regex()
    assert padrao.match("consulta_cand_2026_AC.csv")
    assert padrao.match("consulta_cand_2026_BR.csv")      # UE da eleicao nacional
    assert not padrao.match("consulta_cand_2026_BRASIL.csv")  # consolidado
    assert not padrao.match("consulta_cand_2022_AC.csv")
    assert not padrao.match("leiame-consulta_cand.pdf")


def test_layout_declara_quantas_unidades_eleitorais_esperar():
    assert load_layout(2026).ue_esperadas == 28   # 27 UFs + BR


def test_url_do_pacote_usa_o_ano():
    ds = load_layout(2022).dataset("candidatos")
    assert ds.url.endswith("/consulta_cand/consulta_cand_2022.zip")
    assert ds.zip_name == "consulta_cand_2022.zip"
