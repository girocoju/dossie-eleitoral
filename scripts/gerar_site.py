"""Gerador do Dossie Eleitoral — F-07 / ADR-018.

    python scripts/gerar_site.py [--saida site] [--limite 20]

Le' `marts` e escreve um site ESTATICO. Sem servidor: o dado muda uma vez por dia,
entao pagar query por visita seria desperdicio (Constituicao 5).

O QUE E' GERADO

    /                          porta de entrada
    /presidente/ ... /senador/ listagem de cada cargo majoritario
    /deputado-*/               listagem filtravel por estado (JSON por UF)
    /candidato/<slug>-<sq>/    ficha propria — TODA candidatura (F-18)
    /doadores/                 quem financiou quem
    /metodologia/              fontes, cobertura e glossario
    /dados/*.json              base das listagens filtraveis
    /dossie.css                a folha de estilo, uma vez para o site inteiro
    /sitemap.xml               indice, apontando para /sitemaps/*.xml

TODA CANDIDATURA TEM FICHA — E ANTES NAO TINHA

Ate' 03/09/2026 so' os 529 majoritarios tinham pagina propria. O argumento era
que 19 mil paginas com poucos campos distintos sao o que buscador classifica
como conteudo raso, e o risco nao era penalidade: era o site inteiro passar a
ser lido como de baixa qualidade.

O criterio que decidiu nao foi ranqueamento, foi utilidade publica
(Constituicao 0). Quem decide o voto para deputado enfrenta 1.126 nomes so' em
Sao Paulo, e e' ai' que uma ficha ajuda MAIS, nao menos. Ficha sem endereco
proprio nao e' compartilhavel, e um site de consulta serve quem chega por link.

O que a ficha do deputado NAO tem: indicador socioeconomico atribuido ao mandato
dele. `fct_mandato_indicador` so' tem linha para mandato EXECUTIVO, entao o bloco
so' aparece para quem ja' foi Presidente ou Governador — e fala do periodo
daquele mandato, nunca do de deputado (SPEC 2.2).

SEM DEPENDENCIA NOVA

Template em Python puro. Um motor de template resolveria pouco aqui e somaria uma
dependencia a um projeto cujo nucleo e' stdlib.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ingest.common.config import get_settings
from ingest.common.log import get_logger

log = get_logger("site")

# Prefixo de todo link interno e de toda URL canonica. Em producao e' o endereco
# publico; para conferir no navegador local, `--base http://localhost:8000` faz o
# site inteiro funcionar sem servidor de producao.
BASE_URL = "https://datadubaintel.com/dossie-eleitoral"

# Vice tem candidatura propria, foto propria e trajetoria propria — e quem
# assume quando o titular sai. Ate' 01/09/2026 ele so' aparecia como cartao na
# ficha do titular, sem pagina onde a propria trajetoria coubesse (ADR-032).
CARGOS = {
    1: ("presidente", "Presidente", "Brasil"),
    2: ("vice-presidente", "Vice-Presidente", "Brasil"),
    3: ("governador", "Governador", "estadual"),
    4: ("vice-governador", "Vice-Governador", "estadual"),
    5: ("senador", "Senador", "estadual"),
}
# Cargos que concorrem EM CHAPA como segundo nome. A ficha deles mostra o
# titular; a do titular mostra eles.
VICES = frozenset({2, 4})
PROPORCIONAIS = {
    6: ("deputado-federal", "Deputado Federal"),
    7: ("deputado-estadual", "Deputado Estadual"),
    8: ("deputado-distrital", "Deputado Distrital"),
}

# Ate' a F-18 so' cargo majoritario tinha ficha, e por isso `CARGOS` bastava
# para descobrir o nome e a listagem de origem de uma ficha. Agora as 19.418
# candidaturas proporcionais tambem tem — e `CARGOS[6]` seria KeyError.
TODOS_CARGOS: dict[int, tuple[str, str]] = {
    **{cod: (chave, nome) for cod, (chave, nome, _) in CARGOS.items()},
    **PROPORCIONAIS,
}

# Plano de governo e' exigido de Prefeito, Governador e Presidente (Lei 9.504/97,
# art. 11, par. 1, IX). Dizer isso na ficha de um deputado sem dizer o que ele e'
# deixaria o leitor concluindo que o candidato deixou de entregar algo.
_CARGO_NA_NOTA = {
    5: "Senador é majoritário, mas não consta da lista",
    6: "Deputado Federal não consta da lista",
    7: "Deputado Estadual não consta da lista",
    8: "Deputado Distrital não consta da lista",
    2: "o plano da chapa é o do titular",
    4: "o plano da chapa é o do titular",
}

_NAO_ALFANUM = re.compile(r"[^a-z0-9]+")


def slug(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode()
    return _NAO_ALFANUM.sub("-", sem_acento.lower()).strip("-") or "sem-nome"


# ── indice de busca (F-23) ──────────────────────────────────────────────────

# Palavras que so' engordariam o indice: aparecem em milhares de nomes e ninguem
# busca por elas. Continuam valendo na FILTRAGEM — quem digita "jose da silva"
# casa contra o nome inteiro. Elas so' nao ganham atalho proprio.
_LIGACOES = frozenset({"da", "de", "do", "das", "dos", "di", "du", "dr", "e"})

# Quantos caracteres formam o nome do arquivo. Dois e' o equilibrio medido: com
# um, "m" juntaria todo Marcos, Maria, Miguel e Moacir num arquivo so'; com
# tres, seriam milhares de arquivos com meia duzia de linhas cada.
PREFIXO_BUSCA = 2


def normalizar(texto: str) -> str:
    """Sem acento, minusculo. TEM de casar com o que o navegador faz.

    O JavaScript da home faz `normalize("NFD")` e remove os diacriticos
    combinantes (U+0300-U+036F), que e' exatamente o que
    `encode("ascii","ignore")` faz aqui depois do mesmo NFD. Se os dois
    divergissem, o navegador pediria um arquivo que nao existe e a tela diria
    "nada encontrado" para um nome que esta' na base — ausencia virando
    afirmacao, que e' o erro que este projeto mais persegue (Regra 5).
    """
    return unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode().lower()


def termos_de(texto: str) -> list[str]:
    return [t for t in _NAO_ALFANUM.sub(" ", normalizar(texto)).split() if t]


def indice_de_busca(fichas: list[Candidato]) -> dict[str, list[list]]:
    """Um arquivo por prefixo de duas letras. O navegador baixa UM.

    Um indice unico com 20.162 nomes daria ~1,5 MB. Numa home aberta no celular
    em rede fraca isso e' meio minuto antes de a primeira letra valer alguma
    coisa — o mesmo motivo que ja' quebrou a listagem de deputado estadual por
    UF (ADR-018).

    Cada candidatura entra no arquivo de CADA termo do nome, e nao so' do
    primeiro: quem procura "SILVA" nao deveria precisar saber que a pessoa se
    chama "JOSE DA SILVA". O numero na urna tambem e' um termo — quem decide o
    voto digita o numero.

    ── O NOME COMPLETO ENTRA, E NAO E' DETALHE ──

    Nome de urna e' apelido curto: "ZULU", "DR. TARCISIO", "PROFESSORA ANA".
    Medido em 03/09/2026 sobre as 20.838 candidaturas exibidas:

        SILVA    301 nomes de urna  x  3.322 nomes completos
        JOSE      83 nomes de urna  x    335 nomes completos

    Indexar so' o nome de urna faria a busca perder NOVE em cada dez pessoas
    que alguem procuraria pelo sobrenome — quem le' o nome numa noticia nao sabe
    qual apelido a pessoa registrou na urna.

    O nome completo viaja na linha, e nao so' nos termos: o navegador filtra
    contra o que esta' na linha, e um nome que entrasse no arquivo sem estar la'
    seria encontrado pelo indice e descartado pelo filtro — "nada encontrado"
    para alguem que esta' na base. Quando ele e' igual ao de urna (631 casos),
    fica de fora para nao repetir bytes.

    Custo medido: o maior arquivo vai de 173 kB para 415 kB — cerca de 45 kB no
    fio, porque o servidor entrega JSON com Brotli (medido: 536 kB -> 56 kB). A
    listagem por UF, que ja' e' aceita, e' maior que isso.
    """
    por_prefixo: dict[str, dict[str, list]] = {}
    for c in fichas:
        completo = c.nome_completo or ""
        difere = completo.upper() != c.nome_urna.upper()
        termos = termos_de(c.nome_urna) + (termos_de(completo) if difere else [])
        if c.nr_candidato:
            termos.append(str(c.nr_candidato))
        linha = [c.nome_urna, f"{slug(c.nome_urna)}-{c.sq}", c.sg_uf,
                 c.sigla_partido or "", c.cod_cargo, c.nr_candidato]
        if difere and completo:
            linha.append(completo)
        for t in termos:
            if len(t) < PREFIXO_BUSCA or t in _LIGACOES:
                continue
            # `setdefault` num dicionario por chave: a mesma candidatura entra
            # uma vez por arquivo, mesmo que dois termos dela comecem igual
            # ("MARIA MARIANA" tem dois termos em "ma").
            por_prefixo.setdefault(t[:PREFIXO_BUSCA], {})[linha[1]] = linha
    saida = {p: sorted(v.values(), key=lambda r: r[0]) for p, v in por_prefixo.items()}
    maior = max(saida.items(), key=lambda kv: len(kv[1]))
    log.info("indice de busca: %d arquivos, maior e' '%s' com %d nomes",
             len(saida), maior[0], len(maior[1]))
    return saida


def e(valor: Any) -> str:
    """Escapa para HTML. Nunca interpolar texto de fonte externa sem passar aqui."""
    return html.escape(str(valor), quote=True) if valor is not None else ""


def brl(valor: float | None) -> str:
    if valor is None:
        return "—"
    inteiro = f"{valor:,.0f}".replace(",", ".")
    return f"R$ {inteiro}"


@dataclass
class Candidato:
    sk: str
    sq: str
    cod_cargo: int
    nome_urna: str
    nome_completo: str | None
    sg_uf: str
    sigla_partido: str | None
    nome_partido: str | None
    nr_candidato: int | None
    coligacao: str | None
    composicao: str | None
    federacao: str | None
    situacao: str | None
    url_foto: str | None
    idade: int | None
    genero: str | None
    cor_raca: str | None
    grau_instrucao: str | None
    ocupacao: str | None
    uf_nascimento: str | None
    bens_total: float | None
    bens_n: int | None
    proposta_obrigatoria: bool
    tem_proposta: bool
    url_proposta: str | None
    limite_gasto: float | None = None
    plano_texto: str | None = None
    plano_paginas: int | None = None
    plano_motivo: str | None = None
    plano_url_pdf: str | None = None
    trajetoria: list[dict] = field(default_factory=list)
    mudancas: list[dict] = field(default_factory=list)
    indicadores: list[dict] = field(default_factory=list)
    indicadores_ausentes: list[dict] = field(default_factory=list)
    atividade: list[dict] = field(default_factory=list)
    atividade_senado: list[dict] = field(default_factory=list)
    # Financiamento (F-11 / ADR-020). `None` e `[]` NAO sao a mesma coisa aqui:
    # lista vazia = a candidatura nao consta na prestacao de contas, e a tela
    # precisa dizer "ainda nao entregue", nunca "R$ 0,00".
    financiamento: list[dict] = field(default_factory=list)
    doadores: list[dict] = field(default_factory=list)
    despesa_contratada: float | None = None
    # O TSE publica mais de um registro para esta candidatura (re-inscricao).
    # A tela mostra um e DIZ que ha' outro — esconder sem avisar seria decidir
    # em silencio qual registro do TSE vale.
    registros_no_tse: int = 1
    # Votos e presenca em plenario, por legislatura (F-20).
    plenario: list[dict] = field(default_factory=list)
    # Vice ou suplentes da chapa (F-21). Vazio para cargo proporcional, que nao
    # tem chapa — deputado concorre sozinho.
    chapa: list[dict] = field(default_factory=list)
    chapa_titular: dict | None = None
    # Quando os dados DESTA candidatura mudaram pela ultima vez (ADR-038).
    dado_de: str | None = None

    @property
    def partido_completo(self) -> str:
        """'Democracia Crista (DC)'. Quando o TSE publica nome igual a' sigla —
        AGIR, AVANTE — repetir ficaria bobo, entao sai so' a sigla."""
        if not self.sigla_partido:
            return "—"
        if self.nome_partido and self.nome_partido.upper() != self.sigla_partido.upper():
            return f"{self.nome_partido} ({self.sigla_partido})"
        return self.sigla_partido

    @property
    def caminho(self) -> str:
        return f"candidato/{slug(self.nome_urna)}-{self.sq}"

    @property
    def url(self) -> str:
        return f"{BASE_URL}/{self.caminho}/"

    @property
    def cargo_nome(self) -> str:
        return TODOS_CARGOS[self.cod_cargo][1]

    @property
    def cargo_chave(self) -> str:
        """A listagem de onde a ficha veio — serve de link de volta e de aba
        acesa na navegacao."""
        return TODOS_CARGOS[self.cod_cargo][0]

    @property
    def e_proporcional(self) -> bool:
        return self.cod_cargo in PROPORCIONAIS


