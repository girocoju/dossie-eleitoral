"""Ingestao IBGE/SIDRA — F-04 (S6).

    python -m ingest.ibge_sidra load   [--indicador PIB] [--dry-run] [--target local]
    python -m ingest.ibge_sidra verify [--indicador PIB]

A API do SIDRA devolve uma lista em que o **primeiro elemento e' o cabecalho**
(rotulos) e os demais sao os dados. As dimensoes vem como `D1C/D1N`, `D2C/D2N`, ...
e a ordem NAO e' garantida entre tabelas — por isso o parser identifica cada
dimensao pelo rotulo do cabecalho (`Variavel`, `Ano`, `Trimestre`, ...) em vez de
assumir que territorio e' sempre D1. Conferido em 27/08/2026 nas tabelas
5938 (PIB), 6579 (populacao) e 4099 (desocupacao).
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from ingest.common.cli import executar
from ingest.common.config import DATASET_RAW_IBGE, get_settings
from ingest.common.http import get_json, utc_now
from ingest.common.indicadores import (
    COLUNAS_NUMERICAS,
    COLUNAS_SAIDA,
    Indicador,
    Observacao,
    carregar_catalogo,
    media_anual,
    por_provedor,
    ultimo_do_ano,
)
from ingest.common.log import get_logger
from ingest.common.textnorm import strip_accents
from ingest.common.ufs import sigla_por_cod_ibge
from ingest.common.writer import NdjsonWriter

log = get_logger("sidra")

BASE = "https://apisidra.ibge.gov.br/values"

# Valores que o SIDRA usa para "sem informacao". Viram NULL, nunca 0.
SEM_VALOR = frozenset({"-", "..", "...", "X", "..X", "-0", ""})

ROTULOS_PERIODO = frozenset({"ano", "trimestre", "trimestre movel", "periodo", "mes"})
ROTULO_VARIAVEL = "variavel"


class SidraError(RuntimeError):
    """Resposta do SIDRA fora do formato esperado."""


def montar_url(ind: Indicador, nivel: str) -> str:
    p = ind.parametros
    periodos = p.get("periodos", "all")
    return (
        f"{BASE}/t/{p['tabela']}/{nivel}/all/v/{p['variavel']}"
        f"/p/{periodos}?formato=json"
    )


def _rotulo(texto: str) -> str:
    return strip_accents(str(texto)).strip().lower().replace(" (codigo)", "")


def _mapear_dimensoes(cabecalho: dict[str, str]) -> dict[str, str]:
    """Descobre qual `D#` e' territorio, qual e' variavel e qual e' periodo."""
    papeis: dict[str, str] = {}
    for chave, rotulo in cabecalho.items():
        if not (chave.startswith("D") and chave.endswith("N")):
            continue
        nome = _rotulo(rotulo)
        if nome == ROTULO_VARIAVEL:
            papeis["variavel"] = chave[:-1]
        elif nome in ROTULOS_PERIODO:
            papeis["periodo"] = chave[:-1]
        else:
            papeis.setdefault("territorio", chave[:-1])
    faltando = [p for p in ("territorio", "periodo") if p not in papeis]
    if faltando:
        raise SidraError(
            f"nao identifiquei as dimensoes {faltando} no cabecalho do SIDRA: {cabecalho}"
        )
    return papeis


def _ano_do_periodo(codigo: str) -> int | None:
    """`2023` -> 2023; `202401` (1o trimestre de 2024) -> 2024."""
    codigo = str(codigo).strip()
    if len(codigo) >= 4 and codigo[:4].isdigit():
        return int(codigo[:4])
    return None


def _valor(bruto: str | None) -> float | None:
    if bruto is None:
        return None
    texto = str(bruto).strip()
    if texto in SEM_VALOR:
        return None
    try:
        return float(texto.replace(",", "."))
    except ValueError:
        return None


def parse_resposta(payload: list[dict[str, Any]], ind: Indicador, url: str) -> list[Observacao]:
    """Converte a resposta do SIDRA no formato longo do projeto."""
    if not payload:
        raise SidraError(f"{ind.cod_indicador}: resposta vazia de {url}")
    cabecalho, *linhas = payload
    papeis = _mapear_dimensoes(cabecalho)
    dim_territorio, dim_periodo = papeis["territorio"], papeis["periodo"]

    agregacao = ind.parametros.get("agregacao")
    min_periodos = int(ind.parametros.get("min_periodos", 1))
    extraido_em = utc_now()

    # sg_uf -> lista de (ano, periodo, valor). O periodo entra na tupla, e nao numa
    # lista paralela, para nao existir alinhamento por posicao que possa quebrar.
    bruto: dict[str, list[tuple[int, str, float]]] = {}
    unidade = ind.unidade

    for linha in linhas:
        sg_uf = sigla_por_cod_ibge(linha.get(f"{dim_territorio}C"))
        ano = _ano_do_periodo(linha.get(f"{dim_periodo}C", ""))
        valor = _valor(linha.get("V"))
        if sg_uf is None or ano is None or valor is None:
            continue
        periodo = str(linha.get(f"{dim_periodo}C") or "")
        bruto.setdefault(sg_uf, []).append((ano, periodo, valor))
        if linha.get("MN"):
            unidade = ind.unidade  # mantem a unidade declarada no catalogo

    observacoes: list[Observacao] = []
    for sg_uf, medidas in bruto.items():
        if agregacao == "media_anual":
            por_ano = media_anual(
                [(ano, valor) for ano, _, valor in medidas], min_periodos=min_periodos
            )
        elif agregacao == "ultimo_do_ano":
            por_ano = ultimo_do_ano(medidas, min_periodos=min_periodos)
        else:
            por_ano = {ano: (valor, 1) for ano, _, valor in medidas}
        for ano, (valor, n) in sorted(por_ano.items()):
            observacoes.append(
                Observacao(
                    cod_indicador=ind.cod_indicador,
                    sg_uf=sg_uf,
                    ano=ano,
                    valor=valor,
                    unidade=unidade,
                    fonte=ind.fonte,
                    n_periodos=n,
                    extracted_at=extraido_em,
                    source_url=url,
                )
            )
    return observacoes


