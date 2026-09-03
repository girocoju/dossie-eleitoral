"""A ferramenta que impede o falso negativo de 03/09/2026."""

from __future__ import annotations

from tests.conftest import contem_frase, texto_visivel

# Exatamente como o gerador emite: a frase atravessa a quebra de linha.
HTML = """      <h3 style="margin:24px 0 8px;font-size:15px">A conferência que achou um
        erro grande</h3>
      <p>Em Minas Gerais, 2023, eram <b>R$ 23,8 bilhões</b> contados como
        receita do estado.</p>"""


def test_a_busca_literal_falha_e_por_isso_a_ferramenta_existe():
    assert "A conferência que achou um erro grande" not in HTML


def test_a_frase_e_encontrada_apesar_da_quebra():
    assert contem_frase(HTML, "A conferência que achou um erro grande")


def test_frase_que_atravessa_marcacao_tambem():
    assert contem_frase(HTML, "eram R$ 23,8 bilhões contados como receita do estado")


def test_frase_ausente_continua_ausente():
    """A ferramenta nao pode transformar tudo em verdadeiro."""
    assert not contem_frase(HTML, "Isso não foi feito")


def test_texto_visivel_remove_marcacao_e_normaliza():
    t = texto_visivel("<p>a  <b>b</b>\n   c</p>")
    assert t == "a b c"


def test_a_frase_procurada_tambem_e_normalizada():
    """Quem escreve o teste pode quebrar a frase dele; o resultado nao muda."""
    assert contem_frase(HTML, """A conferência que achou
                                 um erro grande""")
