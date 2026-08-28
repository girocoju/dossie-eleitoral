"""Renderizacao do Dossie Eleitoral — HTML e JSON estaticos (ADR-018).

Separado de `gerar_site.py` de proposito: la' mora a consulta ao BigQuery, aqui
mora a apresentacao. Da' para revisar o texto que vai ao publico sem reler SQL.

REGRAS DE TELA QUE ESTE MODULO IMPLEMENTA (Constituicao 0)

* Nenhuma nota, barra de pontuacao ou ranking. A ficha e' registro, nao avaliacao.
* Cor de partido nunca. A paleta e' a da DDI: navy, ciano e neutros.
* Toda pagina carrega fonte e data de extracao no rodape.
* Plano de governo tem TRES estados: apresentou, nao apresentou, e nao e' exigido
  para o cargo. Juntar os dois ultimos acusaria 318 senadores de uma omissao que a
  lei nao preve.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.gerar_site import BASE_URL, CARGOS, PROPORCIONAIS, Candidato, brl, e

FONTE = "TSE — Divulgação de Candidaturas"

CSS = (Path(__file__).parent / "dossie.css").read_text(encoding="utf-8")



def _pagina(titulo: str, descricao: str, corpo: str, quando: str,
            canonical: str, ativo: str = "") -> str:
    nav = "".join(
        f'<a href="{BASE_URL}/{s}/" class="{"on" if s == ativo else ""}">{n}</a>'
        for s, n, _ in CARGOS.values()
    ) + "".join(
        f'<a href="{BASE_URL}/{s}/" class="{"on" if s == ativo else ""}">{n}</a>'
        for s, n in PROPORCIONAIS.values()
    )
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(titulo)} — Dossiê Eleitoral</title>
<meta name="description" content="{e(descricao)}">
<link rel="canonical" href="{e(canonical)}">
<meta name="robots" content="index,follow">
<meta property="og:type" content="website">
<meta property="og:title" content="{e(titulo)} — Dossiê Eleitoral">
<meta property="og:description" content="{e(descricao)}">
<meta property="og:url" content="{e(canonical)}">
<meta property="og:site_name" content="Data Duba Intelligence">
<style>{CSS}</style>
</head>
<body>
<header class="topo"><div class="wrap">
  <a class="marca" href="{BASE_URL}/">Dossiê Eleitoral<span>Data Duba Intelligence</span></a>
  <nav class="cargos">{nav}</nav>
</div></header>
<main class="wrap">
{corpo}
<footer class="rodape">
  <span>Fonte: {FONTE} · extraído em {e(quando)} UTC</span>
  <span>Dados declarados pelo candidato ao TSE. Este site registra o que foi
    declarado — não avalia, não classifica e não ordena candidatos.</span>
  <span><a href="https://datadubaintel.com/">Data Duba Intelligence</a>
    · <a href="{BASE_URL}/metodologia/">Metodologia e fontes</a></span>
</footer>
</main>
</body>
</html>
"""


def _retrato(c: Candidato) -> str:
    if c.url_foto:
        return (f'<img src="{e(c.url_foto)}" alt="Foto de urna de {e(c.nome_urna)}" '
                f'loading="lazy" width="212" height="283">')
    return '<div class="semfoto"></div>'


