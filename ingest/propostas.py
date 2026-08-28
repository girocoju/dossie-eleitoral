"""Proposta de governo dos candidatos majoritarios — F-14 (S14).

    python -m ingest.propostas load   [--ano 2026] [--dry-run] [--target local]
    python -m ingest.propostas verify [--ano 2026]

A proposta de governo e' exigida pela Lei 9.504/97 (art. 11, par. 1o, IX) apenas
de candidatos a Prefeito, Governador e Presidente. Em 2026 isso sao 211 de 20.769
candidaturas (1,0%): 13 a Presidente e 198 a Governador.

SENADOR fica de fora, ainda que o cargo seja majoritario — a lei nao o inclui, e a
medicao confirma: 0 de 318 senadores tem proposta. Tratar isso como "nao consta"
seria acusar 318 pessoas de uma omissao que a lei nunca exigiu delas.

A tela precisa dizer "nao se aplica a este cargo" com todas as letras, em vez de
deixar campo vazio (SPEC F-14).

Nao existe pacote em lote (docs/LACUNAS.md, L-17). A fonte e' a API do
DivulgaCandContas, que responde com o mesmo conjunto de cabecalhos de navegador
que o CDN exige (L-18):

    /divulga/rest/v1/candidatura/buscar/{ano}/{UE}/{ID_ELEICAO}/candidato/{sq}

O campo `arquivos` traz os documentos do candidato; a proposta e' a de
`codTipo = 5`. Os demais sao certidoes judiciais (TRF, TJ), que o projeto ignora.

O PDF em si NAO e' baixado nem re-hospedado (ADR-013): guarda-se a existencia, o
nome do arquivo e o link para a pagina oficial. O leitor confere na fonte.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from typing import Any

from ingest.common.config import DATASET_RAW_TSE, get_settings
from ingest.common.http import get_json, utc_now
from ingest.common.log import get_logger
from ingest.common.writer import NdjsonWriter

log = get_logger("propostas")

DOMINIO = "https://divulgacandcontas.tse.jus.br"
API = f"{DOMINIO}/divulga/rest/v1"

# Id da eleicao no DivulgaCandContas — NAO e' o `cd_eleicao` do portal de dados
# abertos (6257/6259). Obtido de `/divulga/rest/v1/ata/ordinarias`, onde a
# "Eleicao Geral Federal 2026" aparece com este id. Conferido em 28/08/2026:
# o mesmo id atende presidente, governador e senador — quem delimita o escopo e'
# a unidade eleitoral no caminho.
ID_ELEICAO = {2026: 20322002026}

# `codTipo` do documento "proposta de governo". Codigo nao documentado, inferido
# da observacao: os demais tipos do mesmo candidato sao certidoes judiciais.
COD_TIPO_PROPOSTA = "5"

# Cargos que a LEI obriga a apresentar proposta de governo: Lei 9.504/97, art. 11,
# par. 1o, IX — "propostas defendidas pelo candidato a Prefeito, a Governador de
# Estado ou do Distrito Federal e a Presidente da Republica". SENADOR NAO ESTA NA
# LISTA, ainda que o cargo seja majoritario.
#
# Medido em 28/08/2026, consultando as 529 candidaturas majoritarias:
#   Presidente   13 de  13  (100,0%)
#   Governador  193 de 198  ( 97,5%)
#   Senador       0 de 318  (  0,0%)
#
# Os zeros do Senado nao sao omissao dos candidatos — e' que a lei nao pede. Por
# isso senador nao e' consultado nem rotulado como "nao consta": para ele a tela
# diz "nao se aplica a este cargo".
CARGOS_COM_PROPOSTA = (1, 3)

PAUSA = 2.0
MAX_IDADE_DIAS = 7


@dataclass(frozen=True)
class Proposta:
    sk_candidatura: str
    sq_candidato: str
    sg_ue: str
    cod_cargo: int
    nome_urna: str | None
    tem_proposta: bool
    n_arquivos: int
    nome_arquivo: str | None
    url_oficial: str


def url_pagina_oficial(ano: int, sg_ue: str, sq_candidato: str) -> str:
    """Pagina publica do candidato no DivulgaCandContas.

    E' uma rota de SPA, entao qualquer caminho devolve 200 e nao da' para validar
    por status HTTP. O formato foi lido das rotas do proprio app (ADR-013).
    """
    return f"{DOMINIO}/divulga/#/candidato/{ano}/{ID_ELEICAO[ano]}/{sg_ue}/{sq_candidato}"


def consultar(ano: int, sg_ue: str, sq_candidato: str) -> dict[str, Any] | None:
    url = f"{API}/candidatura/buscar/{ano}/{sg_ue}/{ID_ELEICAO[ano]}/candidato/{sq_candidato}"
    try:
        return get_json(url, timeout=45, attempts=3)
    except Exception as exc:  # noqa: BLE001 — uma candidatura sem resposta nao para a carga
        log.warning("%s/%s: %s", sg_ue, sq_candidato, str(exc)[:120])
        return None


def extrair(
    detalhe: dict[str, Any] | None, ano: int, sg_ue: str, sq: str, cod_cargo: int, nome: str | None
) -> Proposta:
    arquivos = (detalhe or {}).get("arquivos") or []
    propostas = [a for a in arquivos if str(a.get("codTipo")) == COD_TIPO_PROPOSTA]
    return Proposta(
        sk_candidatura=f"{ano}-{sg_ue}-{sq}",
        sq_candidato=sq,
        sg_ue=sg_ue,
        cod_cargo=cod_cargo,
        nome_urna=nome,
        tem_proposta=bool(propostas),
        n_arquivos=len(propostas),
        nome_arquivo=propostas[0].get("nome") if propostas else None,
        url_oficial=url_pagina_oficial(ano, sg_ue, sq),
    )


def candidaturas_majoritarias(ano: int, max_idade_dias: int) -> list[tuple[str, str, int, str]]:
    """Quem consultar: majoritarios sem registro ou com registro velho.

    O pipeline roda todo dia; reconsultar 529 candidaturas diariamente seria 18
    minutos de requisicao para um dado que muda raramente. Nos dias em que nada
    envelheceu, esta funcao devolve lista vazia e a etapa custa uma query.
    """
    from google.cloud import bigquery

    settings = get_settings()
    cliente = bigquery.Client(project=settings.project, location=settings.location)
    cargos = ", ".join(str(c) for c in CARGOS_COM_PROPOSTA)
    consulta = f"""
        with alvo as (
            select f.sk_candidatura, f.sq_candidato, f.sg_ue, f.cod_cargo, d.nome_urna
            from `{settings.project}.marts.fct_candidatura` f
            join `{settings.project}.marts.dim_candidato` d using (sk_candidatura)
            where f.ano_eleicao = {ano} and f.cod_cargo in ({cargos})
        ),
        ja_temos as (
            select sk_candidatura, max(_extracted_at) as visto_em
            from `{settings.project}.raw_tse.propostas`
            group by sk_candidatura
        )
        select a.sq_candidato, a.sg_ue, a.cod_cargo, a.nome_urna
        from alvo a
        left join ja_temos j using (sk_candidatura)
        where j.visto_em is null
           or j.visto_em < timestamp_sub(current_timestamp(), interval {max_idade_dias} day)
        order by a.cod_cargo, a.sg_ue
    """
    try:
        linhas = list(cliente.query(consulta).result())
    except Exception as exc:  # tabela ainda nao existe na primeira execucao
        if "propostas" not in str(exc):
            raise
        log.info("raw_tse.propostas ainda nao existe — consultando todas as candidaturas")
        consulta_sem_historico = f"""
            select f.sq_candidato, f.sg_ue, f.cod_cargo, d.nome_urna
            from `{settings.project}.marts.fct_candidatura` f
            join `{settings.project}.marts.dim_candidato` d using (sk_candidatura)
            where f.ano_eleicao = {ano} and f.cod_cargo in ({cargos})
            order by f.cod_cargo, f.sg_ue
        """
        linhas = list(cliente.query(consulta_sem_historico).result())
    return [(r.sq_candidato, r.sg_ue, r.cod_cargo, r.nome_urna) for r in linhas]


def _schema():
    from google.cloud import bigquery

    from ingest.common.bq import build_schema

    schema = build_schema(
        ["sk_candidatura", "sq_candidato", "sg_ue", "nome_urna", "nome_arquivo", "url_oficial"]
    )
    corte = 6
    return (
        schema[:corte]
        + [
            bigquery.SchemaField("cod_cargo", "INT64"),
            bigquery.SchemaField("n_arquivos", "INT64"),
            bigquery.SchemaField("tem_proposta", "BOOL"),
        ]
        + schema[corte:]
    )


def cmd_load(args: argparse.Namespace) -> int:
    settings = get_settings()
    settings.ensure_dirs()
    if args.ano not in ID_ELEICAO:
        log.error(
            "sem id de eleicao para %s. Obtenha em %s/ata/ordinarias e acrescente em ID_ELEICAO.",
            args.ano,
            API,
        )
        return 1

    alvos = candidaturas_majoritarias(args.ano, args.max_idade_dias)
    log.info("%d candidatura(s) majoritaria(s) a consultar", len(alvos))
    if not alvos:
        log.info("nada envelhecido — nenhuma requisicao feita")
        return 0
    if args.dry_run:
        for sq, ue, cargo, nome in alvos[:5]:
            log.info("[dry-run] consultaria %s/%s (cargo %s, %s)", ue, sq, cargo, nome)
        return 0

    destino = settings.staging_dir / "propostas" / f"propostas_{args.ano}.ndjson.gz"
    extraido_em = utc_now()
    com_proposta = 0

    with NdjsonWriter(destino) as writer:
        for i, (sq, ue, cargo, nome) in enumerate(alvos, 1):
            detalhe = consultar(args.ano, ue, sq)
            p = extrair(detalhe, args.ano, ue, sq, cargo, nome)
            com_proposta += int(p.tem_proposta)
            writer.write(
                {
                    "sk_candidatura": p.sk_candidatura,
                    "sq_candidato": p.sq_candidato,
                    "sg_ue": p.sg_ue,
                    "nome_urna": p.nome_urna,
                    "nome_arquivo": p.nome_arquivo,
                    "url_oficial": p.url_oficial,
                    "cod_cargo": p.cod_cargo,
                    "n_arquivos": p.n_arquivos,
                    "tem_proposta": p.tem_proposta,
                    "_extracted_at": extraido_em,
                    "_source_url": (
                        f"{API}/candidatura/buscar/{args.ano}/{ue}/"
                        f"{ID_ELEICAO[args.ano]}/candidato/{sq}"
                    ),
                    "_source_file": "divulgacandcontas",
                    "_source_sha256": "",
                }
            )
            if i % 50 == 0:
                log.info("%d/%d consultadas, %d com proposta", i, len(alvos), com_proposta)
            time.sleep(PAUSA)

    log.info(
        "%d consultadas | %d com proposta (%.1f%%)",
        len(alvos),
        com_proposta,
        100 * com_proposta / len(alvos),
    )
    if args.target == "local":
        log.info("NDJSON em %s", destino)
        return 0

    from ingest.common.bq import ensure_datasets, load_ndjson

    ensure_datasets()
    load_ndjson(destino, DATASET_RAW_TSE, "propostas", schema=_schema(), clustering=("sg_ue",))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Consulta uma amostra e mostra o que a API devolve. Nao carrega nada."""
    alvos = candidaturas_majoritarias(args.ano, max_idade_dias=0)[: args.amostra]
    print(f"amostra de {len(alvos)} candidaturas majoritarias\n")
    com = 0
    for sq, ue, cargo, nome in alvos:
        detalhe = consultar(args.ano, ue, sq)
        p = extrair(detalhe, args.ano, ue, sq, cargo, nome)
        com += int(p.tem_proposta)
        marca = "tem" if p.tem_proposta else "NAO CONSTA"
        print(f"  {ue} cargo={cargo} {str(nome)[:22]:<22} {marca:<11} {str(p.nome_arquivo)[:40]}")
        time.sleep(PAUSA)
    print(f"\n{com} de {len(alvos)} com proposta de governo.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ingest.propostas", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_load = sub.add_parser("load", help="consulta a API e carrega as propostas")
    p_load.add_argument("--ano", type=int, default=2026)
    p_load.add_argument("--dry-run", action="store_true")
    p_load.add_argument("--target", choices=("bigquery", "local"), default="bigquery")
    p_load.add_argument(
        "--max-idade-dias",
        type=int,
        default=MAX_IDADE_DIAS,
        help="reconsulta so' registros mais velhos que isto (0 = todos)",
    )
    p_load.set_defaults(func=cmd_load)

    p_ver = sub.add_parser("verify", help="consulta uma amostra e mostra o resultado")
    p_ver.add_argument("--ano", type=int, default=2026)
    p_ver.add_argument("--amostra", type=int, default=10)
    p_ver.set_defaults(func=cmd_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
