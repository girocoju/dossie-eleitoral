"""Ingestao IPEA / Ipeadata — F-04 (S7, Atlas da Violencia).

    python -m ingest.ipeadata load    [--indicador HOMICIDIOS] [--dry-run] [--target local]
    python -m ingest.ipeadata verify  [--indicador HOMICIDIOS]
    python -m ingest.ipeadata buscar  --termo homic

Duas coisas descobertas batendo na API de verdade (27/08/2026) e que moldam o codigo:

1. O servico REJEITA as opcoes OData `$filter` e `$select` (responde 403). Entao o
   catalogo de series (`Metadados`, ~7 MB, 3.604 series) e' baixado inteiro, fica em
   cache com sha256 como qualquer outro artefato, e a busca acontece localmente.
2. `ValoresSerie` devolve TODOS os niveis territoriais na mesma resposta — municipio,
   microrregiao, AMC, estado, Brasil (468 mil linhas para a taxa de homicidios). O
   filtro por `NIVNOME` e' feito aqui; so' `Estados` e `Brasil` interessam ao projeto,
   que nao desce de UF no MVP (SPEC 2.2).
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from typing import Any

from ingest.common.config import DATASET_RAW_IPEA, get_settings
from ingest.common.http import DownloadError, download, get_json, utc_now
from ingest.common.indicadores import (
    COLUNAS_NUMERICAS,
    COLUNAS_SAIDA,
    Indicador,
    Observacao,
    carregar_catalogo,
    por_provedor,
)
from ingest.common.log import get_logger
from ingest.common.ufs import sigla_por_cod_ibge
from ingest.common.writer import NdjsonWriter

log = get_logger("ipeadata")

BASE = "http://www.ipeadata.gov.br/api/odata4"
NIVEIS_ACEITOS = {"estados": "UF", "brasil": "BR"}


class IpeadataError(RuntimeError):
    """Resposta do Ipeadata fora do formato esperado."""


def _sem_acento(texto: Any) -> str:
    return (
        unicodedata.normalize("NFD", str(texto or ""))
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def baixar_metadados(*, force: bool = False) -> list[dict[str, Any]]:
    """Catalogo completo de series, em cache no disco."""
    settings = get_settings()
    settings.ensure_dirs()
    destino = settings.download_dir / "ipea" / "metadados.json"
    download(f"{BASE}/Metadados", destino, force=force)
    import json

    return json.loads(destino.read_text(encoding="utf-8-sig"))["value"]


def valores_serie(sercodigo: str) -> list[dict[str, Any]]:
    payload = get_json(f"{BASE}/ValoresSerie(SERCODIGO='{sercodigo}')")
    valores = payload.get("value") if isinstance(payload, dict) else payload
    if not valores:
        raise IpeadataError(f"serie {sercodigo} nao devolveu valores")
    return valores


def parse_valores(
    valores: list[dict[str, Any]], ind: Indicador, url: str
) -> list[Observacao]:
    """Filtra por nivel territorial e converte para o formato longo."""
    extraido_em = utc_now()
    observacoes: list[Observacao] = []
    ignorados = 0

    for item in valores:
        nivel = _sem_acento(item.get("NIVNOME"))
        if nivel not in NIVEIS_ACEITOS:
            ignorados += 1
            continue
        data = str(item.get("VALDATA") or "")
        if len(data) < 4 or not data[:4].isdigit():
            continue
        ano = int(data[:4])
        valor = item.get("VALVALOR")
        if valor is None:
            continue
        sg_uf = "BR" if nivel == "brasil" else sigla_por_cod_ibge(item.get("TERCODIGO"))
        if sg_uf is None:
            continue
        observacoes.append(
            Observacao(
                cod_indicador=ind.cod_indicador,
                sg_uf=sg_uf,
                ano=ano,
                valor=float(valor),
                unidade=ind.unidade,
                fonte=ind.fonte,
                extracted_at=extraido_em,
                source_url=url,
            )
        )

    log.info(
        "%s: %d observacoes UF/BR (%d linhas de outros niveis ignoradas)",
        ind.cod_indicador,
        len(observacoes),
        ignorados,
    )
    return observacoes


def coletar(ind: Indicador, *, dry_run: bool = False) -> list[Observacao]:
    sercodigo = ind.parametros.get("sercodigo")
    if not sercodigo:
        raise IpeadataError(f"{ind.cod_indicador}: catalogo nao declara `sercodigo`")
    url = f"{BASE}/ValoresSerie(SERCODIGO='{sercodigo}')"
    if dry_run:
        log.info("[dry-run] %s: GET %s", ind.cod_indicador, url)
        return []
    return parse_valores(valores_serie(sercodigo), ind, url)


def _schema():
    from google.cloud import bigquery

    from ingest.common.bq import build_schema

    schema = build_schema(list(COLUNAS_SAIDA))
    numericas = [bigquery.SchemaField(nome, tipo) for nome, tipo in COLUNAS_NUMERICAS]
    corte = len(COLUNAS_SAIDA)
    return schema[:corte] + numericas + schema[corte:]


def _alvos(args: argparse.Namespace) -> list[Indicador]:
    catalogo = carregar_catalogo()
    if args.indicador:
        desconhecidos = [c for c in args.indicador if c not in catalogo]
        if desconhecidos:
            raise IpeadataError(f"fora do catalogo: {desconhecidos}")
        alvos = [catalogo[c] for c in args.indicador]
    else:
        alvos = por_provedor("ipeadata")
    return [i for i in alvos if i.provedor == "ipeadata" and i.ingerivel]


def cmd_load(args: argparse.Namespace) -> int:
    settings = get_settings()
    settings.ensure_dirs()
    try:
        alvos = _alvos(args)
    except IpeadataError as exc:
        log.error("%s", exc)
        return 1
    if args.somente_verificados:
        alvos = [i for i in alvos if i.verificado]
    if not alvos:
        log.warning("nenhum indicador Ipeadata a carregar")
        return 0

    destino = settings.staging_dir / "indicadores" / "ipeadata.ndjson.gz"
    total = 0
    with NdjsonWriter(destino) as writer:
        for ind in alvos:
            try:
                observacoes = coletar(ind, dry_run=args.dry_run)
            except (IpeadataError, DownloadError) as exc:
                log.error("%s: %s", ind.cod_indicador, exc)
                return 1
            for obs in observacoes:
                writer.write(obs.to_row())
            total += len(observacoes)

    # A carga substitui a TABELA INTEIRA. Com `--indicador`, o NDJSON contem so'
    # um subconjunto e a carga apagaria os demais indicadores — foi o que
    # aconteceu em 28/08/2026, quando um `--indicador POPULACAO_CENSO` deixou a
    # tabela com 28 linhas no lugar de 1.624. Por isso a carga parcial e' barrada:
    # ou se carrega o catalogo todo, ou nao se toca no BigQuery.
    if args.indicador and args.target != "local":
        log.error(
            "carga parcial nao vai ao BigQuery: `--indicador` gera so' um subconjunto "
            "e a carga substitui a tabela inteira, apagando os demais. Rode sem "
            "`--indicador`, ou use `--target local` para inspecionar o NDJSON."
        )
        return 1

    if args.dry_run or args.target == "local":
        log.info("%d observacoes em %s", total, destino)
        return 0

    from ingest.common.bq import ensure_datasets, load_ndjson

    ensure_datasets()
    load_ndjson(
        destino,
        DATASET_RAW_IPEA,
        "indicadores",
        schema=_schema(),
        particionar_por="ano",
        clustering=("cod_indicador", "sg_uf"),
    )
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    try:
        alvos = _alvos(args)
    except IpeadataError as exc:
        print(f"ERRO: {exc}")
        return 1
    problemas = 0
    for ind in alvos:
        print(f"\n=== {ind.cod_indicador} — {ind.nome}")
        print(f"serie : {ind.parametros.get('sercodigo')}")
        try:
            observacoes = coletar(ind)
        except (IpeadataError, DownloadError) as exc:
            print(f"  ERRO: {exc}")
            problemas += 1
            continue
        anos = sorted({o.ano for o in observacoes})
        ufs = sorted({o.sg_uf for o in observacoes})
        print(f"  observacoes : {len(observacoes)}")
        print(f"  periodo     : {anos[0]}–{anos[-1]}")
        print(f"  unidades    : {len(ufs)} (Brasil presente: {'BR' in ufs})")
        buracos = [a for a in range(anos[0], anos[-1] + 1) if a not in set(anos)]
        if buracos:
            print(f"  !! anos sem dado: {buracos}  -> registrar em docs/LACUNAS.md")
    return 1 if problemas else 0


def cmd_buscar(args: argparse.Namespace) -> int:
    """Procura no catalogo local — e' assim que se acha o SERCODIGO de uma serie."""
    termo = _sem_acento(args.termo)
    series = baixar_metadados(force=args.force)
    achados = [s for s in series if termo in _sem_acento(s.get("SERNOME"))]
    print(f"{len(achados)} serie(s) com '{args.termo}' em {len(series)} do catalogo\n")
    for s in achados[: args.limite]:
        print(f"{s['SERCODIGO']:<24} {str(s.get('SERNOME'))[:58]}")
        print(f"{'':<24} base={s.get('BASNOME')} | per={s.get('PERNOME')} | un={s.get('UNINOME')}")
    if len(achados) > args.limite:
        print(f"\n... e mais {len(achados) - args.limite}. Use --limite.")
    print(
        "\nSo' series de base 'Regional' tem quebra por UF. "
        "Confirme com `verify` antes de marcar `verificado: true` no catalogo."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ingest.ipeadata", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_load = sub.add_parser("load", help="baixa e carrega as series do Ipeadata")
    p_load.add_argument("--indicador", nargs="*")
    p_load.add_argument("--ano", type=int, help="aceito por convencao do SPEC 9; nao filtra")
    p_load.add_argument("--dry-run", action="store_true")
    p_load.add_argument("--target", choices=("bigquery", "local"), default="bigquery")
    p_load.add_argument("--somente-verificados", action="store_true")
    p_load.set_defaults(func=cmd_load)

    p_ver = sub.add_parser("verify", help="confere cobertura real da serie")
    p_ver.add_argument("--indicador", nargs="*")
    p_ver.set_defaults(func=cmd_verify)

    p_bus = sub.add_parser("buscar", help="procura series pelo nome (catalogo em cache)")
    p_bus.add_argument("--termo", required=True)
    p_bus.add_argument("--limite", type=int, default=20)
    p_bus.add_argument("--force", action="store_true", help="rebaixa o catalogo")
    p_bus.set_defaults(func=cmd_buscar)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