def _ficha(c: Candidato, quando: str) -> str:
    partes = [f"""
<a href="{BASE_URL}/{CARGOS[c.cod_cargo][0]}/" style="font-size:13.5px">← {e(c.cargo_nome)}</a>
<div class="ficha">
  <div class="retrato">
    {_retrato(c)}
    <div class="legenda">foto de urna — TSE</div>
    <div class="chips">
      <span class="chip">{e(c.cargo_nome)}</span>
      <span class="chip">{e(c.sg_uf)}</span>
      {f'<span class="chip">{e(c.sigla_partido)}</span>' if c.sigla_partido else ''}
      {f'<span class="chip">{e(c.situacao)}</span>' if c.situacao else ''}
    </div>
  </div>
  <div>
    <h1>{e(c.nome_urna)}</h1>
    <p class="sub">{e(c.nome_completo or '')}</p>

    <section class="bloco"><h2>Perfil declarado ao TSE</h2>
    <dl class="campos">
      <div><dt>Idade na posse</dt><dd>{c.idade if c.idade else '—'}</dd></div>
      <div><dt>Gênero</dt><dd>{e(c.genero) or '—'}</dd></div>
      <div><dt>Cor/raça</dt><dd>{e(c.cor_raca) or '—'}</dd></div>
      <div><dt>Grau de instrução</dt><dd>{e(c.grau_instrucao) or '—'}</dd></div>
      <div><dt>Ocupação</dt><dd>{e(c.ocupacao) or '—'}</dd></div>
      <div><dt>Estado de nascimento</dt><dd>{e(c.uf_nascimento) or '—'}</dd></div>
    </dl></section>
"""]

    # trajetoria
    if c.trajetoria:
        def _linha(t: dict) -> str:
            votos = f"{t['votos']:,}".replace(",", ".") if t["votos"] else "—"
            res = "Eleito" if t["eleito"] else "Não eleito"
            return (f"<tr><td class='num'>{t['ano']}</td><td>{e(t['cargo'])}</td>"
                    f"<td>{e(t['uf'])}</td><td>{e(t['partido']) or '—'}</td>"
                    f"<td>{res}</td><td class='num'>{votos}</td></tr>")

        linhas = "".join(_linha(t) for t in c.trajetoria)
        partes.append(f"""<section class="bloco">
      <h2>Trajetória eleitoral — {len(c.trajetoria)} candidaturas anteriores</h2>
      <div class="rolagem"><table>
        <thead><tr><th>Ano</th><th>Cargo</th><th>UF</th><th>Partido</th><th>Resultado</th><th>Votos</th></tr></thead>
        <tbody>{linhas}</tbody></table></div>
      <p style="font-size:12.5px;color:var(--ink-3);margin:8px 0 0">
        São <b>candidaturas</b>, não mandatos: disputas perdidas também
        aparecem. Série desde 1998.</p>
    </section>""")
    else:
        partes.append("""<section class="bloco"><h2>Trajetória eleitoral</h2>
      <span class="marca-dado m-ausente">nenhuma candidatura anterior
      desde 1998</span></section>""")

    # bens e plano
    if c.proposta_obrigatoria and c.tem_proposta and c.url_proposta:
        plano = (f'<a href="{e(c.url_proposta)}" rel="nofollow noopener">'
                 f'Documento oficial no TSE ↗</a>')
    elif c.proposta_obrigatoria:
        plano = ('<span class="marca-dado m-ausente">exigido para este cargo, não consta</span>')
    else:
        plano = ('<span class="marca-dado m-na">não é exigido para este cargo</span>'
                 '<p style="font-size:12.5px;color:var(--ink-3);margin:8px 0 0">'
                 'A Lei 9.504/97 (art. 11, §1º, IX) exige proposta de Prefeito, Governador e '
                 'Presidente. Senador é cargo majoritário, mas não consta da lista.</p>')

    bens = (f"<dl class='campos'><div><dt>Total declarado</dt><dd>{brl(c.bens_total)}</dd></div>"
            f"<div><dt>Itens</dt><dd>{c.bens_n or 0}</dd></div></dl>"
            if c.bens_total is not None else
            "<span class='marca-dado m-ausente'>não declarou bens</span>")

    partes.append(f"""
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:22px" class="par">
      <section class="bloco"><h2>Bens declarados</h2>{bens}</section>
      <section class="bloco"><h2>Plano de governo</h2>{plano}</section>
    </div>""")

    # mudancas
    if c.mudancas:
        eventos = "".join(
            f"<div class='evento'><time>{m['data'].strftime('%d/%m')}</time>"
            f"<span>{m['texto']}</span></div>"
            for m in c.mudancas
        )
        partes.append(f"""<section class="bloco">
      <h2>Alterações registradas</h2>{eventos}
      <p style="font-size:12.5px;color:var(--ink-3);margin:8px 0 0">
        Capturado diariamente. A data é a da <b>captura</b>, não a do ato do TSE. O TSE publica
        apenas o estado atual — esta série não pode ser refeita depois de 04/10/2026.</p>
    </section>""")

    partes.append("</div></div>")
    desc = (f"{c.nome_urna}, candidatura a {c.cargo_nome} por {c.sg_uf} em 2026. "
            f"Perfil declarado ao TSE, trajetória eleitoral e plano de governo.")
    return _pagina(f"{c.nome_urna} — {c.cargo_nome} {c.sg_uf}", desc,
                   "".join(partes), quando, c.url, CARGOS[c.cod_cargo][0])


