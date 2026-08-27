"""Carga no BigQuery: uma funcao, um contrato — *substituir a particao do ano*.

Regra de F-01: "reexecutar nao duplica linhas (carga substitui particao do ano)".
Implementacao: as tabelas `raw_*` sao particionadas por DIA sobre a coluna
`data_particao` (= 1o de janeiro do ano de referencia), o que permite carregar
com o decorador `tabela$YYYY0101` em modo WRITE_TRUNCATE. Assim a reexecucao de
um ano troca apenas aquele ano, sem tocar nos demais e **sem nenhum SQL**
(SPEC §9: nenhum SQL fora do dbt).

Se a biblioteca `google-cloud-bigquery` nao estiver instalada, o import falha
apenas quando a carga e' de fato pedida — `--target local` e `--dry-run` seguem
funcionando sem nenhuma dependencia externa.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ingest.common.config import Settings, get_settings
from ingest.common.log import get_logger

if TYPE_CHECKING:  # pragma: no cover
    pass

log = get_logger("bq")

# Colunas de procedencia acrescentadas a TODA tabela raw (Constituicao §3).
META_COLUMNS: tuple[tuple[str, str], ...] = (
    ("_extracted_at", "TIMESTAMP"),
    ("_source_url", "STRING"),
    ("_source_file", "STRING"),
    ("_source_sha256", "STRING"),
)
PARTITION_COLUMN = "data_particao"


def _client(settings: Settings | None = None):
    try:
        from google.cloud import bigquery
    except ImportError as exc:  # pragma: no cover - depende do ambiente
        raise RuntimeError(
            "google-cloud-bigquery nao instalado. Rode `make bootstrap`, "
            "ou use `--target local` para gerar apenas o NDJSON."
        ) from exc
    settings = settings or get_settings()
    return bigquery.Client(project=settings.project, location=settings.location)


def build_schema(campos: Sequence[str], *, partition_extra: Sequence[str] = ()) -> list[Any]:
    """Schema explicito (nunca autodetect): campos da fonte em STRING + metadados.

    `partition_extra` sao colunas de chave que precisam de tipo proprio
    (ex.: `ano_eleicao` como INT64) para o dbt nao ter que castear no staging.
    """
    from google.cloud import bigquery

    schema = [bigquery.SchemaField(nome, "STRING") for nome in campos]
    for nome in partition_extra:
        schema.append(bigquery.SchemaField(nome, "INT64"))
    schema.append(bigquery.SchemaField(PARTITION_COLUMN, "DATE"))
    schema += [bigquery.SchemaField(nome, tipo) for nome, tipo in META_COLUMNS]
    return schema


def ensure_datasets(settings: Settings | None = None) -> None:
    """Cria os datasets do SPEC §4 se nao existirem. Idempotente."""
    from google.cloud import bigquery

    settings = settings or get_settings()
    client = _client(settings)
    for nome in settings.datasets:
        ref = bigquery.Dataset(f"{settings.project}.{nome}")
        ref.location = settings.location
        ref.description = f"Radar Brasil — camada {nome}"
        client.create_dataset(ref, exists_ok=True)
        log.info("dataset   %s.%s pronto (%s)", settings.project, nome, settings.location)


def load_ndjson(
    ndjson_path: Path,
    dataset: str,
    tabela: str,
    *,
    schema: list[Any],
    ano_particao: int | None = None,
    clustering: Sequence[str] = (),
    settings: Settings | None = None,
) -> int:
    """Carrega um `.ndjson.gz` numa tabela particionada. Devolve linhas gravadas.

    `ano_particao` define a particao substituida. Sem ele, a tabela inteira e'
    substituida (usado por fontes pequenas, como os indicadores).
    """
    from google.cloud import bigquery

    settings = settings or get_settings()
    client = _client(settings)
    table_id = f"{settings.project}.{dataset}.{tabela}"

    destino = table_id
    if ano_particao is not None:
        destino = f"{table_id}${ano_particao:04d}0101"

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        time_partitioning=bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY, field=PARTITION_COLUMN
        ),
        clustering_fields=list(clustering) or None,
        ignore_unknown_values=False,
        max_bad_records=0,
    )

    with ndjson_path.open("rb") as fh:
        job = client.load_table_from_file(fh, destino, job_config=job_config)
    job.result()

    log.info("carregado %s <- %s (%s linhas)", destino, ndjson_path.name, job.output_rows)
    return int(job.output_rows or 0)
