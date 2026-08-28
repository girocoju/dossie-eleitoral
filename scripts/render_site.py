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

# Nome curto e explicacao de uma linha para cada indicador.
#
# "Rendimento medio mensal real do trabalho" e' o nome tecnico correto e quase
# ninguem sabe o que significa. A tela mostra o nome curto e guarda a definicao
# num tooltip — sem simplificar o DADO, so' a forma de nomea-lo.
_GLOSSARIO = {
    "PIB": ("PIB do estado",
            "Soma de tudo que foi produzido no estado no ano, em reais correntes."),
    "PIB_PER_CAPITA": ("PIB por habitante",
            "O PIB dividido pela população. Não é renda das pessoas: é produção por cabeça."),
    "POPULACAO": ("População",
            "Estimativa do IBGE de quantas pessoas moram no estado."),
    "POPULACAO_CENSO": ("População (Censo)",
            "Contagem do Censo, feita de porta em porta — mais precisa que a estimativa."),
    "DESOCUPACAO": ("Desemprego",
            "Percentual de quem tem 14 anos ou mais, procura trabalho e não encontra."),
    "RENDIMENTO_MEDIO": ("Rendimento do trabalho",
            "Quanto ganha por mês, em média, quem está ocupado — já descontada a inflação."),
    "HOMICIDIOS": ("Homicídios",
            "Mortes por agressão a cada 100 mil habitantes."),
    "MORTALIDADE_INFANTIL": ("Mortalidade infantil",
            "Mortes de crianças com menos de 1 ano a cada mil nascidas vivas."),
    "RECEITA_ESTADUAL": ("Receita do estado",
            "Quanto o governo estadual arrecadou no ano, já descontadas as deduções."),
    "DESPESA_ESTADUAL": ("Despesa do estado",
            "Quanto o governo estadual se comprometeu a gastar no ano."),
    "RESULTADO_ORCAMENTARIO": ("Resultado do estado",
            "Receita menos despesa. Positivo não é bom nem ruim: déficit pode ser "
            "investimento, superávit pode ser gasto que não saiu."),
    "IDEB": ("IDEB (rede pública)",
            "Nota da educação básica pública, de 0 a 10, medida a cada dois anos."),
    "IDHM": ("IDHM",
            "Índice de desenvolvimento humano do município, de 0 a 1. Medido a cada dez anos."),
    "IPCA": ("Inflação (IPCA)",
            "Índice oficial de inflação, acumulado no ano."),
    "SELIC": ("Juros (Selic)",
            "Taxa básica de juros. Definida pelo Banco Central, não pelo Executivo."),
    "RECEITA_LIQUIDA_UNIAO": ("Receita da União",
            "Receita primária federal menos o que é repassado a estados e municípios."),
    "DESPESA_PRIMARIA_UNIAO": ("Despesa da União",
            "Gasto federal sem contar juros da dívida."),
    "RESULTADO_PRIMARIO_UNIAO": ("Resultado primário da União",
            "Receita líquida menos despesa primária. Negativo é déficit."),
}

_CARGO_CURTO = {1: "Presidente", 3: "Governador"}

_UF_NOME = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia",
    "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás",
    "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul",
    "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba", "PR": "Paraná",
    "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro",
    "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul", "RO": "Rondônia",
    "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo", "SE": "Sergipe",
    "TO": "Tocantins", "BR": "Brasil (nacional)",
}



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


def _urna(c: Candidato) -> str:
    """Numero de urna em destaque.

    E' a informacao mais pratica da ficha: e' o que a pessoa digita para votar.
    Fica ao lado do retrato, no tamanho que uma pessoa le' de relance — e nao
    perdido entre atributos declarados.
    """
    if c.nr_candidato is None:
        num = '<span class="marca-dado m-ausente">sem número</span>'
    else:
        num = (f'<div class="urna"><b>{c.nr_candidato}</b>'
               f'<small>{e(c.sigla_partido) or ""}</small></div>')
    return f"""<dl class="rotulado">
      <div><dt>Número na urna</dt>{num}</div>
      <div><dt>Concorre a</dt><dd>{e(c.cargo_nome)}</dd></div>
      <div><dt>{'Circunscrição' if c.cod_cargo == 1 else 'Estado'}</dt>
        <dd>{e(_UF_NOME.get(c.sg_uf, c.sg_uf))}</dd></div>
      <div><dt>Situação no TSE</dt><dd>{e(c.situacao) or '—'}</dd></div>
    </dl>"""