def _cartao(c: Candidato) -> str:
    foto = (f'<img src="{e(c.url_foto)}" alt="" loading="lazy" width="52" height="69">'
            if c.url_foto else '<div class="semfoto"></div>')
    return (f'<a class="cartao" href="{BASE_URL}/{c.caminho}/">{foto}<span>'
            f'<b>{e(c.nome_urna)}</b><small>{e(c.sg_uf)} · {e(c.sigla_partido) or "—"}</small>'
            f'<small>{e(c.situacao) or ""}</small></span></a>')


def _listagem_majoritaria(chave: str, nome: str, cands: list[Candidato], quando: str) -> str:
    corpo = (f"<h1>{e(nome)}</h1><p class='sub'>{len(cands)} candidaturas registradas em 2026. "
             f"Cada uma tem ficha própria, com perfil declarado, trajetória eleitoral e plano de "
             f"governo quando a lei o exige.</p>"
             f"<div class='grade'>{''.join(_cartao(c) for c in cands)}</div>")
    desc = f"{len(cands)} candidaturas a {nome} em 2026, com perfil declarado ao TSE."
    return _pagina(nome, desc, corpo, quando, f"{BASE_URL}/{chave}/", chave)


def _listagem_proporcional(chave: str, nome: str, por_uf: dict[str, list[dict]],
                           quando: str) -> str:
    """Listagem que baixa UM estado por vez.

    O arquivo unico de deputado estadual tinha 3,2 MB. Num celular em rede fraca
    isso e' meio minuto de espera antes de a primeira linha aparecer. Quebrado por
    UF, o maior estado nao passa de algumas centenas de kB — e ninguem baixa 26
    estados para consultar um.
    """
    total = sum(len(v) for v in por_uf.values())
    ufs = sorted(por_uf)
    opcoes = "".join(
        f'<option value="{u}">{u} ({len(por_uf[u])})</option>' for u in ufs
    )
    desc = f"{total} candidaturas a {nome} em 2026, por estado."
    corpo = f"""<h1>{e(nome)}</h1>
<p class="sub">{total:,} candidaturas registradas em 2026.
Escolha o estado para começar.</p>
<p class="aviso">Cargos proporcionais não têm ficha própria: o TSE exige plano de governo apenas
de Prefeito, Governador e Presidente, e o perfil declarado cabe na própria listagem. Publicar
{total:,} páginas quase idênticas seria conteúdo raso, e prejudicaria a indexação
do site inteiro.</p>
<div class="filtros">
  <select id="uf"><option value="">Escolha o estado…</option>{opcoes}</select>
  <select id="partido" disabled><option value="">Todos os partidos</option></select>
  <input id="busca" type="search" placeholder="Buscar por nome" autocomplete="off" disabled>
</div>
<p class="contagem" id="contagem">nenhum estado selecionado</p>
<div class="rolagem" style="max-height:none"><table>
  <thead><tr><th>Nome de urna</th><th>Partido</th><th>Situação</th>
  <th>Idade</th><th>Instrução</th><th>Ocupação</th></tr></thead>
  <tbody id="linhas"></tbody></table></div>
<script>
const BASE = "{BASE_URL}/dados/{chave}";
let dados = [];
const $ = (id) => document.getElementById(id);
function desenhar() {{
  const pt = $("partido").value, q = $("busca").value.trim().toLowerCase();
  const vis = dados.filter(d => (!pt || d.partido === pt) &&
    (!q || (d.nome || "").toLowerCase().includes(q)));
  $("contagem").textContent = vis.length.toLocaleString("pt-BR") + " de " +
    dados.length.toLocaleString("pt-BR") + " candidaturas neste estado";
  $("linhas").innerHTML = vis.map(d => `<tr>
    <td>${{d.nome ?? ""}}</td><td>${{d.partido ?? ""}}</td><td>${{d.situacao ?? ""}}</td>
    <td class="num">${{d.idade ?? "—"}}</td><td>${{d.instrucao ?? ""}}</td>
    <td>${{d.ocupacao ?? ""}}</td></tr>`).join("");
}}
$("uf").addEventListener("change", () => {{
  const uf = $("uf").value;
  if (!uf) {{ dados = []; $("linhas").innerHTML = "";
    $("contagem").textContent = "nenhum estado selecionado"; return; }}
  $("contagem").textContent = "carregando " + uf + "…";
  fetch(BASE + "/" + uf + ".json").then(r => r.json()).then(d => {{
    dados = d;
    const sel = $("partido");
    sel.innerHTML = '<option value="">Todos os partidos</option>';
    [...new Set(d.map(x => x.partido))].filter(Boolean).sort().forEach(v => {{
      const o = document.createElement("option"); o.value = v; o.textContent = v;
      sel.appendChild(o);
    }});
    sel.disabled = false; $("busca").disabled = false;
    desenhar();
  }}).catch(() => {{ $("contagem").textContent = "não foi possível carregar " + uf; }});
}});
$("partido").addEventListener("change", desenhar);
$("busca").addEventListener("input", desenhar);
</script>"""
    return _pagina(nome, desc, corpo, quando, f"{BASE_URL}/{chave}/", chave)


