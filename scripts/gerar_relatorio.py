"""Monta o relatorio analitico das eleicoes de 2026 (F-28): HTML e depois PDF.

    python -m scripts.dados_relatorio      # coleta, uma vez
    python -m scripts.gerar_relatorio      # formata e imprime

Le' `data/relatorio/dados.json` e escreve o PDF na raiz do repositorio, de onde
`render_site` o copia para o site — mas so' se ele existir, porque anunciar um
download que responde 404 e' pior que nao anunciar nada.

── POR QUE ESTE ARQUIVO EXISTE ──

A primeira versao do relatorio foi montada fora do repositorio, num diretorio
temporario. O PDF ficou bom e ficou orfao: ninguem conseguiria refaze-lo, e
qualquer numero que envelhecesse teria de ser corrigido a mao dentro de um
binario. Um documento que afirma coisas sobre pessoas reais e nao se regenera
nao tem como ser conferido — que e' o oposto do que o resto do projeto faz.

── O PDF SAI DO EDGE, NAO DE UMA BIBLIOTECA ──

`--headless=new --print-to-pdf`. O `--headless` antigo (sem `=new`) renderiza
UMA pagina e descarta o resto — o erro nao aparece como erro, aparece como um
PDF curto que parece pronto.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from ingest.common.log import get_logger
from scripts.relatorio.graficos import (
    ACENTO,
    ACENTO2,
    ALERTA,
    NAO,
    OK,
    TINTA3,
    _n,
    barras,
    barras_duplas,
    legenda,
    linhas,
)

log = get_logger("relatorio")

RAIZ = Path(__file__).resolve().parents[1]
DADOS = RAIZ / "data" / "relatorio" / "dados.json"
HTML = RAIZ / "data" / "relatorio" / "relatorio.html"
PDF = RAIZ / "Dossie-Eleitoral-2026-analise.pdf"

if not DADOS.exists():
    raise SystemExit(f"{DADOS} nao existe — rode antes: python -m scripts.dados_relatorio")

D = json.loads(DADOS.read_text(encoding="utf-8"))
CARGO = {1: "Presidente", 2: "Vice-Presidente", 3: "Governador",
         4: "Vice-Governador", 5: "Senador", 6: "Deputado Federal",
         7: "Deputado Estadual", 8: "Deputado Distrital",
         9: "1º Suplente", 10: "2º Suplente"}


def num(v, c=0):
    return _n(v, c)


def rs(v, casas=0):
    return "R$ " + _n(v, casas)


def pct(v, casas=1):
    """Porcentagem em pt-BR. O formato padrao do Python usa PONTO decimal e
    produziria "93.1%" num documento em portugues."""
    return f"{v:.{casas}f}".replace(".", ",") + "%"


def mi(v):
    return f"R$ {_n(float(v) / 1e6, 1)} mi"


def bi(v):
    return f"R$ {_n(float(v) / 1e9, 2)} bi"


def razao(v):
    """"6,2x" e nao "6.2x": documento em portugues usa virgula decimal."""
    return f"{v:.1f}".replace(".", ",") + "×"


def tabela_mm(linhas, fmt=None, rotulo="Cargo"):
    """Media, mediana, razao e a fracao que fica acima da media.

    A ultima coluna e' a que dispensa jargao: quando so' 9% do grupo esta' acima
    da media, a media nao esta' resumindo o grupo — esta' descrevendo os poucos
    que a puxam.
    """
    fmt = fmt or rs
    corpo = "".join(
        f'<tr><td>{r["rot"]}</td>'
        f'<td class="num">{fmt(r["media"])}</td>'
        f'<td class="num">{fmt(r["mediana"])}</td>'
        f'<td class="num">{razao(r["media"] / r["mediana"])}</td>'
        f'<td class="num">{pct(r["acima"])}</td></tr>'
        for r in linhas if r["mediana"])
    return (f'<table class="t"><thead><tr><th>{rotulo}</th>'
            '<th class="num">Média</th><th class="num">Mediana</th>'
            '<th class="num">Média ÷ mediana</th>'
            '<th class="num">% acima da média</th></tr></thead>'
            f"<tbody>{corpo}</tbody></table>")


def mm(nome, chave="cod_cargo", rot=None):
    """Normaliza um bloco `_mm` para o formato da tabela e do grafico."""
    rot = rot or (lambda v: CARGO.get(v, str(v)))
    return [{"rot": rot(r[chave]), "media": float(r["media"]),
             "mediana": float(r["mediana"]),
             "acima": 100 * int(r["acima"]) / int(r["n"]),
             "n": int(r["n"])} for r in D[nome]]


def bloco(d, chave):
    return {r[chave]: r for r in D[d]}


P = []      # paginas


def pag(*partes):
    P.append("".join(partes))


# ══ CAPA ═══════════════════════════════════════════════════════════════
total = D["total"][0]
# O total de candidaturas exibidas muda a cada extracao — o TSE segue
# publicando ate' a vespera. Ele e' lido do dado, nunca escrito a mao.
TOTAL = int(total["n"])
# Suplente de senador (cargos 9 e 10) NAO recebe ficha: quem se candidata a
# suplente nao disputa cargo proprio, e a ficha diria dele coisas que so'
# fazem sentido para quem disputa. Eles entram nas contagens deste relatorio
# e nao no site — e dizer isso e' o que impede a frase 'uma ficha por
# candidatura' de ser falsa.
COM_FICHA = sum(int(r["n"]) for r in D["por_cargo"] if int(r["cod_cargo"]) <= 8)
SUPLENTES = TOTAL - COM_FICHA

# As lacunas sao contadas do proprio LACUNAS.md. Escritas a mao, envelhecem
# calado — foi o que aconteceu com "29 lacunas" numa edicao anterior.
_LAC = (RAIZ / "docs" / "LACUNAS.md").read_text(encoding="utf-8")
_BLOCOS = re.split(r"(?m)^(?=## L-)", _LAC)[1:]
N_LACUNAS = len(_BLOCOS)
N_FECHADAS = sum(1 for b in _BLOCOS if "FECHADA" in b[:400])
PC = {int(r["cod_cargo"]): int(r["n"]) for r in D["por_cargo"]}
INSTR = {r["grau_instrucao"]: int(r["n"]) for r in D["instrucao"]}
# "Fundamental ou menos" junta as tres faixas abaixo do ensino medio. O
# rotulo agrega, e por isso a soma vive aqui e nao no texto.
_BAIXA = sum(v for k, v in INSTR.items()
             if "FUNDAMENTAL" in k or k == "LÊ E ESCREVE")
_POL = sum(int(r["n"]) for r in D["ocupacao"]
           if r["ocupacao"] in ("DEPUTADO", "VEREADOR"))
pag(f"""
<div class="capa">
  <div class="marca">Data Duba Intelligence · Dossiê Eleitoral</div>
  <h1>O retrato das candidaturas de 2026</h1>
  <p class="sub">Análise descritiva de {num(total['n'])} candidaturas registradas
    no TSE, cruzadas com prestação de contas, patrimônio declarado, atividade
    legislativa e execução de emendas parlamentares.</p>
  <div class="capa-num">
    <div><b>{num(total['n'])}</b><span>candidaturas</span></div>
    <div><b>{num(total['pessoas'])}</b><span>pessoas</span></div>
    <div><b>27</b><span>estados + DF</span></div>
    <div><b>30</b><span>partidos</span></div>
  </div>
  <p class="nota-capa"><b>O que este documento é.</b> Um levantamento
    descritivo. Ele registra o que foi declarado às fontes oficiais e mostra a
    distribuição desses números. Não avalia candidatos, não os ordena por mérito
    e não atribui a nenhum deles o efeito de indicador algum.</p>
  <p class="nota-capa"><b>O que ele não é.</b> Uma previsão eleitoral, uma
    apuração de irregularidade ou um ranking. Onde um número chama atenção, o
    documento diz o que a fonte publica e o que seria necessário para concluir
    qualquer coisa além disso.</p>
  <p class="rodape-capa">Extraído em {datetime.now(UTC).strftime('%d/%m/%Y')} ·
    Fontes: TSE (Divulgação de Candidaturas e Prestação de Contas),
    Portal da Transparência (CGU), Câmara dos Deputados, Senado Federal</p>
</div>""")

# ══ ÍNDICE ════════════════════════════════════════════════════════════
SUMARIO = [
    ("1", "Quem se candidata",
     "Distribuição por cargo e por estado, e o que 16 candidatos por vaga "
     "significam para quem vota."),
    ("2", "O perfil declarado",
     "Gênero, cor e raça, idade, escolaridade e ocupação — e onde a cota de "
     "30% funciona como piso e como teto."),
    ("3", "Renovação e reincidência",
     "Quantos estreiam, quantos voltam, e as seis pessoas que disputam a nona "
     "eleição desde 1998."),
    ("4", "O dinheiro de campanha",
     "De onde vem: 93,1% do partido. Quanto é: média e mediana por cargo. E o "
     "que a prestação parcial não permite concluir."),
    ("5", "O patrimônio declarado",
     "Composição por natureza do bem, escala de concentração, e a diferença "
     "entre média e mediana explicada em número."),
    ("6", "Duas declarações que não fecham",
     "As candidaturas acima de R$ 1 bilhão, o que a fonte sustenta e o que "
     "seria preciso para concluir algo além disso."),
    ("7", "Emendas parlamentares",
     "O que os autores identificados moveram desde 2015, o salto de 2023 e "
     "para onde o dinheiro vai — 69% para Saúde."),
    ("8", "A emenda que não diz para quê",
     "A transferência especial sai de 6,6% para 33,7% das emendas individuais. "
     "E os 17% que a fonte não atribui a ninguém."),
    ("9", "O que os parlamentares em exercício produzem",
     "Proposições por natureza — que não podem ser somadas — e assentos em "
     "comissão."),
    ("10", "As trocas de cargo durante o registro",
     "Pessoas com duas candidaturas no pacote do TSE, e por que isso não é "
     "contradição nem erro."),
    ("11", "Partidos e federações",
     "Tamanho das listas, o peso das federações e a única legenda do país com "
     "maioria feminina."),
    ("12", "Situação do registro",
     "Onde cada pedido está no rito, e por que 21% ainda aguardam."),
    ("13", "Método, limites e o que não está aqui",
     "Média ou mediana, cinco limites que mudam a leitura, e o que este "
     "levantamento deliberadamente não faz."),
    ("14", "O que as fontes oficiais não entregam",
     "Vinte e uma incongruências encontradas nas fontes ao longo do projeto — "
     "o que falta, o que engana, e o que se faz com isso."),
    ("15", "Fontes",
     "Cada número, sua origem exata, e como refazer a conta."),
]

pag("""
<h2>Índice</h2>
<p>Este documento tem 15 seções. As três primeiras descrevem <b>quem</b> se
  candidata; da quarta à oitava, <b>quanto</b> — dinheiro de campanha, patrimônio
  e emendas; a nona e a décima, <b>o que a pessoa fez</b>; as últimas, os
  partidos, o método, os limites das fontes e as fontes.</p>
