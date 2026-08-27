"""Ingestao TSE ponta a ponta contra um zip sintetico — sem rede."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

import pytest

from ingest import tse
from ingest.common.http import Artifact
from ingest.common.layout import load_layout
from ingest.common.writer import NdjsonWriter, read_ndjson

CABECALHO = [
    "DT_GERACAO", "ANO_ELEICAO", "NR_TURNO", "CD_ELEICAO", "SG_UF", "SG_UE", "NM_UE",
    "CD_CARGO", "DS_CARGO", "SQ_CANDIDATO", "NM_CANDIDATO", "NM_URNA_CANDIDATO",
    "NR_CPF_CANDIDATO", "DS_EMAIL", "NR_TITULO_ELEITORAL_CANDIDATO", "SG_PARTIDO",
    "NM_PARTIDO", "DT_NASCIMENTO", "DS_GENERO", "DS_COR_RACA", "CD_SIT_TOT_TURNO",
    "DS_SIT_TOT_TURNO", "COLUNA_INESPERADA",
]

LINHAS = [
    ["27/08/2026", "2026", "1", "6259", "AC", "AC", "ACRE", "3", "GOVERNADOR",
     "10002551866", "MARIA DA SILVA", "MARIA", "12345678900", "NAO DIVULGAVEL",
     "005192212488", "PRD", "PARTIDO RENOVACAO DEMOCRATICA", "15/10/1986",
     "FEMININO", "PARDA", "-1", "#NULO", "valor extra"],
    ["27/08/2026", "2026", "1", "6259", "AC", "AC", "ACRE", "6", "DEPUTADO FEDERAL",
     "10002551867", "JOAO SOUZA", "JOAO", "", "#NULO", "", "PT", "PARTIDO DOS TRABALHADORES",
     "01/01/1970", "MASCULINO", "BRANCA", "-1", "#NULO", ""],
]


@pytest.fixture
def zip_sintetico(tmp_path: Path) -> Path:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter=";", quotechar='"', lineterminator="\r\n")
    writer.writerow(CABECALHO)
    writer.writerows(LINHAS)
    destino = tmp_path / "consulta_cand_2026.zip"
    with zipfile.ZipFile(destino, "w") as zf:
        zf.writestr("consulta_cand_2026_AC.csv", buffer.getvalue().encode("latin-1"))
        zf.writestr("leiame-consulta_cand.pdf", b"nao e csv")
    return destino


@pytest.fixture
def artifact(zip_sintetico: Path) -> Artifact:
    return Artifact(
        url="https://exemplo/consulta_cand_2026.zip",
        path=str(zip_sintetico),
        sha256="a" * 64,
        size_bytes=zip_sintetico.stat().st_size,
        extracted_at="2026-08-27T12:00:00+00:00",
    )


def _linhas(zip_sintetico, artifact, monkeypatch):
    monkeypatch.setenv("RADAR_CPF_SALT", "salt-de-teste")
    ds = load_layout(2026).dataset("candidatos")
    return [linha for linha, _, _ in tse._linhas(zip_sintetico, ds, artifact)]


def test_le_apenas_os_csv_que_casam_o_padrao(zip_sintetico, artifact, monkeypatch):
    linhas = _linhas(zip_sintetico, artifact, monkeypatch)
    assert len(linhas) == 2
    assert {linha["_source_file"] for linha in linhas} == {"consulta_cand_2026_AC.csv"}


def test_ano_eleicao_e_particao_sao_derivados_do_layout(zip_sintetico, artifact, monkeypatch):
    linha = _linhas(zip_sintetico, artifact, monkeypatch)[0]
    assert linha["ano_eleicao"] == 2026  # inteiro, nao string
    assert linha["data_particao"] == "2026-01-01"


def test_procedencia_vai_junto_com_cada_linha(zip_sintetico, artifact, monkeypatch):
    linha = _linhas(zip_sintetico, artifact, monkeypatch)[0]
    assert linha["_extracted_at"] == "2026-08-27T12:00:00+00:00"
    assert linha["_source_url"].endswith("consulta_cand_2026.zip")
    assert linha["_source_sha256"] == "a" * 64


class TestPrivacidade:
    """Constituicao 0.7: CPF vira hash; e-mail e titulo nao sao gravados."""

    def test_cpf_vira_hash_e_some(self, zip_sintetico, artifact, monkeypatch):
        linha = _linhas(zip_sintetico, artifact, monkeypatch)[0]
        assert "nr_cpf" not in linha
        assert len(linha["cpf_hash"]) == 64
        assert "12345678900" not in json.dumps(linha)

    def test_email_e_titulo_nao_sobram_nem_em_extras(
        self, zip_sintetico, artifact, monkeypatch
    ):
        for linha in _linhas(zip_sintetico, artifact, monkeypatch):
            serializado = json.dumps(linha)
            assert "ds_email" not in serializado
            assert "nr_titulo" not in serializado
            assert "005192212488" not in serializado

    def test_candidatura_sem_cpf_fica_sem_chave(self, zip_sintetico, artifact, monkeypatch):
        linha = _linhas(zip_sintetico, artifact, monkeypatch)[1]
        assert linha["cpf_hash"] is None


def test_coluna_nao_mapeada_vai_para_extras(zip_sintetico, artifact, monkeypatch):
    linha = _linhas(zip_sintetico, artifact, monkeypatch)[0]
    extras = json.loads(linha["_extras"])
    assert extras["coluna_inesperada"] == "valor extra"
    assert extras["dt_geracao"] == "27/08/2026"


def test_sentinelas_chegam_intactas_ao_raw(zip_sintetico, artifact, monkeypatch):
    # `raw` e' copia fiel (SPEC 4): quem limpa `#NULO` e' o dbt, nao a ingestao
    linha = _linhas(zip_sintetico, artifact, monkeypatch)[0]
    assert linha["situacao_turno"] == "#NULO"


def test_ndjson_ida_e_volta(tmp_path, zip_sintetico, artifact, monkeypatch):
    linhas = _linhas(zip_sintetico, artifact, monkeypatch)
    destino = tmp_path / "saida.ndjson.gz"
    with NdjsonWriter(destino) as writer:
        writer.write_all(linhas)
    assert list(read_ndjson(destino)) == linhas


def test_zip_sem_csv_do_padrao_falha_apontando_o_conteudo(tmp_path, monkeypatch):
    vazio = tmp_path / "consulta_cand_2026.zip"
    with zipfile.ZipFile(vazio, "w") as zf:
        zf.writestr("outra_coisa.csv", b"a;b\n1;2\n")
    ds = load_layout(2026).dataset("candidatos")
    art = Artifact(url="u", path=str(vazio), sha256="", size_bytes=0, extracted_at="")
    with pytest.raises(Exception, match="nenhum CSV"):
        list(tse._linhas(vazio, ds, art))