# ── consultas ───────────────────────────────────────────────────────────────


def _cliente():
    from google.cloud import bigquery

    s = get_settings()
    return bigquery.Client(project=s.project, location=s.location)


# Abreviacao do cargo para a tabela de doadores: a coluna e' estreita e o nome
# por extenso empurraria o resto para fora da tela no celular.
# 7.390 das 8.082 linhas de pessoa juridica trazem este mesmo ramo, e ele
# responde por 99,6% do dinheiro PJ — doacao de EMPRESA a candidato e'
# inconstitucional desde 2015 (ADI 4650), entao o dinheiro juridico passa por
# diretorio partidario. Repetir a string 7 mil vezes no JSON custa ~300 KB e nao
# informa nada que o nome "PARTIDO LIBERAL (PL)" ja' nao diga. Os OUTROS ramos
# sao justamente os casos que valem a tela, e esses vao inteiros.
RAMO_OBVIO = "Atividades de organizações políticas"

CARGO_CURTO_DOADOR = {
    1: "Presidente", 2: "Vice-pres.", 3: "Governador", 4: "Vice-gov.",
    5: "Senador", 6: "Dep. federal", 7: "Dep. estadual", 8: "Dep. distrital",
    9: "1º Supl.", 10: "2º Supl.",
}


def carimbo_de_publicacao() -> dict[str, str]:
    """Quem gerou este site, quando, e de qual commit (ADR-036).

    O carimbo viaja junto com o site e fica no servidor. `scripts/publicar.py`
    le' o do servidor antes de enviar e RECUSA publicar por cima de um site que
    veio de um commit mais novo.

    O criterio e' linhagem, nao horario. Em 03/09/2026 uma execucao do CI gerou
    as 02:54 a partir de um commit ANTERIOR e sobrescreveu uma publicacao manual
    de 01:41 que ja' tinha a correcao — a mais recente no relogio era a mais
    velha no conteudo. Comparar horario teria deixado passar.
    """
    import subprocess

    def git(*args: str) -> str:
        try:
            return subprocess.run(("git", *args), capture_output=True, text=True,
                                  timeout=15, check=False).stdout.strip()
        except Exception:  # noqa: BLE001 — sem git o carimbo sai incompleto, nao quebra
            return ""

    commit = git("rev-parse", "HEAD")
    sujo = bool(git("status", "--porcelain"))
    return {
        "gerado_em": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": commit or "desconhecido",
        # Arvore suja e' o caso da publicacao manual: o conteudo NAO esta' em
        # nenhum commit, entao ele nao pode ser tratado como ancestral de nada.
        "arvore_suja": "sim" if sujo else "nao",
    }


