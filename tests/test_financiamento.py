"""Financiamento de campanha — F-11 / ADR-020. Testes puros, sem rede.

O foco e' `_documento`. Ela decide, para cada doador, se o numero vai para o
BigQuery em claro ou hasheado — e e' a unica funcao deste projeto cujo erro
publicaria o CPF de alguem que nao se candidatou a nada.
"""

from __future__ import annotations

import pytest

from ingest.common.textnorm import cpf_hash
from ingest.financiamento import _documento, _limpo, _numero

# CPF sintetico com digito verificador valido: o `cpf_hash` do projeto recusa
# repeticoes como 11111111111 (sao sentinelas do TSE) e devolveria None, o que
# faria o teste passar pelo motivo errado.
CPF = "12345678900"
CNPJ = "59933952000100"  # AVANTE Diretorio Nacional, doador real em 2026


class TestDocumento:
    def test_cpf_vira_hash_e_nunca_o_numero(self):
        cnpj, hash_, tipo = _documento(CPF)
        assert tipo == "fisica"
        assert cnpj is None
        assert hash_ == cpf_hash(CPF)
        assert CPF not in (hash_ or "")

    def test_cnpj_fica_em_claro(self):
        # E' a decisao central da ADR-020: CNPJ identifica empresa, nao pessoa,
        # e e' o que permite ver a mesma empresa financiando partidos diferentes.
        cnpj, hash_, tipo = _documento(CNPJ)
        assert tipo == "juridica"
        assert cnpj == CNPJ
        assert hash_ is None

    def test_cpf_formatado_tambem_e_hasheado(self):
        # Se o TSE mudar o layout e passar a escrever com pontuacao, o numero nao
        # pode escapar pela porta do "nao reconheci o formato".
        _, hash_, tipo = _documento("123.456.789-00")
        assert tipo == "fisica"
        assert hash_ == cpf_hash(CPF)

    def test_documento_ausente_nao_inventa_tipo(self):
        for bruto in (None, "", "#NULO", "N/A", "  "):
            cnpj, hash_, tipo = _documento(bruto)
            assert (cnpj, hash_, tipo) == (None, None, "nao informado")

    @pytest.mark.parametrize("bruto", ["123", "1234567890", "123456789012", "abc"])
    def test_tamanho_estranho_nao_vaza_nem_vira_cnpj(self, bruto):
        # Um numero de 12 digitos nao e' CPF nem CNPJ. Deixa-lo cair no ramo do
        # CNPJ o publicaria em claro sem ninguem perceber.
        cnpj, hash_, tipo = _documento(bruto)
        assert cnpj is None
        assert hash_ is None
        assert tipo == "nao informado"

    def test_o_mesmo_cpf_sempre_da_o_mesmo_hash(self):
        # E' o que permite somar as doacoes de uma pessoa sem guardar o numero.
        # Sem isso, `fct_doador_candidatura` contaria um doador por lancamento.
        assert _documento(CPF)[1] == _documento("123.456.789-00")[1]


class TestSentinelas:
    def test_sentinelas_do_tse_viram_ausencia(self):
        for bruto in ("#NULO", "#NE", "-1", "-3", "N/A", ""):
            assert _limpo(bruto) is None

    def test_aspas_do_csv_saem(self):
        # O TSE entrega o cabecalho e os campos entre aspas literais.
        assert _limpo('"SP"') == "SP"

    def test_valor_brasileiro(self):
        assert _numero("1.750.000,00") == 1750000.0
        assert _numero("50,00") == 50.0
        assert _numero("#NULO") is None
        assert _numero("nao e' numero") is None
