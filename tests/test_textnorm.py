"""Normalizacao de texto e valores das fontes brasileiras."""

from __future__ import annotations

import datetime as dt

import pytest

from ingest.common import textnorm as tn


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("DS_GRAU_INSTRUÇÃO", "ds_grau_instrucao"),
        ("NM_URNA_CANDIDATO", "nm_urna_candidato"),
        ("Unidade da Federação (Código)", "unidade_da_federacao_codigo"),
        ("  espaço   sobrando  ", "espaco_sobrando"),
    ],
)
def test_snake_case_tira_acento_e_achata(entrada, esperado):
    assert tn.snake_case(entrada) == esperado


@pytest.mark.parametrize("sentinela", ["#NULO#", "#NULO", "#NE", "#NE#", "-1", "-3", "", "   "])
def test_clean_transforma_sentinela_do_tse_em_none(sentinela):
    assert tn.clean(sentinela) is None


def test_clean_preserva_texto_util():
    assert tn.clean("  ENSINO   MEDIO COMPLETO ") == "ENSINO MEDIO COMPLETO"


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("1.234.567,89", 1234567.89),
        ("3176572.53", 3176572.53),  # formato real de VR_DESPESA_MAX_CAMPANHA em 2026
        ("0,00", 0.0),
        ("R$ 1.500,50", 1500.50),
        ("1,5", 1.5),
        ("#NULO#", None),
        ("abc", None),
    ],
)
def test_parse_decimal_br_decide_pelo_separador_mais_a_direita(entrada, esperado):
    assert tn.parse_decimal_br(entrada) == esperado


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("15/10/1986", dt.date(1986, 10, 15)),
        ("2026-08-03", dt.date(2026, 8, 3)),
        ("31/12/9999", None),  # sentinela de "sem informacao"
        ("01/01/1900", None),
        ("#NULO#", None),
        ("nao e data", None),
    ],
)
def test_parse_data_recusa_sentinela(entrada, esperado):
    assert tn.parse_data(entrada) == esperado


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [("S", True), ("SIM", True), ("N", False), ("NAO", False), ("#NE", None), ("X", None)],
)
def test_parse_bool_sn(entrada, esperado):
    assert tn.parse_bool_sn(entrada) is esperado


class TestCpfHash:
    """Constituicao 0.7: o CPF vira chave sem virar dado exposto.

    O numero usado aqui e' `12345678900`, INVALIDO por construcao: a Receita
    rejeita CPF de digitos repetidos, entao ele nao pertence nem pode pertencer a
    ninguem.

    Ate' 28/08/2026 estes testes usavam um numero que passava no digito
    verificador. Como qualquer CPF valido pode ser de uma pessoa real, e o
    repositorio e' publico, um numero impossivel serve igual e nao carrega esse
    risco. A funcao so' normaliza e faz hash — nao valida CPF — entao a troca nao
    enfraquece o teste.
    """

    def test_hash_e_deterministico_com_o_mesmo_salt(self, monkeypatch):
        monkeypatch.setenv("DOSSIE_CPF_SALT", "salt-de-teste")
        assert tn.cpf_hash("12345678900") == tn.cpf_hash("123.456.789-00")

    def test_hash_muda_com_o_salt(self, monkeypatch):
        monkeypatch.setenv("DOSSIE_CPF_SALT", "salt-a")
        a = tn.cpf_hash("12345678900")
        monkeypatch.setenv("DOSSIE_CPF_SALT", "salt-b")
        assert tn.cpf_hash("12345678900") != a

    def test_hash_nao_contem_o_cpf(self, monkeypatch):
        monkeypatch.setenv("DOSSIE_CPF_SALT", "salt-de-teste")
        digest = tn.cpf_hash("12345678900")
        assert digest is not None
        assert "12345678900" not in digest
        assert len(digest) == 64

    @pytest.mark.parametrize("invalido", ["", None, "123", "00000000000", "#NULO#", "1234567890a"])
    def test_cpf_invalido_nao_gera_chave(self, invalido, monkeypatch):
        monkeypatch.setenv("DOSSIE_CPF_SALT", "salt-de-teste")
        assert tn.cpf_hash(invalido) is None


def test_pessoa_fallback_precisa_das_duas_pontas(monkeypatch):
    monkeypatch.setenv("DOSSIE_CPF_SALT", "salt-de-teste")
    assert tn.pessoa_fallback_key("Maria da Silva", "01/02/1970") is not None
    assert tn.pessoa_fallback_key("Maria da Silva", None) is None
    assert tn.pessoa_fallback_key(None, "01/02/1970") is None


def test_pessoa_fallback_ignora_acento_e_caixa(monkeypatch):
    monkeypatch.setenv("DOSSIE_CPF_SALT", "salt-de-teste")
    assert tn.pessoa_fallback_key("JOSÉ ANTÔNIO", "01/02/1970") == tn.pessoa_fallback_key(
        "jose antonio", "01/02/1970"
    )
