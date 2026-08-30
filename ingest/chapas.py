"""Ligacao entre titular e vice/suplente — S14b / F-21 (ADR-025).

    python -m ingest.chapas load   [--ano 2026] [--limite 20] [--dry-run]
    python -m ingest.chapas verify [--amostra 10]

O QUE FALTAVA NAO ERA O VICE — ERA O VINCULO

Vice e suplente ja' estao no lake, com foto e perfil completo: 13
vice-presidentes, 203 vice-governadores e 661 suplentes de senador em 2026. Eles
tem candidatura propria, com `sq_candidato` proprio, como qualquer outro.

O que NAO existe em lugar nenhum do pacote em lote do TSE e' a CHAPA — quem
concorre com quem. Sem isso, Geraldo Alckmin esta' na base como candidato a
Vice-Presidente pelo PSB e nada diz que ele e' o vice do Lula.

O vinculo so' aparece no DivulgaCandContas, no campo `vices` do detalhe de cada
candidatura majoritaria. E' uma requisicao por chapa: 529 em 2026, cerca de onze
minutos.

POR QUE NAO GUARDAR OS DADOS DO VICE AQUI

Este modulo grava so' o PAR (titular, vice) e o cargo. Nome, partido, foto e
perfil vem de `dim_candidato`, onde ja' estao — copiar seria criar uma segunda
versao da verdade que envelhece sozinha, e o TSE altera cadastro ate' a eleicao.
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

from ingest.common.cli import executar
from ingest.common.config import DATASET_RAW_TSE, get_settings
from ingest.common.http import utc_now
from ingest.common.log import get_logger
from ingest.common.writer import NdjsonWriter
from ingest.propostas import consultar

log = get_logger("chapas")

PAUSA = 1.1

# Cargos majoritarios: sao os unicos que tem chapa. Deputado concorre sozinho.
CARGOS_COM_CHAPA = (1, 3, 5)


def _texto(valor: Any) -> str | None:
    v = str(valor or "").strip()
    return v or None


def extrair(detalhe: dict[str, Any], sk_titular: str, sq_titular: str,
            cod_cargo: int, sg_ue: str) -> list[dict[str, Any]]:
    """Uma linha por vice/suplente da chapa.

    A ORDEM importa para senador: o 1o suplente assume antes do 2o. O TSE nao
    numera explicitamente, entao a ordem da lista e' preservada — e o cargo
    declarado (`ds_CARGO`) confirma qual e' qual.
    """
    saida = []
    for ordem, v in enumerate(detalhe.get("vices") or [], start=1):
        sq_vice = _texto(v.get("sq_CANDIDATO"))
        if not sq_vice:
            continue
        saida.append({
            "ano_eleicao": 2026,
            "sk_titular": sk_titular,
            "sq_titular": sq_titular,
            "cod_cargo_titular": cod_cargo,
            "sg_ue": sg_ue,
            "sq_vice": sq_vice,
            "ordem": ordem,
            "cargo_vice": _texto(v.get("ds_CARGO")),
            # Guardados so' para conferencia contra `dim_candidato` — a tela usa
            # o mart, nunca estes campos.
            "nome_urna_vice": _texto(v.get("nm_URNA")),
            "sigla_partido_vice": _texto(v.get("sg_PARTIDO")),
        })
    return saida


def candidaturas(cliente, ano: int, limite: int | None) -> list[dict[str, Any]]:
    p = cliente.project
    lim = f"limit {limite}" if limite else ""
    cargos = ", ".join(str(c) for c in CARGOS_COM_CHAPA)
    sql = f"""
        select d.sk_candidatura, d.sq_candidato, d.cod_cargo, d.sg_ue, d.nome_urna
        from `{p}.marts.dim_candidato` d
        join `{p}.marts.fct_candidatura` f using (sk_candidatura)
        where d.ano_eleicao = {ano} and d.cod_cargo in ({cargos})
          and f.e_registro_exibido
        order by d.cod_cargo, d.sg_ue, d.nome_urna
        {lim}
    """
    return [dict(r) for r in cliente.query(sql).result()]


def coletar(candidatos: list[dict[str, Any]], ano: int) -> list[dict[str, Any]]:
    saida: list[dict[str, Any]] = []
    sem_chapa = 0
    for i, c in enumerate(candidatos, 1):
        try:
            detalhe = consultar(ano, c["sg_ue"], str(c["sq_candidato"])) or {}
        except Exception as exc:  # noqa: BLE001
            # Uma candidatura sem resposta nao para a carga — a chapa dela fica
            # simplesmente ausente, que e' melhor que uma chapa inventada.
            log.warning("%s: %s", c["nome_urna"], str(exc)[:90])
            continue
        linhas = extrair(detalhe, c["sk_candidatura"], str(c["sq_candidato"]),
                         int(c["cod_cargo"]), c["sg_ue"])
        if not linhas:
            sem_chapa += 1
        saida.extend(linhas)
        time.sleep(PAUSA)
        if i % 50 == 0:
            log.info("%d/%d consultadas, %d vinculos", i, len(candidatos), len(saida))

    log.info("%d vinculos em %d candidaturas | %d sem vice/suplente na resposta",
             len(saida), len(candidatos), sem_chapa)
    return saida


def _schema():
    from google.cloud import bigquery  # noqa: PLC0415

    from ingest.common.bq import build_schema  # noqa: PLC0415

    textos = ["sk_titular", "sq_titular", "sg_ue", "sq_vice", "cargo_vice",
              "nome_urna_vice", "sigla_partido_vice"]
    schema = build_schema(textos)
    corte = len(textos)
    tipados = [bigquery.SchemaField(n, "INT64")
               for n in ("ano_eleicao", "cod_cargo_titular", "ordem")]
    return schema[:corte] + tipados + schema[corte:]


def cmd_load(args: argparse.Namespace) -> int:
    from google.cloud import bigquery  # noqa: PLC0415

    settings = get_settings()
    settings.ensure_dirs()
    cliente = bigquery.Client(project=settings.project, location=settings.location)
    alvos = candidaturas(cliente, args.ano, args.limite)
    log.info("%d candidaturas majoritarias a consultar", len(alvos))

    if args.dry_run:
        log.info("[dry-run] faria %d consultas, ~%.0f min", len(alvos),
                 len(alvos) * PAUSA / 60)
        return 0

    linhas = coletar(alvos, args.ano)
    if not linhas:
        log.error("nenhum vinculo coletado — a carga nao substitui a tabela por vazio")
        return 1

    destino = settings.staging_dir / "tse" / "chapas.ndjson.gz"
    quando = utc_now()
    with NdjsonWriter(destino) as w:
        for linha in linhas:
            w.write({**linha, "_extracted_at": quando,
                     "_source_url": "divulgacandcontas", "_source_file": "vices",
                     "_source_sha256": ""})

    if args.target == "local":
        log.info("NDJSON em %s", destino)
        return 0

    from ingest.common.bq import ensure_datasets, load_ndjson  # noqa: PLC0415

    ensure_datasets()
    load_ndjson(destino, DATASET_RAW_TSE, "chapas", schema=_schema(),
                particionar_por="ano_eleicao", clustering=("sk_titular",))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    from google.cloud import bigquery  # noqa: PLC0415

    s = get_settings()
    cliente = bigquery.Client(project=s.project, location=s.location)
    alvos = candidaturas(cliente, args.ano, args.amostra)
    linhas = coletar(alvos, args.ano)

    por_titular: dict[str, list[dict]] = {}
    for linha in linhas:
        por_titular.setdefault(linha["sk_titular"], []).append(linha)

    nomes = {c["sk_candidatura"]: c["nome_urna"] for c in alvos}
    print(f"\n{len(alvos)} candidaturas, {len(linhas)} vinculos\n")
    for sk, itens in por_titular.items():
        print(f"  {nomes.get(sk, sk)[:26]:<28}", end="")
        print(" · ".join(f"{i['nome_urna_vice']} ({i['cargo_vice']})" for i in itens)[:80])
    faltando = [nomes[c["sk_candidatura"]] for c in alvos
                if c["sk_candidatura"] not in por_titular]
    if faltando:
        print(f"\n  sem chapa na resposta: {', '.join(faltando[:6])}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ingest.chapas", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_load = sub.add_parser("load", help="varre as chapas majoritarias")
    p_load.add_argument("--ano", type=int, default=2026)
    p_load.add_argument("--limite", type=int)
    p_load.add_argument("--dry-run", action="store_true")
    p_load.add_argument("--target", choices=("bigquery", "local"), default="bigquery")
    p_load.set_defaults(func=cmd_load)

    p_ver = sub.add_parser("verify", help="mostra as chapas de uma amostra")
    p_ver.add_argument("--ano", type=int, default=2026)
    p_ver.add_argument("--amostra", type=int, default=10)
    p_ver.set_defaults(func=cmd_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return executar(args.func, args)


if __name__ == "__main__":
    sys.exit(main())