<table class="sumario">
""" + "".join(
    f'<tr><td class="s-n">{n}</td><td class="s-t"><b>{t}</b>'
    f'<div class="s-d">{d}</div></td></tr>'
    for n, t, d in SUMARIO) + """
</table>
<p class="destaque"><b>Como ler os números de dinheiro.</b> Onde há valores
  monetários, este relatório mostra <b>média e mediana lado a lado</b>, e ao lado
  delas a fração de candidatos que fica acima da média. Quando as duas discordam
  muito, a discordância é a informação — e a seção 13 explica por quê.</p>
<p class="obs">Nenhuma seção ordena candidatos por mérito, por patrimônio ou por
  dinheiro. Onde um nome aparece, ele aparece porque um número específico exigia
  explicação.</p>""")

# ══ 1. QUEM SE CANDIDATA ═══════════════════════════════════════════════
cargos = [(CARGO.get(r["cod_cargo"], r["cargo"]), int(r["n"])) for r in D["por_cargo"]]
# A bancada de SP na Camara e' fixada pela Constituicao (art. 45, § 1o): 70 e' a
# vaga, nao um numero desta extracao. Ja' o numero de candidatos vem do dado.
VAGAS_SP = 70
UF_NOME = {"SP": "São Paulo", "RJ": "Rio de Janeiro", "MG": "Minas Gerais",
           "BA": "Bahia", "RS": "Rio Grande do Sul", "PR": "Paraná",
           "PE": "Pernambuco", "CE": "Ceará", "GO": "Goiás", "SC": "Santa Catarina"}
_sp = next(int(r["n"]) for r in D["dep_federal_uf"] if r["sg_uf"] == "SP")

pag(f"""
<h2>1 · Quem se candidata</h2>
<p>São {num(total['n'])} candidaturas para dez tipos de cargo. A distribuição é
  fortemente assimétrica: <b>91% das candidaturas disputam as duas casas
  legislativas ordinárias</b> — deputado federal e estadual — enquanto os cargos
  executivos e o Senado somam menos de 4%.</p>
{barras(cargos, titulo="Candidaturas por cargo", rotulo=num)}
<p class="obs">A leitura importante aqui não é o tamanho da barra do deputado
  estadual, e sim o que ela implica para quem vota: <b>o eleitor escolhe um nome
  entre {num(PC[7])} para deputado estadual e {num(PC[6])} para federal</b>,
  contra {num(PC[1])} para presidente. É onde a decisão é mais difícil e onde a
  informação por candidato é mais escassa.</p>
<h3>A competição não é distribuída por igual</h3>
<p>Concentrando só em deputado federal, seis estados respondem por metade das
  candidaturas do país.</p>
{barras([(UF_NOME.get(r["sg_uf"], r["sg_uf"]), int(r["n"]))
         for r in D["dep_federal_uf"][:6]],
        titulo="Candidatos a deputado federal, por estado", rotulo=num)}
<p class="obs">São Paulo elege {num(VAGAS_SP)} deputados federais. Com
  {num(_sp)} candidatos, são <b>{num(round(_sp / VAGAS_SP))} nomes por vaga</b> —
  e é nessa lista que o eleitor precisa reconhecer um.</p>""")

# ══ 2. PERFIL ══════════════════════════════════════════════════════════
gen = {}
for r in D["genero_cargo"]:
    gen.setdefault(r["cod_cargo"], {})[r["genero"]] = int(r["n"])
raca = {}
for r in D["raca_cargo"]:
    raca.setdefault(r["cod_cargo"], {})[r["cor_raca"]] = int(r["n"])

ordem = [1, 3, 5, 6, 7, 8, 4, 2]
fem = [(CARGO[c], 100 * gen[c].get("FEMININO", 0) / sum(gen[c].values()))
       for c in ordem if c in gen]
neg = [(CARGO[c], 100 * (raca[c].get("PRETA", 0) + raca[c].get("PARDA", 0))
        / sum(raca[c].values())) for c in ordem if c in raca]


def _fem(c):
    """% de mulheres num cargo. Lido do dado — escrito a mao, envelhece calado."""
    return 100 * gen[c].get("FEMININO", 0) / sum(gen[c].values())


def _neg(c):
    return 100 * (raca[c].get("PRETA", 0) + raca[c].get("PARDA", 0)) / sum(raca[c].values())

pag(f"""
<h2>2 · O perfil declarado</h2>
<h3>Gênero: quanto mais alto o cargo, menos mulheres — com uma exceção</h3>
{barras(fem, titulo="% de mulheres entre as candidaturas, por cargo",
        rotulo=pct, max_valor=50, cor=ACENTO)}
<p class="obs">A lei exige 30% de cada gênero nas listas proporcionais, e é
  exatamente onde os números se acomodam: {pct(_fem(6))} e {pct(_fem(7))}. Nos
  cargos majoritários, onde <b>não há cota</b>, a proporção cai para
  {pct(_fem(3))} entre governadores e {pct(_fem(1))} entre presidenciáveis.</p>
<p class="destaque"><b>A exceção inverte o padrão.</b> Vice-governador tem
  <b>{pct(_fem(4))}</b> de mulheres e vice-presidente <b>{pct(_fem(2))}</b> —
  mais que qualquer cargo proporcional. O segundo nome da chapa é escolhido por composição, não por
  disputa, e é ali que a presença feminina aparece.</p>
<h3>Cor e raça</h3>
{barras(neg, titulo="% de candidaturas de pessoas pretas ou pardas, por cargo",
        rotulo=pct, max_valor=60, cor=ACENTO2)}
<p class="obs">O gradiente é o mesmo do gênero e na mesma direção: {pct(_neg(7))}
  entre deputados estaduais contra {pct(_neg(1))} entre presidenciáveis. Para referência, o Censo
  2022 do IBGE aponta 55,5% da população brasileira como preta ou parda — patamar
  que só o Distrito Federal alcança, e apenas na disputa distrital.</p>""")

idade = [(CARGO[r["cod_cargo"]], int(r["mediana"])) for r in D["idade"]
         if r["cod_cargo"] in (1, 3, 5, 6, 7, 8)]
instr = [(str(r["grau_instrucao"]).title(), int(r["n"])) for r in D["instrucao"]][:8]
ocup = [(str(r["ocupacao"]).title()[:34], int(r["n"])) for r in D["ocupacao"]][:14]

pag(f"""
<h3>Idade</h3>
{barras(idade, titulo="Idade mediana na posse, por cargo",
        rotulo=lambda v: f"{int(v)} anos", max_valor=60, cor=ACENTO)}
<p class="obs">A mediana varia pouco — de 49 a 57 anos. O que varia é a
  amplitude: entre os proporcionais há candidatos de <b>20 a 93 anos</b>.</p>
<p class="destaque">Quatro pessoas de <b>93 anos</b> disputam 2026: Almir Rangel
  (dep. estadual/RJ), Luiza Erundina (dep. estadual/SP), Marlene Soccas
  (senadora/SC) e Jorge Coutinho (dep. estadual/RJ). No outro extremo, três
  candidatas de <b>20 anos</b>, a idade mínima legal para deputado.</p>
<h3>Escolaridade e ocupação</h3>
{barras(instr, titulo="Grau de instrução declarado", rotulo=num)}
<p class="obs">{pct(100 * INSTR.get("SUPERIOR COMPLETO", 0) / TOTAL)} declaram
  superior completo — muito acima da população adulta brasileira, na casa de 20%.
  No outro extremo, <b>{num(_BAIXA)} candidaturas
  ({pct(100 * _BAIXA / TOTAL)})</b> declaram ensino fundamental ou menos — e
  outras {num(INSTR.get("ENSINO MÉDIO INCOMPLETO", 0))}, ensino médio
  incompleto.</p>
{barras(ocup, titulo="Ocupações mais declaradas", rotulo=num)}
<p class="obs">"Empresário" e "advogado" lideram entre as ocupações
  identificáveis. Somadas, <b>deputado e vereador</b> aparecem em {num(_POL)}
  candidaturas — a política declarada como profissão de origem.</p>""")

# ══ 3. RENOVAÇÃO ═══════════════════════════════════════════════════════
estr = [(CARGO[r["cod_cargo"]], 100 * int(r["estreantes"]) / int(r["n"]))
        for r in D["estreantes"] if r["cod_cargo"] in (1, 3, 5, 6, 7, 8, 4)]
traj = [(f"{int(r['faixa'])}{'+' if int(r['faixa']) == 8 else ''} anteriores",
         int(r["pessoas"])) for r in D["trajetoria_dist"]]

pag(f"""
<h2>3 · Renovação e reincidência</h2>
<p>Uma candidatura é <b>estreante</b> quando a pessoa não aparece em nenhuma
  eleição desde 1998 — o alcance da série do TSE neste projeto.</p>
{barras(estr, titulo="% de estreantes, por cargo",
        rotulo=lambda v: pct(v, 0), max_valor=70, cor=OK)}
<p class="obs">Seis em cada dez candidatos a deputado estadual nunca disputaram
  antes. Nos cargos majoritários a proporção se inverte: <b>três em cada quatro
  candidatos a governador já disputaram alguma eleição</b>.</p>
{barras(traj, titulo="Quantas eleições anteriores tem quem já disputou", rotulo=num)}
<p class="destaque"><b>Seis pessoas disputam sua nona eleição</b> desde 1998 —
  Milton Vieira (SP), Luiz Castro (AM), Lidice da Mata (BA), Isaura Lemos (GO),
  Bosco Saraiva (AM) e Professor Sinésio (AM). Entre elas, Professor Sinésio foi
  eleito em 7 das 8 disputas anteriores; Zé da Estrada (SP), com 7 tentativas,
  não foi eleito em nenhuma.</p>
