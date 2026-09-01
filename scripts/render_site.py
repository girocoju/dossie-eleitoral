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
import re
from pathlib import Path

from ingest.common.textnorm import strip_accents
from scripts.gerar_site import BASE_URL, CARGOS, PROPORCIONAIS, Candidato, brl, e

FONTE = "TSE — Divulgação de Candidaturas"

# Nome curto e explicacao de uma linha para cada indicador.
#
# "Rendimento medio mensal real do trabalho" e' o nome tecnico correto e quase
# ninguem sabe o que significa. A tela mostra o nome curto e guarda a definicao
# num tooltip — sem simplificar o DADO, so' a forma de nomea-lo.
# Indicadores cujo NOME e explicacao dependem do ente governado. `True` = mandato
# nacional, `False` = estadual, `None` = fora de uma ficha (catalogo da
# metodologia, que fala dos dois casos ao mesmo tempo).
#
# So' entram aqui os que diziam "estado" no texto. Receita/Despesa/Resultado do
# estado e da Uniao nao precisam: depois do ADR-029 cada um so' aparece na ficha
# do cargo que chefiou aquele ente, entao o nome ja' esta' sempre certo.
_ESCOPO = {
    "PIB": {
        True: ("PIB do Brasil",
               "Soma de tudo que foi produzido no país no ano, a preços correntes — "
               "a variação inclui a inflação e não é crescimento real."),
        False: ("PIB do estado",
                "Soma de tudo que foi produzido no estado no ano, a preços correntes — "
                "a variação inclui a inflação e não é crescimento real."),
        None: ("PIB",
               "Soma de tudo que foi produzido no território no ano, a preços "
               "correntes — a variação inclui a inflação e não é crescimento real."),
    },
    "POPULACAO": {
        True: ("População", "Estimativa do IBGE de quantas pessoas moram no país."),
        False: ("População", "Estimativa do IBGE de quantas pessoas moram no estado."),
        None: ("População", "Estimativa do IBGE de quantas pessoas moram no território."),
    },
}


def _rotulo_indicador(cod: str, nome_de_origem: str,
                      nacional: bool | None = None) -> tuple[str, str]:
    """Nome de tela e explicacao, com o escopo resolvido pelo mandato.

    Uma ficha de PRESIDENTE dizia "PIB do estado" e "quantas pessoas moram no
    estado" para um numero nacional. Rotulo errado sobre dado certo e' a familia
    de erro que este projeto mais evita (ADR-023).
    """
    variantes = _ESCOPO.get(cod)
    if variantes is not None:
        return variantes[nacional]
    return _GLOSSARIO.get(
        cod, (nome_de_origem, "Ver metodologia para a definição completa."))


