"""Ingestao TSE — F-01 (2026) e F-02 (1998-2022).

    python -m ingest.tse load          --ano 2026 [--dataset candidatos] [--dry-run]
    python -m ingest.tse verify-layout --ano 2026
    python -m ingest.tse anos

Fluxo: baixa o `.zip` do CDN do TSE (cache + sha256), le os CSVs Latin-1 de dentro
sem extrair para o disco, resolve o header contra `layouts/tse_{ano}.yml`, grava
NDJSON gzip e — se `--target bigquery` — substitui a particao do ano em `raw_tse`.

Nada aqui interpreta o dado: conversao de tipo, deduplicacao e regra de negocio
sao responsabilidade do dbt (SPEC 4: `raw_*` e' copia fiel, tudo STRING).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import zipfile
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ingest.common.bq import build_schema, ensure_datasets, load_ndjson
from ingest.common.config import DATASET_RAW_TSE, get_settings
from ingest.common.http import Artifact, download, utc_now
from ingest.common.layout import (
    DatasetLayout,
    LayoutError,
    Resolucao,
    anos_disponiveis,
    load_layout,
)
from ingest.common.log import get_logger
from ingest.common.textnorm import cpf_hash
from ingest.common.writer import NdjsonWriter

log = get_logger("tse")

# CSV do TSE tem campos longos (composicao de coligacao com dezenas de partidos)
csv.field_size_limit(10 * 1024 * 1024)

CLUSTERING = {
    "candidatos": ("sg_uf", "cod_cargo", "sigla_partido"),
    "bens": ("sg_uf",),
    "vagas": ("sg_uf", "cod_cargo"),
    "coligacoes": ("sg_uf", "cod_cargo"),
    "complementar": ("sg_uf",),
}


@dataclass
class Resultado:
    dataset: str
    ano: int
    linhas: int
    arquivos: int
    ndjson: Path
    por_uf: dict[str, int]
    por_cargo: dict[str, int]
    campos_ausentes: list[str]
    extras: list[str]
    ano_divergente: int = 0

    def resumo(self) -> str:
        return (
            f"{self.dataset} {self.ano}: {self.linhas} linhas de {self.arquivos} arquivos, "
            f"{len(self.por_uf)} UEs, {len(self.por_cargo)} cargos"
        )


def _zip_path(ano: int, ds: DatasetLayout) -> Path:
    return get_settings().download_dir / "tse" / str(ano) / ds.zip_name


def baixar(ds: DatasetLayout, *, force: bool = False, dry_run: bool = False) -> Artifact:
    return download(ds.url, _zip_path(ds.ano, ds), force=force, dry_run=dry_run)


def _membros(zf: zipfile.ZipFile, ds: DatasetLayout) -> list[str]:
    padrao = ds.compila_regex()
    nomes = [n for n in zf.namelist() if padrao.match(Path(n).name)]
    if not nomes:
        raise LayoutError(
            f"nenhum CSV de {ds.nome} {ds.ano} casou com {padrao.pattern}. "
            f"Conteudo do zip: {zf.namelist()[:20]}"
        )
    return sorted(nomes)


def _leitor(zf: zipfile.ZipFile, membro: str, ds: DatasetLayout):
    raw = zf.open(membro, "r")
    texto = io.TextIOWrapper(raw, encoding=ds.encoding, errors="replace", newline="")
    return csv.reader(texto, delimiter=ds.delimitador, quotechar='"')


def _linhas(
    zip_file: Path, ds: DatasetLayout, art: Artifact, *, limite: int | None = None
) -> Iterator[tuple[dict[str, Any], Resolucao, str]]:
    """Gera as linhas de todos os CSVs do pacote, ja' no formato da tabela raw."""
    extraido_em = art.extracted_at or utc_now()
    particao = f"{ds.ano:04d}-01-01"
    emitidas = 0

    with zipfile.ZipFile(zip_file) as zf:
        for membro in _membros(zf, ds):
            leitor = _leitor(zf, membro, ds)
            try:
                header = next(leitor)
            except StopIteration:
                log.warning("arquivo vazio: %s", membro)
                continue

            resolucao = ds.resolve(header)
            ds.exige(resolucao)

            nome_arquivo = Path(membro).name
            for valores in leitor:
                if not valores or all(not v.strip() for v in valores):
                    continue
                linha: dict[str, Any] = {}
                for canonico, idx in resolucao.indices.items():
                    if canonico == "ano_eleicao" or canonico in ds.descartar:
                        continue
                    bruto = valores[idx].strip() if idx < len(valores) else None
                    # privacidade: o valor sensivel vira hash e o original nunca
                    # e' escrito em lugar nenhum (Constituicao 0.7 / ADR-007)
                    if canonico in ds.hash_map:
                        linha[ds.hash_map[canonico]] = cpf_hash(bruto)
                    else:
                        linha[canonico] = bruto
                for canonico in resolucao.faltando_opcionais:
                    if canonico in ds.descartar:
                        continue
                    linha[ds.hash_map.get(canonico, canonico)] = None

                extras = {
                    nome: (valores[idx].strip() if idx < len(valores) else None)
                    for nome, idx in resolucao.extras.items()
                    if nome not in ds.descartar
                }
                linha["_extras"] = json.dumps(extras, ensure_ascii=False) if extras else None
                linha["ano_eleicao"] = ds.ano
                linha["data_particao"] = particao
                linha["_extracted_at"] = extraido_em
                linha["_source_url"] = art.url
                linha["_source_file"] = nome_arquivo
                linha["_source_sha256"] = art.sha256

                idx_ano = resolucao.indices.get("ano_eleicao")
                ano_fonte = valores[idx_ano].strip() if idx_ano is not None else ""
                yield linha, resolucao, ano_fonte

                emitidas += 1
                if limite and emitidas >= limite:
                    return