def carregar_doadores(cliente) -> list[list]:
    """Quem financiou quem — uma linha por doador x candidatura (ADR-033).

    Sai como ARRAY DE ARRAYS, nao de objetos: sao 23,5 mil linhas, e repetir
    catorze nomes de chave em cada uma triplicaria o download sem acrescentar
    nada. O cabecalho vai no JS da pagina.

    CPF de pessoa fisica nunca foi ingerido (ADR-020). CNPJ de empresa entra,
    porque identifica quem financia e e' de pessoa juridica.
    """
    p = cliente.project
    sql = f"""
        select nome_doador, doador_tipo, doador_cnpj, doador_uf, doador_ramo,
               vl_doado, qt_doacoes, e_o_proprio_candidato,
               sq_candidato, nome_candidato, partido_candidato, cod_cargo,
               sg_uf_candidato, candidaturas_do_doador
        from `{p}.marts.fct_ranking_doador`
        order by vl_doado desc
    """
    linhas: list[list] = []
    try:
        resultado = cliente.query(sql).result()
    except Exception as exc:  # noqa: BLE001
        log.warning("fct_ranking_doador indisponivel (%s) — site sai sem a pagina",
                    str(exc)[:90])
        return []
    for r in resultado:
        # Ficha so' existe para os cargos de CARGOS; para deputado o link
        # apontaria para pagina que nao existe.
        ficha = (f"candidato/{slug(r.nome_candidato or '')}-{r.sq_candidato}"
                 if r.cod_cargo in CARGOS and r.nome_candidato else "")
        linhas.append([
            r.nome_doador or "",
            "J" if r.doador_tipo == "juridica" else "F",
            r.doador_cnpj or "",
            r.doador_uf or "",
            "" if (r.doador_ramo or "") == RAMO_OBVIO else (r.doador_ramo or ""),
            round(float(r.vl_doado or 0), 2),
            int(r.qt_doacoes or 0),
            1 if r.e_o_proprio_candidato else 0,
            r.nome_candidato or "",
            r.partido_candidato or "",
            CARGO_CURTO_DOADOR.get(r.cod_cargo, "—"),
            r.sg_uf_candidato or "",
            int(r.candidaturas_do_doador or 1),
            ficha,
        ])
    log.info("%d linhas de doador x candidatura", len(linhas))
    return linhas


# ACIMA DISTO O FILTRO `in (...)` DEIXA DE COMPENSAR.
#
# Com os 529 majoritarios, listar os `id_pessoa` na consulta evitava ler tabelas
# inteiras. Com as 19.947 fichas da F-18 a lista cobre praticamente toda a base
# de 2026: o SQL passa de 700 kB — perto do teto de 1 MB do BigQuery — e filtra
# quase nada. Acima do teto a consulta vem inteira e o recorte acontece em
# Python, no `por_pessoa.get()` que ja' existe em toda funcao.
_TETO_FILTRO_SQL = 4000


def _filtro(chaves: dict, coluna: str = "id_pessoa") -> str:
    if len(chaves) > _TETO_FILTRO_SQL:
        return "true"
    lista = "','".join(chaves)
    return f"{coluna} in ('{lista}')"