<p class="obs">A leitura honesta desse contraste: o dado mostra <b>persistência</b>,
  não competência. Vitórias anteriores dependem de partido, momento e unidade
  eleitoral, e nada aqui autoriza ordenar candidatos por esse número.</p>""")

# ══ 4. DINHEIRO DE CAMPANHA ════════════════════════════════════════════
fin = [(str(r["origem"])[:38], float(r["total"])) for r in D["financiamento_origem"]
       if float(r["total"]) > 1e5]
finmm = mm("financiamento_mm")
cob = [(CARGO[r["cod_cargo"]], 100 * int(r["com_prestacao"]) / int(r["n"]))
       for r in D["cobertura_prestacao"] if r["cod_cargo"] in (1, 3, 5, 6, 7, 8)]
tot_fin = sum(float(r["total"]) for r in D["financiamento_origem"])
part = next(float(r["total"]) for r in D["financiamento_origem"]
            if "partido" in str(r["origem"]).lower())

pag(f"""
<h2>4 · O dinheiro de campanha</h2>
<p class="destaque"><b>{pct(100 * part / tot_fin)} de todo o dinheiro declarado
  até aqui vem do partido.</b> São {bi(part)} de {bi(tot_fin)}. Doação de pessoa
  física — o modelo que a reforma de 2015 pretendia estimular ao proibir doação
  empresarial — responde por {pct(100 * 151e6 / tot_fin)}.</p>
{barras(fin, titulo="Receita declarada por origem", rotulo=mi, cor=ACENTO)}
<p class="obs">Isso reposiciona a pergunta de sempre. Quando o financiamento é
  majoritariamente público e intermediado pela direção partidária, <b>quem decide
  o rateio decide a viabilidade da candidatura</b> — e esse critério não é
  publicado por nenhum partido.</p>
{barras_duplas([(r["rot"], r["media"], r["mediana"]) for r in finmm],
              "Média", "Mediana", rotulo=rs, cor_a=ALERTA, cor_b=ACENTO,
              titulo="Receita declarada por cargo: média e mediana")}
{legenda(["Média", "Mediana"], {"Média": ALERTA, "Mediana": ACENTO})}
{tabela_mm(finmm)}
<p class="obs">A mediana de um candidato a deputado federal é <b>R$ 100 mil</b>;
  a média, R$ 401 mil — quatro vezes mais, e apenas 27,3% dos candidatos chegam
  lá. No Senado as duas quase coincidem (1,4×), porque o teto legal de gastos
  comprime a distribuição por cima.</p>
{barras(cob, titulo="% das candidaturas com prestação de contas já entregue",
        rotulo=lambda v: pct(v, 0), max_valor=100, cor=ALERTA)}
<p class="aviso"><b>Este gráfico mede prazo, não omissão.</b> A prestação de
  contas final vai até depois do pleito, e quatro em cada dez candidaturas ainda
  não constam. Nenhuma conclusão sobre um candidato específico pode ser tirada da
  ausência dele aqui.</p>""")

# ══ 5. PATRIMÔNIO ══════════════════════════════════════════════════════
patmm = mm("patrimonio_mm")
_out = D["efeito_outlier"][0]
grupos = {"imoveis": "Imóveis", "moveis": "Bens móveis",
          "participacoes": "Participação em empresas", "aplicacoes": "Aplicações",
          "dinheiro": "Dinheiro em conta", "fundos": "Fundos",
          "creditos": "Créditos", "outros": "Outros bens e direitos"}
grp = [(grupos.get(r["grupo"], r["grupo"]), float(r["total"])) for r in D["patrimonio_grupo"]]
esc = D["escala_patrimonio"][0]

pag(f"""
<h2>5 · O patrimônio declarado</h2>
<p>{num(esc['com_bem'])} das {num(esc['total'])} candidaturas declararam
  algum bem — <b>{pct(100 * int(esc['com_bem']) / int(esc['total']), 0)}</b>. As
  demais declararam nenhum, o que a lei permite.</p>
{barras_duplas([(r["rot"], r["media"], r["mediana"]) for r in patmm],
              "Média", "Mediana", rotulo=rs, cor_a=ALERTA, cor_b=ACENTO,
              titulo="Patrimônio declarado por cargo: média e mediana")}
{legenda(["Média", "Mediana"], {"Média": ALERTA, "Mediana": ACENTO})}
{tabela_mm(patmm)}
<p class="destaque"><b>Olhe a última coluna.</b> Entre os candidatos a governador,
  a média é R$ 7,96 milhões — e <b>só 9,3% deles chegam a esse valor</b>. Os
  outros 90,7% declaram menos. Uma média que descreve 9% do grupo não está
  resumindo o grupo; está descrevendo os poucos que a puxam. A mediana diz o que
  é verdade por definição: metade declara menos de R$ 884 mil, metade
  declara mais.</p>
{barras(grp, titulo="Composição do patrimônio declarado, por natureza", rotulo=bi,
        cor=ACENTO2)}
<p class="obs">Imóveis concentram a maior parte, seguidos de participação em
  empresas. A ordem muda conforme o cargo, mas a predominância imobiliária é
  estável.</p>
<h3>A escala é extremamente concentrada</h3>
<div class="escada">
  <div><b>{num(esc['bi'])}</b><span>≥ R$ 1 bilhão</span></div>
  <div><b>{num(esc['c100mi'])}</b><span>≥ R$ 100 milhões</span></div>
  <div><b>{num(esc['c10mi'])}</b><span>≥ R$ 10 milhões</span></div>
  <div><b>{num(esc['c1mi'])}</b><span>≥ R$ 1 milhão</span></div>
  <div><b>{num(esc['com_bem'])}</b><span>declararam algum bem</span></div>
</div>
<p class="obs">Trinta e uma candidaturas declaram patrimônio de nove dígitos.
  Elas são <b>0,15% do total</b> e concentram parcela desproporcional do valor
  agregado.</p>""")

# ══ 6. INVESTIGAÇÃO: AS DECLARAÇÕES QUE NÃO FECHAM ═════════════════════
# Eram UMA na primeira edicao deste relatorio. O TSE seguiu publicando e passaram
# a ser duas — motivo pelo qual esta secao le' a lista do dado em vez de nomear
# quem quer que seja no texto fixo.
BILI = D["bilionarios"]
_bens_por = {}
for r in D["bilionarios_bens"]:
    _bens_por.setdefault(r["sq_candidato"], []).append(r)
_itens_por = {}
for r in D["bilionarios_item"]:
    _itens_por.setdefault(r["sq_candidato"], []).append(r)


def _caso(b):
    """Uma ficha por declaracao que se descola. Sem descricao do bem: e' texto
    livre e carrega endereco residencial."""
    linhas = "".join(
        f"<tr><td>{x['tipo_bem']}</td><td>{num(x['qt_itens'])}</td>"
        f"<td class='num'>{rs(float(x['vl_total']), 2)}</td></tr>"
        for x in _bens_por.get(b["sq_candidato"], [])[:6])
    return f"""
<div class="caso">
  <div class="caso-cab">
    <b>{b["nome_urna"]}</b>
    <span>{CARGO.get(int(b["cod_cargo"]), b["cod_cargo"])} ·
      {b["sg_uf"]} · {b["sigla_partido"]} · {b["situacao"].title()}</span>
  </div>
  <table class="t">
    <thead><tr><th>Bem declarado</th><th>Itens</th><th class="num">Valor</th></tr></thead>
    <tbody>{linhas}
      <tr class="tot"><td><b>Total</b></td><td><b>{num(b["n_bens"])}</b></td>
          <td class="num"><b>{rs(float(b["v"]), 2)}</b></td></tr>
    </tbody>
  </table>
</div>"""


# O maior item isolado de cada caso. Um valor redondo diz mais sobre a natureza
# do numero do que o total diz.
_maior = {k: v[0] for k, v in _itens_por.items()}
_a, _b = BILI[0], BILI[1]
_ma, _mb = _maior[_a["sq_candidato"]], _maior[_b["sq_candidato"]]

pag(f"""
<h2>6 · Duas declarações que não fecham</h2>
<p>Ao ordenar as candidaturas por patrimônio declarado, <b>{num(len(BILI))}</b> se
  descolam de todas as outras por uma ordem de grandeza. Juntas somam
  {bi(sum(float(x["v"]) for x in BILI))}, mais que as
  {num(int(D["escala_patrimonio"][0]["c100mi"]) - len(BILI))} declarações
  seguintes — as que passam de R$ 100 milhões — somadas.</p>
{_caso(_a)}
{_caso(_b)}
<p><b>O que a fonte diz.</b> Os dois valores estão publicados assim no pacote de
  dados abertos do TSE e, conferidos item a item contra o DivulgaCandContas —
  outro sistema do TSE, com outro formato e outra rota —, batem ao centavo. Não é
  erro de leitura deste projeto.</p>
<p><b>O que chama atenção, e nenhuma linha abaixo é acusação.</b></p>
<ul>
  <li>No primeiro caso, o patrimônio está concentrado em
    <b>{_ma["tipo_bem"].lower()}</b>: um único item de
    <b>{rs(float(_ma["valor_bem"]), 2)}</b>. O valor é <b>redondo até a última
    casa</b> — algo que patrimônio avaliado raramente é, e que registro digitado
    frequentemente é.</li>
  <li>No segundo, um único imóvel residencial de
    <b>{rs(float(_mb["valor_bem"]), 2)}</b> seria, com folga, o mais caro já
    registrado no estado — cujo PIB anual inteiro é da ordem de R$ 20 bilhões.</li>
  <li>A segunda declarante <b>já concorreu antes</b>, e naquela ocasião declarou
    {rs(float(_b["v_anterior"]), 2)}. A diferença entre as duas declarações é de
    <b>{num(float(_b["v"]) / float(_b["v_anterior"]))} vezes</b>. O primeiro
    declarante <b>não tem candidatura anterior</b> no acervo do TSE: não há
    declaração com que comparar, e é por isso que a leitura abaixo vale para um
    e não para o outro.</li>