def _home(majoritarios: list[Candidato], prop: dict[str, list[dict]], quando: str) -> str:
    linhas = []
    for cod, (chave, nome, _) in CARGOS.items():
        n = sum(1 for c in majoritarios if c.cod_cargo == cod)
        linhas.append(f"<li><a href='{BASE_URL}/{chave}/'>{nome}</a> — {n} candidaturas, "
                      f"cada uma com ficha própria</li>")
    for chave, nome in PROPORCIONAIS.values():
        n = len(prop.get(chave, []))
        if n:
            linhas.append(f"<li><a href='{BASE_URL}/{chave}/'>{nome}</a> — "
                          f"{n:,} candidaturas em listagem filtrável</li>".replace(",", "."))
    corpo = f"""<h1>Dossiê Eleitoral 2026</h1>
<p class="sub">O que cada candidatura declarou ao TSE, organizado e conferível. Sem nota, sem
ranking e sem cor de partido — o que está aqui é registro público, não avaliação.</p>
<p class="aviso">Todo número nesta página vem de fonte oficial, com a data em que foi extraído.
Onde o dado não existe, o site diz que não existe — nunca preenche a lacuna.</p>
<h2 style="margin:28px 0 10px">Por cargo</h2>
<ul style="line-height:2;padding-left:20px">{''.join(linhas)}</ul>
<h2 style="margin:28px 0 10px">O que este site não faz</h2>
<ul style="line-height:1.9;padding-left:20px;color:var(--ink-2)">
  <li>Não classifica candidatos como melhores ou piores.</li>
  <li>Não atribui indicador socioeconômico ao efeito de um mandato — apenas ao período dele.</li>
  <li>Não expõe CPF, título de eleitor nem endereço.</li>
  <li>Não usa cor de partido como padrão visual.</li>
</ul>"""
    return _pagina("Dossiê Eleitoral 2026",
                   "O que cada candidatura de 2026 declarou ao TSE: perfil, trajetória eleitoral "
                   "e plano de governo. Apartidário, com fonte e data em toda tela.",
                   corpo, quando, f"{BASE_URL}/")


def _sitemap(majoritarios: list[Candidato], quando: str) -> str:
    urls = [f"{BASE_URL}/"]
    urls += [f"{BASE_URL}/{s}/" for s, _, _ in CARGOS.values()]
    urls += [f"{BASE_URL}/{s}/" for s, _ in PROPORCIONAIS.values()]
    urls += [c.url for c in majoritarios]
    corpo = "".join(f"  <url><loc>{e(u)}</loc></url>\n" for u in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{corpo}</urlset>\n")


def escrever_site(destino: Path, majoritarios: list[Candidato],
                  proporcionais: dict[str, list[dict]], quando: str) -> None:
    def grava(caminho: str, conteudo: str) -> None:
        alvo = destino / caminho
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(conteudo, encoding="utf-8")

    grava("index.html", _home(majoritarios, proporcionais, quando))

    for cod, (chave, nome, _) in CARGOS.items():
        do_cargo = [c for c in majoritarios if c.cod_cargo == cod]
        grava(f"{chave}/index.html", _listagem_majoritaria(chave, nome, do_cargo, quando))

    for c in majoritarios:
        grava(f"{c.caminho}/index.html", _ficha(c, quando))

    for chave, nome in PROPORCIONAIS.values():
        registros = proporcionais.get(chave, [])
        if not registros:
            continue
        por_uf: dict[str, list[dict]] = {}
        for r in registros:
            # a UF ja' esta' no caminho do arquivo; repetir em cada linha so'
            # engordaria o download
            por_uf.setdefault(r["uf"], []).append({k: v for k, v in r.items() if k != "uf"})
        for uf, linhas in por_uf.items():
            bruto = json.dumps(linhas, ensure_ascii=False, separators=(",", ":"))
            grava(f"dados/{chave}/{uf}.json", bruto)
        grava(f"{chave}/index.html", _listagem_proporcional(chave, nome, por_uf, quando))

    grava("sitemap.xml", _sitemap(majoritarios, quando))