def _legenda(c: Candidato) -> str:
    """Coligacao e federacao — a 'legenda' pela qual a candidatura foi registrada.

    Federacao NAO e' coligacao: e' uniao partidaria que dura no minimo quatro anos
    e vale para todos os cargos, enquanto coligacao morre com a eleicao. Sao
    exibidas separadas porque significam coisas diferentes.
    """
    partes = []
    if c.federacao:
        partes.append(f"<div><dt>Federação</dt><dd>{e(c.federacao)}</dd></div>")
    if c.coligacao:
        partes.append(f"<div><dt>Coligação</dt><dd>{e(c.coligacao)}</dd></div>")
    if c.composicao and c.composicao != c.sigla_partido:
        partes.append(f"<div style='grid-column:1/-1'><dt>Composição</dt>"
                      f"<dd style='font-size:14px'>{e(c.composicao)}</dd></div>")
    if not partes:
        return ""
    return ('<section class="bloco"><h2>Legenda</h2>'
            f'<dl class="campos">{"".join(partes)}</dl></section>')


def _atividade(c: Candidato) -> str:
    """Atividade na Camara de quem ja' foi deputado federal.

    Separada por CLASSE, sem total. Somar projeto de lei com requerimento de
    retirada de pauta produz o numero que circula na imprensa e nao significa
    nada: em 2025 foram 7.695 projetos de lei contra 31.479 requerimentos de
    retirada de pauta. E nao ha' taxa de aprovacao — aprovar depende de estar na
    base do governo, nao do merito do texto (ADR-015).
    """
    if not c.atividade:
        return ""
    rotulos = {
        "normativa": "Propôs criar ou mudar lei",
        "fiscalizacao": "Pediu contas ao Executivo",
        "relatoria": "Relatou proposta de outro",
        "procedimental": "Rito, homenagem, emenda",
        "outra": "Outros tipos",
    }
    linhas = "".join(
        f"<tr><td>{rotulos.get(a['classe'], a['classe'])}</td>"
        f"<td class='num'>{a['total']:,}</td>"
        f"<td class='num'>{a['norma'] or '—'}</td></tr>".replace(",", ".")
        for a in c.atividade
    )
    anos = f"{min(a['a1'] for a in c.atividade)}–{max(a['a2'] for a in c.atividade)}"
    return f"""<section class="bloco">
      <h2>Atividade na Câmara dos Deputados — {anos}</h2>
      <div class="rolagem"><table>
        <thead><tr><th>Tipo de proposição</th><th>Apresentadas</th>
        <th>Viraram norma</th></tr></thead><tbody>{linhas}</tbody></table></div>
      <p style="font-size:12.5px;color:var(--ink-3);margin:8px 0 0">
        Só entram proposições em que a pessoa é <b>proponente</b> — assinatura de
        apoio não conta. Os tipos aparecem separados porque somá-los não significa
        nada: um projeto de lei e um requerimento de retirada de pauta custam
        coisas muito diferentes. <b>Não há taxa de aprovação</b>: aprovar depende de
        estar na base do governo, não do mérito do texto.</p>
    </section>"""


