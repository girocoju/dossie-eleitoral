"""Ingestao das fotos oficiais de urna — F-13 (S13).

    python -m ingest.fotos load   [--ano 2026] [--ue AC SP] [--dry-run] [--target local]
    python -m ingest.fotos verify [--ano 2026]

O TSE publica um `.zip` por unidade eleitoral em
`eleicoes/eleicoes{ano}/fotos/foto_cand{ano}_{UE}_div.zip`. Cada arquivo dentro se
chama `F{SG_UE}{SQ_CANDIDATO}_div.jpg` — ou seja, o nome carrega exatamente os
componentes da `sk_candidatura` do projeto, o que dispensa qualquer mapeamento
intermediario.

As imagens NAO vao para o BigQuery (ADR-012): sobem para um bucket publico e o
warehouse guarda so' a URL. Binario nao pertence a um warehouse analitico, e o
Power BI em Import mode carregaria as imagens para dentro do modelo publicado.

Conferido em 27/08/2026 no pacote do Acre: 385 fotos para 387 candidaturas
(99,5%), zero fotos sem candidatura correspondente, mediana de 5 KB, 161x225 px.
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from ingest.common.cli import executar
from ingest.common.config import DATASET_RAW_TSE, get_settings
from ingest.common.http import download, utc_now
from ingest.common.log import get_logger
from ingest.common.ufs import BRASIL_SG, SIGLAS
from ingest.common.writer import NdjsonWriter

log = get_logger("fotos")

BASE = "https://cdn.tse.jus.br/estatistica/sead/eleicoes"
BUCKET = "radar-brasil-fotos"

# `F` + sigla da UE + sequencial do candidato + `_div.jpg`
PADRAO_ARQUIVO = re.compile(r"^F(?P<ue>[A-Z]{2})(?P<sq>\d+)_div\.jpg$", re.IGNORECASE)

# Unidades eleitorais: as 27 UFs mais `BR`, que guarda os presidenciais.
UES: tuple[str, ...] = (*SIGLAS, BRASIL_SG)

# F-13: abaixo disto a carga falha. Nao e' "candidato sem foto" — e' sinal de que
# a nomenclatura da fonte mudou, o mesmo principio que protege os layouts (ADR-008).
COBERTURA_MINIMA = 0.95

# Sao ~20 mil imagens de 5 KB. Sequencial, cada upload e' uma viagem HTTP e o
# total passa de uma hora; com 16 threads cai para poucos minutos. O gargalo e'
# latencia, nao banda, entao thread resolve.
THREADS_UPLOAD = 16


@dataclass(frozen=True)
class Foto:
    sk_candidatura: str
    sq_candidato: str
    sg_ue: str
    ano_eleicao: int
    caminho: str
    tamanho_bytes: int

    @property
    def url(self) -> str:
        return f"https://storage.googleapis.com/{BUCKET}/{self.caminho}"


def url_pacote(ano: int, ue: str) -> str:
    return f"{BASE}/eleicoes{ano}/fotos/foto_cand{ano}_{ue}_div.zip"


def _zip_path(ano: int, ue: str) -> Path:
    return get_settings().download_dir / "fotos" / str(ano) / f"foto_cand{ano}_{ue}_div.zip"


def ler_pacote(ano: int, ue: str, *, force: bool = False) -> tuple[list[Foto], bytes, int]:
    """Baixa o pacote de uma UE e devolve as fotos reconhecidas e as ignoradas."""
    art = download(url_pacote(ano, ue), _zip_path(ano, ue), force=force)
    fotos: list[Foto] = []
    ignorados = 0
    with zipfile.ZipFile(art.file) as zf:
        for info in zf.infolist():
            nome = Path(info.filename).name
            m = PADRAO_ARQUIVO.match(nome)
            if not m:
                # o pacote traz um leiame em PDF junto das imagens
                ignorados += 1
                continue
            sg_ue = m.group("ue").upper()
            sq = m.group("sq")
            fotos.append(
                Foto(
                    sk_candidatura=f"{ano}-{sg_ue}-{sq}",
                    sq_candidato=sq,
                    sg_ue=sg_ue,
                    ano_eleicao=ano,
                    caminho=f"{ano}/{sg_ue}/{sq}.jpg",
                    tamanho_bytes=info.file_size,
                )
            )
    return fotos, b"", ignorados


def enviar_ao_bucket(ano: int, ue: str, fotos: list[Foto], *, reenviar: bool = False) -> int:
    """Sobe as imagens do pacote para o Cloud Storage. Idempotente por caminho.

    O pipeline roda todo dia; reenviar 20 mil imagens identicas seria desperdicio.
    Uma listagem por prefixo (uma chamada paginada) diz o que ja' esta' la', e so'
    o que falta sobe. Substituicao de candidato traz foto nova, e essa entra.
    """
    from google.cloud import storage

    cliente = storage.Client(project=get_settings().project)
    bucket = cliente.bucket(BUCKET)

    existentes: set[str] = set()
    if not reenviar:
        prefixo = f"{ano}/{ue}/"
        existentes = {b.name for b in cliente.list_blobs(BUCKET, prefix=prefixo)}

    # O ZipFile nao e' seguro para leitura concorrente, entao os bytes sao lidos
    # aqui, em sequencia, e so' o upload vai para as threads.
    payloads: list[tuple[str, bytes]] = []
    with zipfile.ZipFile(_zip_path(ano, ue)) as zf:
        indice = {Path(i.filename).name: i.filename for i in zf.infolist()}
        for foto in fotos:
            if foto.caminho in existentes:
                continue
            origem = indice.get(f"F{foto.sg_ue}{foto.sq_candidato}_div.jpg")
            if origem is not None:
                payloads.append((foto.caminho, zf.read(origem)))

    def sobe(par: tuple[str, bytes]) -> None:
        caminho, dados = par
        blob = bucket.blob(caminho)
        # Cache longo: o caminho e' deterministico e a foto de urna nao muda.
        blob.cache_control = "public, max-age=86400"
        blob.upload_from_string(dados, content_type="image/jpeg")

    with ThreadPoolExecutor(max_workers=THREADS_UPLOAD) as pool:
        list(pool.map(sobe, payloads))

    if existentes and not payloads:
        log.info("%s %s: %d imagens ja' no bucket, nada a enviar", ue, ano, len(existentes))
    else:
        log.info(
            "%s %s: %d imagens enviadas (%d ja' estavam la')", ue, ano, len(payloads),
            len(existentes),
        )
    return len(payloads)


def _schema():
    from google.cloud import bigquery

    from ingest.common.bq import build_schema

    schema = build_schema(["sk_candidatura", "sq_candidato", "sg_ue", "url_foto", "caminho"])
    corte = 5
    return (
        schema[:corte]
        + [
            bigquery.SchemaField("ano_eleicao", "INT64"),
            bigquery.SchemaField("tamanho_bytes", "INT64"),
        ]
        + schema[corte:]
    )


def cmd_load(args: argparse.Namespace) -> int:
    settings = get_settings()
    settings.ensure_dirs()
    ues = [u.upper() for u in args.ue] if args.ue else list(UES)

    destino = settings.staging_dir / "fotos" / f"fotos_{args.ano}.ndjson.gz"
    extraido_em = utc_now()
    total = ignorados_total = 0

    with NdjsonWriter(destino) as writer:
        for ue in ues:
            if args.dry_run:
                log.info("[dry-run] %s: baixaria %s", ue, url_pacote(args.ano, ue))
                continue
            fotos, _, ignorados = ler_pacote(args.ano, ue, force=args.force)
            ignorados_total += ignorados
            if args.target != "local":
                enviar_ao_bucket(args.ano, ue, fotos, reenviar=args.reenviar)
            for foto in fotos:
                writer.write(
                    {
                        "sk_candidatura": foto.sk_candidatura,
                        "sq_candidato": foto.sq_candidato,
                        "sg_ue": foto.sg_ue,
                        "url_foto": foto.url,
                        "caminho": foto.caminho,
                        "ano_eleicao": foto.ano_eleicao,
                        "tamanho_bytes": foto.tamanho_bytes,
                        "_extracted_at": extraido_em,
                        "_source_url": url_pacote(args.ano, ue),
                        "_source_file": f"foto_cand{args.ano}_{ue}_div.zip",
                        "_source_sha256": "",
                    }
                )
            total += len(fotos)
            log.info("%s: %d fotos (%d arquivos ignorados)", ue, len(fotos), ignorados)

    if args.dry_run:
        return 0
    log.info("%d fotos de %d unidades eleitorais", total, len(ues))

    if args.target == "local":
        log.info("NDJSON em %s", destino)
        return 0

    from ingest.common.bq import ensure_datasets, load_ndjson

    ensure_datasets()
    load_ndjson(
        destino,
        DATASET_RAW_TSE,
        "fotos",
        schema=_schema(),
        clustering=("sg_ue",),
    )
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Confere cobertura contra as candidaturas ja' materializadas. Nao carrega nada."""
    from google.cloud import bigquery

    settings = get_settings()
    ues = [u.upper() for u in args.ue] if args.ue else list(UES)
    cliente = bigquery.Client(project=settings.project, location=settings.location)

    consulta = f"""
        select sg_ue, count(*) as n
        from `{settings.project}.marts.dim_candidato`
        where ano_eleicao = {args.ano}
        group by sg_ue
    """
    por_ue = {r.sg_ue: r.n for r in cliente.query(consulta).result()}

    print(f"{'UE':<5}{'fotos':>8}{'candidaturas':>14}{'cobertura':>12}")
    problemas = 0
    for ue in ues:
        fotos, _, _ = ler_pacote(args.ano, ue)
        esperado = por_ue.get(ue, 0)
        pct = len(fotos) / esperado if esperado else 0.0
        marca = "" if pct >= COBERTURA_MINIMA else "  << ABAIXO DO MINIMO"
        print(f"{ue:<5}{len(fotos):>8,}{esperado:>14,}{pct:>11.1%}{marca}")
        if pct < COBERTURA_MINIMA:
            problemas += 1

    if problemas:
        print(
            f"\n{problemas} unidade(s) abaixo de {COBERTURA_MINIMA:.0%}. "
            "Quase sempre significa mudanca de nomenclatura na fonte — confira o "
            "padrao em `ingest/fotos.py` (PADRAO_ARQUIVO)."
        )
        return 1
    print(f"\nCobertura acima de {COBERTURA_MINIMA:.0%} em todas as unidades.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ingest.fotos", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    def comum(p: argparse.ArgumentParser) -> None:
        p.add_argument("--ano", type=int, default=2026, help="ano da eleicao")
        p.add_argument("--ue", nargs="*", help="unidades eleitorais (default: 27 UFs + BR)")
        p.add_argument("--force", action="store_true", help="ignora o cache de download")

    p_load = sub.add_parser("load", help="baixa, envia ao bucket e registra as URLs")
    comum(p_load)
    p_load.add_argument("--dry-run", action="store_true")
    p_load.add_argument(
        "--reenviar",
        action="store_true",
        help="reenvia imagens que ja' estao no bucket (default: pula o que existe)",
    )
    p_load.add_argument(
        "--target",
        choices=("bigquery", "local"),
        default="bigquery",
        help="local = so' gera o NDJSON, sem bucket nem BigQuery",
    )
    p_load.set_defaults(func=cmd_load)

    p_ver = sub.add_parser("verify", help="confere a cobertura contra as candidaturas")
    comum(p_ver)
    p_ver.set_defaults(func=cmd_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return executar(args.func, args)


if __name__ == "__main__":
    sys.exit(main())