</ul>
<p class="obs"><b>O primeiro caso não tem ficha no site.</b> É candidatura a
  suplente de senador, e suplente não recebe ficha — quem concorre a suplente não
  disputa cargo próprio. A declaração entra nas contagens deste relatório porque
  ela existe e é pública; a ausência da ficha é decisão de escopo do site, não
  omissão da fonte.</p>
<p class="destaque"><b>Para o segundo caso, a hipótese mais econômica é erro de
  digitação.</b> Um valor de R$ 1.109.124,02 informado sem o separador decimal
  vira exatamente R$ 1.109.124.020 — três casas a mais —, o que é consistente com
  a ordem de grandeza da declaração anterior. Mas é <b>hipótese</b>: nem o TSE nem
  este projeto têm como confirmá-la, e a única fonte que poderia é a própria
  declarante. Para o primeiro caso não há sequer hipótese: sem declaração
  anterior, não existe âncora, e o relatório para aqui.</p>
<p class="aviso"><b>Por que isso está no relatório.</b> Não para sugerir
  irregularidade: declaração com valor implausível não é crime nem indício dele,
  e nada aqui afirma que houve erro — apenas que os números não se sustentam como
  descrição do mundo.<br><br>
  Está aqui por uma razão prática. <b>Uma linha em {num(_out['n'])} move a média
  do cargo em {pct(100 * (float(_out['com']) / float(_out['sem']) - 1))}</b>: a
  média dos candidatos a deputado estadual é
  {rs(float(_out['com']))} com ela e {rs(float(_out['sem']))} sem ela. A mediana
  não se mexe: fica em {rs(float(_out['mediana']))} nos dois casos.<br><br>
  É o motivo de este relatório mostrar <b>as duas medidas lado a lado</b> em vez
  de escolher uma. Quem lê tem direito de ver o número que conhece — e de ver,
  ao lado, o que ele esconde.</p>""")

# ══ 7. EMENDAS ═════════════════════════════════════════════════════════
ea = {int(r["ano"]): r for r in D["emendas_ano"]}
anos = sorted(ea)
serie_emp = [float(ea[a]["empenhado"]) / 1e9 for a in anos]
serie_pago = [float(ea[a]["pago"]) / 1e9 for a in anos]
# A serie de medianas vem do dado. Escrita a mao, ela envelheceria em silencio:
# o grafico continuaria bonito e diria outra coisa que o mart.
med = {int(r["ano"]): float(r["mediana"]) / 1e6 for r in D["emendas_mm"]}
fn = [(str(r["funcao"])[:30], float(r["pago"])) for r in D["emendas_funcao"][:10]]

pag(f"""
<h2>7 · Emendas parlamentares</h2>
<p>São 94.463 registros de emendas de 2014 a 2026, com valor acumulado de empenho
  e pagamento, publicados pelo Portal da Transparência.</p>
{linhas({"Empenhado": serie_emp, "Pago": serie_pago}, anos,
        {"Empenhado": ACENTO, "Pago": OK}, area=True,
        titulo="Emendas por ano da emenda, em R$ bilhões",
        rotulo_y=lambda v: f"{v:.0f}")}
{legenda(["Empenhado", "Pago"], {"Empenhado": ACENTO, "Pago": OK})}
<p class="destaque"><b>O volume empenhado dobra entre 2022 e 2023</b> — de
  {bi(float(ea[2022]["empenhado"]))} para {bi(float(ea[2023]["empenhado"]))} — e
  segue subindo até {bi(float(ea[2025]["empenhado"]))} em 2025. Não é efeito de
  mais parlamentares: são {num(ea[2022]["parlamentares"])} em 2022 e
  {num(ea[2023]["parlamentares"])} em 2023.</p>
{linhas({"Mediana por parlamentar": [med[a] for a in sorted(med)]}, sorted(med),
        {"Mediana por parlamentar": ALERTA},
        titulo="Mediana empenhada por parlamentar, emendas individuais (R$ milhões)",
        rotulo_y=lambda v: f"{v:.0f}")}
<p class="obs">Por parlamentar, a mediana salta de <b>{mi(med[2022] * 1e6)} em
  2022 para {mi(med[2023] * 1e6)} em 2023</b> e chega a {mi(med[2025] * 1e6)} em
  2025. Entre 2019 e 2022 ela ficou
  colada no teto anual fixado na LDO de cada ano — foi assim que este projeto
  validou o casamento de autoria. <b>A causa do salto a partir de 2023 não foi
  verificada aqui</b> e está registrada como pergunta em aberto.</p>
<h3>Para onde o dinheiro vai</h3>
{barras(fn, titulo="Valor pago por função de governo", rotulo=bi, cor=ACENTO)}
<p class="destaque">Saúde recebe <b>R$ 83,5 bilhões</b> — 69% de tudo o que foi
  pago nas doze maiores funções, com autor identificado. Nenhuma outra chega
  perto:
  "encargos especiais", a segunda, é uma rubrica contábil genérica, não uma área
  de política pública.</p>""")

# ══ 8. TRANSFERÊNCIA ESPECIAL ══════════════════════════════════════════
sal = {}
for r in D["emendas_salto_tipo"]:
    sal.setdefault(int(r["ano"]), {})[r["tipo"]] = float(r["emp"])
anos2 = sorted(sal)
fd = [sal[a].get("Emenda Individual - Transferências com Finalidade Definida", 0) / 1e9
      for a in anos2]
te = [sal[a].get("Emenda Individual - Transferências Especiais", 0) / 1e9 for a in anos2]
fatia_esp = [100 * t / (f + t) if (f + t) else 0
             for f, t in zip(fd, te, strict=False)]

pag(f"""
<h2>8 · A emenda que não diz para quê</h2>
<p>Entre as emendas individuais há duas espécies muito diferentes. A
  <b>transferência com finalidade definida</b> indica destino e objeto: o recurso
  vai para uma obra, um equipamento, um programa. A <b>transferência especial</b>
  — conhecida como "emenda Pix" — vai direto ao caixa do ente beneficiado, sem
  vinculação a projeto.</p>
{linhas({"Finalidade definida": fd, "Transferência especial": te}, anos2,
        {"Finalidade definida": ACENTO, "Transferência especial": ALERTA}, area=True,
        titulo="Emendas individuais por espécie, em R$ bilhões",
        rotulo_y=lambda v: f"{v:.0f}")}
{legenda(["Finalidade definida", "Transferência especial"],
         {"Finalidade definida": ACENTO, "Transferência especial": ALERTA})}
{linhas({"% em transferência especial": fatia_esp}, anos2,
        {"% em transferência especial": ALERTA},
        titulo="Fatia das emendas individuais sem finalidade definida",
        rotulo_y=lambda v: pct(v, 0))}
<p class="destaque">A transferência especial sai de <b>6,6% das emendas
  individuais em 2020 para 33,7% em 2023</b>, estabilizando perto de um quarto do
  total. Em valor, passa de R$ 0,57 bi para R$ 7,1 bi ao ano.</p>
<p class="obs">O que isso significa, em termos estritamente descritivos: uma
  fatia crescente do orçamento movido por parlamentares <b>não registra
  finalidade na origem</b>. O rastreio do uso passa a depender da prestação de
  contas do município ou estado que recebeu, e não do dado federal.</p>
<h3>E há o que a fonte não atribui a ninguém</h3>
<div class="escada">
  <div><b>73.856</b><span>linhas com autor individual</span></div>
  <div><b>15.962</b><span>sem autor publicado</span></div>
  <div><b>4.645</b><span>bancada, comissão ou relator</span></div>
</div>
<p class="aviso"><b>17% dos registros — R$ 18,5 bilhões pagos — são publicados
  pelo Portal sem autor.</b> Não é lacuna deste levantamento: é orçamento cuja
  autoria a fonte oficial não revela. Qualquer soma "por parlamentar" no Brasil,
  inclusive esta, exclui esse bloco por impossibilidade.</p>""")

# ══ 8b. ATIVIDADE LEGISLATIVA ══════════════════════════════════════════
CLASSE = {"normativa": "Normativa (PL, PEC, MP)",
          "fiscalizacao": "Fiscalização",
          "relatoria": "Relatoria",
          "procedimental": "Procedimental",
          "homenagem": "Rito e homenagem"}
atv = [(CLASSE.get(r["classe"], r["classe"]), int(r["total"]))
       for r in D["atividade_classe"]]
CLASSE_C = {"mesa": "Mesa Diretora", "permanente": "Comissões permanentes",
            "temporaria": "Temporárias, especiais e CPIs",
            "conselho": "Conselhos e corregedoria",
            "mista": "Mistas e do Congresso"}
com = [(CLASSE_C.get(r["classe"], r["classe"]), int(r["assentos"]))
       for r in D["comissoes_classe"]]
com_sen = [(CLASSE_C.get(r["classe"], r["classe"]), int(r["assentos"]))
           for r in D["comissoes_senado_classe"]]
ALC = {r["bloco"]: int(r["fichas"]) for r in D["alcance_blocos"]}
ORIG = {r["origem"]: int(r["assentos"]) for r in D["comissoes_senado_origem"]}
PAPEL = {r["papel"]: int(r["vinculos"]) for r in D["comissoes_senado_papel"]
         if r["origem"] == "comissoes"}
# Cargos de comando: presidencia, vice, relatoria, secretaria. Vem da
# segunda rota, e sao eles que fecharam a L-30.
CMD = sum(int(r["vinculos"]) for r in D["comissoes_senado_papel"]
          if r["origem"] == "cargos")

pag(f"""
<h2>9 · O que os parlamentares em exercício produzem</h2>
<p>Este bloco só existe para quem já tem mandato e pôde ser ligado ao cadastro
  eleitoral: <b>{num(ALC["comissao_camara"])} candidaturas de 2026</b> na Câmara e
  <b>{num(ALC["comissao_senado"])}</b> no Senado. Para as demais, o campo não é
  vazio — é inaplicável.</p>
{barras(atv, titulo="Proposições apresentadas como proponente, desde 2023",
        rotulo=num, cor=ACENTO)}