def _indicadores(c: Candidato) -> str:
    """Bloco socioeconomico — so' para quem ja' teve mandato executivo."""
    if not c.indicadores:
        return ""
    linhas = []
    for i in c.indicadores:
        if i["v1"] is None or i["v2"] is None:
            continue
        pct = f"{i['pct']:+.1f}%" if i["pct"] is not None else "—"
        pct_br = f"{i['pct_br']:+.1f}%" if i["pct_br"] is not None else "—"
        janela = f"{i['ref1']}–{i['ref2']}"
        incompleta = (' <span class="marca-dado m-ausente">janela incompleta</span>'
                      if i["incompleta"] else "")
        nome, ajuda = _GLOSSARIO.get(
            i["cod"], (i["indicador"], "Ver metodologia para a definição completa."))
        cargo = _CARGO_CURTO.get(i["cargo"], "—")
        linhas.append(
            f"<tr><td>{e(nome)}<span class='ajuda' tabindex='0' "
            f"aria-label='{e(ajuda)}' title='{e(ajuda)}'>?</span>{incompleta}</td>"
            f"<td>{e(cargo)}</td>"
            f"<td class='num'>{janela}</td>"
            f"<td class='num'>{pct}</td><td class='num'>{pct_br}</td></tr>")
    if not linhas:
        return ""
    primeiro = c.indicadores[0]
    return f"""<section class="bloco">
      <h2>Durante mandatos anteriores — {e(primeiro['ue'])}, {primeiro['a1']}–{primeiro['a2']}</h2>
      <div class="rolagem"><table>
        <thead><tr><th>Indicador</th><th>No cargo de</th><th>Janela</th>
        <th>Variação</th><th>Brasil no mesmo período</th></tr></thead>
        <tbody>{''.join(linhas)}</tbody></table></div>
      <p class="aviso" style="margin:10px 0 0">
        <b>Estes números descrevem o período, não o efeito do mandato.</b>
        Cada variação aparece ao lado da variação nacional no mesmo intervalo,
        porque um número isolado vira nota de gestão. PIB, desemprego e homicídios
        dependem de fatores muito além do alcance de um governo estadual.</p>
    </section>"""