_GLOSSARIO = {
    "PIB": ("PIB do estado",
            "Soma de tudo que foi produzido no estado no ano, a preços correntes — "
            "a variação inclui a inflação e não é crescimento real."),
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
    # A home passa "Dossie Eleitoral 2026" como titulo, e o sufixo fixo fazia
    # "Dossie Eleitoral 2026 — Dossie Eleitoral" — que e' o texto que aparece na
    # aba do navegador, no resultado do Google e no card compartilhado. Nome
    # repetido na primeira coisa que se le' de um projeto e' o tipo de descuido
    # que custa credibilidade justamente com quem vai avaliar o trabalho.
    marca = "Dossiê Eleitoral"
    titulo_aba = titulo if titulo.startswith(marca) else f"{titulo} — {marca}"

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
<title>{e(titulo_aba)}</title>
<meta name="description" content="{e(descricao)}">
<link rel="canonical" href="{e(canonical)}">
<meta name="robots" content="index,follow">
<meta property="og:type" content="website">
<meta property="og:title" content="{e(titulo_aba)}">
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
    # Uma tabela por LEGISLATURA. Somar as passagens de alguem que serviu de
    # 2003 a 2010 e voltou em 2019 esconderia justamente o que interessa: o que
    # ele fez em CADA mandato, e que houve um intervalo.
    plenario = c.plenario
    por_leg: dict[int, list[dict]] = {}
    for a in c.atividade:
        por_leg.setdefault(a.get("leg") or 0, []).append(a)

    blocos = []
    for leg in sorted(por_leg, reverse=True):
        itens = sorted(por_leg[leg], key=lambda x: -x["total"])
        ini, fim = itens[0].get("leg_ini"), itens[0].get("leg_fim")
        periodo = f"{ini}–{fim}" if ini else "período não identificado"
        # Atividade registrada SEM mandato de deputado no periodo. Nao e' erro do
        # dado: senador apresenta emenda a Medida Provisoria na comissao mista, e
        # a Camara registra. Apresentar isso como legislatura afirmaria um mandato
        # que nao houve — o mesmo tipo de erro do "2006 · Nao eleito".
        sem_mandato = not itens[0].get("mandato", True)
        marca = ("" if not sem_mandato else
                 " <span class='marca-dado m-ausente'>sem mandato de deputado "
                 "neste período</span>")
        linhas = "".join(
            f"<tr><td>{rotulos.get(a['classe'], a['classe'])}</td>"
            f"<td class='num'>{a['total']:,}</td>"
            f"<td class='num'>{a['norma'] or '—'}</td></tr>".replace(",", ".")
            for a in itens
        )
        total = sum(a["total"] for a in itens)
        # Votos e presenca da MESMA legislatura, logo abaixo das proposicoes.
        # Separado nao ajudaria ninguem: sao tres medidas do mesmo mandato.
        pl = next((x for x in plenario if x["leg"] == leg), None)
        extra = "" if not pl else f"""
      <dl class="campos" style="margin:10px 0 0">
        <div><dt>Votações em que votou</dt><dd>{pl['votacoes']:,}</dd></div>
        <div><dt>Sessões de plenário</dt><dd>{pl['plenario'] or '—'}</dd></div>
        <div><dt>Eventos no total</dt><dd>{pl['eventos'] or '—'}
          <span class='ajuda' tabindex='0' title='Plenário e comissões somados.
          Não é taxa de presença: a fonte não diz a quantos eventos o
          parlamentar deveria ter comparecido.'>?</span></dd></div>
        <div><dt>Como votou</dt><dd>{pl['sim']:,} sim · {pl['nao']:,} não
          · {pl['abstencao']:,} abst. · {pl['obstrucao']:,} obstr.</dd></div>
      </dl>""".replace(",", ".")
        blocos.append(f"""
      <h3 style="margin:24px 0 8px;font-size:15px">{leg}ª legislatura · {periodo}
        <small style="font-weight:400;color:var(--ink-3)"> — {total:,} proposições</small>
        {marca}</h3>
      <div class="rolagem"><table>
        <thead><tr><th>Tipo de proposição</th><th>Apresentadas</th>
        <th>Viraram norma</th></tr></thead><tbody>{linhas}</tbody></table></div>{extra}""".replace(
            f"{total:,}", f"{total:,}".replace(",", ".")))

    return f"""<section class="bloco">
      <h2>Atividade na Câmara dos Deputados</h2>
      <p style="font-size:13px;color:var(--ink-3);margin:0 0 4px">
        Separado por legislatura: somá-las esconderia o intervalo entre
        passagens. Onde se lê <b>sem mandato de deputado neste período</b>, a
        atividade é real mas não vem de mandato na Câmara — senador apresenta
        emenda a Medida Provisória na comissão mista, e a Câmara registra a
        autoria.</p>
      {"".join(blocos)}
      <p style="font-size:12.5px;color:var(--ink-3);margin:12px 0 0">
        Só entram proposições em que a pessoa é <b>proponente</b> — assinatura de
        apoio não conta. Os tipos aparecem separados porque somá-los não significa
        nada: um projeto de lei e um requerimento de retirada de pauta custam
        coisas muito diferentes. <b>Não há taxa de aprovação</b>: aprovar depende de
        estar na base do governo, não do mérito do texto.
        <b>Não há taxa de presença</b> pelo mesmo motivo estrutural: a fonte diz
        onde o parlamentar esteve, não a quantos eventos deveria ter ido — e sem
        denominador não existe percentual honesto.</p>
    </section>"""


# Indicadores em REAIS CORRENTES. A variacao deles inclui a inflacao do periodo
# e NAO e' crescimento real: entre 2022 e 2023 o PIB do Brasil sobe 8,6% nesta
# serie, contra 3,2% de crescimento real medido pelo IBGE. A diferenca e' preco.
#
# Nao deflacionamos: o deflator correto do PIB nao e' o IPCA, e usar o indice
# errado produziria um "valor real" que parece rigoroso e nao e'. O que se faz e'
# DIZER que o numero e' nominal, na propria linha.
_NOMINAIS = frozenset({
    "PIB", "PIB_PER_CAPITA",
    "RECEITA_ESTADUAL", "DESPESA_ESTADUAL", "RESULTADO_ORCAMENTARIO",
    "RECEITA_LIQUIDA_UNIAO", "DESPESA_PRIMARIA_UNIAO", "RESULTADO_PRIMARIO_UNIAO",
})

_MARCA_NOMINAL = ("<span class='ajuda' tabindex='0' aria-label='Valor a preços "
                  "correntes: a variação inclui a inflação do período e não é "
                  "crescimento real.' title='A preços correntes — a variação "
                  "inclui a inflação do período, não é crescimento real.'>nominal</span>")


def _indicadores(c: Candidato) -> str:
    """Bloco socioeconomico — so' para quem ja' teve mandato executivo.

    SEPARADO POR MANDATO, do mais recente para o mais antigo.

    A versao anterior jogava todos os mandatos numa tabela unica sob um `h2` que
    nomeava apenas o mandato da PRIMEIRA linha. Para 57 dos 129 candidatos com
    este bloco isso era uma afirmacao falsa: a ficha do Lula trazia 35 linhas de
    tres mandatos presidenciais sob "BRASIL, 2023-2026", com "Produto Interno
    Bruto" aparecendo tres vezes e so' a coluna Janela dizendo qual era qual.

    Separado, a trajetoria se le' sem inferir nada — e o titulo de cada bloco ja'
    diz o cargo, a unidade e o periodo, o que dispensa a coluna "No cargo de" e
    devolve uma coluna de largura ao celular.
    """
    if not c.indicadores:
        return ""

    grupos: dict[tuple[int, int, str, int], list[dict]] = {}
    for i in c.indicadores:
        if i["v1"] is None or i["v2"] is None:
            continue
        grupos.setdefault((i["a1"], i["a2"], i["ue"], i["cargo"]), []).append(i)
    if not grupos:
        return ""


    blocos = []
    # Mandato mais recente primeiro: e' a leitura de trajetoria, do que a pessoa
    # fez por ultimo para tras.
    for (a1, a2, ue, cargo), itens in sorted(grupos.items(),
                                             key=lambda kv: (-kv[0][0], kv[0][2])):
        linhas = []
        # Alfabetica pelo nome EXIBIDO, nao pelo nome do banco: o glossario troca
        # "Produto Interno Bruto a precos correntes" por "PIB do estado" e "Taxa
        # de desocupacao" por "Desemprego". Ordenar pela origem produziria, na
        # tela, uma ordem que parece aleatoria.
        # Mandato nacional: o indicador JA' E' o Brasil, entao a coluna
        # "Brasil no mesmo periodo" repetiria o mesmo numero. Medido em
        # 31/08/2026: 76 das 78 linhas de ficha presidencial tinham as duas
        # variacoes identicas, e as outras 2 nao tinham comparador nenhum.
        # Comparar o Brasil com o Brasil nao e' comparacao — e' ruido que parece
        # erro.
        nacional = cargo == 1

        # `nacional` amarrado por default: a funcao e' redefinida a cada volta
        # do laco, e fechar sobre a variavel livre e' o tipo de bug que so'
        # aparece quando alguem torna a chamada preguicosa (ruff B023).
        def _rot(i: dict, nacional: bool = nacional) -> tuple[str, str]:
            return _rotulo_indicador(i["cod"], i["indicador"], nacional)

        for i in sorted(itens, key=lambda x: strip_accents(_rot(x)[0]).casefold()):
            pct = f"{i['pct']:+.1f}%" if i["pct"] is not None else "—"
            pct_br = f"{i['pct_br']:+.1f}%" if i["pct_br"] is not None else "—"
            incompleta = (' <span class="marca-dado m-ausente">janela incompleta</span>'
                          if i["incompleta"] else "")
            nome, ajuda = _rot(i)
            # Sem esta marca, "+8,6%" no PIB e' lido como crescimento economico.
            nominal = _MARCA_NOMINAL if i["cod"] in _NOMINAIS else ""
            linhas.append(
                f"<tr><td>{e(nome)}<span class='ajuda' tabindex='0' "
                f"aria-label='{e(ajuda)}' title='{e(ajuda)}'>?</span>{incompleta}</td>"
                f"<td class='num'>{i['ref1']}–{i['ref2']}</td>"
                f"<td class='num'>{pct}{nominal}</td>"
                + ("" if nacional else f"<td class='num'>{pct_br}</td>")
                + "</tr>")
        if not linhas:
            continue
        blocos.append(f"""
      <h3 style="margin:24px 0 8px;font-size:15px">{e(_CARGO_CURTO.get(cargo, "—"))}
        · {e(ue)} · {a1}–{a2}</h3>
      <div class="rolagem"><table>
        <thead><tr><th>Indicador</th><th>Janela</th><th>Variação</th>
        {"" if nacional else "<th>Brasil no mesmo período</th>"}</tr></thead>
        <tbody>{"".join(linhas)}</tbody></table></div>""")
    if not blocos:
        return ""

    return f"""<section class="bloco">
      <h2>Durante mandatos anteriores</h2>
      <p style="font-size:13px;color:var(--ink-3);margin:0 0 4px">
        Separado por mandato, do mais recente para o mais antigo. A
        <b>janela</b> de cada indicador pode não coincidir com o mandato: ela é o
        intervalo em que a fonte publicou dado, e aparece em cada linha.</p>
      {"".join(blocos)}
      <p class="aviso" style="margin:10px 0 0">
        <b>Estes números descrevem o período, não o efeito do mandato.</b>
        Valores marcados <b>nominal</b> estão a preços correntes: a variação
        inclui a inflação e não é crescimento real.
        Cada variação aparece ao lado da variação nacional no mesmo intervalo,
        porque um número isolado vira nota de gestão. PIB, desemprego e homicídios
        dependem de fatores muito além do alcance de um governo estadual.</p>
    </section>"""


def _pct(parte: float, todo: float) -> str:
    """Percentual que o arredondamento nao transforma em mentira.

    Dois extremos, e os dois enganam do mesmo jeito — dizendo que uma parcela e'
    o todo, ou que nao existe:

        0,22%   `.0f` escreve "0%"    -> o leitor le' "nao arrecadou nada"
       99,67%   `.0f` escreve "100%"  -> o leitor le' "veio tudo dessa origem"

    Sai `&lt;1%` e `&gt;99%`, que sao pequenos e grandes sem serem falsos. As
    entidades vao ESCAPADAS: `<1%` cru fecha a celula da tabela, porque o
    navegador le' o `<` como inicio de tag. Aconteceu no ar em 29/08/2026 — a
    coluna "Fatia" da linha de pessoas fisicas do Lula ficou vazia.
    """
    if not todo:
        return "—"
    v = parte / todo * 100
    if 0 < v < 1:
        return "&lt;1%"
    if 99 < v < 100:
        return "&gt;99%"
    return f"{v:.0f}%"


def _financiamento(c: Candidato) -> str:
    """Quem sustenta a campanha (F-11 / ADR-020).

    TRES ESTADOS, NUNCA DOIS. Uma candidatura sem linha na prestacao de contas
    NAO declarou zero — nao declarou nada, porque o prazo vai ate' depois de
    04/10/2026. Escrever "R$ 0,00" ali sugeriria campanha sem dinheiro onde ha'
    apenas prazo em aberto. E' o mesmo erro que a ADR-013 evitou entre "nao
    apresentou plano" e "nao e' exigido plano".

    SEM RANKING. O valor aparece ao lado do limite legal do cargo, que e' o unico
    comparador que significa alguma coisa. Nao ha' posicao, nem comparacao com
    outras candidaturas: lista de politico ordenada por dinheiro e' placar
    (Constituicao 0.1).

    A ORIGEM VEM ANTES DO TOTAL, na leitura. R$ 40 milhoes todos do partido e
    R$ 40 milhoes vindos de tres mil pessoas sao fatos politicos opostos, e o
    total sozinho nao distingue.
    """
    if not c.financiamento:
        return """<section class="bloco">
      <h2>Financiamento de campanha</h2>
      <p><span class="marca-dado m-ausente">prestação ainda não entregue</span></p>
      <p style="font-size:12.5px;color:var(--ink-3);margin:8px 0 0">
        Isto <b>não</b> significa campanha sem arrecadação: significa que esta
        candidatura ainda não consta na prestação de contas publicada pelo TSE.
        O prazo final é posterior a 04/10/2026, e a cobertura cresce a cada carga.</p>
    </section>"""

    total = sum(f["valor"] for f in c.financiamento)
    proprio = sum(f["proprio"] for f in c.financiamento)

    linhas = "".join(
        f"<tr><td>{e(f['origem'])}</td>"
        f"<td class='num'>{brl(f['valor'])}</td>"
        f"<td class='num'>{_pct(f['valor'], total)}</td>"
        f"<td class='num'>{f['doadores']:,}</td></tr>".replace(",", ".")
        for f in c.financiamento
    )

    # O limite legal e' o unico comparador honesto: e' o teto que a lei impoe a
    # ESTE cargo, nao o que outra campanha arrecadou.
    if c.limite_gasto:
        contra_limite = (
            f"<p style='margin:12px 0 0;font-size:13.5px'>Arrecadado equivale a "
            f"<b>{_pct(total, c.limite_gasto)}</b> do limite legal de gastos deste "
            f"cargo ({brl(c.limite_gasto)}).</p>")
    else:
        contra_limite = ""

    if c.despesa_contratada:
        despesa = (f"<p style='margin:6px 0 0;font-size:13.5px'>Despesa "
                   f"<b>contratada</b>: {brl(c.despesa_contratada)}"
                   f"<span class='ajuda' tabindex='0' title='Contratada, não paga. "
                   f"É o quanto a campanha se comprometeu a gastar; o valor já pago "
                   f"é um subconjunto disso e responde outra pergunta.'>?</span></p>")
    else:
        despesa = ("<p style='margin:6px 0 0;font-size:13.5px'>Despesa contratada: "
                   "<span class='marca-dado m-ausente'>nada declarado até aqui</span></p>")

    proprio_txt = (f" Desse total, {brl(proprio)} são recursos do próprio candidato."
                   if proprio else "")

    doadores = ""
    if c.doadores:
        itens = []
        for d in c.doadores[:12]:
            # CNPJ aparece; CPF nao existe no dado (ADR-020). Pessoa fisica sai
            # so' com o nome, que e' o que a prestacao de contas publica.
            if d["proprio"]:
                marca = " <small>(recursos próprios)</small>"
            elif d["cnpj"]:
                marca = f" <small>CNPJ {e(d['cnpj'])}</small>"
            else:
                marca = ""
            vezes = f" · {d['n']} doações" if d["n"] > 1 else ""
            itens.append(
                f"<tr><td>{e(d['nome'] or '—')}{marca}</td>"
                f"<td class='num'>{brl(d['valor'])}{vezes}</td></tr>")
        doadores = f"""
      <h3 style="margin:26px 0 10px;font-size:15px">Maiores doadores declarados</h3>
      <div class="rolagem"><table>
        <thead><tr><th>Doador</th><th>Valor</th></tr></thead>
        <tbody>{''.join(itens)}</tbody></table></div>
      <p style="font-size:12.5px;color:var(--ink-3);margin:8px 0 0">
        Doações repetidas do mesmo doador aparecem <b>somadas</b>, não repetidas —
        quem transferiu cinquenta vezes é um doador, não cinquenta. O CNPJ de
        empresa aparece porque identifica quem financia; o <b>CPF de pessoa física
        nunca é publicado nem armazenado</b> por este projeto.</p>"""

    ate = max((f["ate"] for f in c.financiamento if f["ate"]), default=None)
    corte = (f" Última receita declarada em {ate[8:10]}/{ate[5:7]}/{ate[:4]}."
             if ate else "")

    return f"""<section class="bloco">
      <h2>Financiamento de campanha</h2>
      <p style="font-size:20px;font-weight:700;margin:0 0 4px">{brl(total)}</p>
      <p style="font-size:13px;color:var(--ink-3);margin:0">
        declarados até aqui.{proprio_txt}</p>
      {contra_limite}{despesa}
      <h3 style="margin:26px 0 10px;font-size:15px">De onde veio</h3>
      <div class="rolagem"><table>
        <thead><tr><th>Origem</th><th>Valor</th><th>Fatia</th>
        <th>Doadores</th></tr></thead><tbody>{linhas}</tbody></table></div>
      {doadores}
      <p class="aviso" style="margin:14px 0 0">
        <b>Prestação parcial.</b> O prazo final é posterior a 04/10/2026, então
        estes valores sobem a cada carga e não são comparáveis entre candidaturas
        que prestaram contas em datas diferentes.{corte} Arrecadar muito não é
        mérito nem demérito — por isso não há classificação por valor em lugar
        nenhum deste site.</p>
    </section>"""


# Situacoes de registro em que a pessoa NAO chegou a disputar. Sem isto, uma
# candidatura barrada apareceria como "resultado nao publicado", quando o
# resultado nao existe porque nao houve disputa — sao coisas diferentes.
_NAO_DISPUTOU = {
    "INAPTO": "candidatura indeferida",
    "INDEFERIDO": "candidatura indeferida",
    "INDEFERIDO COM RECURSO": "candidatura indeferida",
    "CASSADO": "registro cassado",
    "RENUNCIA": "renunciou",
    "FALECIDO": "falecido",
}


# Marca de que o resultado NAO veio do TSE — foi apurado dos votos oficiais.
# Aparece na propria celula, e nao so' num rodape: quem le' a linha precisa saber
# de onde veio aquela palavra sem ter que procurar a explicacao.
_APURADO = ("<span class='ajuda' tabindex='0' aria-label='Resultado apurado a "
            "partir dos votos oficiais do TSE e do número de vagas em disputa. "
            "O TSE não publica o desfecho desta eleição no cadastro de "
            "candidaturas.' title='Apurado dos votos oficiais — o TSE não publica "
            "o desfecho desta eleição no cadastro de candidaturas.'>apurado</span>")


def _resultado(t: dict) -> str:
    """O desfecho de uma candidatura, em TRES estados — nunca dois.

    `eleito` e' `NULL` quando o TSE nao publicou `DS_SIT_TOT_TURNO`. Escrever
    "Nao eleito" ali e' uma AFIRMACAO FALSA sobre uma pessoa real, e foi
    exatamente o que este site fez: a ficha do Lula trazia "2006 · Presidente ·
    Nao eleito". Ele foi eleito em segundo turno, com 58,3 milhoes de votos. O
    TSE simplesmente nao publica o resultado de 2006 no `consulta_cand` — para
    nenhum dos 8 candidatos (L-16).

    Sao 13.834 candidaturas de 1998-2022 na mesma situacao.
    """
    derivado = t.get("origem") == "apurado dos votos"
    if t["eleito"] is True:
        return "Eleito" + (_APURADO if derivado else "")
    if t["eleito"] is False:
        return "Não eleito" + (_APURADO if derivado else "")

    # Daqui para baixo o resultado NAO foi publicado. Se a candidatura sequer
    # chegou a' disputa, dizer isso e' mais informativo que dizer "nao consta".
    situacao = (t.get("situacao") or "").strip().upper()
    for chave, rotulo in _NAO_DISPUTOU.items():
        if chave in situacao:
            return f"<span class='marca-dado m-ausente'>{rotulo}</span>"
    return ("<span class='marca-dado m-ausente'>resultado não publicado</span>")


def _chapa(c: Candidato) -> str:
    """Com quem a pessoa concorre (F-21).

    O vinculo nao existe no pacote em lote do TSE: vice e suplente tem
    candidatura propria, e nada nos arquivos diz que uma pertence a' chapa da
    outra. Sem isto, Geraldo Alckmin aparece na base como candidato a
    Vice-Presidente pelo PSB e mais nada.

    Cargo proporcional nao tem chapa — deputado concorre sozinho —, entao o bloco
    simplesmente nao existe nessas fichas, em vez de aparecer vazio.
    """
    if not c.chapa:
        return ""
    cartoes = "".join(
        f"""<div class="parceiro">
        {'<img src="' + e(v['foto']) + '" alt="" loading="lazy">' if v.get('foto') else ''}
        <div><b>{e(v['nome'] or '—')}</b>
          <small>{e(v['completo'] or '')}</small>
          <small>{e(v['cargo'] or '')} · {e(v['partido'] or '—')}</small></div>
      </div>"""
        for v in c.chapa
    )
    titulo = "Vice" if len(c.chapa) == 1 else "Suplentes"
    return f"""<section class="bloco">
      <h2>{titulo} da chapa</h2>
      <div class="chapa">{cartoes}</div>
      <p style="font-size:12.5px;color:var(--ink-3);margin:10px 0 0">
        Quem concorre junto na mesma chapa. O vínculo vem do DivulgaCandContas —
        os arquivos em lote do TSE trazem cada candidatura isolada, sem dizer a
        qual chapa pertence.</p>
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
            # Em eleicao decidida em dois turnos, `votos_nominais` e' a SOMA
            # dos dois — um numero que nao existe em lugar nenhum e que ninguem
            # consegue conferir. Lula em 2022 aparecia com 117.605.503; o numero
            # que o leitor reconhece e' 60.345.999, do segundo turno.
            if t.get("turno") and t["turno"] > 1 and t.get("votos_turno"):
                votos = (f"{t['votos_turno']:,}".replace(",", ".")
                         + f"<small> · {t['turno']}º turno</small>")
            elif t["votos"]:
                votos = f"{t['votos']:,}".replace(",", ".")
            else:
                votos = "—"
            return (f"<tr><td class='num'>{t['ano']}</td><td>{e(t['cargo'])}</td>"
                    f"<td>{e(t['uf'])}</td><td>{e(t['partido']) or '—'}</td>"
                    f"<td>{_resultado(t)}</td><td class='num'>{votos}</td></tr>")

        linhas = "".join(_linha(t) for t in c.trajetoria)
        partes.append(f"""<section class="bloco">
      <h2>Trajetória eleitoral — {len(c.trajetoria)} candidaturas anteriores</h2>
      <div class="rolagem"><table>
        <thead><tr><th>Ano</th><th>Cargo</th><th>UF</th><th>Partido</th><th>Resultado</th><th>Votos</th></tr></thead>
        <tbody>{linhas}</tbody></table></div>
      <p style="font-size:12.5px;color:var(--ink-3);margin:8px 0 0">
        São <b>candidaturas</b>, não mandatos: disputas perdidas também
        aparecem. Série desde 1998.</p>
      <p class="aviso" style="margin:10px 0 0">
        <b>Sobre a eleição de 2006.</b> O TSE não publica o desfecho de 2006 no
        cadastro de candidaturas — nenhum dos candidatos a Presidente daquele ano
        tem resultado na fonte. Onde a linha diz <b>apurado</b>, o resultado foi
        calculado aqui a partir de dois conjuntos oficiais do próprio TSE: a
        votação por turno e o número de vagas em disputa. Em cargo majoritário a
        regra é aritmética — elegem-se os mais votados do último turno. O método
        foi conferido contra os anos em que o TSE <i>publica</i> o resultado:
        acerta 2.636 de 2.640, e 50 de 50 nas eleições presidenciais.
        <b>Cargos proporcionais (deputado) nunca são apurados assim</b>, porque
        cadeira proporcional não vai para quem teve mais voto pessoal.
        Onde se lê <b>resultado não publicado</b>, a fonte é omissa e nada foi
        calculado — é ausência de dado, <b>não</b> derrota.</p>
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

    if c.registros_no_tse > 1:
        # Nao basta esconder a linha repetida: o leitor tem direito de saber que
        # a fonte publica mais de um registro para esta candidatura.
        partes.append(f"""<p class="aviso">
      O TSE publica <b>{c.registros_no_tse} registros</b> para esta candidatura —
      mesma pessoa, mesmo cargo, mesmo número de urna e mesmo partido, com
      sequenciais diferentes. É uma reinscrição em que o registro anterior
      continuou publicado. Esta página mostra um deles; nenhum campo da fonte
      indica qual prevalece.</p>""")

    partes.append(_chapa(c))
    partes.append(_atividade(c))
    partes.append(_financiamento(c))
    partes.append(_indicadores(c))
    partes.append("</div></div>")
    desc = (f"{c.nome_urna}, candidatura a {c.cargo_nome} por {c.sg_uf} em 2026. "
            f"Perfil declarado ao TSE, trajetória eleitoral e plano de governo.")
    return _pagina(f"{c.nome_urna} — {c.cargo_nome} {c.sg_uf}", desc,
                   "".join(partes), quando, c.url, CARGOS[c.cod_cargo][0])


_LIMITE_PARAGRAFO = 900
_FIM_DE_FRASE = re.compile(r"(?<=[.;:!?])" + chr(92) + "s+")


def _e_titulo(bloco: str) -> bool:
    """Linha curta e predominantemente em caixa alta = titulo no PDF original.

    Detectar isso e' FORMATACAO, nao edicao: nenhuma palavra muda, nenhuma ordem
    muda. So' deixa de ser um paragrafo indistinguivel no meio do texto corrido.
    """
    if len(bloco) > 90 or len(bloco) < 3:
        return False
    letras = [ch for ch in bloco if ch.isalpha()]
    if len(letras) < 3:
        return False
    return sum(1 for ch in letras if ch.isupper()) / len(letras) > 0.8


def _quebrar(bloco: str) -> list[str]:
    """Quebra bloco gigante em pedacos legiveis, sempre em fim de frase.

    A extracao devolve trechos de milhares de caracteres sem uma quebra sequer —
    o PDF diagramava em colunas e caixas que viram texto corrido. Reagrupar em fim
    de frase nao altera palavra nem ordem: e' o mesmo que qualquer leitor faz ao
    reformatar um documento para outra tela.
    """
    if len(bloco) <= _LIMITE_PARAGRAFO:
        return [bloco]
    saida, atual = [], ""
    for frase in _FIM_DE_FRASE.split(bloco):
        if atual and len(atual) + len(frase) > _LIMITE_PARAGRAFO:
            saida.append(atual.strip())
            atual = frase
        else:
            atual = (atual + " " + frase).strip()
    if atual.strip():
        saida.append(atual.strip())
    return saida


def _formatar_plano(texto: str) -> str:
    partes = []
    for bruto in texto.split("\n\n"):
        bloco = bruto.strip()
        if not bloco:
            continue
        if _e_titulo(bloco):
            partes.append("<h2>" + e(bloco) + "</h2>")
        else:
            partes.extend("<p>" + e(x) + "</p>" for x in _quebrar(bloco))
    return "".join(partes)


def _pagina_plano(c: Candidato, quando: str) -> str:
    """Plano de governo em pagina propria, com URL propria.

    Nao cabe na ficha: a mediana e' 111 mil caracteres, e enfiar isso num bloco
    empurraria todo o resto para fora da tela. Em pagina propria vira o conteudo
    mais substantivo do site — e o unico lugar onde alguem que busca "o que fulano
    propoe sobre saude" tem onde chegar.

    O texto sai em paragrafos, sem nenhuma edicao. Cabecalho de pagina e quebra
    tortas do PDF aparecem como estao: e' transcricao, nao diagramacao.
    """
    paragrafos = _formatar_plano(c.plano_texto or "")
    palavras = f"{len((c.plano_texto or '').split()):,}".replace(",", ".")
    original = (f'<a href="{e(c.plano_url_pdf)}" rel="nofollow noopener">'
                f'Abrir o PDF original no TSE ↗</a>' if c.plano_url_pdf else "")
    corpo = f"""<a href="{BASE_URL}/{c.caminho}/" style="font-size:13.5px">← {e(c.nome_urna)}</a>
<h1>Plano de governo — {e(c.nome_urna)}</h1>
<p class="sub">{e(c.cargo_nome)} · {e(_UF_NOME.get(c.sg_uf, c.sg_uf))} ·
{e(c.partido_completo)}</p>
<p class="aviso"><b>Transcrição automática do PDF oficial</b> entregue ao TSE:
{c.plano_paginas} páginas, {palavras} palavras. O texto está <b>íntegro e sem
edição</b> — nenhuma palavra foi resumida, corrigida ou reordenada. As quebras
de parágrafo foram refeitas em fim de frase para caber na tela, e títulos em
caixa alta ganharam destaque; cabeçalhos e numeração de página aparecem como
saíram do arquivo. {original}</p>
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
  <input id="busca" type="search" placeholder="Buscar por nome ou número" autocomplete="off">
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
  <input id="busca" type="search" autocomplete="off" disabled
         placeholder="Buscar por nome ou número">
</div>
<p class="contagem" id="contagem">nenhum estado selecionado</p>
<div class="rolagem" style="max-height:none"><table>
  <thead><tr><th></th><th>Nome de urna</th>
  <th title="o número que se digita na urna">Nº</th>
  <th>Partido</th><th>Federação</th><th>Coligação</th><th>Situação</th>
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
    (!q || (d.nome || "").toLowerCase().includes(q)
        || String(d.nr ?? "").startsWith(q)));
  $("contagem").textContent = vis.length.toLocaleString("pt-BR") + " de " +
    dados.length.toLocaleString("pt-BR") + " candidaturas neste estado";
  $("linhas").innerHTML = vis.map(d => `<tr>
    <td class="foto-lista">${{d.foto
      ? `<img src="${{d.foto}}" alt="" loading="lazy" decoding="async">` : ""}}</td>
    <td>${{d.nome ?? ""}}</td>
    <td class="urna-lista">${{d.nr ?? "—"}}</td>
    <td>${{d.partido ?? ""}}</td><td>${{d.fed ?? ""}}</td>
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
</ul>
<h2 style="margin:28px 0 10px">Antes de usar um número daqui</h2>
<p>Cada indicador tem alcance, unidade e ressalvas próprias — e algumas importam
muito: valores em reais estão a <b>preços correntes</b>, a série de mortalidade
infantil <b>termina em 2016</b>, e o TSE <b>não publica</b> o resultado da eleição
de 2006 no cadastro de candidaturas.</p>
<p><a class="cta" href="{BASE_URL}/metodologia/">Metodologia, fontes e glossário
dos indicadores &rarr;</a></p>"""
    return _pagina("Dossiê Eleitoral 2026",
                   "O que cada candidatura de 2026 declarou ao TSE: perfil, trajetória eleitoral "
                   "e plano de governo. Apartidário, com fonte e data em toda tela.",
                   corpo, quando, f"{BASE_URL}/")


# Uma explicacao por indicador, para a pagina de metodologia. O que NAO esta'
# aqui — cobertura, fonte, unidade — vem do proprio lake, para nao envelhecer.
#
# Cada entrada e' (o que mede, como o ano e' formado, ressalva). A ressalva e' a
# parte que importa: e' onde mora a diferenca entre o numero desta pagina e o
# numero que a pessoa viu no jornal.
_NOTAS_INDICADOR: dict[str, tuple[str, str, str]] = {
    "PIB": (
        "Valor de tudo o que foi produzido na unidade da federação no ano.",
        "Já vem anual das Contas Regionais do IBGE.",
        "A preços correntes: a variação <b>inclui a inflação</b> e não é "
        "crescimento real. Divulgado com cerca de dois anos de defasagem."),
    "PIB_PER_CAPITA": (
        "O PIB dividido pela população estimada.",
        "Calculado aqui, a partir de duas tabelas do IBGE.",
        "<b>Não é renda das pessoas</b> — é produção por cabeça. Termina um ano "
        "antes do PIB porque depende também da estimativa populacional."),
    "POPULACAO": (
        "Quantas pessoas o IBGE estima que moram na unidade da federação.",
        "Estimativa anual, publicada em 1º de julho.",
        "É <b>estimativa</b>, não contagem. Nos anos de Censo as duas diferem."),
    "POPULACAO_CENSO": (
        "Contagem do Censo Demográfico, feita de porta em porta.",
        "Decenal — existe apenas para 2022 nesta base.",
        "Mais precisa que a estimativa, e disponível só no ano censitário."),
    "DESOCUPACAO": (
        "Percentual de quem tem 14 anos ou mais, procura trabalho e não encontra.",
        "<b>Média dos quatro trimestres</b> da PNAD Contínua. Um ano com menos de "
        "quatro trimestres publicados não vira ano.",
        "Pode diferir da <i>taxa anual</i> que o IBGE divulga, que é calculada por "
        "outro caminho. Diferenças de duas a três décimas são esperadas."),
    "RENDIMENTO_MEDIO": (
        "Quanto ganha por mês, em média, quem está ocupado.",
        "Média dos trimestres da PNAD Contínua.",
        "<b>É a única série monetária já em valores reais</b> aqui: o IBGE publica "
        "com a inflação descontada. Todas as outras estão a preços correntes."),
    "IPCA": (
        "Índice oficial de inflação ao consumidor.",
        "<b>Acumulado no ano</b> — o valor de dezembro, não a média dos meses.",
        "Média mensal daria aproximadamente metade da inflação real e seria "
        "simplesmente errada."),
    "SELIC": (
        "Taxa básica de juros da economia (Over/Selic).",
        "Média do ano.",
        "Série macroeconômica: existe só para o Brasil, nunca por estado."),
    "HOMICIDIOS": (
        "Mortes por agressão a cada 100 mil habitantes.",
        "Já vem anual do Atlas da Violência.",
        "O IPEA <b>revisa anos anteriores</b> a cada edição, então a série pode "
        "mudar retroativamente entre uma carga e outra."),
    "MORTALIDADE_INFANTIL": (
        "Óbitos de crianças com menos de um ano a cada mil nascidas vivas.",
        "Já vem anual.",
        "<b>A série disponível termina em 2016.</b> Mandatos posteriores aparecem "
        "sem este indicador — não porque não houve mortes, mas porque a fonte não "
        "publicou o dado."),
    "IDEB": (
        "Nota da educação básica pública, de 0 a 10 — anos finais do ensino "
        "fundamental.",
        "Bienal: medido a cada dois anos.",
        "É a série que melhor cabe numa janela de mandato: um mandato de "
        "governador contém duas ou três medições."),
    "IDHM": (
        "Índice de desenvolvimento humano, de 0 a 1.",
        "Decenal — calculado a partir do Censo.",
        "<b>A última medição é de 2010.</b> Nenhum mandato recente é coberto, e "
        "isso não tem conserto pelo lado dos dados: o índice depende do Censo."),
    "RECEITA_ESTADUAL": (
        "Quanto o governo estadual arrecadou no ano, já descontadas as deduções.",
        "Declaração de Contas Anuais entregue ao Tesouro.",
        "A preços correntes. Depende de o estado ter entregue a declaração."),
    "DESPESA_ESTADUAL": (
        "Quanto o governo estadual empenhou no ano.",
        "Declaração de Contas Anuais entregue ao Tesouro.",
        "A preços correntes. É despesa <b>empenhada</b>, não paga."),
    "RESULTADO_ORCAMENTARIO": (
        "Receita menos despesa do governo estadual.",
        "Calculado aqui, a partir das duas séries acima.",
        "<b>Positivo não é bom nem ruim</b>: déficit pode ser investimento, "
        "superávit pode ser gasto que não saiu do papel."),
    "RECEITA_LIQUIDA_UNIAO": (
        "Receita líquida do Governo Central.",
        "Resultado do Tesouro Nacional, tabela 2.1.",
        "<b>Governo Central</b> — Tesouro, Previdência e Banco Central. Não é o "
        "setor público consolidado, que inclui estados e municípios."),
    "DESPESA_PRIMARIA_UNIAO": (
        "Despesa primária do Governo Central.",
        "Resultado do Tesouro Nacional, tabela 2.1.",
        "Primária: exclui juros da dívida."),
    "RESULTADO_PRIMARIO_UNIAO": (
        "Receita menos despesa primária do Governo Central.",
        "Resultado do Tesouro Nacional, tabela 2.1 (acima da linha).",
        "<b>É o resultado cheio, sem ajustes.</b> Não é o mesmo número que se lê "
        "quando o resultado é medido <i>contra a meta fiscal</i>, que exclui itens "
        "que o arcabouço permite excluir — os dois são oficiais e medem coisas "
        "diferentes. Também não inclui estados e municípios."),
}


def _linha_catalogo(ind: dict) -> str:
    """Uma linha da tabela de indicadores, com a cobertura vinda do lake."""
    cod = ind["cod_indicador"]
    nome, _ = _rotulo_indicador(cod, ind["nome"])
    mede, agrega, ressalva = _NOTAS_INDICADOR.get(
        cod, (ind["nome"], "—", "Ver a documentação técnica do projeto."))

    if ind["ano_ini"] is None:
        alcance = "<span class='marca-dado m-ausente'>sem dados</span>"
    elif ind["ano_ini"] == ind["ano_fim"]:
        alcance = str(ind["ano_ini"])
    else:
        alcance = f"{ind['ano_ini']}–{ind['ano_fim']}"

    # 28 unidades = 26 estados + DF + Brasil. Menos que isso e' cobertura parcial,
    # e a tabela precisa dizer, nao esconder.
    n = ind["n_ues"] or 0
    if n >= 28:
        onde = "Brasil e todas as UFs"
    elif ind["tem_br"] and n <= 1:
        onde = "só Brasil"
    else:
        onde = f"{n} unidades"

    return (
        f"<tr><td><b>{e(nome)}</b><br>"
        f"<small>{mede}</small></td>"
        f"<td class='num'>{alcance}<br><small>{e(onde)}</small></td>"
        f"<td><small>{e(str(ind['unidade'] or '—'))} · {agrega}<br>"
        f"{ressalva}</small></td>"
        f"<td><small>{e(str(ind['fonte'] or '—'))}</small></td></tr>")


def _metodologia(quando: str, catalogo: list[dict]) -> str:
    """Pagina de metodologia e LIMITES — o rodape de toda pagina aponta para ca'.

    Existe para dizer o que os numeros NAO dizem. Um site que so' mostra dado e
    esconde a limitacao dele transfere para o leitor um risco que ele nao tem
    como avaliar.
    """
    linhas_catalogo = "".join(_linha_catalogo(i) for i in catalogo)
    corpo = f"""
    <div class="capa">
      <h1>Metodologia, fontes e limites</h1>
      <p class="sub">O que este dossiê mede, de onde vêm os números e onde eles
        não alcançam.</p>
    </div>
    <div class="miolo"><div class="col">

    <section class="bloco">
      <h2>O que este site faz, e o que não faz</h2>
      <p>Ele registra <b>o que foi declarado ao TSE</b> e o coloca ao lado de
        indicadores públicos do período. Não avalia, não classifica e não ordena
        candidatos.</p>
      <ul>
        <li>Não existe ranking de "melhor" ou "pior" em lugar nenhum.</li>
        <li>Nenhum indicador é apresentado como <b>efeito</b> de um mandato — só
          como o que aconteceu <b>durante</b> ele. PIB, desemprego e homicídios
          dependem de fatores muito além do alcance de um governo.</li>
        <li>Não expõe CPF, título de eleitor nem endereço de ninguém — incluindo
          doadores de campanha, cujo CPF é publicado pelo TSE e <b>não</b> é
          armazenado aqui.</li>
        <li>Cor de partido nunca é usada como padrão visual.</li>
      </ul>
    </section>

    <section class="bloco">
      <h2>A eleição de 2006</h2>
      <p class="aviso"><b>O TSE não publica o resultado de 2006 no cadastro de
        candidaturas.</b> Nenhum dos oito candidatos a Presidente daquele ano tem
        o campo de desfecho preenchido na fonte oficial — e o mesmo vale para
        outras 13.834 candidaturas entre 1998 e 2022.</p>
      <p>Isso já produziu um erro neste site: a ficha de um candidato eleito em
        2006 dizia <b>“Não eleito”</b>, porque a ausência de dado estava sendo
        tratada como negativa. O erro esteve publicado e foi corrigido em
        29/08/2026.</p>
      <p>Hoje há três estados possíveis, nunca dois:</p>
      <dl class="campos">
        <div><dt>Eleito / Não eleito</dt><dd>o TSE publicou o desfecho.</dd></div>
        <div><dt>Eleito <span class="marca-dado">apurado</span></dt>
          <dd>o TSE não publicou, e o resultado foi <b>calculado aqui</b> — veja
            abaixo como.</dd></div>
        <div><dt><span class="marca-dado m-ausente">resultado não publicado</span></dt>
          <dd>a fonte é omissa e nada foi calculado. É ausência de dado,
            <b>não</b> derrota.</dd></div>
      </dl>
    </section>

    <section class="bloco">
      <h2>Como o resultado é apurado quando o TSE não publica</h2>
      <p>Só para cargos <b>majoritários</b> — Presidente, Governador e Senador —
        onde a regra é aritmética e não admite interpretação: elegem-se os mais
        votados do último turno realizado. Os dois insumos são oficiais e vêm do
        próprio TSE:</p>
      <dl class="campos">
        <div><dt>Votação por turno</dt><dd>quantos votos cada candidatura teve.</dd></div>
        <div><dt>Vagas em disputa</dt><dd>quantas cadeiras a unidade eleitoral
          elegia naquele ano — o Senado renovou 1 por estado em 2006 e 2 em
          2018.</dd></div>
      </dl>
      <p><b>Cargos proporcionais nunca são apurados assim.</b> Cadeira de
        deputado não vai para quem teve mais voto pessoal: depende de quociente
        eleitoral, quociente partidário e sobras. Aplicar "os mais votados" ali
        produziria uma lista errada com aparência de certa.</p>
      <p><b>O método foi conferido contra os anos em que o TSE publica o
        resultado</b>, onde existe gabarito:</p>
      <div class="rolagem"><table>
        <thead><tr><th>Confronto</th><th>Resultado</th></tr></thead>
        <tbody>
          <tr><td>Candidaturas conferidas</td><td class="num">2.640</td></tr>
          <tr><td>Acertos</td><td class="num">2.636</td></tr>
          <tr><td>Divergências</td><td class="num">4</td></tr>
          <tr><td>Eleições presidenciais</td><td class="num">50 de 50</td></tr>
        </tbody></table></div>
      <p style="font-size:12.5px;color:var(--ink-3);margin:8px 0 0">
        As quatro divergências são cassação e eleição suplementar — casos em que
        quem ocupou a cadeira não foi quem teve mais voto na urna, e que contagem
        nenhuma tem como saber. Onde o TSE publica, <b>o TSE prevalece sempre</b>;
        a apuração só fala onde ele cala.</p>
    </section>

    <section class="bloco">
      <h2>Valores em reais: o que está e o que não está descontado</h2>
      <p class="aviso"><b>PIB, receitas, despesas e resultados orçamentários estão
        a preços correntes.</b> A variação mostrada nas fichas <b>inclui a
        inflação do período</b> e não é crescimento real.</p>
      <p>Um exemplo concreto: entre 2022 e 2023 o PIB do Brasil sobe <b>8,6%</b>
        nestes dados, enquanto o crescimento <i>real</i> medido pelo IBGE foi de
        <b>3,2%</b>. A diferença é inflação, não economia.</p>
      <p>A comparação que <b>faz</b> sentido é a que aparece ao lado de cada
        linha: a variação da unidade da federação contra a do Brasil no mesmo
        intervalo. A inflação afeta as duas igualmente, então a comparação
        continua válida mesmo com o número absoluto inflado.</p>
      <p>Não deflacionamos a série aqui de propósito: o deflator correto do PIB
        não é o IPCA, e usar o índice errado produziria um "valor real" que
        parece rigoroso e não é. <b>Rendimento médio do trabalho</b> é a exceção —
        o IBGE já o publica em termos reais.</p>
    </section>

    <section class="bloco">
      <h2>Glossário dos indicadores</h2>
      <p>Um por linha: o que mede, até onde a série alcança, como o valor do ano
        é formado e de onde vem. <b>A cobertura desta tabela é lida dos próprios
        dados a cada geração do site</b> — se uma série avançar ou parar, a
        tabela muda junto.</p>
      <div class="rolagem"><table class="glossario">
        <thead><tr><th>Indicador</th><th>Alcance</th>
        <th>Unidade, agregação e ressalvas</th><th>Fonte</th></tr></thead>
        <tbody>{linhas_catalogo}</tbody></table></div>
      <p style="font-size:12.5px;color:var(--ink-3);margin:10px 0 0">
        Nenhum valor é estendido, estimado ou projetado para cobrir o intervalo
        que a fonte não publica. Onde a série termina, a ficha fica sem o
        indicador — e diz isso.</p>
    </section>

    <section class="bloco">
      <h2>O que este dossiê não tem</h2>
      <ul>
        <li><b>Dívida pública</b> (DBGG) e outras estatísticas do Banco Central.</li>
        <li><b>Orçamento por ministério</b> — só o resultado consolidado da União
          e os orçamentos estaduais.</li>
        <li><b>Programas de governo</b> (Bolsa Família, Minha Casa Minha Vida):
          são políticas, não indicadores, e medir a execução delas exigiria uma
          fonte que este projeto não ingere.</li>
        <li><b>Resultado das eleições de 2026</b>, que ainda não ocorreram.</li>
        <li><b>Atividade legislativa do Senado</b> — a fonte não publica marca de
          proponente, e uma contagem sem esse filtro pareceria comparável à da
          Câmara sem ser.</li>
      </ul>
    </section>

    <section class="bloco">
      <h2>Prestação de contas de campanha</h2>
      <p>O prazo legal de prestação vai até <b>depois de 04/10/2026</b>, então a
        cobertura cresce a cada dia. Uma candidatura que não aparece
        <b>não declarou zero</b> — não declarou nada, e a ficha diz exatamente
        isso.</p>
      <p>O nome do doador é publicado porque é dele que trata a prestação de
        contas. <b>O CPF não</b>: o TSE o publica em texto puro, e aqui ele é
        substituído por um código irreversível antes de ser gravado. CNPJ
        aparece legível — identifica empresa, não pessoa.</p>
    </section>

    <section class="bloco">
      <h2>Erros</h2>
      <p>Este site é gerado por um pipeline aberto, com 240 verificações
        automáticas sobre os dados. Elas não pegam tudo — o erro de 2006 descrito
        acima passou por todas elas e foi encontrado por um leitor.</p>
      <p>O código, os testes e o registro de cada decisão estão públicos em
        <a href="https://github.com/girocoju/dossie-eleitoral">github.com/girocoju/dossie-eleitoral</a>.
        Encontrou um número errado? Abra uma issue — a correção e o motivo dela
        ficam registrados lá.</p>
    </section>

    </div></div>"""
    return _pagina("Metodologia e fontes", "Como o Dossiê Eleitoral 2026 é feito: "
                   "fontes, limites dos dados e o que os números não dizem.",
                   corpo, quando, f"{BASE_URL}/metodologia/", "metodologia")


def _sitemap(majoritarios: list[Candidato], quando: str) -> str:
    urls = [f"{BASE_URL}/", f"{BASE_URL}/metodologia/"]
    urls += [f"{BASE_URL}/{s}/" for s, _, _ in CARGOS.values()]
    urls += [f"{BASE_URL}/{s}/" for s, _ in PROPORCIONAIS.values()]
    urls += [c.url for c in majoritarios]
    urls += [f"{c.url}plano/" for c in majoritarios if c.plano_texto]
    corpo = "".join(f"  <url><loc>{e(u)}</loc></url>\n" for u in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{corpo}</urlset>\n")


def escrever_site(destino: Path, majoritarios: list[Candidato],
                  proporcionais: dict[str, list[dict]], quando: str, catalogo: list[dict]) -> None:
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

    grava("metodologia/index.html", _metodologia(quando, catalogo))
    grava("sitemap.xml", _sitemap(majoritarios, quando))