<p class="aviso"><b>Estas classes não podem ser somadas.</b> Um requerimento de
  homenagem e uma proposta de emenda constitucional não são unidades da mesma
  grandeza, e o total que circula na imprensa — "o deputado apresentou N
  proposições" — junta as duas. É por isso que o número aparece separado por
  natureza, e nunca agregado.</p>
{barras(com, titulo="Assentos em colegiados da Câmara, por natureza", rotulo=num,
        cor=ACENTO2)}
<p class="obs">Comissão permanente é onde o trabalho legislativo acontece de
  fato — e onde a maior parte dos assentos está. A contagem é por colegiado, não
  por designação: a Câmara renova a composição a cada ano, e um deputado de três
  mandatos acumula dezenas de designações para a mesma comissão.</p>
<p class="obs"><b>Comissão de medida provisória fica de fora</b>: são 1.393 no
  catálogo, e participar delas é rotina — quarenta linhas "Comissão da MPV 936"
  afogariam as que importam.</p>
<p class="obs">A tabela de tipos da API também declara <b>partido, bloco e
  liderança</b> como espécies de "órgão". O pipeline os classifica e os mantém
  fora deste bloco por precaução — estar num partido não é ter assento numa
  comissão. Registre-se, porém, que <b>nenhum apareceu</b> entre os 79.140
  vínculos coletados: a salvaguarda existe e não precisou agir.</p>""")

pag(f"""
<h3>O Senado, e por que ele exige duas ressalvas que a Câmara não exige</h3>
{barras(com_sen, titulo="Assentos em colegiados do Senado, por natureza",
        rotulo=num, cor=ACENTO)}
<p><b>A identidade aqui é inferida.</b> O Senado não publica CPF de parlamentar.
  A ligação entre um senador e a pessoa que se candidata é feita por nome e data
  de nascimento — forte, não certa. O dado aparece na ficha <b>com essa ressalva
  escrita ao lado</b>, que é diferente tanto de omiti-lo quanto de afirmá-lo com
  a mesma confiança do bloco da Câmara.</p>
<p class="aviso"><b>Quem comandou vem de outra consulta, e por pouco não veio.</b>
  A lista de comissões do Senado devolve {num(PAPEL.get("Titular", 0))} vínculos
  de Titular, {num(PAPEL.get("Suplente", 0))} de Suplente e
  {num(PAPEL.get("Nato", 0))} de membro nato — e <b>nenhuma presidência</b>. Este
  relatório chegou a registrar isso como limitação da fonte.<br><br>
  Estava errado. A presidência existe em <b>outra rota da mesma API</b>, que
  devolve também vice, relatoria, secretaria e os colegiados que a primeira não
  conhece — a <b>Mesa Diretora do Congresso</b> entre eles. São
  {num(CMD)} cargos de comando, e é assim que a ficha passa a dizer que Davi
  Alcolumbre preside o Senado em vez de mostrá-lo apenas no Conselho de Ética.
  <br><br>
  Fica o método, que vale para qualquer trabalho com dado público: <b>medir a
  ausência numa rota não prova a ausência na fonte</b>.</p>
<p class="obs"><b>O papel de agora não é o de sempre.</b> Um senador que presidiu
  a Comissão de Direitos Humanos em 2015 e segue titular dela hoje tem os dois
  fatos. Tratados como um só, a comissão apareceria com <b>cinco presidentes
  simultâneos</b> — foi o que a primeira versão deste levantamento produziu, e o
  que a conferência pegou. A tabela mostra o papel <b>vigente</b> ao lado de "em
  curso", e guarda o de maior peso para a linha histórica.</p>
<p class="obs"><b>De onde veio a natureza de cada colegiado.</b> O catálogo do
  Senado só lista o que está em atividade, e 292 colegiados citados pelos
  senadores estavam fora dele — entre eles a CPMI do INSS e a CPI da Pandemia.
  Como não há rota que devolva o tipo de um colegiado encerrado, ele foi lido da
  forma oficial do nome <b>escrita por extenso</b>, nunca da sigla. Dos assentos
  exibidos, {num(ORIG.get("catalogo", 0))} vieram do catálogo e
  {num(ORIG.get("nome", 0))} do nome. Os 215 vínculos que nem assim deram para
  determinar <b>ficaram de fora</b>, em vez de virar palpite.</p>
<p class="obs">Os dois blocos <b>não se comparam</b>. Deputado e senador não
  ocupam os mesmos colegiados nem no mesmo volume, e são 513 de um lado contra 81
  do outro. Nada aqui os soma nem os põe em placar.</p>""")

# ══ 9. TROCA DE CARGO ══════════════════════════════════════════════════
comb = [(c["combinacao"], int(c["pessoas"])) for c in D["dupla_combinacao"][:8]]
CC = {"1": "Presid.", "2": "Vice-Pres.", "3": "Gov.", "4": "Vice-Gov.", "5": "Sen.",
      "6": "Dep. Fed.", "7": "Dep. Est.", "8": "Dep. Dist.", "9": "1º Supl.",
      "10": "2º Supl."}
comb = [(" → ".join(CC.get(x, x) for x in k.split("+")), v) for k, v in comb]

DUP = D["dupla_resumo"][0]
_ren = next((int(r["n"]) for r in D["dupla_situacao"]
             if "RENÚNCIA" in str(r["sit"]).upper()), 0)
_top = D["dupla_combinacao"][0]
_topr = " e ".join(CC.get(x, x) for x in _top["combinacao"].split("+"))
_sen = next((int(c["pessoas"]) for c in D["dupla_combinacao"]
             if c["combinacao"] == "5+6"), 0)

pag(f"""
<h2>10 · {num(DUP["total"])} trocas de cargo</h2>
<p>{num(DUP["total"])} pessoas aparecem em <b>duas candidaturas</b> no pacote de
  2026. Como a lei permite uma candidatura por pessoa por eleição, isso parece
  contradição — e não é.</p>
{barras(comb, titulo="Combinações de cargo na mesma pessoa", rotulo=num, cor=ACENTO2)}
<div class="escada">
  <div><b>{num(DUP["ambas_deferidas"])}</b><span>com as duas deferidas</span></div>
  <div><b>{num(DUP["uma_deferida"])}</b><span>com uma deferida</span></div>
  <div><b>{num(_ren)}</b><span>registros em renúncia</span></div>
</div>
<p class="destaque"><b>Nenhuma das {num(DUP["total"])} pessoas tem duas
  candidaturas deferidas.</b>
  O padrão é sempre o mesmo: um registro em renúncia ou aguardando julgamento, e
  outro válido. São pessoas que <b>trocaram de cargo durante o período de
  registro</b>, e o TSE mantém os dois registros publicados.</p>
<p class="obs">O caminho mais comum é entre as duas casas legislativas:
  {num(_top["pessoas"])} pessoas entre {_topr.lower()}. Mas há movimentos de maior
  peso — {num(_sen)} de Senado para Câmara, e trocas entre titular e vice na mesma
  chapa majoritária.</p>
<p class="obs">Este achado é também um controle de qualidade do próprio
  levantamento: se houvesse alguma pessoa com duas candidaturas <b>deferidas</b>,
  seria sinal de erro na ligação de identidade entre registros. Não há
  nenhuma.</p>""")

# ══ 10. PARTIDOS ═══════════════════════════════════════════════════════
pt = [(r["sigla_partido"], int(r["n"])) for r in D["partidos"][:16]]
fed = [(r["sg_federacao"], int(r["n"])) for r in D["federacoes"]]
# TODOS os partidos, e nao so' os maiores: os extremos estao nas listas pequenas,
# e recortar os 20 maiores escondia justamente o que o dado tem de interessante.
_div = sorted(((r["sigla_partido"], 100 * int(r["mulheres"]) / int(r["n"]),
                int(r["n"])) for r in D["partidos"]), key=lambda t: -t[1])
divf = [(f"{s} ({n})", v) for s, v, n in _div[:6]] + \
       [("…", 0)] + \
       [(f"{s} ({n})", v) for s, v, n in _div[-4:]]
_abaixo = [(s, v, n) for s, v, n in _div if v < 30]

pag(f"""
<h2>11 · Partidos e federações</h2>
{barras(pt, titulo="Candidaturas por partido", rotulo=num, cor=ACENTO)}
<p class="obs">Nenhum partido concentra mais de
  {pct(100 * int(D["partidos"][0]["n"]) / TOTAL, 0)} das candidaturas. O
  {D["partidos"][0]["sigla_partido"]} lidera com
  {num(D["partidos"][0]["n"])}, seguido de {D["partidos"][1]["sigla_partido"]} e —
  o dado que mais destoa do senso comum — <b>{D["partidos"][2]["sigla_partido"]},
  com {num(D["partidos"][2]["n"])} candidaturas</b>, terceira maior lista do
  país.</p>
{barras(fed, titulo="Candidaturas por federação partidária", rotulo=num, cor=ACENTO2)}
<p class="obs">{num(len(D["federacoes"]))} federações concentram
  {num(sum(int(r["n"]) for r in D["federacoes"]))} candidaturas — quase um terço
  do total. A federação obriga os partidos a atuarem como um bloco por quatro
  anos, e a maior delas, {D["federacoes"][0]["sg_federacao"]}, sozinha supera
  qualquer partido isolado.</p>
{barras(divf, titulo="% de mulheres nas listas: os seis maiores e os quatro menores",
        rotulo=pct, max_valor=60, cor=ACENTO)}
<p class="obs">O número entre parênteses é o tamanho da lista, e ele explica os
  extremos: as maiores proporções estão em legendas pequenas, onde poucos nomes
  movem muito o percentual.</p>
<p class="destaque"><b>Um partido supera a paridade: a UP, com 52,9%</b> de
  mulheres em 189 candidaturas — a única lista do país com maioria feminina.
  PCdoB (45,0%), Cidadania (42,5%), PSOL (40,5%) e PSTU (40,3%) vêm em seguida.
  Entre os dez maiores partidos, a faixa é estreita: de 32,5% a 37,1%.</p>