def _ficha(c: Candidato, quando: str) -> str:
    partes = [f"""
<a href="{BASE_URL}/{CARGOS[c.cod_cargo][0]}/" style="font-size:13.5px">← {e(c.cargo_nome)}</a>
<div class="ficha">
  <div class="retrato">
    {_retrato(c)}
    <div class="legenda">foto de urna — TSE</div>
    {_urna(c)}
  </div>
  <div>
    <h1>{e(c.nome_urna)}</h1>
    <p class="sub" style="margin-bottom:28px">{e(c.nome_completo or '')}</p>

    <section class="bloco"><h2>Perfil declarado ao TSE</h2>
    <dl class="campos">
      <div style="grid-column:1/-1"><dt>Partido</dt>
        <dd><b>{e(c.partido_completo)}</b></dd></div>
      <div><dt>Idade na posse</dt><dd>{c.idade if c.idade else '—'}</dd></div>
      <div><dt>Gênero</dt><dd>{e(c.genero) or '—'}</dd></div>
      <div><dt>Cor/raça</dt><dd>{e(c.cor_raca) or '—'}</dd></div>
      <div><dt>Grau de instrução</dt><dd>{e(c.grau_instrucao) or '—'}</dd></div>
      <div><dt>Ocupação</dt><dd>{e(c.ocupacao) or '—'}</dd></div>
      <div><dt>Estado de nascimento</dt><dd>{e(c.uf_nascimento) or '—'}</dd></div>
    </dl></section>
    {_legenda(c)}
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
    if c.proposta_obrigatoria and c.plano_texto:
        palavras = len(c.plano_texto.split())
        plano = (
            f'<p style="margin:0 0 8px"><a href="{BASE_URL}/{c.caminho}/plano/">'
            f'<b>Ler o plano de governo na íntegra →</b></a></p>'
            f'<p style="margin:0;font-size:13px;color:var(--ink-3)">'
            f'{c.plano_paginas} páginas, {palavras:,} palavras. '
            f'Transcrição do PDF oficial.</p>'.replace(",", "."))
    elif c.proposta_obrigatoria and c.tem_proposta and c.plano_motivo:
        extra = (f' <a href="{e(c.plano_url_pdf)}" rel="nofollow noopener">'
                 f'Abrir o PDF original ↗</a>' if c.plano_url_pdf else '')
        plano = ('<span class="marca-dado m-ausente">apresentou, mas não foi '
                 'possível transcrever</span>'
                 f'<p style="margin:8px 0 0;font-size:13px;color:var(--ink-3)">'
                 f'{e(c.plano_motivo)}.{extra}</p>')
    elif c.proposta_obrigatoria and c.tem_proposta:
        plano = ('<span class="marca-dado m-ausente">apresentou — '
                 'transcrição pendente</span>')
    elif c.proposta_obrigatoria:
        plano = ('<span class="marca-dado m-ausente">exigido para este cargo, não consta</span>')
    else:
        # Nao vira bloco proprio: dar peso visual igual ao de conteudo real
        # sugeriria que falta alguma coisa. Vira uma nota discreta, que ainda
        # impede alguem de ler ausencia como omissao do candidato.
        plano = None

    if c.bens_total is not None:
        bens = (f"<dl class='campos'><div><dt>Total declarado</dt>"
                f"<dd>{brl(c.bens_total)}</dd></div>"
                f"<div><dt>Itens</dt><dd>{c.bens_n or 0}</dd></div></dl>")
    else:
        bens = "<span class='marca-dado m-ausente'>não declarou bens</span>"

    # Limite LEGAL de gastos, nao gasto realizado. A diferenca importa: e' o teto
    # que a lei impoe a' campanha, e nao diz nada sobre quanto foi gasto.
    if c.limite_gasto:
        bens += (f"<dl class='campos' style='margin-top:12px'><div style='grid-column:1/-1'>"
                 f"<dt>Limite legal de gastos de campanha</dt>"
                 f"<dd>{brl(c.limite_gasto)}"
                 f"<span class='ajuda' tabindex='0' title='Teto que a Lei 9.504/97 impõe "
                 f"à campanha deste cargo. Não é o quanto foi gasto — é o quanto pode "
                 f"ser gasto.'>?</span></dd></div></dl>")

    if plano is None:
        partes.append(f"""
    <section class="bloco"><h2>Bens declarados</h2>{bens}</section>
    <p class="nota-lei">Plano de governo não é exigido para este cargo. A Lei
      9.504/97 (art. 11, §1º, IX) o exige de Prefeito, Governador e Presidente;
      Senador é majoritário, mas não consta da lista.</p>""")
    else:
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

    partes.append(_atividade(c))
    partes.append(_indicadores(c))
    partes.append("</div></div>")
    desc = (f"{c.nome_urna}, candidatura a {c.cargo_nome} por {c.sg_uf} em 2026. "
            f"Perfil declarado ao TSE, trajetória eleitoral e plano de governo.")
    return _pagina(f"{c.nome_urna} — {c.cargo_nome} {c.sg_uf}", desc,
                   "".join(partes), quando, c.url, CARGOS[c.cod_cargo][0])


def _pagina_plano(c: Candidato, quando: str) -> str:
    """Plano de governo em pagina propria, com URL propria.

    Nao cabe na ficha: a mediana e' 111 mil caracteres, e enfiar isso num bloco
    empurraria todo o resto para fora da tela. Em pagina propria vira o conteudo
    mais substantivo do site — e o unico lugar onde alguem que busca "o que fulano
    propoe sobre saude" tem onde chegar.

    O texto sai em paragrafos, sem nenhuma edicao. Cabecalho de pagina e quebra
    tortas do PDF aparecem como estao: e' transcricao, nao diagramacao.
    """
    blocos = (c.plano_texto or "").split("\n\n")
    paragrafos = "".join(
        f"<p>{e(b.strip())}</p>" for b in blocos if b.strip()
    )
    palavras = f"{len((c.plano_texto or '').split()):,}".replace(",", ".")
    original = (f'<a href="{e(c.plano_url_pdf)}" rel="nofollow noopener">'
                f'Abrir o PDF original no TSE ↗</a>' if c.plano_url_pdf else "")
    corpo = f"""<a href="{BASE_URL}/{c.caminho}/" style="font-size:13.5px">← {e(c.nome_urna)}</a>
<h1>Plano de governo — {e(c.nome_urna)}</h1>
<p class="sub">{e(c.cargo_nome)} · {e(_UF_NOME.get(c.sg_uf, c.sg_uf))} ·
{e(c.partido_completo)}</p>
<p class="aviso"><b>Transcrição automática do PDF oficial</b> entregue ao TSE:
{c.plano_paginas} páginas, {palavras} palavras. O texto está <b>íntegro e sem
edição</b> — não foi resumido, corrigido nem reorganizado. Quebras de linha e
cabeçalhos de página aparecem como saíram do arquivo. {original}</p>
<article class="plano">{paragrafos}</article>"""
    desc = (f"Plano de governo de {c.nome_urna}, candidatura a {c.cargo_nome} por "
            f"{c.sg_uf} em 2026. Texto integral entregue ao TSE.")
    return _pagina(f"Plano de governo de {c.nome_urna}", desc, corpo, quando,
                   f"{c.url}plano/", CARGOS[c.cod_cargo][0])


def _cartao(c: Candidato) -> str:
    foto = (f'<img src="{e(c.url_foto)}" alt="" loading="lazy" width="52" height="69">'
            if c.url_foto else '<div class="semfoto"></div>')
    busca = e((c.nome_urna + " " + (c.nome_completo or "")).lower())
    return (f'<a class="cartao" href="{BASE_URL}/{c.caminho}/" data-uf="{e(c.sg_uf)}" '
            f'data-partido="{e(c.sigla_partido) or ""}" data-nome="{busca}">{foto}<span>'
            f'<b>{e(c.nome_urna)}</b>'
            f'<small>{e(_UF_NOME.get(c.sg_uf, c.sg_uf))} · {e(c.sigla_partido) or "—"}'
            f' · nº {c.nr_candidato or "—"}</small>'
            f'<small>{e(c.situacao) or ""}</small></span></a>')


def _listagem_majoritaria(chave: str, nome: str, cands: list[Candidato], quando: str) -> str:
    ufs = sorted({c.sg_uf for c in cands})
    op_uf = "".join(f'<option value="{u}">{_UF_NOME.get(u, u)}</option>' for u in ufs)
    partidos = sorted({c.sigla_partido for c in cands if c.sigla_partido})
    op_pt = "".join(f'<option value="{p}">{p}</option>' for p in partidos)
    filtro_uf = (f'<select id="uf"><option value="">Todos os estados</option>{op_uf}</select>'
                 if len(ufs) > 1 else "")
    corpo = f"""<h1>{e(nome)}</h1>
<p class="sub">{len(cands)} candidaturas registradas em 2026. Cada uma tem ficha
própria, com perfil declarado, trajetória eleitoral e plano de governo quando a lei
o exige.</p>
<div class="filtros">
  {filtro_uf}
  <select id="partido"><option value="">Todos os partidos</option>{op_pt}</select>
  <input id="busca" type="search" placeholder="Buscar por nome" autocomplete="off">
</div>
<p class="contagem" id="contagem">{len(cands)} candidaturas</p>
<div class="grade" id="grade">{''.join(_cartao(c) for c in cands)}</div>
<script>
const $ = (id) => document.getElementById(id);
const cartoes = [...document.querySelectorAll("#grade .cartao")];
function filtrar() {{
  const uf = $("uf") ? $("uf").value : "";
  const pt = $("partido").value, q = $("busca").value.trim().toLowerCase();
  let n = 0;
  cartoes.forEach(el => {{
    const ok = (!uf || el.dataset.uf === uf) && (!pt || el.dataset.partido === pt) &&
      (!q || el.dataset.nome.includes(q));
    el.hidden = !ok; if (ok) n++;
  }});
  $("contagem").textContent = n + (n === 1 ? " candidatura" : " candidaturas");
}}
["uf","partido"].forEach(i => $(i) && $(i).addEventListener("change", filtrar));
$("busca").addEventListener("input", filtrar);
</script>"""
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
<p class="aviso">As duas últimas colunas só têm número para quem <b>já é deputado
federal</b> e busca reeleição: são as proposições em que a pessoa é proponente na
legislatura atual. Para quem nunca teve mandato na Câmara, aparecem vazias — e vazio
aqui significa "não se aplica", não "não fez nada".</p>
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
  <thead><tr><th>Nome de urna</th><th>Partido</th><th>Coligação</th><th>Situação</th>
  <th>Idade</th><th>Ocupação</th><th title="projetos de lei, PEC e afins como proponente"
  >PLs na Câmara</th><th>Viraram norma</th></tr></thead>
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
    <td>${{d.nome ?? ""}}</td><td>${{d.partido ?? ""}}</td>
    <td>${{d.coligacao ?? ""}}</td><td>${{d.situacao ?? ""}}</td>
    <td class="num">${{d.idade ?? "—"}}</td><td>${{d.ocupacao ?? ""}}</td>
    <td class="num">${{d.pl ?? "—"}}</td><td class="num">${{d.norma ?? "—"}}</td></tr>`).join("");
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
    urls += [f"{c.url}plano/" for c in majoritarios if c.plano_texto]
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
        if c.plano_texto:
            grava(f"{c.caminho}/plano/index.html", _pagina_plano(c, quando))

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