def carregar_fichas(cliente, cargos: tuple[int, ...],
                    limite: int | None = None) -> list[Candidato]:
    """Toda candidatura que ganha pagina propria.

    Ate' 03/09/2026 so' os 529 cargos majoritarios entravam aqui. A F-18 trouxe
    as 19.418 candidaturas proporcionais para a MESMA funcao, de proposito: duas
    rotinas de carga divergiriam com o tempo, e a divergencia apareceria como
    ficha de deputado com menos rigor que a de senador — exatamente o contrario
    do que a F-18 argumenta (quem enfrenta 1.126 nomes precisa de MAIS ajuda).

    O bloco de indicadores socioeconomicos aparece em qualquer ficha, mas so'
    existe para quem ja' foi Presidente ou Governador: `fct_mandato_indicador` so'
    tem linha para mandato EXECUTIVO. Um candidato a deputado que governou um
    estado ve' o periodo daquele mandato; nenhum numero e' atribuido ao mandato
    de deputado, que e' o que a F-18 e o SPEC 2.2 proibem.
    """
    lim = f"limit {limite}" if limite else ""
    codigos = ", ".join(str(c) for c in cargos)
    p = cliente.project
    sql = f"""
        select
            d.sk_candidatura, d.sq_candidato, d.cod_cargo, d.nome_urna, d.nome_completo,
            d.sg_uf, d.sigla_partido, pt.nome_partido, d.nr_candidato, d.url_foto,
            d.genero, d.cor_raca,
            d.grau_instrucao,
            d.ocupacao, d.sg_uf_nascimento,
            d.idade_na_posse_valida as idade,
            f.situacao_julgamento, f.total_bens_declarados, f.n_bens,
            f.nome_coligacao, f.composicao_coligacao, f.sg_federacao,
            f.proposta_obrigatoria, f.tem_proposta_governo, f.url_proposta_oficial,
            f.despesa_max_campanha,
            f.tem_registro_repetido, f.n_registros_no_tse,
            d.id_pessoa
        from `{p}.marts.dim_candidato` d
        join `{p}.marts.fct_candidatura` f using (sk_candidatura)
        left join `{p}.marts.dim_partido` pt
               on pt.sigla_partido = d.sigla_partido and pt.ano_eleicao = d.ano_eleicao
        -- `e_registro_exibido` corta a re-inscricao repetida do TSE: 23
        -- pessoas de 2026 tem DOIS registros para a mesma candidatura, e sem
        -- este filtro a mesma pessoa aparece duas vezes na listagem — foi o que
        -- aconteceu com GUTO SCHIAVETTO na pagina de senadores. As duas linhas
        -- continuam no mart; a tela mostra uma. Ver a CTE `repetidos` em
        -- `fct_candidatura`.
        where d.ano_eleicao = 2026 and d.cod_cargo in ({codigos})
          and f.e_registro_exibido
        order by d.cod_cargo, d.sg_uf, d.nome_urna
        {lim}
    """
    saida, ids = [], {}
    for r in cliente.query(sql).result():
        c = Candidato(
            sk=r.sk_candidatura, sq=str(r.sq_candidato), cod_cargo=r.cod_cargo,
            nome_urna=r.nome_urna or "SEM NOME", nome_completo=r.nome_completo,
            sg_uf=r.sg_uf, sigla_partido=r.sigla_partido, nome_partido=r.nome_partido,
            nr_candidato=r.nr_candidato,
            coligacao=r.nome_coligacao, composicao=r.composicao_coligacao,
            federacao=r.sg_federacao,
            situacao=r.situacao_julgamento, url_foto=r.url_foto, idade=r.idade,
            genero=r.genero, cor_raca=r.cor_raca, grau_instrucao=r.grau_instrucao,
            ocupacao=r.ocupacao, uf_nascimento=r.sg_uf_nascimento,
            bens_total=r.total_bens_declarados, bens_n=r.n_bens,
            proposta_obrigatoria=bool(r.proposta_obrigatoria),
            tem_proposta=bool(r.tem_proposta_governo),
            url_proposta=r.url_proposta_oficial,
            limite_gasto=r.despesa_max_campanha,
            registros_no_tse=r.n_registros_no_tse or 1,
        )
        saida.append(c)
        if r.id_pessoa:
            ids.setdefault(r.id_pessoa, []).append(c)
    log.info("%d candidaturas com ficha propria", len(saida))
    _anexar_trajetoria(cliente, ids)
    _anexar_mudancas(cliente, {c.sk: c for c in saida})
    _anexar_indicadores(cliente, ids)
    _anexar_indicadores_ausentes(cliente, ids)
    _anexar_atividade(cliente, ids)
    _anexar_atividade_senado(cliente, ids)
    _anexar_data_do_dado(cliente, {c.sk: c for c in saida})
    _anexar_planos(cliente, {c.sk: c for c in saida})
    _anexar_financiamento(cliente, {c.sk: c for c in saida})
    _anexar_plenario(cliente, ids)
    _anexar_chapa(cliente, {c.sk: c for c in saida})
    return saida


def catalogo_indicadores(cliente) -> list[dict]:
    """Catalogo de indicadores COM a cobertura real, lida do lake.

    A cobertura nao e' digitada em lugar nenhum: sai de `count`/`min`/`max` sobre
    os dados que existem. Se uma serie avancar um ano, a pagina de metodologia
    avanca junto; se uma parar, a pagina passa a dizer que parou.

    A alternativa — escrever "IDEB: ate' 2025" no HTML — envelhece em silencio, e
    uma pagina de metodologia desatualizada e' pior que nenhuma: ela promete
    rigor e entrega desinformacao.
    """
    p = cliente.project
    sql = f"""
        select
            d.cod_indicador, d.nome, d.unidade, d.fonte, d.direcao_desejavel,
            min(f.ano)                          as ano_ini,
            max(f.ano)                          as ano_fim,
            count(distinct f.ano)               as n_anos,
            count(distinct f.sg_uf)             as n_ues,
            logical_or(f.sg_uf = 'BR')          as tem_br
        from `{p}.marts.dim_indicador` d
        left join `{p}.marts.fct_indicador_uf_ano` f using (cod_indicador)
        group by 1, 2, 3, 4, 5
        order by d.nome
    """
    saida = [dict(r) for r in cliente.query(sql).result()]
    log.info("%d indicadores no catalogo", len(saida))
    return saida


def _anexar_trajetoria(cliente, por_pessoa: dict[str, list[Candidato]]) -> None:
    """Candidaturas anteriores da mesma pessoa. Nao sao mandatos: quem perdeu entra."""
    if not por_pessoa:
        return
    p = cliente.project
    sql = f"""
        select d.id_pessoa, d.ano_eleicao, g.descricao as cargo, d.sg_uf,
               d.sigla_partido, f.votos_nominais,
               -- `resultado_final` = o TSE quando publicou; a apuracao por votos
               -- onde ele nao publicou (ADR-023). `origem_do_resultado` diz qual
               -- dos dois, e a tela mostra a diferenca em vez de escondê-la.
               f.resultado_final as foi_eleito, f.origem_do_resultado,
               f.nr_turno_decisivo, f.votos_no_turno_decisivo,
               -- `situacao_candidatura` diz se a pessoa chegou a concorrer, e a
               -- diferenca importa: Lula em 2018 aparece INAPTO — a candidatura
               -- foi indeferida, ele nao perdeu a eleicao.
               f.situacao_candidatura
        from `{p}.marts.dim_candidato` d
        join `{p}.marts.fct_candidatura` f using (sk_candidatura)
        join `{p}.marts.dim_cargo` g on g.cod_cargo = d.cod_cargo
        where {_filtro(por_pessoa, 'd.id_pessoa')} and d.ano_eleicao < 2026
          and f.e_registro_exibido
        order by d.ano_eleicao desc
    """
    n = 0
    for r in cliente.query(sql).result():
        for c in por_pessoa.get(r.id_pessoa, []):
            c.trajetoria.append({
                "ano": r.ano_eleicao, "cargo": r.cargo, "uf": r.sg_uf,
                "partido": r.sigla_partido, "eleito": r.foi_eleito,
                "votos": r.votos_nominais, "situacao": r.situacao_candidatura,
                "origem": r.origem_do_resultado,
                "turno": r.nr_turno_decisivo, "votos_turno": r.votos_no_turno_decisivo,
            })
            n += 1
    log.info("%d linhas de trajetoria anexadas", n)