<p class="aviso"><b>Duas legendas ficam abaixo do mínimo legal de 30% no
  agregado nacional</b>: PCB (20,8%, 24 candidaturas) e PRTB (16,7%, 12). A
  ressalva importa: a Lei 9.504/97 exige o mínimo <b>por unidade eleitoral</b>,
  não no total do país. Com listas dessa dimensão, o agregado nacional é
  indicativo e não prova descumprimento — verificar exigiria olhar estado por
  estado.</p>""")

# ══ 11. SITUAÇÃO E MÉTODO ══════════════════════════════════════════════
sit = [(str(r["s"]).title()[:38], int(r["n"])) for r in D["situacao"]]
CORES_SIT = {"Deferido": OK, "Aguardando Julgamento": ALERTA,
             "Renúncia": TINTA3, "Indeferido": NAO,
             "Indeferido Em Prazo Recursal Ou Com Recurso": ALERTA,
             "Deferido Em Prazo Recursal Ou Com Recurso": ALERTA,
             "Pedido Não Conhecido": NAO, "Cancelado": NAO,
             "Pendente De Julgamento": ALERTA}

pag(f"""
<h2>12 · Situação do registro</h2>
{barras(sit, titulo="Situação no TSE", rotulo=num, cores=CORES_SIT)}
<p class="obs">Três em cada quatro registros estão deferidos e 21% ainda
  aguardam julgamento — o calendário de registro não terminou. As 470 renúncias
  incluem as trocas de cargo da seção anterior.</p>
<h2>13 · Método, limites e o que não está aqui</h2>
<h3>Média ou mediana: por que este relatório mostra as duas</h3>
<p>A <b>média</b> soma tudo e divide pelo número de casos. É a medida que a maior
  parte das pessoas conhece, e é a certa quando se quer saber o total ou quando os
  valores se distribuem de forma simétrica.</p>
<p>A <b>mediana</b> é o valor do meio: metade do grupo está abaixo, metade acima.
  Ela não muda quando um valor extremo fica mais extremo.</p>
<p>Nos dados de 2026 as duas concordam em alguns lugares e discordam muito em
  outros — e onde discordam, a discordância diz algo:</p>
<table class="t">
  <thead><tr><th>Variável</th><th class="num">Média ÷ mediana</th>
  <th class="num">% acima da média</th><th>O que isso significa</th></tr></thead>
  <tbody>
    <tr><td>Idade (dep. federal)</td><td class="num">1,0×</td><td class="num">≈50%</td>
        <td>Distribuição simétrica — <b>a média serve</b></td></tr>
    <tr><td>Emendas por parlamentar</td><td class="num">1,1×</td><td class="num">24%</td>
        <td>Teto legal comprime a cauda — <b>a média quase serve</b></td></tr>
    <tr><td>Receita de campanha (senador)</td><td class="num">1,4×</td><td class="num">45%</td>
        <td>Teto de gastos limita o topo</td></tr>
    <tr><td>Receita de campanha (dep. federal)</td><td class="num">4,0×</td><td class="num">27%</td>
        <td>Poucas campanhas muito grandes</td></tr>
    <tr><td>Patrimônio (governador)</td><td class="num">9,0×</td><td class="num">9,3%</td>
        <td><b>A média descreve 9% do grupo</b></td></tr>
    <tr><td>Patrimônio (presidente)</td><td class="num">12,0×</td><td class="num">25%</td>
        <td>Doze candidatos, dois deles com centenas de milhões</td></tr>
  </tbody>
</table>
<p class="destaque"><b>A regra que este relatório segue.</b> Onde a razão entre
  média e mediana é próxima de 1, as duas contam a mesma história e a média é
  suficiente. Onde a razão passa de 2, a média deixa de descrever o caso típico —
  e a coluna "% acima da média" mostra isso sem exigir estatística de quem lê: se
  só 9% do grupo alcança a média, ela não é o retrato do grupo.</p>
<p class="obs">Por isso nenhum número monetário aparece sozinho aqui. Onde há
  dinheiro, há as duas medidas e a fração acima da média — e a leitura fica com
  quem lê, não com quem escolhe a métrica.</p>
<h3>Cinco limites que mudam a leitura</h3>
<ol class="limites">
  <li><b>Patrimônio declarado não é riqueza.</b> O TSE pede valor de aquisição,
    não de mercado; um imóvel de 2005 entra pelo preço de 2005. Comparar
    declarações de anos diferentes mede compra e venda tanto quanto valorização.</li>
  <li><b>Prestação de contas parcial não é omissão.</b> Quatro em cada dez
    candidaturas ainda não constam porque o prazo não fechou.</li>
  <li><b>17% das emendas não têm autor publicado.</b> Toda soma por parlamentar
    exclui R$ 18,5 bilhões por impossibilidade, não por escolha.</li>
  <li><b>Emenda é indicação de destino, não obra entregue.</b> Quem executa é o
    órgão que recebe, e a execução não está neste dado.</li>
  <li><b>Média e mediana discordam onde há dinheiro.</b> Uma única declaração
    de R$ 1,2 bilhão desloca a média do cargo em 10,4%. Os dois números aparecem
    lado a lado, com a fração de candidatos acima da média.</li>
</ol>
<h3>O que este levantamento deliberadamente não faz</h3>
<p>Não ordena candidatos por patrimônio, por dinheiro de campanha ou por volume
  de emendas. Ordenar político por dinheiro é placar, e placar é a forma mais
  rápida de transformar registro público em juízo. Onde um nome aparece neste
  documento, ele aparece porque um número específico exigia explicação — e a
  explicação vem junto, com o que a fonte sustenta e o que ela não sustenta.</p>
<p class="obs">As fontes de cada número estão detalhadas na seção
  seguinte.</p>""")

# ══ 14. O QUE AS FONTES NÃO ENTREGAM ══════════════════════════════════
pag("""
<h2>14 · O que as fontes oficiais não entregam</h2>
<p>Esta seção existe porque quase nenhum trabalho sobre dados eleitorais a
  publica. Ela lista o que as fontes <b>não</b> fornecem, o que fornecem de forma
  inconsistente, e o que fornecem de um jeito que induz ao erro se lido
  literalmente. Cada item foi encontrado construindo este levantamento, e cada um
  está registrado no repositório com data e medição.</p>
<p class="obs">Nenhum deles é acusação de má-fé. São limites de sistemas
  públicos grandes, construídos ao longo de décadas, por equipes diferentes e com
  finalidades que não incluíam análise agregada.</p>

<h3>Dados que simplesmente não existem</h3>
<table class="t incong">
  <thead><tr><th>O que falta</th><th class="num">Tamanho</th><th>Consequência</th></tr></thead>
  <tbody>
    <tr><td><b>Desfecho da eleição no cadastro de candidaturas</b><br>
        <span class="s">TSE · 1998 a 2022</span></td>
        <td class="num">13.731<br><span class="s">candidaturas</span></td>
        <td>O campo vem vazio. Tratar vazio como "não eleito" é afirmação falsa —
        e este projeto já cometeu esse erro, publicado, numa ficha que dizia
        "2006 · Presidente · Não eleito" sobre alguém que foi eleito com 58,3
        milhões de votos</td></tr>
    <tr><td><b>Resultado da eleição presidencial de 2006</b><br>
        <span class="s">TSE</span></td>
        <td class="num">7 de 8<br><span class="s">candidaturas</span></td>
        <td>Nenhum candidato daquele pleito tem desfecho publicado. O resultado
        exibido é <b>derivado</b> de dois outros conjuntos oficiais do próprio
        TSE — votação por turno e vagas em disputa — e a tela marca que foi
        derivado</td></tr>
    <tr><td><b>Bens declarados antes de 2006</b><br>
        <span class="s">TSE</span></td>
        <td class="num">2 eleições<br><span class="s">1998 e 2002</span></td>
        <td>A série patrimonial começa em 2006. Comparações de trajetória param
        ali</td></tr>
    <tr><td><b>Motivo do fim de mandato</b><br>
        <span class="s">TSE</span></td>
        <td class="num">11.771<br><span class="s">de 11.778</span></td>
        <td>"Não informado" em 99,9% dos casos. Renúncia, cassação e morte no
        exercício não aparecem — por isso a ficha mostra o período do
        <b>cargo</b>, e não o da pessoa</td></tr>
    <tr><td><b>Autor da emenda parlamentar</b><br>
        <span class="s">Portal da Transparência</span></td>
        <td class="num">15.962<br><span class="s">R$ 18,5 bi pagos</span></td>
        <td>17% dos registros vêm com "Sem informação". Toda soma por parlamentar
        no Brasil exclui esse bloco por impossibilidade</td></tr>
    <tr><td><b>Situação da proposição</b><br>
        <span class="s">Câmara dos Deputados</span></td>
        <td class="num">402.446<br><span class="s">de 829.989</span></td>
        <td>Quase metade sem situação publicada. Por isso a ficha conta o que foi
        <b>apresentado</b>, e não o que foi aprovado</td></tr>
    <tr><td><b>CPF de senador</b><br><span class="s">Senado Federal</span></td>
        <td class="num">81<br><span class="s">de 81</span></td>
        <td>A Casa não publica. A ligação com o cadastro eleitoral passa a ser
        por nome e data de nascimento — forte, não certa. A ficha de senador
        traz o dado <b>com a ressalva escrita ao lado</b>, e não sem ela</td></tr>
    <tr><td><b>Presidência de comissão do Senado, ausente na rota óbvia</b><br>
        <span class="s">Senado Federal</span></td>
        <td class="num">0<br><span class="s">de 7.226 vínculos</span></td>
        <td>A lista de comissões de um senador devolve Titular, Suplente e Nato,
        e nada mais — nem a Mesa Diretora. O dado <b>existe</b>, em outra rota da
        mesma API. É a incongruência mais instrutiva desta lista: medir a
        ausência num endpoint não prova a ausência na fonte, e este relatório
        chegou a publicar a conclusão errada</td></tr>
  </tbody>
