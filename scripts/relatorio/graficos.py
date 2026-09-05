"""Graficos em SVG, escritos a mao — sem dependencia nova.

Vetorial dentro do PDF: escala sem borrar, e o arquivo fica pequeno.

REGRAS DE COR, herdadas da Constituicao do projeto:
  - cor de partido NUNCA e' usada;
  - a paleta e' sequencial e neutra, para nao sugerir juizo;
  - toda barra tem o numero escrito ao lado, porque cor e comprimento sozinhos
    nao informam quem tem daltonismo ou le' impresso em preto e branco.
"""

from html import escape

TINTA = "#0B1F3B"
TINTA2 = "#43505F"
TINTA3 = "#5A6577"
REGUA = "#CDD9EA"
ACENTO = "#0E7D8B"
ACENTO2 = "#8FCBD4"
ALERTA = "#B45309"
OK = "#1F7A4D"
NAO = "#A32B2B"


def _n(v, casas=0):
    try:
        s = f"{float(v):,.{casas}f}"
    except (TypeError, ValueError):
        return str(v)
    return s.replace(",", " ").replace(".", ",").replace(" ", ".")


def barras(dados, *, largura=680, alt_barra=22, gap=7, cor=ACENTO,
           rotulo=lambda v: _n(v), titulo=None, max_valor=None, cores=None):
    """Barras horizontais. `dados` = [(rotulo, valor), ...]."""
    if not dados:
        return ""
    esq = 190
    dir_ = 92
    corpo = largura - esq - dir_
    topo = 26 if titulo else 6
    altura = topo + len(dados) * (alt_barra + gap) + 6
    maximo = max_valor or max((v for _, v in dados), default=1) or 1

    p = [f'<svg viewBox="0 0 {largura} {altura}" width="100%" '
         f'style="max-width:{largura}px" role="img">']
    if titulo:
        p.append(f'<text x="0" y="15" font-size="12.5" font-weight="700" '
                 f'fill="{TINTA}">{escape(titulo)}</text>')
    for i, (rot, val) in enumerate(dados):
        y = topo + i * (alt_barra + gap)
        w = max(1.5, corpo * (float(val) / maximo))
        c = (cores or {}).get(rot, cor)
        p.append(f'<text x="{esq - 8}" y="{y + alt_barra * 0.72}" font-size="11" '
                 f'text-anchor="end" fill="{TINTA2}">{escape(str(rot))}</text>')
        p.append(f'<rect x="{esq}" y="{y}" width="{w:.1f}" height="{alt_barra}" '
                 f'fill="{c}" rx="1.5"/>')
        p.append(f'<text x="{esq + w + 7:.1f}" y="{y + alt_barra * 0.72}" '
                 f'font-size="11" fill="{TINTA3}">{escape(rotulo(val))}</text>')
    p.append("</svg>")
    return "".join(p)


def barras_empilhadas(dados, series, cores, *, largura=680, alt_barra=22, gap=7,
                      titulo=None, rotulo=lambda v: _n(v)):
    """`dados` = [(rotulo, {serie: valor})]. Mostra o total ao lado."""
    if not dados:
        return ""
    esq, dir_ = 190, 92
    corpo = largura - esq - dir_
    topo = 26 if titulo else 6
    altura = topo + len(dados) * (alt_barra + gap) + 6
    maximo = max(sum(d.values()) for _, d in dados) or 1

    p = [f'<svg viewBox="0 0 {largura} {altura}" width="100%" '
         f'style="max-width:{largura}px" role="img">']
    if titulo:
        p.append(f'<text x="0" y="15" font-size="12.5" font-weight="700" '
                 f'fill="{TINTA}">{escape(titulo)}</text>')
    for i, (rot, valores) in enumerate(dados):
        y = topo + i * (alt_barra + gap)
        x = esq
        total = sum(valores.values())
        for s in series:
            v = valores.get(s, 0)
            if not v:
                continue
            w = corpo * (float(v) / maximo)
            p.append(f'<rect x="{x:.1f}" y="{y}" width="{max(0.8, w):.1f}" '
                     f'height="{alt_barra}" fill="{cores[s]}"/>')
            x += w
        p.append(f'<text x="{esq - 8}" y="{y + alt_barra * 0.72}" font-size="11" '
                 f'text-anchor="end" fill="{TINTA2}">{escape(str(rot))}</text>')
        p.append(f'<text x="{x + 7:.1f}" y="{y + alt_barra * 0.72}" font-size="11" '
                 f'fill="{TINTA3}">{escape(rotulo(total))}</text>')
    p.append("</svg>")
    return "".join(p)


def legenda(series, cores):
    itens = "".join(
        f'<span class="leg"><i style="background:{cores[s]}"></i>{escape(s)}</span>'
        for s in series)
    return f'<div class="legenda">{itens}</div>'