def _anexar_mudancas(cliente, por_sk: dict[str, Candidato]) -> None:
    """Alteracoes capturadas pelo snapshot diario — irreproduzivel apos 04/10."""
    p = cliente.project
    sql = f"""
        select sk_candidatura, data_observacao, versao,
               situacao_julgamento_anterior, situacao_julgamento,
               nome_urna_anterior, nome_urna,
               sigla_partido_anterior, sigla_partido,
               mudou_julgamento, mudou_nome_urna, mudou_partido, consta_na_lista_atual
        from `{p}.marts.fct_mudanca_candidatura`
        order by data_observacao desc
    """
    n = 0
    for r in cliente.query(sql).result():
        c = por_sk.get(r.sk_candidatura)
        if not c:
            continue
        if r.mudou_julgamento:
            texto = (f"Situação do julgamento passou de "
                     f"<b>{e(r.situacao_julgamento_anterior)}</b> para "
                     f"<b>{e(r.situacao_julgamento)}</b>")
        elif r.mudou_nome_urna:
            texto = (f"Nome de urna corrigido de <b>{e(r.nome_urna_anterior)}</b> "
                     f"para <b>{e(r.nome_urna)}</b>")
        elif r.mudou_partido:
            texto = (f"Partido alterado de <b>{e(r.sigla_partido_anterior)}</b> "
                     f"para <b>{e(r.sigla_partido)}</b>")
        else:
            continue
        c.mudancas.append({"data": r.data_observacao, "texto": texto})
        n += 1
    log.info("%d alteracoes anexadas", n)


def _anexar_indicadores(cliente, por_pessoa: dict[str, list[Candidato]]) -> None:
    """Indicadores durante mandatos executivos ANTERIORES da mesma pessoa.

    So' existe para quem ja' foi Presidente ou Governador — a seed `cargo_tse`
    marca isso em `modulo_durante_mandato`. Para senador e deputado nao ha' bloco:
    o vinculo entre um parlamentar e um indicador estadual e' fraco demais para
    ser exibido sem induzir leitura errada (SPEC 2.2).

    Cada linha vem com o comparador nacional ao lado, porque a Constituicao 0.2
    proibe numero de UF sozinho na tela — e com o aviso de que o indicador
    descreve o PERIODO, nunca o efeito do mandato.
    """
    if not por_pessoa:
        return
    p = cliente.project
    sql = f"""
        select m.id_pessoa, m.cod_indicador, i.nome as indicador, m.unidade,
               m.nm_ue, m.sg_uf, m.ano_inicio, m.ano_fim, m.cod_cargo,
               m.ano_referencia_inicio, m.ano_referencia_fim,
               m.valor_inicio, m.valor_fim, m.variacao_pct,
               m.variacao_brasil_pct, m.delta_vs_brasil, m.janela_incompleta
        from `{p}.marts.fct_mandato_indicador` m
        join `{p}.marts.dim_indicador` i using (cod_indicador)
        where {_filtro(por_pessoa, 'm.id_pessoa')}
        -- A ordem final e' decidida no render (o glossario troca o nome
        -- exibido, entao ordenar por `i.nome` aqui daria outra coisa na
        -- tela). Isto aqui e' so' para a saida ser deterministica.
        order by m.ano_inicio desc, m.nm_ue, i.nome
    """
    n = 0
    for r in cliente.query(sql).result():
        for c in por_pessoa.get(r.id_pessoa, []):
            c.indicadores.append({
                "cod": r.cod_indicador, "indicador": r.indicador,
                "unidade": r.unidade, "ue": r.nm_ue, "uf": r.sg_uf,
                "cargo": r.cod_cargo, "a1": r.ano_inicio, "a2": r.ano_fim,
                "ref1": r.ano_referencia_inicio, "ref2": r.ano_referencia_fim,
                "v1": r.valor_inicio, "v2": r.valor_fim,
                "pct": r.variacao_pct, "pct_br": r.variacao_brasil_pct,
                "delta": r.delta_vs_brasil, "incompleta": r.janela_incompleta,
            })
            n += 1
    log.info("%d linhas de indicador de mandato anexadas", n)


def _anexar_indicadores_ausentes(cliente, por_pessoa: dict[str, list[Candidato]]) -> None:
    """O que NAO aparece no bloco de mandato, e por que (ADR-031).

    A Regra 5 proibe preencher buraco de dado, e o bloco cumpre: a linha nao
    existe. Mas omitir sem dizer que omitiu deixa o leitor sem distinguir "nao ha'
    dado" de "esconderam". Quem le' nao tem como saber que a PNAD Continua comeca
    em 2012 — e por isso um mandato de 2003 nao tem desemprego.
    """
    if not por_pessoa:
        return
    p = cliente.project
    sql = f"""
        select id_pessoa, ano_inicio, ano_fim, nm_ue, sg_uf, cod_cargo,
               cod_indicador, motivo, serie_inicio, serie_fim
        from `{p}.marts.fct_mandato_indicador_ausente`
        where {_filtro(por_pessoa)}
        order by ano_inicio desc, cod_indicador
    """
    n = 0
    for r in cliente.query(sql).result():
        for c in por_pessoa.get(r.id_pessoa, []):
            c.indicadores_ausentes.append({
                "a1": r.ano_inicio, "a2": r.ano_fim, "ue": r.nm_ue, "uf": r.sg_uf,
                "cargo": r.cod_cargo, "cod": r.cod_indicador,
                "motivo": r.motivo, "s1": r.serie_inicio, "s2": r.serie_fim,
            })
            n += 1
    log.info("%d ausencias de indicador anexadas", n)


