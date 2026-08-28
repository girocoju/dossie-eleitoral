"""Fotos oficiais de urna — F-13. Testes puros, sem rede."""

from __future__ import annotations

import pytest

from ingest.fotos import BUCKET, PADRAO_ARQUIVO, UES, Foto, url_pacote


class TestPadraoDoArquivo:
    """O nome do arquivo e' o que permite a juncao — se ele mudar, tudo quebra."""

    @pytest.mark.parametrize(
        ("arquivo", "ue", "sq"),
        [
            ("FAC10002544107_div.jpg", "AC", "10002544107"),
            ("FSP10002551975_div.jpg", "SP", "10002551975"),
            ("FBR280002552484_div.jpg", "BR", "280002552484"),
            ("fac10002544107_div.jpg", "ac", "10002544107"),  # caixa baixa
        ],
    )
    def test_reconhece_o_padrao_real(self, arquivo, ue, sq):
        m = PADRAO_ARQUIVO.match(arquivo)
        assert m is not None
        assert m.group("ue") == ue
        assert m.group("sq") == sq

    @pytest.mark.parametrize(
        "arquivo",
        [
            "leiame.pdf",                    # o pacote traz um PDF junto
            "FAC10002544107.jpg",            # sem o sufixo _div
            "F1010002544107_div.jpg",        # UE numerica
            "FAC_div.jpg",                   # sem sequencial
            "FACabcdefg_div.jpg",            # sequencial nao numerico
            "FAC10002544107_div.png",        # outra extensao
        ],
    )
    def test_recusa_o_que_nao_e_foto(self, arquivo):
        assert PADRAO_ARQUIVO.match(arquivo) is None


def test_caminho_e_url_sao_deterministicos():
    """A URL vira contrato publico: muda-la quebra relatorio ja' publicado."""
    foto = Foto(
        sk_candidatura="2026-AC-10002544107",
        sq_candidato="10002544107",
        sg_ue="AC",
        ano_eleicao=2026,
        caminho="2026/AC/10002544107.jpg",
        tamanho_bytes=5147,
    )
    assert foto.caminho == "2026/AC/10002544107.jpg"
    assert foto.url == f"https://storage.googleapis.com/{BUCKET}/2026/AC/10002544107.jpg"


def test_sk_candidatura_bate_com_a_do_mart():
    """O nome do arquivo carrega os componentes da chave: ano, UE e sequencial."""
    m = PADRAO_ARQUIVO.match("FAC10002544107_div.jpg")
    assert m is not None
    montada = f"2026-{m.group('ue').upper()}-{m.group('sq')}"
    assert montada == "2026-AC-10002544107"


def test_sao_28_unidades_eleitorais():
    """27 UFs mais BR, que guarda os presidenciais."""
    assert len(UES) == 28
    assert "BR" in UES
    assert "SP" in UES
    assert len(set(UES)) == 28


def test_url_do_pacote_usa_ano_e_ue():
    url = url_pacote(2026, "AC")
    assert url.endswith("/eleicoes2026/fotos/foto_cand2026_AC_div.zip")
    assert url_pacote(2022, "SP").endswith("foto_cand2022_SP_div.zip")
