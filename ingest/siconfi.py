"""Ingestao SICONFI / Tesouro Nacional — S11.

    python -m ingest.siconfi load   [--ano-inicio 2015] [--dry-run] [--target local]
    python -m ingest.siconfi verify [--ano 2023]

Receita e despesa orcamentaria dos governos estaduais, da Declaracao de Contas
Anuais (DCA). E' o indicador com o vinculo MAIS FORTE de todo o projeto com um
mandato executivo: PIB, desemprego e homicidios dependem de mil fatores fora do
alcance de um governador, mas receita e despesa do estado sao literalmente o que
ele administra.

Isso NAO muda a regra da Constituicao 0.2 — a tela continua mostrando o que
aconteceu no periodo, com o comparador ao lado, sem atribuir merito. Muda apenas
que aqui a proximidade entre o mandato e o numero e' defensavel, e nas outras
series e' tenue.

Conferido em 28/08/2026:

* A API exige consulta POR ENTE — omitir `id_ente` devolve lista vazia. Sao
  27 UFs x 11 anos x 2 anexos, cerca de 594 requisicoes.
* Cobertura de 2015 a 2025. Antes de 2015 o anexo devolve vazio.
* `DCA-Anexo I-C` traz a receita, com as colunas "Receitas Brutas Realizadas",
  "Deducoes - FUNDEB" e "Outras Deducoes da Receita".
* `DCA-Anexo I-D` traz a despesa, com "Despesas Empenhadas", "Liquidadas" e "Pagas".
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

from ingest.common.config import DATASET_RAW_TESOURO, get_settings
from ingest.common.http import get_json, utc_now
from ingest.common.indicadores import COLUNAS_NUMERICAS, COLUNAS_SAIDA, Observacao
from ingest.common.log import get_logger
from ingest.common.textnorm import strip_accents
from ingest.common.ufs import UFS
from ingest.common.writer import NdjsonWriter

log = get_logger("siconfi")

API = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/dca"

ANEXO_RECEITA = "DCA-Anexo I-C"
ANEXO_DESPESA = "DCA-Anexo I-D"

ANO_INICIO = 2015  # antes disso o anexo devolve vazio (conferido em 28/08/2026)
PAUSA = 1.5

# Rotulos das colunas, ja' sem acento — a API devolve com acentuacao e ela varia
# de ano para ano em detalhes de grafia.
RECEITA_BRUTA = "RECEITAS BRUTAS REALIZADAS"
DEDUCOES = ("DEDUCOES - FUNDEB", "OUTRAS DEDUCOES DA RECEITA")
DESPESA_EMPENHADA = "DESPESAS EMPENHADAS"

CONTA_RECEITA = "TotalReceitas"
CONTA_DESPESA = "TotalDespesas"

FONTE = "Tesouro Nacional — SICONFI/DCA"

# A Uniao tambem declara no SICONFI, com esfera 'U' e cod_ibge 1. Sao SERIES
# SEPARADAS das estaduais, de proposito: o orcamento federal (R$ 4,4 tri em 2023)
# e o de um estado (R$ 50 bi) nao sao comparaveis, e misturar os dois num mesmo
# indicador produziria um "Brasil" que nao serve de comparador para ninguem.
#
#   RECEITA_ESTADUAL / DESPESA_ESTADUAL   -> 27 UFs, e o BR e' a SOMA delas.
#                                            E' o comparador de um GOVERNADOR.
#   RECEITA_UNIAO / DESPESA_UNIAO         -> so' BR, o orcamento federal.
#                                            E' o que responde por um PRESIDENTE.
ENTE_UNIAO = "1"


def _rotulo(texto: Any) -> str:
    return strip_accents(str(texto or "")).strip().upper()


def consultar(ano: int, anexo: str, cod_ibge: str) -> list[dict[str, Any]]:
    url = (
        f"{API}?an_exercicio={ano}"
        f"&no_anexo={anexo.replace(' ', '%20')}"
        f"&id_ente={cod_ibge}"
    )
    try:
        payload = get_json(url, timeout=90, attempts=3)
    except Exception as exc:  # noqa: BLE001 — um ente sem resposta nao para a carga
        log.warning("%s %s ente %s: %s", anexo, ano, cod_ibge, str(exc)[:110])
        return []
    return payload.get("items") or []


def receita_liquida(itens: list[dict[str, Any]]) -> float | None:
    """Receita bruta realizada menos as deducoes (FUNDEB e outras).

    A receita BRUTA superestima o que o estado de fato dispoe: a parcela do FUNDEB
    e' constitucionalmente vinculada e sai antes. Usar a bruta faria estados com
    mais alunos parecerem mais ricos do que sao.
    """
    bruta = deducoes = None
    for i in itens:
        if i.get("cod_conta") != CONTA_RECEITA:
            continue
        col = _rotulo(i.get("coluna"))
        valor = i.get("valor")
        if valor is None:
            continue
        if col == RECEITA_BRUTA:
            bruta = float(valor)
        elif col in DEDUCOES:
            deducoes = (deducoes or 0.0) + float(valor)
    if bruta is None:
        return None
    return bruta - (deducoes or 0.0)


def despesa_empenhada(itens: list[dict[str, Any]]) -> float | None:
    """Despesa empenhada — o compromisso assumido no exercicio.

    Empenhada e nao paga: pagamento pode escorregar para o exercicio seguinte via
    restos a pagar, e o que mede a decisao do gestor no ano e' o empenho.
    """
    for i in itens:
        if i.get("cod_conta") == CONTA_DESPESA and _rotulo(i.get("coluna")) == DESPESA_EMPENHADA:
            if i.get("valor") is not None:
                return float(i["valor"])
    return None


def coletar_uniao(ano_inicio: int, ano_fim: int, extraido_em: str) -> list[Observacao]:
    """Orcamento federal. E' o nivel de governo pelo qual um presidente responde."""
    obs: list[Observacao] = []
    for ano in range(ano_inicio, ano_fim + 1):
        rec = receita_liquida(consultar(ano, ANEXO_RECEITA, ENTE_UNIAO))
        time.sleep(PAUSA)
        des = despesa_empenhada(consultar(ano, ANEXO_DESPESA, ENTE_UNIAO))
        time.sleep(PAUSA)
        for cod, valor in (("RECEITA_UNIAO", rec), ("DESPESA_UNIAO", des)):
            if valor is None:
                continue
            obs.append(
                Observacao(
                    cod_indicador=cod,
                    sg_uf="BR",
                    ano=ano,
                    valor=valor,
                    unidade="R$ correntes",
                    fonte=f"{FONTE} — Uniao",
                    extracted_at=extraido_em,
                    source_url=API,
                )
            )
    log.info("Uniao: %d observacoes", len(obs))
    return obs