def _anexar_atividade(cliente, por_pessoa: dict[str, list[Candidato]]) -> None:
    """Atividade na Camara de quem ja' foi deputado federal.

    Vale para quem passou pela Camara. O equivalente do Senado existe desde
    02/09/2026 em `_anexar_atividade_senado` (F-22): a marca de autoria principal
    fica no detalhe de cada processo, e foi validada contra o campo oficial do
    endpoint antigo antes de virar contagem (L-20 fechada).

    A classe faz parte da chave de proposito: somar projeto de lei com requerimento
    de retirada de pauta produz um numero sem significado.
    """
    if not por_pessoa:
        return
    p = cliente.project
    sql = f"""
        with atividade as (
        -- POR LEGISLATURA, e nao pela vida inteira.
        --
        -- Agregado, alguem que serviu de 2003 a 2010 e voltou em 2019 aparecia
        -- como "2003-2023", sugerindo mandato continuo que nao houve. A
        -- legislatura e' a unidade real do mandato de deputado, e quebrar por
        -- ela e' o que permite ler "o que fez em cada passagem".
        --
        -- A legislatura e' derivada do ano: a 52a comeca em 2003 e cada uma dura
        -- quatro anos. Nao ha' tabela de legislatura no lake, e a aritmetica e'
        -- exata para todo o periodo coberto.
        select id_pessoa, classe_proposicao,
               52 + div(ano - 2003, 4)          as legislatura,
               2003 + 4 * div(ano - 2003, 4)    as leg_inicio,
               2006 + 4 * div(ano - 2003, 4)    as leg_fim,
               sum(qt_proposicoes) as total,
               sum(qt_virou_norma) as virou_norma,
               min(ano) as a1, max(ano) as a2
        from `{p}.marts.fct_atividade_legislativa`
        where {_filtro(por_pessoa)} and ligado_ao_tse and ano >= 2003
        group by 1, 2, 3, 4, 5
    ),
    com_mandato as (
        -- Ter atividade registrada na Camara num ano NAO significa ter sido
        -- deputado naquele ano. Senador atua na comissao mista de Medida
        -- Provisoria, e a Camara registra a autoria: Ronaldo Caiado tem 102
        -- emendas a MP entre 2015 e 2017, quando era SENADOR. O dado e' certo;
        -- rotular aquilo de "legislatura da Camara" e' que seria falso.
        select a.*, l.id_legislatura is not null as teve_mandato
        from atividade a
        left join `{p}.marts.dim_legislatura_parlamentar` l
               on l.id_pessoa = a.id_pessoa
              and l.casa = 'camara'
              and l.id_legislatura = a.legislatura
    )
    select * from com_mandato
    order by legislatura desc, total desc
    """
    n = 0
    for r in cliente.query(sql).result():
        for c in por_pessoa.get(r.id_pessoa, []):
            c.atividade.append({
                "classe": r.classe_proposicao, "total": r.total,
                "norma": r.virou_norma, "a1": r.a1, "a2": r.a2,
                "leg": r.legislatura, "leg_ini": r.leg_inicio, "leg_fim": r.leg_fim,
                "mandato": bool(r.teve_mandato),
            })
            n += 1
    log.info("%d linhas de atividade legislativa anexadas", n)


def _anexar_data_do_dado(cliente, por_sk: dict[str, Candidato]) -> None:
    """Quando os dados de cada candidatura mudaram pela ultima vez (ADR-038).

    O rodape mostrava `max(_extracted_at)` da tabela inteira — quando o SITE
    rodou, nao quando AQUELE dado mudou. `dim_candidato` tem um unico carimbo,
    reescrito a cada ingestao, entao a data mudava todo dia em toda ficha mesmo
    quando nada na candidatura tinha mudado.

    Duas consequencias, e as duas ruins:

      - o leitor era informado da hora da maquina, nao da idade do dado;
      - toda pagina mudava todo dia, e por isso envio incremental nao economizava
        nada. Com 20.765 fichas (F-18) a publicacao diaria passaria de 2,5 horas.

    O snapshot ja' guarda a resposta certa: `dbt_valid_from` da versao vigente e'
    a data em que aquela candidatura mudou pela ultima vez. Medido em 03/09/2026:
    12.729 das 20.856 candidaturas nao mudam desde 27/08.
    """
    if not por_sk:
        return
    p = cliente.project
    try:
        linhas = list(cliente.query(f"""
            select sk_candidatura,
                   format_timestamp('%d/%m/%Y', dbt_valid_from, 'UTC') as quando
            from `{p}.marts.snap_candidatura_2026`
            where dbt_valid_to is null
        """).result())
    except Exception as exc:  # noqa: BLE001 — sem snapshot a ficha cai na data global
        log.warning("snapshot indisponivel (%s) — fichas usam a data do site",
                    str(exc)[:90])
        return
    n = 0
    for r in linhas:
        c = por_sk.get(r.sk_candidatura)
        if c is not None:
            c.dado_de = r.quando
            n += 1
    log.info("%d fichas com data propria do dado", n)


def _anexar_atividade_senado(cliente, por_pessoa: dict[str, list[Candidato]]) -> None:
    """Atividade no Senado de quem ja' foi senador (F-22, fecha a L-20).

    Espelha `_anexar_atividade` de proposito, ate' na quebra por legislatura: a
    legislatura e' de quatro anos e vale para AS DUAS CASAS — senador serve duas
    seguidas. Os dois blocos ficam lado a lado na ficha e nunca sao somados nem
    comparados entre si: deputado e senador nao propoem as mesmas coisas nem no
    mesmo volume.

    So' entram autorias PRINCIPAIS. O filtro ja' aconteceu no mart.
    """
    if not por_pessoa:
        return
    p = cliente.project
    sql = f"""
        select id_pessoa, classe_proposicao,
               52 + div(ano - 2003, 4)          as legislatura,
               2003 + 4 * div(ano - 2003, 4)    as leg_inicio,
               2006 + 4 * div(ano - 2003, 4)    as leg_fim,
               sum(qt_proposicoes)              as total,
               sum(qt_em_tramitacao)            as tramitando,
               min(ano) as a1, max(ano) as a2
        from `{p}.marts.fct_atividade_senado`
        where {_filtro(por_pessoa)} and ligado_ao_tse and ano >= 2003
        group by 1, 2, 3, 4, 5
        order by legislatura desc, total desc
    """
    try:
        linhas = list(cliente.query(sql).result())
    except Exception as exc:  # noqa: BLE001
        log.warning("fct_atividade_senado indisponivel (%s) — site sai sem o bloco",
                    str(exc)[:90])
        return
    n = 0
    for r in linhas:
        for c in por_pessoa.get(r.id_pessoa, []):
            c.atividade_senado.append({
                "classe": r.classe_proposicao, "total": r.total,
                "tramitando": r.tramitando, "a1": r.a1, "a2": r.a2,
                "leg": r.legislatura, "leg_ini": r.leg_inicio, "leg_fim": r.leg_fim,
            })
            n += 1
    log.info("%d linhas de atividade no Senado anexadas", n)