def coletar(ind: Indicador, *, dry_run: bool = False) -> list[Observacao]:
    niveis = ind.parametros.get("niveis") or ["n3"]
    todas: list[Observacao] = []
    for nivel in niveis:
        url = montar_url(ind, nivel)
        if dry_run:
            log.info("[dry-run] %s: GET %s", ind.cod_indicador, url)
            continue
        log.info("%s (%s): %s", ind.cod_indicador, nivel, url)
        todas.extend(parse_resposta(get_json(url), ind, url))
    return todas


def _schema():
    from google.cloud import bigquery

    from ingest.common.bq import build_schema

    schema = build_schema(list(COLUNAS_SAIDA))
    numericas = [bigquery.SchemaField(nome, tipo) for nome, tipo in COLUNAS_NUMERICAS]
    # insere as numericas antes das colunas de metadado
    corte = len(COLUNAS_SAIDA)
    return schema[:corte] + numericas + schema[corte:]


def cmd_load(args: argparse.Namespace) -> int:
    settings = get_settings()
    settings.ensure_dirs()
    catalogo = carregar_catalogo()

    if args.indicador:
        alvos = [catalogo[c] for c in args.indicador if c in catalogo]
        desconhecidos = [c for c in args.indicador if c not in catalogo]
        if desconhecidos:
            log.error("indicador(es) fora do catalogo: %s", desconhecidos)
            return 1
    else:
        alvos = por_provedor("sidra")

    alvos = [i for i in alvos if i.provedor == "sidra" and i.ingerivel]
    if args.somente_verificados:
        alvos = [i for i in alvos if i.verificado]
    if not alvos:
        log.warning("nenhum indicador SIDRA a carregar")
        return 0

    destino = settings.staging_dir / "indicadores" / "ibge_sidra.ndjson.gz"
    total = 0
    with NdjsonWriter(destino) as writer:
        for ind in alvos:
            observacoes = coletar(ind, dry_run=args.dry_run)
            for obs in observacoes:
                writer.write(obs.to_row())
            total += len(observacoes)
            if observacoes:
                anos = sorted({o.ano for o in observacoes})
                ufs = sorted({o.sg_uf for o in observacoes})
                log.info(
                    "%s: %d obs, %d..%d, %d UEs",
                    ind.cod_indicador,
                    len(observacoes),
                    anos[0],
                    anos[-1],
                    len(ufs),
                )

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
        DATASET_RAW_IBGE,
        "indicadores",
        schema=_schema(),
        particionar_por="ano",
        clustering=("cod_indicador", "sg_uf"),
    )
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Bate na API de verdade e mostra cobertura por indicador. Nao carrega nada."""
    catalogo = carregar_catalogo()
    alvos = (
        [catalogo[c] for c in args.indicador if c in catalogo]
        if args.indicador
        else por_provedor("sidra")
    )
    problemas = 0
    for ind in alvos:
        print(f"\n=== {ind.cod_indicador} — {ind.nome}")
        print(f"fonte : {ind.fonte}")
        try:
            observacoes = coletar(ind)
        except (RuntimeError, SidraError) as exc:
            print(f"  ERRO: {exc}")
            problemas += 1
            continue
        if not observacoes:
            print("  ERRO: nenhuma observacao devolvida")
            problemas += 1
            continue
        anos = sorted({o.ano for o in observacoes})
        ufs = sorted({o.sg_uf for o in observacoes})
        buracos = [a for a in range(anos[0], anos[-1] + 1) if a not in set(anos)]
        print(f"  observacoes : {len(observacoes)}")
        print(f"  periodo     : {anos[0]}–{anos[-1]}")
        print(f"  unidades    : {len(ufs)} (Brasil presente: {'BR' in ufs})")
        if buracos:
            print(f"  !! anos sem dado: {buracos}  -> registrar em docs/LACUNAS.md")
        if len(ufs) < 28:
            faltando = 28 - len(ufs)
            print(f"  !! faltam {faltando} unidade(s) — esperado 27 UFs + BR")
    return 1 if problemas else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ingest.ibge_sidra", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_load = sub.add_parser("load", help="baixa e carrega os indicadores do SIDRA")
    p_load.add_argument("--indicador", nargs="*", help="codigos do catalogo (default: todos)")
    p_load.add_argument(
        "--ano", type=int, help="aceito por convencao do SPEC 9; nao filtra o SIDRA"
    )
    p_load.add_argument("--dry-run", action="store_true")
    p_load.add_argument("--target", choices=("bigquery", "local"), default="bigquery")
    p_load.add_argument(
        "--somente-verificados",
        action="store_true",
        help="pula indicadores com `verificado: false` no catalogo",
    )
    p_load.set_defaults(func=cmd_load)

    p_ver = sub.add_parser("verify", help="confere cobertura real da API")
    p_ver.add_argument("--indicador", nargs="*")
    p_ver.set_defaults(func=cmd_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return executar(args.func, args)


if __name__ == "__main__":
    sys.exit(main())