def coletar(ano_inicio: int, ano_fim: int, *, dry_run: bool = False) -> list[Observacao]:
    extraido_em = utc_now()
    obs: list[Observacao] = []
    total = len(UFS) * (ano_fim - ano_inicio + 1)
    feitas = 0

    for uf in UFS:
        for ano in range(ano_inicio, ano_fim + 1):
            feitas += 1
            if dry_run:
                continue
            rec = receita_liquida(consultar(ano, ANEXO_RECEITA, uf.cod_ibge))
            time.sleep(PAUSA)
            des = despesa_empenhada(consultar(ano, ANEXO_DESPESA, uf.cod_ibge))
            time.sleep(PAUSA)

            for cod, valor in (("RECEITA_ESTADUAL", rec), ("DESPESA_ESTADUAL", des)):
                if valor is None:
                    continue
                obs.append(
                    Observacao(
                        cod_indicador=cod,
                        sg_uf=uf.sg_uf,
                        ano=ano,
                        valor=valor,
                        unidade="R$ correntes",
                        fonte=FONTE,
                        extracted_at=extraido_em,
                        source_url=API,
                    )
                )
            if feitas % 27 == 0:
                log.info("%d/%d consultas, %d observacoes", feitas, total, len(obs))

    if dry_run:
        consultas = total + (ano_fim - ano_inicio + 1)
        log.info("[dry-run] faria %d consultas (x2 anexos) em %s", consultas, API)
        return obs

    obs.extend(coletar_uniao(ano_inicio, ano_fim, extraido_em))
    return obs