def _anexar_financiamento(cliente, por_sk: dict[str, Candidato]) -> None:
    """Receita por origem, principais doadores e despesa contratada (ADR-020).

    AUSENCIA NAO E' ZERO. Candidatura que nao aparece na prestacao de contas fica
    com `financiamento = []`, e a tela diz "prestacao ainda nao entregue". Escrever
    R$ 0,00 sugeriria campanha sem gasto onde ha' apenas prazo em aberto — o prazo
    vai ate' depois de 04/10/2026.

    O doador vem SOMADO por identidade (`sk_doador`), nunca por nome: quem fez
    cinquenta transferencias e' um doador, e cinquenta linhas iguais na tela dariam
    a impressao de cinquenta apoiadores.
    """
    p = cliente.project
    try:
        origens = list(cliente.query(f"""
            select sk_candidatura, origem_recurso, vl_receita, qt_doadores,
                   vl_autofinanciamento, dt_ultima_receita
            from `{p}.marts.fct_financiamento_candidatura`
            order by vl_receita desc
        """).result())
        doadores = list(cliente.query(f"""
            select sk_candidatura, nome_doador, doador_cnpj, doador_tipo,
                   doador_ramo, vl_doado, qt_doacoes, e_o_proprio_candidato
            from `{p}.marts.fct_doador_candidatura`
            qualify row_number() over (
                partition by sk_candidatura order by vl_doado desc) <= 20
        """).result())
        despesas = list(cliente.query(f"""
            select sk_candidatura, sum(valor) as total
            from `{p}.stg.stg_tse__despesas_campanha`
            group by 1
        """).result())
    except Exception as exc:  # noqa: BLE001
        log.warning("financiamento indisponivel (%s) — o site sai sem o bloco",
                    str(exc)[:90])
        return

    for r in origens:
        c = por_sk.get(r.sk_candidatura)
        if c:
            c.financiamento.append({
                "origem": r.origem_recurso, "valor": float(r.vl_receita),
                "doadores": r.qt_doadores,
                "proprio": float(r.vl_autofinanciamento or 0),
                "ate": r.dt_ultima_receita.isoformat() if r.dt_ultima_receita else None,
            })
    for r in doadores:
        c = por_sk.get(r.sk_candidatura)
        if c:
            c.doadores.append({
                "nome": r.nome_doador, "cnpj": r.doador_cnpj,
                "tipo": r.doador_tipo, "ramo": r.doador_ramo,
                "valor": float(r.vl_doado), "n": r.qt_doacoes,
                "proprio": bool(r.e_o_proprio_candidato),
            })
    for r in despesas:
        c = por_sk.get(r.sk_candidatura)
        if c:
            c.despesa_contratada = float(r.total)

    com = sum(1 for c in por_sk.values() if c.financiamento)
    log.info("%d de %d candidaturas com prestacao de contas declarada",
             com, len(por_sk))


def _anexar_plenario(cliente, por_pessoa: dict[str, list[Candidato]]) -> None:
    """Quantas vezes votou e em quantos eventos esteve, por legislatura (F-20).

    NAO ha' taxa de presenca, e a ausencia e' deliberada: a fonte diz onde a
    pessoa esteve, nao a quantos eventos ela DEVIA comparecer. Sem denominador
    nao existe percentual honesto, e um numero errado ali seria uma acusacao
    publicada sobre uma pessoa real (ADR-025).
    """
    if not por_pessoa:
        return
    p = cliente.project
    sql = f"""
        select id_pessoa,
               id_legislatura                       as leg,
               2003 + 4 * (id_legislatura - 52)     as leg_ini,
               2006 + 4 * (id_legislatura - 52)     as leg_fim,
               sum(qt_votacoes)                     as votacoes,
               sum(qt_sim)                          as sim,
               sum(qt_nao)                          as nao,
               sum(qt_abstencao)                    as abstencao,
               sum(qt_obstrucao)                    as obstrucao,
               sum(qt_eventos)                      as eventos,
               sum(qt_eventos_plenario)             as eventos_plenario
        from `{p}.marts.fct_plenario_deputado`
        where {_filtro(por_pessoa)} and ligado_ao_tse
        group by 1, 2, 3, 4
    """
    n = 0
    for r in cliente.query(sql).result():
        for c in por_pessoa.get(r.id_pessoa, []):
            c.plenario.append({
                "leg": r.leg, "leg_ini": r.leg_ini, "leg_fim": r.leg_fim,
                "votacoes": r.votacoes, "sim": r.sim, "nao": r.nao,
                "abstencao": r.abstencao, "obstrucao": r.obstrucao,
                "eventos": r.eventos, "plenario": r.eventos_plenario,
            })
            n += 1
    log.info("%d linhas de plenario anexadas", n)


def _anexar_chapa(cliente, por_sk: dict[str, Candidato]) -> None:
    """Vice ou suplentes de cada chapa majoritaria (F-21).

    O vinculo nao existe no pacote em lote do TSE — so' no DivulgaCandContas.
    Sem ele, Alckmin esta' na base como candidato a Vice-Presidente pelo PSB e
    nada diz que ele concorre com Lula.
    """
    p = cliente.project
    try:
        linhas = list(cliente.query(f"""
            select sk_titular, nome_urna_titular, cod_cargo_titular,
                   sk_vice, sq_vice, ordem, cargo_vice, nome_urna_vice,
                   nome_completo_vice, sigla_partido_vice, url_foto_vice,
                   id_pessoa_vice, vice_encontrado
            from `{p}.marts.dim_chapa`
            order by sk_titular, ordem
        """).result())
    except Exception as exc:  # noqa: BLE001
        log.warning("dim_chapa indisponivel (%s) — o site sai sem a chapa",
                    str(exc)[:80])
        return
    n, m = 0, 0
    for r in linhas:
        if not r.vice_encontrado:
            continue
        vice = por_sk.get(r.sk_vice)
        titular = por_sk.get(r.sk_titular)

        # A ficha do TITULAR mostra o vice — e agora LINKA para ele, quando o
        # vice tem ficha (presidente e governador tem; suplente de senador nao).
        if titular is not None:
            titular.chapa.append({
                "cargo": r.cargo_vice, "nome": r.nome_urna_vice,
                "completo": r.nome_completo_vice, "partido": r.sigla_partido_vice,
                "foto": r.url_foto_vice,
                "url": vice.url if vice is not None else None,
            })
            n += 1

        # E a ficha do VICE mostra com quem ele concorre. Sem isto a ficha do
        # vice seria a de alguem que aparece do nada: e' a chapa que explica por
        # que aquela pessoa esta' na eleicao.
        if vice is not None and titular is not None:
            vice.chapa_titular = {
                "nome": r.nome_urna_titular,
                "cargo": CARGOS.get(r.cod_cargo_titular, ("", "—", ""))[1],
                "partido": titular.sigla_partido,
                "completo": titular.nome_completo,
                "foto": titular.url_foto,
                "url": titular.url,
            }
            m += 1
    log.info("%d vices/suplentes anexados ao titular; %d titulares anexados ao vice",
             n, m)