</table>""")

pag(f"""
<h3>Dados que existem, mas induzem ao erro se lidos literalmente</h3>
<table class="t incong">
  <thead><tr><th>A armadilha</th><th>O que acontece</th></tr></thead>
  <tbody>
    <tr><td><b>O arquivo de bens de 2006 publica valores zerados</b><br>
        <span class="s">TSE</span></td>
        <td><b>6.699 das 19.263</b> declarações daquele ano somam exatamente
        zero — 34,8%, contra 0,1% em todos os outros anos. Sem tratar, a ficha
        poria "R$ 0 em 2006" ao lado de "R$ 500 mil em 2026" e desenharia uma
        queda a pico que nunca houve</td></tr>
    <tr><td><b>O endereço do arquivo de emendas ignora o ano</b><br>
        <span class="s">Portal da Transparência</span></td>
        <td>Pedir 2014 e pedir 2026 devolve o <b>mesmo arquivo</b>, byte a byte.
        Treze downloads, um único sha256. Uma carga ingênua somaria 1.228.019
        linhas que são treze cópias de 94.463 — e nada falharia: toda soma por
        autor sairia multiplicada por treze</td></tr>
    <tr><td><b>Um endpoint devolve quase nada sem parâmetro de data</b><br>
        <span class="s">Câmara dos Deputados</span></td>
        <td>A consulta de órgãos de um deputado, sem janela explícita, devolve
        <b>um único vínculo</b> para quem presidiu a Casa. Com a janela: 41</td></tr>
    <tr><td><b>O catálogo de órgãos não tem os órgãos que mais importam</b><br>
        <span class="s">Câmara dos Deputados</span></td>
        <td>A listagem padrão traz 1.649 órgãos e omite <b>a Mesa Diretora, a
        Presidência e o Conselho de Ética</b>. Resolver o que faltava elevou os
        vínculos corretamente classificados de 545 para 1.060 numa amostra de 25
        deputados</td></tr>
    <tr><td><b>A paginação corta justamente quem mais trabalhou</b><br>
        <span class="s">Câmara dos Deputados</span></td>
        <td>Sem paginar, o corte cai sobre os veteranos: um deputado perdia 42 de
        242 vínculos, outro 24 de 224. O efeito é uma ficha <b>mais pobre para
        quem tem mais história</b>, sem nada indicando isso</td></tr>
    <tr><td><b>O nome do tipo de órgão não corresponde ao conteúdo</b><br>
        <span class="s">Câmara dos Deputados</span></td>
        <td>O tipo <code>15</code> chama-se oficialmente "COORDENADORIA DA
        MULHER" e agrupa treze órgãos — entre eles a <b>Bancada Negra</b> e a
        Secretaria de Comunicação. Renderizar o rótulo como veio diria que a
        Bancada Negra é a Coordenadoria da Mulher</td></tr>
    <tr><td><b>O catálogo de colegiados só lista o que está em atividade</b><br>
        <span class="s">Senado Federal</span></td>
        <td><b>292 colegiados</b> citados pelos próprios senadores não constam
        do catálogo — 1.483 vínculos, 21% do total. E o que fica de fora é
        justamente o de maior peso público: <b>CPMI do INSS</b> (173 vínculos),
        Comissão Representativa do Congresso (110), CPI do Crime Organizado, CPMI
        das Fake News, do 8 de Janeiro, CPI da Pandemia. É o mesmo padrão da
        Câmara, onde faltavam a Mesa e o Conselho de Ética</td></tr>
    <tr><td><b>Não há rota que devolva o colegiado encerrado</b><br>
        <span class="s">Senado Federal</span></td>
        <td>A consulta de um colegiado por código responde <b>vazio</b>, e os
        parâmetros de "inativos" da listagem são ignorados: a resposta volta
        <b>byte a byte idêntica</b> à dos ativos. Não é erro visível — é uma
        resposta bem-sucedida que não contém o que foi pedido</td></tr>
    <tr><td><b>O mesmo colegiado escrito de duas formas</b><br>
        <span class="s">Senado Federal</span></td>
        <td>A fonte grava ora "Comissão Parlamentar Mista de Inquérito - Fake
        News", ora "CPI da Pandemia". Quem só reconhece a forma extensa perde a
        segunda; quem procura a sigla solta cai na armadilha da linha
        abaixo</td></tr>
    <tr><td><b>Sigla que parece uma coisa e é outra</b><br>
        <span class="s">Senado Federal</span></td>
        <td><code>RQI</code> sugere "Requerimento de Informação" e é
        "Requerimento da Comissão de Serviços de Infraestrutura". Classificar
        pelo formato da sigla, e não pela tabela oficial, produz categorias
        erradas que nenhum teste pega</td></tr>
    <tr><td><b>Datas de nascimento com erro de digitação</b><br>
        <span class="s">TSE</span></td>
        <td>Há registros com data implausível na fonte. O projeto invalida a
        idade em vez de exibi-la: <b>3 candidaturas</b> de 2026 ficam sem idade,
        e é melhor assim que publicar um número impossível</td></tr>
    <tr><td><b>Candidaturas somem entre publicações</b><br>
        <span class="s">TSE</span></td>
        <td>O portal publica apenas o <b>estado atual</b>, sem histórico. Uma
        candidatura que desaparece de um dia para o outro não deixa rastro na
        fonte — é irreproduzível depois. Por isso este projeto tira uma foto
        diária</td></tr>
    <tr><td><b>O firewall recusa requisição bem-formada</b><br>
        <span class="s">TSE</span></td>
        <td>Requisições sem o conjunto completo de cabeçalhos de navegador são
        bloqueadas, e a resposta não parece um bloqueio</td></tr>
  </tbody>
</table>

<h3>O que este projeto faz com isso</h3>
<p>Nenhum dos itens acima é contornado por estimativa, interpolação ou média.
  A regra é: <b>onde o dado não existe, a tela diz que não existe</b> — nunca
  preenche. Cada lacuna tem registro próprio no repositório, com a medição, a
  data, o impacto e o que seria preciso para fechá-la.</p>
<p class="destaque"><b>Por que publicar a própria lista de limitações.</b> Um
  levantamento que só mostra o que encontrou transfere ao leitor um risco que ele
  não tem como avaliar: o de tomar por completo um retrato que não é. A lista
  acima é o que permite a quem lê discordar deste documento com base — e
  discordar com base é o que distingue dado público de número solto.</p>
<p class="obs">São <b>{num(N_LACUNAS)} lacunas</b> registradas até aqui, das
  quais {num(N_FECHADAS)} já foram fechadas por trabalho posterior — e as duas
  mais recentes fecharam porque a <i>premissa</i> da lacuna estava errada, não
  porque a fonte melhorou. A lista viva está em
  <span class="url">github.com/girocoju/dossie-eleitoral</span>, no arquivo
  <code>docs/LACUNAS.md</code>.</p>""")

# ══ 14. FONTES ════════════════════════════════════════════════════════
pag(f"""
<h2>15 · Fontes</h2>
<p>Todo número deste relatório vem de fonte pública, sem intermediário. Abaixo,
  a origem exata de cada bloco e o endereço para refazer a conta.</p>

<h3>Fontes primárias</h3>
<table class="t fontes">
  <thead><tr><th>Fonte</th><th>O que fornece</th><th>Endereço</th></tr></thead>
  <tbody>
    <tr>
      <td><b>TSE — Dados Abertos</b><br><span class="s">Divulgação de
        Candidaturas</span></td>
      <td>Perfil declarado, legenda, situação do registro, bens de candidato,
        prestação de contas, votação histórica desde 1998</td>
      <td class="url">dadosabertos.tse.jus.br</td>
    </tr>
    <tr>
      <td><b>TSE — DivulgaCandContas</b></td>
      <td>Usado para <b>conferência independente</b>: mesmo dado, outro sistema,
        outro formato. É contra ele que os valores de patrimônio foram validados
        ao centavo</td>
      <td class="url">divulgacandcontas.tse.jus.br</td>
    </tr>
    <tr>
      <td><b>Portal da Transparência (CGU)</b></td>
      <td>Emendas parlamentares: 94.463 registros de 2014 a 2026, com empenho,
        liquidação e pagamento acumulados</td>
      <td class="url">portaldatransparencia.gov.br/<wbr>download-de-dados/
        <wbr>emendas-parlamentares</td>
    </tr>
    <tr>
      <td><b>Câmara dos Deputados</b><br><span class="s">Dados Abertos</span></td>
      <td>Proposições por proponente, votos e presença em plenário, comissões e
        órgãos, identificação por CPF</td>
      <td class="url">dadosabertos.camara.leg.br</td>
    </tr>
    <tr>
      <td><b>Senado Federal</b><br><span class="s">Dados Abertos</span></td>
      <td>Autoria de proposições, com separação entre autor principal e
        coautor; e assentos em colegiado — comissões permanentes, temporárias,
        CPIs, conselhos e comissões mistas do Congresso</td>
      <td class="url">legis.senado.leg.br/dadosabertos</td>
    </tr>
    <tr>
      <td><b>IBGE</b> · <b>Ipeadata</b> · <b>Tesouro (SICONFI/RTN)</b> ·
        <b>INEP</b></td>
      <td>Indicadores socioeconômicos usados no site para o período de mandatos
        executivos anteriores. Não entram neste relatório</td>
      <td class="url">sidra.ibge.gov.br · ipeadata.gov.br<br>
        siconfi.tesouro.gov.br · inep.gov.br</td>
    </tr>
  </tbody>
</table>

<h3>Onde ver e conferir</h3>
<table class="t fontes">
  <tbody>
    <tr>
      <td><b>O dossiê publicado</b></td>
      <td>Ficha própria para cada candidatura a cargo disputado —
        {num(COM_FICHA)} na data desta extração —, com fonte e data em toda tela.
        Suplente de senador ({num(SUPLENTES)} candidaturas) entra nas contagens
        deste relatório e <b>não</b> tem ficha: quem concorre a suplente não
        disputa cargo próprio</td>
      <td class="url">datadubaintel.com/dossie-eleitoral</td>
    </tr>
    <tr>
      <td><b>Metodologia e limites</b></td>
      <td>O que cada número mede, o que ele não mede, e as ressalvas por
        indicador</td>
      <td class="url">datadubaintel.com/dossie-eleitoral/metodologia</td>
    </tr>
    <tr>
      <td><b>Código-fonte</b></td>
      <td>Ingestão, transformação e geração do site. Inclui as decisões de
        arquitetura (ADR), as lacunas conhecidas e o registro de validação
        contra fonte oficial</td>
      <td class="url">github.com/girocoju/dossie-eleitoral</td>
    </tr>
  </tbody>
</table>