def processar(
    ano: int,
    nome_dataset: str,
    *,
    force: bool = False,
    dry_run: bool = False,
    limite: int | None = None,
) -> Resultado | None:
    """Baixa + converte um dataset de um ano para NDJSON. Nao toca no BigQuery."""
    settings = get_settings()
    settings.ensure_dirs()
    ds = load_layout(ano).dataset(nome_dataset)

    art = baixar(ds, force=force, dry_run=dry_run)
    if dry_run:
        log.info("[dry-run] %s %s: leria %s", nome_dataset, ano, ds.url)
        return None

    destino = settings.staging_dir / "tse" / f"{nome_dataset}_{ano}.ndjson.gz"
    por_uf: Counter[str] = Counter()
    por_cargo: Counter[str] = Counter()
    arquivos: set[str] = set()
    ausentes: set[str] = set()
    extras: set[str] = set()
    divergente = 0

    with NdjsonWriter(destino) as writer:
        for linha, resolucao, ano_fonte in _linhas(_zip_path(ano, ds), ds, art, limite=limite):
            writer.write(linha)
            arquivos.add(str(linha["_source_file"]))
            ausentes.update(resolucao.faltando_opcionais)
            extras.update(resolucao.extras)
            if linha.get("sg_uf"):
                por_uf[str(linha["sg_uf"])] += 1
            if linha.get("cod_cargo"):
                por_cargo[str(linha["cod_cargo"])] += 1
            if ano_fonte and ano_fonte != str(ano):
                divergente += 1
        linhas = writer.rows

    if divergente:
        log.warning(
            "%d linhas com ANO_ELEICAO diferente de %d — conferir o pacote da fonte",
            divergente,
            ano,
        )

    resultado = Resultado(
        dataset=nome_dataset,
        ano=ano,
        linhas=linhas,
        arquivos=len(arquivos),
        ndjson=destino,
        por_uf=dict(por_uf),
        por_cargo=dict(por_cargo),
        campos_ausentes=sorted(ausentes),
        extras=sorted(extras),
        ano_divergente=divergente,
    )
    _grava_qa(resultado)
    log.info("%s", resultado.resumo())
    return resultado


def _grava_qa(resultado: Resultado) -> None:
    """Relatorio de carga — insumo para docs/LACUNAS.md (SPEC 9)."""
    qa = get_settings().staging_dir / "qa" / f"tse_{resultado.dataset}_{resultado.ano}.json"
    qa.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset": resultado.dataset,
        "ano": resultado.ano,
        "linhas": resultado.linhas,
        "arquivos": resultado.arquivos,
        "por_uf": resultado.por_uf,
        "por_cargo": resultado.por_cargo,
        "campos_opcionais_ausentes": resultado.campos_ausentes,
        "colunas_nao_mapeadas": resultado.extras,
        "linhas_com_ano_divergente": resultado.ano_divergente,
    }
    qa.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def carregar_bigquery(ano: int, nome_dataset: str, resultado: Resultado) -> int:
    ds = load_layout(ano).dataset(nome_dataset)
    campos = ds.colunas_saida() + ["_extras"]
    schema = build_schema(campos, partition_extra=["ano_eleicao"])
    ensure_datasets()
    return load_ndjson(
        resultado.ndjson,
        DATASET_RAW_TSE,
        nome_dataset,
        schema=schema,
        ano_particao=ano,
        clustering=CLUSTERING.get(nome_dataset, ()),
    )


