"""Acessibilidade da tela (WCAG 2.2 AA).

O site tem uma folha de estilo so' e um esqueleto de pagina so'. As duas coisas
que este arquivo protege sao as que quebram em silencio: contraste, que ninguem
ve' quebrar porque a cor continua bonita, e marcacao semantica, que so' falha
para quem nao esta' olhando a tela.

O tema claro e o escuro NAO sao dois sites. O escuro entra por
`prefers-color-scheme`, e um celular no claro ao lado de um monitor no escuro
mostram a mesma pagina com paletas diferentes. As duas sao medidas aqui.
"""

from __future__ import annotations

import re
from pathlib import Path

from scripts.render_site import _acessivel

_BRUTO = (Path(__file__).resolve().parents[1] / "scripts" / "dossie.css").read_text(
    encoding="utf-8")
# Sem os comentarios: eles CITAM as regras removidas ("tinha `outline:none`"), e
# um teste que procura texto acharia a explicacao em vez da regra.
CSS = re.sub(r"/\*.*?\*/", "", _BRUTO, flags=re.S)


# ── contraste ─────────────────────────────────────────────────────────────

def _tokens(bloco: str) -> dict[str, str]:
    return dict(re.findall(r"--([\w-]+)\s*:\s*(#[0-9A-Fa-f]{3,6})", bloco))


def _paletas() -> dict[str, dict[str, str]]:
    corte = CSS.index("@media(prefers-color-scheme:dark)")
    claro = _tokens(CSS[:corte])
    escuro = dict(claro)
    escuro.update(_tokens(CSS[corte:CSS.index("*{box-sizing")]))
    return {"claro": claro, "escuro": escuro}


def _lum(h: str) -> float:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    v = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    v = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in v]
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]


def _razao(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


# (frente, fundo, minimo). 4.5 e' texto normal (1.4.3); 3.0 e' componente de
# interface e texto grande (1.4.11).
PARES = [
    ("ink", "surface", 4.5), ("ink", "ground", 4.5),
    ("ink-2", "surface", 4.5), ("ink-2", "ground", 4.5),
    ("ink-3", "surface", 4.5), ("ink-3", "ground", 4.5),
    ("ink-3", "surface-2", 4.5),
    ("accent", "surface", 4.5), ("accent", "ground", 4.5),
    ("accent-forte", "accent-soft", 4.5),
    ("ausente", "ausente-soft", 4.5), ("ok", "ok-soft", 4.5),
    ("nao", "nao-soft", 4.5), ("na", "na-soft", 4.5),
    ("rule-campo", "surface", 3.0),
    ("foco", "surface", 3.0), ("foco", "ground", 3.0),
]


def test_todo_par_de_cor_passa_na_wcag_nos_dois_temas():
    """Tres pares reprovavam no tema CLARO — nav ativo 3,97, marca ausente 4,29
    e marca ok 4,43 — e nenhum reprovava no escuro. Quem projeta no escuro nao
    ve' o problema do claro, e vice-versa: por isso os dois sao medidos."""
    falhas = []
    for tema, cores in _paletas().items():
        for fg, bg, minimo in PARES:
            r = _razao(cores[fg], cores[bg])
            if r < minimo:
                falhas.append(f"{tema}: {fg} sobre {bg} = {r:.2f}:1 (min {minimo})")
    assert not falhas, "\n".join(falhas)


def test_os_dois_temas_definem_os_mesmos_tokens():
    """Token que existe so' num tema vira cor herdada do outro — e o resultado e'
    texto invisivel numa das duas paletas, que ninguem ve' porque ninguem olha as
    duas no mesmo dia."""
    claro, escuro = _paletas()["claro"], _paletas()["escuro"]
    so_no_claro = {k for k in claro if k not in escuro}
    assert not so_no_claro, so_no_claro


# ── foco visivel ──────────────────────────────────────────────────────────

def test_o_foco_do_teclado_e_visivel():
    """Sem isto, quem navega por teclado nao sabe onde esta'. A versao anterior
    tinha `outline:none` no unico controle interativo da pagina (WCAG 2.4.7)."""
    assert ":focus-visible{outline:" in CSS.replace(" ", "")
    assert "outline:none" not in CSS.replace(" ", "")


def test_ha_atalho_para_pular_a_navegacao():
    """Dez links repetidos em toda pagina. Sem atalho, chegar ao conteudo por
    teclado custa dez tabulacoes em CADA ficha (WCAG 2.4.1)."""
    assert ".pular{" in CSS.replace(" ", "")
    assert ".pular:focus{top:" in CSS.replace(" ", "")


def test_nenhum_texto_abaixo_de_12px():
    """Nao ha' minimo na norma, mas 10px em versalete espacado e' o tamanho em
    que a leitura para de ser leitura. O site tinha sete lugares assim."""
    tamanhos = [float(x) for x in re.findall(r"font-size:([\d.]+)px", CSS)]
    assert tamanhos and min(tamanhos) >= 12, sorted(tamanhos)[:5]


def test_o_alvo_de_ajuda_tem_24px():
    """WCAG 2.5.8: alvo de ponteiro tem no minimo 24x24 CSS px. Tinha 15x15."""
    bloco = CSS[CSS.index(".ajuda{"):CSS.index(".ajuda:hover")]
    assert "width:24px" in bloco.replace(" ", "")
    assert "height:24px" in bloco.replace(" ", "")


def test_o_modo_de_alto_contraste_do_windows_e_tratado():
    """O sistema descarta background e border-color. O que era desenhado SO' com
    fundo — o item de navegacao ativo, as marcas de dado — some."""
    assert "forced-colors:active" in CSS.replace(" ", "")


# ── marcacao ──────────────────────────────────────────────────────────────

def test_todo_cabecalho_de_tabela_declara_a_coluna():
    """Sem `scope`, o leitor de tela nao diz a que coluna pertence a celula 7 da
    linha 12 — e a tabela de bens tem oito colunas (WCAG 1.3.1)."""
    saida = _acessivel('<table><thead><tr><th>Ano</th><th class="num">Valor</th>'
                       '</tr></thead></table>')
    assert saida.count('scope="col"') == 2


def test_o_thead_nao_e_confundido_com_th():
    """`<thead>` comeca com `<th`. Um casamento ingenuo produz `<th scope="col"ead>`
    e destroi a tabela inteira."""
    assert "<thead>" in _acessivel("<thead>")
    assert "ead" not in _acessivel("<thead>").replace("<thead>", "")


def test_scope_ja_existente_nao_e_duplicado():
    assert _acessivel('<th scope="row">x</th>') == '<th scope="row">x</th>'


def test_a_area_que_rola_recebe_foco():
    """`.rolagem` tem `overflow:auto`. O Firefox da' foco a uma area assim; o
    Chrome nao — e sem foco as linhas de baixo da tabela ficam inalcancaveis por
    teclado (WCAG 2.1.1)."""
    for html in ('<div class="rolagem">', "<div class='rolagem'>",
                 '<div class="rolagem" style="max-height:none">'):
        assert 'tabindex="0"' in _acessivel(html), html


def test_a_area_que_rola_tem_altura_relativa_a_janela():
    """340px fixos e' um terco da tela num monitor de 1080 e mais que a tela
    inteira num celular deitado."""
    bloco = CSS[CSS.index(".rolagem{"):CSS.index("table{")]
    assert "vh" in bloco