def _anexar_planos(cliente, por_sk: dict[str, Candidato]) -> None:
    """Texto integral do plano de governo (ADR-019).

    Vem de `raw_tse.planos`, tabela que so' existe porque o endpoint certo do TSE
    foi encontrado no bundle do proprio app. Onde `texto` e' nulo ha' um `motivo`
    legivel — PDF escaneado, protegido, ilegivel — e a tela diz qual, em vez de
    mostrar um bloco vazio.
    """
    p = cliente.project
    try:
        linhas = list(cliente.query(f"""
            select sk_candidatura, texto, n_paginas, motivo, url_pdf
            from `{p}.raw_tse.planos`
        """).result())
    except Exception as exc:  # noqa: BLE001
        log.warning("raw_tse.planos indisponivel (%s) — o site sai sem os planos",
                    str(exc)[:80])
        return
    com = 0
    for r in linhas:
        c = por_sk.get(r.sk_candidatura)
        if not c:
            continue
        c.plano_texto = r.texto
        c.plano_paginas = r.n_paginas
        c.plano_motivo = r.motivo
        c.plano_url_pdf = r.url_pdf
        if r.texto:
            com += 1
    log.info("%d planos com texto integral anexados", com)


def carregar_proporcionais(cliente) -> dict[str, list[dict]]:
    """Base das listagens filtraveis. Um JSON por cargo, filtrado no navegador."""
    p = cliente.project
    sql = f"""
        with ativ as (
          select id_pessoa,
                 sum(if(classe_proposicao='normativa', qt_proposicoes, 0)) as normativa,
                 sum(if(classe_proposicao='fiscalizacao', qt_proposicoes, 0)) as fiscalizacao,
                 sum(qt_virou_norma) as virou_norma
          from `{p}.marts.fct_atividade_legislativa`
          where ligado_ao_tse group by 1
        )
        select d.cod_cargo, d.sq_candidato, d.nome_urna, d.sg_uf, d.sigla_partido,
               f.situacao_julgamento, d.url_foto, d.genero, d.grau_instrucao, d.ocupacao,
               d.idade_na_posse_valida as idade, f.nome_coligacao,
               -- O numero na urna e' a informacao mais operacional que existe
               -- numa lista de 1.126 nomes, e era a unica que faltava: quem
               -- decide o voto digita o numero, nao o nome.
               d.nr_candidato, f.sg_federacao,
               a.normativa, a.fiscalizacao, a.virou_norma
        from `{p}.marts.dim_candidato` d
        join `{p}.marts.fct_candidatura` f using (sk_candidatura)
        left join ativ a on a.id_pessoa = d.id_pessoa
        where d.ano_eleicao = 2026 and d.cod_cargo in (6, 7, 8)
          and f.e_registro_exibido
        order by d.sg_uf, d.nome_urna
    """
    por_cargo: dict[str, list[dict]] = {}
    for r in cliente.query(sql).result():
        chave = PROPORCIONAIS[r.cod_cargo][0]
        por_cargo.setdefault(chave, []).append({
            # `s` e' o pedaco do endereco da ficha (F-18). Vai pronto do
            # gerador porque `slug()` normaliza acento em NFD e descarta o que
            # nao e' ASCII — reimplementar isso em JavaScript daria endereco
            # diferente para "JOSÉ" em algum navegador, e link quebrado numa
            # ficha e' pior que link nenhum.
            "s": slug(r.nome_urna or "SEM NOME"),
            "sq": str(r.sq_candidato), "nome": r.nome_urna, "uf": r.sg_uf,
            "nr": r.nr_candidato, "fed": r.sg_federacao,
            "partido": r.sigla_partido, "situacao": r.situacao_julgamento,
            "foto": r.url_foto, "genero": r.genero, "instrucao": r.grau_instrucao,
            "ocupacao": r.ocupacao, "idade": r.idade, "coligacao": r.nome_coligacao,
            "pl": r.normativa, "fisc": r.fiscalizacao, "norma": r.virou_norma,
        })
    for k, v in por_cargo.items():
        log.info("%s: %d candidaturas", k, len(v))
    return por_cargo


def extraido_em(cliente) -> str:
    p = cliente.project
    sql = (f"select format_timestamp('%d/%m/%Y %H:%M', max(_extracted_at), 'UTC') as q "
           f"from `{p}.marts.dim_candidato`")
    return list(cliente.query(sql).result())[0].q


def main(argv: list[str] | None = None) -> int:
    global BASE_URL  # noqa: PLW0603 — rebind por --base, ver abaixo
    ap = argparse.ArgumentParser(prog="gerar_site", description=__doc__)
    ap.add_argument("--saida", default="site", help="diretorio de saida (padrao: site)")
    ap.add_argument("--limite", type=int, help="gera so' N fichas — para testar rapido")
    ap.add_argument("--sem-proporcionais", action="store_true",
                    help="gera so' os cargos majoritarios — para iterar rapido "
                         "no visual. NAO publique: a limpeza de orfas recusa uma "
                         "saida assim, por ser indistinguivel de geracao truncada")
    ap.add_argument("--base", help="prefixo dos links (padrao: %(default)s)",
                    default=BASE_URL)
    args = ap.parse_args(argv)

    from scripts import render_site  # noqa: PLC0415

    # As f-strings do render leem BASE_URL na hora da chamada, entao trocar aqui
    # muda todo link interno de uma vez.
    BASE_URL = args.base.rstrip("/")
    render_site.BASE_URL = BASE_URL
    escrever_site = render_site.escrever_site

    cliente = _cliente()
    quando = extraido_em(cliente)
    cargos = tuple(CARGOS) if args.sem_proporcionais else tuple(TODOS_CARGOS)
    fichas = carregar_fichas(cliente, cargos, args.limite)
    proporcionais = carregar_proporcionais(cliente)
    doadores = carregar_doadores(cliente)
    catalogo = catalogo_indicadores(cliente)

    destino = Path(args.saida)
    escrever_site(destino, fichas, proporcionais, quando, catalogo,
                  doadores)
    n = sum(1 for _ in destino.rglob("*.html"))
    log.info("site em %s — %d paginas HTML", destino.resolve(), n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
