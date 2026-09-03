"""A ficha diz quando AQUELE dado mudou, nao quando o site rodou (ADR-038).

O rodape mostrava `max(_extracted_at)` da tabela inteira. `dim_candidato` tem um
unico carimbo, reescrito a cada ingestao — entao a data mudava todo dia em toda
ficha, mesmo quando nada naquela candidatura tinha mudado.

Duas consequencias:

  - o leitor era informado da hora da maquina, nao da idade do dado;
  - TODA pagina mudava todo dia, e envio incremental nao economizava nada. Com as
    20.765 fichas da F-18 a publicacao diaria passaria de 2,5 horas.

Medido em 03/09/2026: ~900 a 1.300 candidaturas mudam por dia, de 20.765. A
mudanca real e' de ~5%; a aparente era de 100%.
"""

from __future__ import annotations

import re

from scripts.render_site import _pagina
from tests.conftest import contem_frase, texto_visivel

GLOBAL = "03/09/2026 17:41"


def _rodape(html: str) -> str:
    m = re.search(r"<footer.*?</footer>", html, re.S)
    return texto_visivel(m.group(0)) if m else ""


def test_pagina_comum_mostra_quando_o_site_rodou():
    """Home, listagem e metodologia falam do site, e a data do site e' a certa."""
    html = _pagina("t", "d", "<p>x</p>", GLOBAL, "https://x/")
    assert contem_frase(_rodape(html), f"extraído em {GLOBAL} UTC")


def test_ficha_mostra_quando_o_dado_mudou():
    html = _pagina("t", "d", "<p>x</p>", GLOBAL, "https://x/",
                   fonte_data="dados desta candidatura como o TSE publicava em 27/08/2026")
    rodape = _rodape(html)
    assert contem_frase(rodape, "o TSE publicava em 27/08/2026")
    assert GLOBAL not in rodape, (
        "com o carimbo global na ficha, toda pagina muda todo dia e o envio "
        "incremental nao economiza nada")


def test_a_fonte_continua_declarada_nos_dois_casos():
    """Constituicao §0.3: fonte e data em toda visualizacao."""
    for fd in (None, "dados desta candidatura como o TSE publicava em 27/08/2026"):
        rodape = _rodape(_pagina("t", "d", "<p>x</p>", GLOBAL, "https://x/", fonte_data=fd))
        assert "Fonte:" in rodape
        assert re.search(r"\d{2}/\d{2}/\d{4}", rodape), "sem data nenhuma no rodape"


def test_sem_data_propria_a_ficha_cai_na_data_do_site():
    """Snapshot indisponivel nao pode deixar a ficha sem data — so' menos precisa."""
    html = _pagina("t", "d", "<p>x</p>", GLOBAL, "https://x/", fonte_data=None)
    assert contem_frase(_rodape(html), f"extraído em {GLOBAL}")
