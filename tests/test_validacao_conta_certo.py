"""A contagem do relatorio de validacao tem de bater com o catalogo.

A primeira versao de docs/VALIDACAO.md dizia "14 de 18 conferem" quando a tabela
tinha 13 linhas, e a atualizacao seguinte escreveu 15. Numero que nao fecha, num
documento cujo proposito inteiro e' ser confiavel, custa mais que o erro que ele
descreve — e ninguem confere soma escrita a mao.
"""

from __future__ import annotations

import re
from pathlib import Path

from ingest.common.indicadores import carregar_catalogo

DOC = Path(__file__).resolve().parents[1] / "docs" / "VALIDACAO.md"


def _texto() -> str:
    return DOC.read_text(encoding="utf-8")


def test_o_documento_existe():
    assert DOC.exists(), "a validacao contra fonte oficial precisa ficar registrada"


def test_a_contagem_bate_com_as_linhas_da_tabela():
    texto = _texto()
    secao = texto[texto.index("## Confere"):texto.index("## Série oficial")]
    codigos = set(carregar_catalogo())
    listados = {c for c in codigos if re.search(rf"^\|\s*{c}\s*\|", secao, re.M)}

    declarado = re.search(r"Confere com a fonte oficial \| \*\*(\d+)\*\* de (\d+)", texto)
    assert declarado, "o resumo precisa declarar quantos conferem"
    n, total = int(declarado.group(1)), int(declarado.group(2))

    assert n == len(listados), (
        f"o resumo diz {n} mas a tabela lista {len(listados)}: "
        f"{sorted(listados)}")
    assert total == len(codigos), (
        f"o resumo diz {total} indicadores no total, o catalogo tem {len(codigos)}")


def test_o_que_nao_confere_esta_declarado():
    """Todo indicador fora da tabela precisa aparecer nomeado em algum lugar."""
    texto = _texto()
    secao = texto[texto.index("## Confere"):texto.index("## Série oficial")]
    codigos = set(carregar_catalogo())
    listados = {c for c in codigos if re.search(rf"^\|\s*{c}\s*\|", secao, re.M)}
    resto = texto[texto.index("## Série oficial"):]

    for cod in sorted(codigos - listados):
        assert cod in resto, (
            f"{cod} nao confere e nao esta' explicado — silencio sobre o que nao "
            "foi conferido e' pior que a lacuna")