def linhas(series, rotulos_x, cores, *, largura=680, altura=210, titulo=None,
           rotulo_y=lambda v: _n(v), area=False):
    """`series` = {nome: [valores]}, alinhado com `rotulos_x`."""
    esq, dir_, topo, base = 62, 14, 30 if titulo else 12, 30
    cw = largura - esq - dir_
    ch = altura - topo - base
    todos = [v for vs in series.values() for v in vs]
    maximo = max(todos) or 1
    n = len(rotulos_x)

    def px(i):
        return esq + (cw * i / max(1, n - 1))

    def py(v):
        return topo + ch - (ch * float(v) / maximo)

    p = [f'<svg viewBox="0 0 {largura} {altura}" width="100%" '
         f'style="max-width:{largura}px" role="img">']
    if titulo:
        p.append(f'<text x="0" y="15" font-size="12.5" font-weight="700" '
                 f'fill="{TINTA}">{escape(titulo)}</text>')
    # grade
    for f in (0, 0.25, 0.5, 0.75, 1):
        y = topo + ch - ch * f
        p.append(f'<line x1="{esq}" y1="{y:.1f}" x2="{largura - dir_}" y2="{y:.1f}" '
                 f'stroke="{REGUA}" stroke-width="0.7"/>')
        p.append(f'<text x="{esq - 6}" y="{y + 3.5:.1f}" font-size="9.5" '
                 f'text-anchor="end" fill="{TINTA3}">{escape(rotulo_y(maximo * f))}</text>')
    for i, rot in enumerate(rotulos_x):
        p.append(f'<text x="{px(i):.1f}" y="{altura - 10}" font-size="9.5" '
                 f'text-anchor="middle" fill="{TINTA3}">{escape(str(rot))}</text>')
    for nome, vs in series.items():
        pontos = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(vs))
        if area:
            p.append(f'<polygon points="{esq},{topo + ch} {pontos} '
                     f'{px(n - 1):.1f},{topo + ch}" fill="{cores[nome]}" opacity="0.13"/>')
        p.append(f'<polyline points="{pontos}" fill="none" stroke="{cores[nome]}" '
                 f'stroke-width="2.2" stroke-linejoin="round"/>')
        for i, v in enumerate(vs):
            p.append(f'<circle cx="{px(i):.1f}" cy="{py(v):.1f}" r="2.8" '
                     f'fill="{cores[nome]}"/>')
    p.append("</svg>")
    return "".join(p)


def pizza_barra(dados, cores, *, largura=680, altura=34, rotulo=lambda v: _n(v)):
    """Uma barra unica dividida — melhor que pizza para comparar fatias."""
    total = sum(v for _, v in dados) or 1
    p = [f'<svg viewBox="0 0 {largura} {altura}" width="100%" '
         f'style="max-width:{largura}px" role="img">']
    x = 0
    for rot, v in dados:
        w = largura * (float(v) / total)
        p.append(f'<rect x="{x:.1f}" y="0" width="{max(0.8, w):.1f}" height="20" '
                 f'fill="{cores.get(rot, ACENTO)}"/>')
        if w > 44:
            p.append(f'<text x="{x + w / 2:.1f}" y="14" font-size="10.5" '
                     f'text-anchor="middle" fill="#fff" font-weight="600">'
                     f'{escape(f"{100 * v / total:.0f}%")}</text>')
        x += w
    p.append("</svg>")
    return "".join(p)


def barras_duplas(dados, rot_a, rot_b, *, largura=680, alt=15, gap=9,
                  cor_a=ACENTO, cor_b=ALERTA, titulo=None, rotulo=lambda v: _n(v),
                  max_valor=None):
    """Duas barras por categoria. `dados` = [(rotulo, valor_a, valor_b), ...].

    Existe para mostrar MEDIA e MEDIANA lado a lado. Esconder uma das duas e'
    uma escolha de quem escreve, nao da estatistica — e quando elas discordam,
    a discordancia E' a informacao.
    """
    if not dados:
        return ""
    esq, dir_ = 150, 118
    corpo = largura - esq - dir_
    topo = 26 if titulo else 6
    par = alt * 2 + 3
    altura = topo + len(dados) * (par + gap) + 6
    maximo = max_valor or max(max(a, b) for _, a, b in dados) or 1

    p = [f'<svg viewBox="0 0 {largura} {altura}" width="100%" '
         f'style="max-width:{largura}px" role="img">']
    if titulo:
        p.append(f'<text x="0" y="15" font-size="12.5" font-weight="700" '
                 f'fill="{TINTA}">{escape(titulo)}</text>')
    for i, (rot, va, vb) in enumerate(dados):
        y = topo + i * (par + gap)
        p.append(f'<text x="{esq - 8}" y="{y + par * 0.62}" font-size="11" '
                 f'text-anchor="end" fill="{TINTA2}">{escape(str(rot))}</text>')
        for j, (v, c) in enumerate(((va, cor_a), (vb, cor_b))):
            yy = y + j * (alt + 3)
            w = max(1.2, corpo * (float(v) / maximo))
            p.append(f'<rect x="{esq}" y="{yy}" width="{w:.1f}" height="{alt}" '
                     f'fill="{c}" rx="1.5"/>')
            p.append(f'<text x="{esq + w + 6:.1f}" y="{yy + alt * 0.78}" '
                     f'font-size="9.6" fill="{TINTA3}">{escape(rotulo(v))}</text>')
    p.append("</svg>")
    return "".join(p)