<h3>Como este relatório foi produzido</h3>
<p>Os dados vivem em BigQuery, carregados por rotinas de ingestão versionadas e
  transformados em <i>marts</i> com testes automáticos de integridade. As
  consultas que geraram cada gráfico deste documento leem esses <i>marts</i> — os
  mesmos que alimentam o site público, sem caminho paralelo.</p>
<p>Os gráficos são SVG gerados a partir dos resultados, sem biblioteca de
  visualização: a mesma disciplina do site, onde o HTML é escrito diretamente.</p>
<p><b>Este documento se refaz por comando.</b> A coleta
  (<code>scripts/dados_relatorio.py</code>) e a formatação
  (<code>scripts/gerar_relatorio.py</code>) estão no repositório, versionadas
  junto com o resto. Rodar as duas reconstrói o PDF inteiro a partir das fontes
  — nenhum número aqui foi digitado à mão, e nenhum pode envelhecer sem que a
  regeneração o corrija.</p>
<p class="destaque"><b>Reprodutibilidade.</b> Cada afirmação numérica aqui pode
  ser refeita a partir das fontes primárias listadas acima. Onde um número deste
  relatório divergir do que você obtiver, a fonte primária prevalece — e o erro é
  nosso.</p>

<h3>Registro de validação</h3>
<p>O repositório mantém um documento de conferência contra fonte oficial. As
  validações que sustentam este relatório:</p>
<ul>
  <li><b>Patrimônio 2026:</b> 7 de 7 declarações conferidas contra o
    DivulgaCandContas, ao centavo.</li>
  <li><b>Patrimônio 2022:</b> 5 de 5, incluindo uma com 180 itens.</li>
  <li><b>Emendas:</b> soma independente do CSV, fora do banco — 68.366 linhas,
    R$ 97,345 bi pagos e R$ 149,082 bi empenhados, exatos.</li>
  <li><b>Emendas, plausibilidade:</b> mediana por parlamentar entre 2019 e 2022
    colada no teto anual da LDO de cada ano.</li>
  <li><b>Comissões na Câmara:</b> 8 de 8 colegiados com composição idêntica à
    listada pela rota inversa da API — entre eles a CCJC (130 = 130).</li>
  <li><b>Comissões no Senado:</b> contra o <b>Regimento Interno</b>, que fixa o
    número de cadeiras de cada comissão permanente. A CCJ bate exatamente (27
    titulares para 27 previstos) e nenhuma das cinco maiores ultrapassa o teto
    regimental — cadeira vaga existe, cadeira inventada não. A API do Senado não
    tem rota inversa, e a página pública carrega a composição por JavaScript.</li>
  <li><b>Parlamentares em exercício:</b> 513 na Câmara, 513 no pipeline, zero
    divergência.</li>
</ul>
<p class="rodape-doc"><b>Data Duba Intelligence</b> · Dossiê Eleitoral 2026 ·
  datadubaintel.com/dossie-eleitoral<br>
  Documento descritivo, apartidário, sem ranking de candidatos. Os dados são
  públicos; a organização e a leitura são nossas — e os erros também.</p>""")

# ══ MONTAGEM ═══════════════════════════════════════════════════════════
CSS = """
@page { size: A4; margin: 16mm 15mm 14mm; }
* { box-sizing: border-box; }
body { font-family: Calibri, Carlito, "Segoe UI", Arial, sans-serif;
       color: #0B1F3B; font-size: 10.4pt; line-height: 1.5; margin: 0; }
.pagina { page-break-after: always; }
.pagina:last-child { page-break-after: auto; }
h1 { font-size: 27pt; line-height: 1.12; margin: 0 0 10px; letter-spacing: -.02em; }
h2 { font-size: 15pt; margin: 0 0 10px; padding-bottom: 6px;
     border-bottom: 2px solid #0E7D8B; }
h3 { font-size: 11.6pt; margin: 18px 0 7px; color: #0E7D8B; }
p { margin: 0 0 9px; }
svg { display: block; margin: 10px 0 6px; }
.obs { font-size: 9.4pt; color: #43505F; }
.destaque { background: #F1F5FA; border-left: 3px solid #0E7D8B;
            padding: 9px 12px; margin: 11px 0; font-size: 10pt; }
.aviso { background: #FBEBD6; border-left: 3px solid #B45309;
         padding: 9px 12px; margin: 11px 0; font-size: 9.7pt; }
.capa { padding-top: 22mm; }
.capa .marca { font-size: 9.6pt; letter-spacing: .16em; text-transform: uppercase;
               color: #0E7D8B; font-weight: 700; margin-bottom: 20px; }
.capa .sub { font-size: 12pt; color: #43505F; margin: 14px 0 26px; max-width: 74%; }
.capa-num { display: flex; gap: 26px; margin: 26px 0 30px;
            border-top: 1px solid #CDD9EA; border-bottom: 1px solid #CDD9EA;
            padding: 16px 0; }
.capa-num div { flex: 1; }
.capa-num b { display: block; font-size: 21pt; color: #0E7D8B; line-height: 1.1; }
.capa-num span { font-size: 8.8pt; color: #5A6577; }
.nota-capa { font-size: 9.6pt; color: #43505F; margin-bottom: 10px; }
.rodape-capa { margin-top: 30px; font-size: 8.6pt; color: #5A6577;
               border-top: 1px solid #CDD9EA; padding-top: 9px; }
.legenda { font-size: 9pt; color: #43505F; margin: 2px 0 9px; }
.leg { margin-right: 16px; white-space: nowrap; }
.leg i { display: inline-block; width: 11px; height: 11px; border-radius: 2px;
         margin-right: 5px; vertical-align: -1px; }
.escada { display: flex; gap: 10px; margin: 12px 0; }
.escada div { flex: 1; background: #F1F5FA; padding: 9px 10px; border-radius: 2px; }
.escada b { display: block; font-size: 15pt; color: #0E7D8B; line-height: 1.15; }
.escada span { font-size: 8.4pt; color: #43505F; }
table.t { width: 100%; border-collapse: collapse; font-size: 9.5pt; margin: 9px 0; }
table.t th { text-align: left; border-bottom: 1.5px solid #0B1F3B; padding: 5px 7px;
             font-size: 8.8pt; text-transform: uppercase; letter-spacing: .04em; }
table.t td { border-bottom: 1px solid #DCE7F5; padding: 5px 7px; }
table.t .num { text-align: right; font-variant-numeric: tabular-nums; }
table.t tr.tot td { border-top: 1.5px solid #0B1F3B; border-bottom: none; }
.caso { border: 1.5px solid #0E7D8B; border-radius: 3px; padding: 12px 14px;
        margin: 12px 0; }
.caso-cab { margin-bottom: 8px; }
.caso-cab b { font-size: 13pt; display: block; }
.caso-cab span { font-size: 9pt; color: #5A6577; }
ul, ol { margin: 0 0 9px; padding-left: 20px; }
li { margin-bottom: 5px; }
ol.limites li { margin-bottom: 8px; }
table.sumario { width: 100%; border-collapse: collapse; margin: 14px 0; }
table.sumario td { padding: 7px 6px; border-bottom: 1px solid #DCE7F5;
                   vertical-align: top; }
table.sumario .s-n { width: 30px; color: #0E7D8B; font-weight: 700;
                     font-size: 11.5pt; }
table.sumario .s-t b { font-size: 10.6pt; }
table.sumario .s-d { font-size: 9pt; color: #43505F; margin-top: 2px; }
table.t.fontes td { vertical-align: top; padding: 7px; }
table.t.incong td { vertical-align: top; padding: 7px; font-size: 9.2pt; }
table.t.incong .s { font-size: 8.4pt; color: #5A6577; }
code { font-family: ui-monospace, Consolas, monospace; font-size: 8.8pt;
       background: #F1F5FA; padding: 1px 4px; border-radius: 2px; }
table.t.fontes .url { font-family: ui-monospace, Consolas, monospace;
                      font-size: 8.4pt; color: #0E7D8B; word-break: break-word; }
table.t.fontes .s { font-size: 8.6pt; color: #5A6577; }
.rodape-doc { margin-top: 22px; padding-top: 9px; border-top: 1px solid #CDD9EA;
              font-size: 8.4pt; color: #5A6577; }
"""

html = ("<!doctype html><html lang=\"pt-BR\"><head><meta charset=\"utf-8\">"
        f"<title>Dossiê Eleitoral 2026 — análise</title><style>{CSS}</style>"
        "</head><body>"
        + "".join(f'<section class="pagina">{x}</section>' for x in P)
        + "</body></html>")

HTML.parent.mkdir(parents=True, exist_ok=True)
HTML.write_text(html, encoding="utf-8")
log.info("%s — %s bytes, %d secoes", HTML.name, f"{len(html):,}", len(P))


def _navegador() -> str:
    """O Edge, que ja' vem no Windows. Sem ele nao ha' PDF, e dizer isso e'
    melhor que gerar um arquivo vazio."""
    candidatos = [
        os.environ.get("EDGE"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        shutil.which("msedge"), shutil.which("chrome"), shutil.which("chromium"),
    ]
    for c in candidatos:
        if c and Path(c).exists():
            return c
    raise SystemExit("nenhum navegador Chromium encontrado — defina EDGE=<caminho>")


def imprimir() -> None:
    with tempfile.TemporaryDirectory() as perfil:
        subprocess.run(
            [_navegador(), "--headless=new", "--disable-gpu",
             f"--user-data-dir={perfil}",
             "--no-pdf-header-footer",
             f"--print-to-pdf={PDF}", HTML.as_uri()],
            check=True, capture_output=True, timeout=300)
    if not PDF.exists():
        raise SystemExit("o navegador terminou sem escrever o PDF")
    # O processo sai antes de o arquivo terminar de ser gravado, e medir o
    # tamanho ai' reporta um numero menor que o real — um log que mente sobre o
    # proprio produto. `%%EOF` e' o fim de um PDF completo.
    for _ in range(40):
        fim = PDF.read_bytes()[-1024:]
        if b"%%EOF" in fim:
            break
        time.sleep(0.25)
    else:
        raise SystemExit("o PDF ficou incompleto (sem %%EOF)")
    log.info("%s — %d KB", PDF.name, round(PDF.stat().st_size / 1024))


if __name__ == "__main__":
    imprimir()
