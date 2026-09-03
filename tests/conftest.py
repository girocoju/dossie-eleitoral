"""Ferramentas compartilhadas dos testes.

`texto_visivel` existe por causa de um erro repetido em 03/09/2026. Ao conferir a
pagina de metodologia publicada, procurei a frase "A conferência que achou um
erro grande" no HTML e nao achei — o gerador quebra a linha entre "um" e "erro",
e a busca literal falha. Concluí tres vezes que uma correcao NAO estava no ar
quando ela estava, e uma dessas conclusoes quase virou um "conserto" do que ja'
funcionava.

O jeito certo nao pode depender de eu lembrar: quem compara texto renderizado usa
esta funcao.
"""

from __future__ import annotations

import re

_TAG = re.compile(r"<[^>]+>")


def texto_visivel(html: str) -> str:
    """O que a pessoa le': sem marcacao e com espaco normalizado.

    Quebra de linha no fonte NAO e' quebra de frase para quem le'. Comparar
    contra o HTML cru transforma formatacao em falso negativo.
    """
    return " ".join(_TAG.sub(" ", html).split())


def contem_frase(html: str, frase: str) -> bool:
    """A frase aparece na pagina, independentemente de onde a linha quebrou."""
    return " ".join(frase.split()) in texto_visivel(html)
