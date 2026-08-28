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
    trajetoria: list[dict] = field(default_factory=list)
    mudancas: list[dict] = field(default_factory=list)

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
            d.sg_uf, d.sigla_partido, d.url_foto, d.genero, d.cor_raca, d.grau_instrucao,
            d.ocupacao, d.sg_uf_nascimento,
            d.idade_na_posse_valida as idade,
            f.situacao_julgamento, f.total_bens_declarados, f.n_bens,
            f.proposta_obrigatoria, f.tem_proposta_governo, f.url_proposta_oficial,
            d.id_pessoa
        from `{p}.marts.dim_candidato` d
        join `{p}.marts.fct_candidatura` f using (sk_candidatura)
        where d.ano_eleicao = 2026 and d.cod_cargo in (1, 3, 5)
        order by d.cod_cargo, d.sg_uf, d.nome_urna
        {lim}
    """
    saida, ids = [], {}
    for r in cliente.query(sql).result():
        c = Candidato(
            sk=r.sk_candidatura, sq=str(r.sq_candidato), cod_cargo=r.cod_cargo,
            nome_urna=r.nome_urna or "SEM NOME", nome_completo=r.nome_completo,
            sg_uf=r.sg_uf, sigla_partido=r.sigla_partido,
            situacao=r.situacao_julgamento, url_foto=r.url_foto, idade=r.idade,
            genero=r.genero, cor_raca=r.cor_raca, grau_instrucao=r.grau_instrucao,
            ocupacao=r.ocupacao, uf_nascimento=r.sg_uf_nascimento,
            bens_total=r.total_bens_declarados, bens_n=r.n_bens,
            proposta_obrigatoria=bool(r.proposta_obrigatoria),
            tem_proposta=bool(r.tem_proposta_governo),
            url_proposta=r.url_proposta_oficial,
        )
        saida.append(c)
        if r.id_pessoa:
            ids.setdefault(r.id_pessoa, []).append(c)
    log.info("%d candidaturas majoritarias", len(saida))
    _anexar_trajetoria(cliente, ids)
    _anexar_mudancas(cliente, {c.sk: c for c in saida})
    return saida


def _anexar_trajetoria(cliente, por_pessoa: dict[str, list[Candidato]]) -> None:
    """Candidaturas anteriores da mesma pessoa. Nao sao mandatos: quem perdeu entra."""
    if not por_pessoa:
        return
    p = cliente.project
    lista = "','".join(por_pessoa)
    sql = f"""
        select d.id_pessoa, d.ano_eleicao, g.descricao as cargo, d.sg_uf,
               d.sigla_partido, f.foi_eleito, f.votos_nominais
        from `{p}.marts.dim_candidato` d
        join `{p}.marts.fct_candidatura` f using (sk_candidatura)
        join `{p}.marts.dim_cargo` g on g.cod_cargo = d.cod_cargo
        where d.id_pessoa in ('{lista}') and d.ano_eleicao < 2026
        order by d.ano_eleicao desc
    """
    n = 0
    for r in cliente.query(sql).result():
        for c in por_pessoa.get(r.id_pessoa, []):
            c.trajetoria.append({
                "ano": r.ano_eleicao, "cargo": r.cargo, "uf": r.sg_uf,
                "partido": r.sigla_partido, "eleito": r.foi_eleito,
                "votos": r.votos_nominais,
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


def carregar_proporcionais(cliente) -> dict[str, list[dict]]:
    """Base das listagens filtraveis. Um JSON por cargo, filtrado no navegador."""
    p = cliente.project
    sql = f"""
        select d.cod_cargo, d.sq_candidato, d.nome_urna, d.sg_uf, d.sigla_partido,
               f.situacao_julgamento, d.url_foto, d.genero, d.grau_instrucao, d.ocupacao,
               d.idade_na_posse_valida as idade
        from `{p}.marts.dim_candidato` d
        join `{p}.marts.fct_candidatura` f using (sk_candidatura)
        where d.ano_eleicao = 2026 and d.cod_cargo in (6, 7, 8)
        order by d.sg_uf, d.nome_urna
    """
    por_cargo: dict[str, list[dict]] = {}
    for r in cliente.query(sql).result():
        chave = PROPORCIONAIS[r.cod_cargo][0]
        por_cargo.setdefault(chave, []).append({
            "sq": str(r.sq_candidato), "nome": r.nome_urna, "uf": r.sg_uf,
            "partido": r.sigla_partido, "situacao": r.situacao_julgamento,
            "foto": r.url_foto, "genero": r.genero, "instrucao": r.grau_instrucao,
            "ocupacao": r.ocupacao, "idade": r.idade,
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
    ap = argparse.ArgumentParser(prog="gerar_site", description=__doc__)
    ap.add_argument("--saida", default="site", help="diretorio de saida (padrao: site)")
    ap.add_argument("--limite", type=int, help="gera so' N fichas — para testar rapido")
    args = ap.parse_args(argv)

    from scripts.render_site import escrever_site  # noqa: PLC0415

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