# --------------------------------- CLI ---------------------------------


def cmd_load(args: argparse.Namespace) -> int:
    layout = load_layout(args.ano)
    if not layout.verificado:
        log.warning(
            "layout tse_%s.yml ainda nao foi conferido contra o arquivo real "
            "(`verificado: false`). Rode `verify-layout --ano %s`.",
            args.ano,
            args.ano,
        )
    alvos = [args.dataset] if args.dataset else list(layout.datasets)
    codigo = 0
    for nome in alvos:
        try:
            resultado = processar(
                args.ano,
                nome,
                force=args.force,
                dry_run=args.dry_run,
                limite=args.limite,
            )
        except (LayoutError, RuntimeError) as exc:
            log.error("falha em %s %s: %s", nome, args.ano, exc)
            codigo = 1
            continue
        if resultado is None or args.target == "local":
            continue
        carregar_bigquery(args.ano, nome, resultado)
    return codigo


def cmd_verify_layout(args: argparse.Namespace) -> int:
    """Confere o header real de cada CSV contra o YAML do ano. Nao carrega nada."""
    layout = load_layout(args.ano)
    alvos = [args.dataset] if args.dataset else list(layout.datasets)
    problemas = 0

    for nome in alvos:
        ds = layout.dataset(nome)
        print(f"\n=== {nome} {args.ano} ===")
        print(f"url   : {ds.url}")
        print(f"leiame: {ds.leiame_url}")
        try:
            art = baixar(ds, force=args.force)
        except RuntimeError as exc:
            print(f"  ERRO no download: {exc}")
            problemas += 1
            continue

        with zipfile.ZipFile(_zip_path(args.ano, ds)) as zf:
            try:
                membros = _membros(zf, ds)
            except LayoutError as exc:
                print(f"  ERRO: {exc}")
                problemas += 1
                continue
            print(f"arquivos no zip que casam o padrao: {len(membros)} (ex.: {membros[0]})")
            leitor = _leitor(zf, membros[0], ds)
            header = next(leitor)

        resolucao = ds.resolve(header)
        print(f"colunas no header : {len(header)}")
        print(f"campos resolvidos : {len(resolucao.indices)}/{len(ds.campos)}")
        if resolucao.faltando_obrigatorios:
            problemas += 1
            print(f"  !! OBRIGATORIOS AUSENTES: {list(resolucao.faltando_obrigatorios)}")
        if resolucao.faltando_opcionais:
            print(f"  -- opcionais ausentes (viram NULL): {list(resolucao.faltando_opcionais)}")
        if resolucao.extras:
            print(f"  ++ colunas nao mapeadas (vao para _extras): {list(resolucao.extras)}")
        print(f"  sha256 do pacote: {art.sha256[:16]}...")

    if problemas:
        print(
            f"\n{problemas} dataset(s) com pendencia. Abra o leiame do ano e atualize "
            f"ingest/layouts/tse_{args.ano}.yml (nunca o .py)."
        )
        return 1
    print(f"\nTudo resolvido. Pode marcar `verificado: true` em ingest/layouts/tse_{args.ano}.yml.")
    return 0


def cmd_anos(_: argparse.Namespace) -> int:
    for ano in anos_disponiveis():
        layout = load_layout(ano)
        marca = "conferido" if layout.verificado else "NAO conferido"
        print(f"{ano}  [{marca}]  datasets: {', '.join(layout.datasets)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ingest.tse", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    def comum(p: argparse.ArgumentParser) -> None:
        p.add_argument("--ano", type=int, required=True, help="ano da eleicao (ex.: 2026)")
        p.add_argument("--dataset", help="so' um dataset (candidatos, bens, vagas, ...)")
        p.add_argument("--force", action="store_true", help="ignora o cache de download")

    p_load = sub.add_parser("load", help="baixa, converte e carrega")
    comum(p_load)
    p_load.add_argument("--dry-run", action="store_true", help="mostra o que faria e sai")
    p_load.add_argument(
        "--target",
        choices=("bigquery", "local"),
        default="bigquery",
        help="local = para no NDJSON, sem tocar no BigQuery",
    )
    p_load.add_argument("--limite", type=int, help="processa so' N linhas (teste de fumaca)")
    p_load.set_defaults(func=cmd_load)

    p_ver = sub.add_parser("verify-layout", help="confere o header real contra o YAML do ano")
    comum(p_ver)
    p_ver.set_defaults(func=cmd_verify_layout)

    p_anos = sub.add_parser("anos", help="lista os anos com layout declarado")
    p_anos.set_defaults(func=cmd_anos)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
