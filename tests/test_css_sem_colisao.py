"""Duas regras para a mesma classe, em contextos diferentes, quebram a tela.

Aconteceu em 30/08/2026. `.retrato` era a foto da FICHA (`width:100%`, coluna de
212px). Ao acrescentar a foto da LISTAGEM reusei o mesmo nome, com `width:38px`.
Como a regra nova vem depois no arquivo, ela venceu — e a coluna esquerda de
TODAS as fichas foi esmagada para 44px, com o texto quebrando linha a linha.

Nao foi erro de CSS invalido: o arquivo estava sintaticamente perfeito. Foi
colisao de nome, que nenhuma ferramenta de lint pega e nenhum teste de dado
alcanca — so' se ve' abrindo a pagina, e quem viu foi o usuario.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

CSS = Path(__file__).resolve().parents[1] / "scripts" / "dossie.css"

# Classes que PODEM aparecer em mais de um bloco por serem, de fato, variacoes do
# mesmo componente. Cada entrada aqui e' uma excecao consciente, nao um descuido.
DUPLICATAS_ACEITAS: set[str] = set()


def _blocos(css: str) -> list[tuple[str, str]]:
    """(contexto, seletores) de cada bloco.

    O CONTEXTO E' A MEDIA QUERY, e ignora-lo produzia falso positivo: `.ficha`
    aparece duas vezes — uma no fluxo normal, com duas colunas, e outra dentro de
    `@media(max-width:760px)` com uma so'. Isso e' sobrescrita RESPONSIVA, o uso
    correto do CSS, e nao a colisao que este arquivo caca.

    A colisao de verdade e' o mesmo seletor no MESMO contexto.
    """
    sem_comentario = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    saida: list[tuple[str, str]] = []
    resto = sem_comentario
    # Primeiro as media queries, com o conteudo delas marcado pelo contexto.
    for m in re.finditer(r"(@media[^{]*)\{((?:[^{}]|\{[^{}]*\})*)\}", sem_comentario):
        contexto = " ".join(m.group(1).split())
        for sel in re.findall(r"([^{}]+)\{[^{}]*\}", m.group(2)):
            saida.append((contexto, sel))
        resto = resto.replace(m.group(0), "")
    for sel in re.findall(r"([^{}]+)\{[^{}]*\}", resto):
        saida.append(("", sel))
    return saida


def _seletores(css: str) -> list[str]:
    """Cada seletor individual, normalizado.

    Um bloco pode declarar varios seletores separados por virgula, e cada um e'
    uma regra propria. `.bloco h2` e `.bloco p` sao seletores DIFERENTES — usar a
    mesma classe como ancestral e' o uso normal do CSS e nao colide.

    O que colide e' o MESMO seletor abrindo dois blocos: foi `.retrato img`
    declarado na linha 33 e de novo na 117, com larguras incompativeis.
    """
    saida = []
    for contexto, bloco in _blocos(css):
        for sel in bloco.split(","):
            limpo = " ".join(sel.split())
            if limpo and "." in limpo:
                saida.append(f"{contexto} {limpo}".strip())
    return saida


def test_o_css_existe_e_tem_regras():
    assert CSS.exists(), CSS
    assert len(_seletores(CSS.read_text(encoding="utf-8"))) > 20


def test_nenhuma_classe_e_redefinida_em_bloco_separado():
    """Um seletor, um bloco.

    Redefinir noutro ponto do arquivo e' o padrao que esmagou a ficha: a segunda
    regra vence pela ordem, e quem escreveu a primeira nao fica sabendo.

    Sobrescrita dentro de `@media` NAO acusa: o contexto faz parte da chave, e
    redefinir `.ficha` para uma coluna em tela estreita e' o uso correto do CSS.
    Acusa so' o mesmo seletor no mesmo contexto — que foi o caso de `.retrato`.
    """
    css = CSS.read_text(encoding="utf-8")
    contagem = Counter(_seletores(css))
    repetidas = {c: n for c, n in contagem.items()
                 if n > 1 and c not in DUPLICATAS_ACEITAS}
    assert not repetidas, (
        "classes definidas em mais de um bloco — a ultima vence e quebra a "
        f"primeira: {sorted(repetidas)}. Se for deliberado, nomeie a variacao "
        "(`.foto-lista` em vez de reusar `.retrato`) ou registre em "
        "DUPLICATAS_ACEITAS com o motivo.")


@pytest.mark.parametrize(("classe", "onde"), [
    ("retrato", "foto da ficha, coluna de 212px"),
    ("foto-lista", "foto da listagem de proporcionais, 38px"),
])
def test_as_duas_fotos_tem_nomes_distintos(classe, onde):
    """Trava o caso concreto, alem da regra geral."""
    css = CSS.read_text(encoding="utf-8")
    assert re.search(rf"\.{re.escape(classe)}\b", css), f"{classe} sumiu ({onde})"
