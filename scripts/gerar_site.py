"""Gerador do Dossie Eleitoral — F-07 / ADR-018.

    python scripts/gerar_site.py [--saida site] [--limite 20]

Le' `marts` e escreve um site ESTATICO. Sem servidor: o dado muda uma vez por dia,
entao pagar query por visita seria desperdicio (Constituicao 5).

O QUE E' GERADO

    /                          porta de entrada
    /presidente/               13 candidaturas
    /governador/               198
    /senador/                  318
    /deputado-federal/         listagem filtravel (JSON)
    /deputado-estadual/        listagem filtravel (JSON)
    /candidato/<slug>-<sq>/    ficha propria — SO' para os 529 majoritarios
    /dados/*.json              base das listagens filtraveis
    /sitemap.xml

POR QUE SO' 529 FICHAS PROPRIAS

Sao 20.765 candidaturas. Gerar uma pagina para cada produziria 19 mil paginas
quase identicas — o Google chama isso de conteudo raso e pode penalizar o dominio
inteiro. Majoritario tem plano de governo, trajetoria densa e disputa nacional ou
estadual; proporcional tem meia duzia de campos declarados.

Entao: ficha indexavel para quem tem conteudo, listagem filtravel para o resto.

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
from pathlib import Path
from typing import Any

from ingest.common.config import get_settings
from ingest.common.log import get_logger

log = get_logger("site")

# Prefixo de todo link interno e de toda URL canonica. Em producao e' o endereco
# publico; para conferir no navegador local, `--base http://localhost:8000` faz o
# site inteiro funcionar sem servidor de producao.
BASE_URL = "https://datadubaintel.com/dossie"

CARGOS = {
    1: ("presidente", "Presidente", "Brasil"),
    3: ("governador", "Governador", "estadual"),
    5: ("senador", "Senador", "estadual"),
}
PROPORCIONAIS = {
    6: ("deputado-federal", "Deputado Federal"),
    7: ("deputado-estadual", "Deputado Estadual"),
    8: ("deputado-distrital", "Deputado Distrital"),
}

_NAO_ALFANUM = re.compile(r"[^a-z0-9]+")


def slug(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode()
    return _NAO_ALFANUM.sub("-", sem_acento.lower()).strip("-") or "sem-nome"


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
    atividade: list[dict] = field(default_factory=list)
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
        return CARGOS[self.cod_cargo][1]


# ── consultas ───────────────────────────────────────────────────────────────


def _cliente():
    from google.cloud import bigquery

    s = get_settings()
    return bigquery.Client(project=s.project, location=s.location)


def carregar_majoritarios(cliente, limite: int | None) -> list[Candidato]:
    lim = f"limit {limite}" if limite else ""
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
        where d.ano_eleicao = 2026 and d.cod_cargo in (1, 3, 5)
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
    log.info("%d candidaturas majoritarias", len(saida))
    _anexar_trajetoria(cliente, ids)
    _anexar_mudancas(cliente, {c.sk: c for c in saida})
    _anexar_indicadores(cliente, ids)
    _anexar_atividade(cliente, ids)
    _anexar_planos(cliente, {c.sk: c for c in saida})
    _anexar_financiamento(cliente, {c.sk: c for c in saida})
    return saida


def _anexar_trajetoria(cliente, por_pessoa: dict[str, list[Candidato]]) -> None:
    """Candidaturas anteriores da mesma pessoa. Nao sao mandatos: quem perdeu entra."""
    if not por_pessoa:
        return
    p = cliente.project
    lista = "','".join(por_pessoa)
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
        where d.id_pessoa in ('{lista}') and d.ano_eleicao < 2026
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
    lista = "','".join(por_pessoa)
    sql = f"""
        select m.id_pessoa, m.cod_indicador, i.nome as indicador, m.unidade,
               m.nm_ue, m.ano_inicio, m.ano_fim, m.cod_cargo,
               m.ano_referencia_inicio, m.ano_referencia_fim,
               m.valor_inicio, m.valor_fim, m.variacao_pct,
               m.variacao_brasil_pct, m.delta_vs_brasil, m.janela_incompleta
        from `{p}.marts.fct_mandato_indicador` m
        join `{p}.marts.dim_indicador` i using (cod_indicador)
        where m.id_pessoa in ('{lista}')
        order by m.ano_inicio desc, i.nome
    """
    n = 0
    for r in cliente.query(sql).result():
        for c in por_pessoa.get(r.id_pessoa, []):
            c.indicadores.append({
                "cod": r.cod_indicador, "indicador": r.indicador,
                "unidade": r.unidade, "ue": r.nm_ue,
                "cargo": r.cod_cargo, "a1": r.ano_inicio, "a2": r.ano_fim,
                "ref1": r.ano_referencia_inicio, "ref2": r.ano_referencia_fim,
                "v1": r.valor_inicio, "v2": r.valor_fim,
                "pct": r.variacao_pct, "pct_br": r.variacao_brasil_pct,
                "delta": r.delta_vs_brasil, "incompleta": r.janela_incompleta,
            })
            n += 1
    log.info("%d linhas de indicador de mandato anexadas", n)


def _anexar_atividade(cliente, por_pessoa: dict[str, list[Candidato]]) -> None:
    """Atividade na Camara de quem ja' foi deputado federal.

    Vale para 43 dos 317 candidatos a senador e 5 dos 197 a governador — os que
    passaram pela Camara antes. Nao existe equivalente para o SENADO: a fonte nao
    publica marca de proponente, e uma contagem sem esse filtro pareceria
    comparavel a' da Camara sem ser (L-20).

    A classe faz parte da chave de proposito: somar projeto de lei com requerimento
    de retirada de pauta produz um numero sem significado.
    """
    if not por_pessoa:
        return
    p = cliente.project
    lista = "','".join(por_pessoa)
    sql = f"""
        select id_pessoa, classe_proposicao,
               sum(qt_proposicoes) as total,
               sum(qt_virou_norma) as virou_norma,
               min(ano) as a1, max(ano) as a2
        from `{p}.marts.fct_atividade_legislativa`
        where id_pessoa in ('{lista}') and ligado_ao_tse
        group by 1, 2
        order by total desc
    """
    n = 0
    for r in cliente.query(sql).result():
        for c in por_pessoa.get(r.id_pessoa, []):
            c.atividade.append({
                "classe": r.classe_proposicao, "total": r.total,
                "norma": r.virou_norma, "a1": r.a1, "a2": r.a2,
            })
            n += 1
    log.info("%d linhas de atividade legislativa anexadas", n)


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
            "sq": str(r.sq_candidato), "nome": r.nome_urna, "uf": r.sg_uf,
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
    majoritarios = carregar_majoritarios(cliente, args.limite)
    proporcionais = carregar_proporcionais(cliente)

    destino = Path(args.saida)
    escrever_site(destino, majoritarios, proporcionais, quando)
    n = sum(1 for _ in destino.rglob("*.html"))
    log.info("site em %s — %d paginas HTML", destino.resolve(), n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