def _schema():
    from google.cloud import bigquery

    from ingest.common.bq import build_schema

    schema = build_schema(list(COLUNAS_SAIDA))
    numericas = [bigquery.SchemaField(nome, tipo) for nome, tipo in COLUNAS_NUMERICAS]
    corte = len(COLUNAS_SAIDA)
    return schema[:corte] + numericas + schema[corte:]


def cmd_load(args: argparse.Namespace) -> int:
    settings = get_settings()
    settings.ensure_dirs()
    obs = coletar(args.ano_inicio, args.ano_fim, dry_run=args.dry_run)
    if args.dry_run:
        return 0
    if not obs:
        log.error("nenhuma observacao coletada — a carga nao substitui a tabela por vazio")
        return 1

    destino = settings.staging_dir / "indicadores" / "siconfi.ndjson.gz"
    with NdjsonWriter(destino) as writer:
        for o in obs:
            writer.write(o.to_row())

    anos = sorted({o.ano for o in obs})
    ufs = sorted({o.sg_uf for o in obs})
    log.info("%d observacoes | %d..%d | %d UFs", len(obs), anos[0], anos[-1], len(ufs))

    if args.target == "local":
        log.info("NDJSON em %s", destino)
        return 0

    from ingest.common.bq import ensure_datasets, load_ndjson

    ensure_datasets()
    load_ndjson(
        destino,
        DATASET_RAW_TESOURO,
        "indicadores",
        schema=_schema(),
        particionar_por="ano",
        clustering=("cod_indicador", "sg_uf"),
    )
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Consulta alguns estados de um ano e mostra receita, despesa e resultado."""
    print(f"SICONFI/DCA — exercicio {args.ano}\n")
    print(f"{'UF':<5}{'receita liquida':>20}{'despesa empenhada':>20}{'resultado':>18}")
    for uf in UFS[: args.amostra]:
        rec = receita_liquida(consultar(args.ano, ANEXO_RECEITA, uf.cod_ibge))
        time.sleep(PAUSA)
        des = despesa_empenhada(consultar(args.ano, ANEXO_DESPESA, uf.cod_ibge))
        time.sleep(PAUSA)
        res = (rec - des) if (rec is not None and des is not None) else None
        fmt = lambda v: f"{v:>18,.0f}" if v is not None else f"{'—':>18}"  # noqa: E731
        print(f"{uf.sg_uf:<5}{fmt(rec)}  {fmt(des)}  {fmt(res)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ingest.siconfi", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_load = sub.add_parser("load", help="baixa receita e despesa estadual e carrega")
    p_load.add_argument("--ano-inicio", type=int, default=ANO_INICIO)
    p_load.add_argument("--ano-fim", type=int, default=2025)
    p_load.add_argument("--ano", type=int, help="aceito por convencao do SPEC 9; nao filtra")
    p_load.add_argument("--dry-run", action="store_true")
    p_load.add_argument("--target", choices=("bigquery", "local"), default="bigquery")
    p_load.set_defaults(func=cmd_load)

    p_ver = sub.add_parser("verify", help="mostra receita, despesa e resultado de alguns estados")
    p_ver.add_argument("--ano", type=int, default=2023)
    p_ver.add_argument("--amostra", type=int, default=6)
    p_ver.set_defaults(func=cmd_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
