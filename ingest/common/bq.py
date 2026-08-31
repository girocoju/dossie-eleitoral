"""Carga no BigQuery: uma funcao, um contrato — *a tabela reflete o staging*.

Regra de F-01: "reexecutar nao duplica linhas". A primeira implementacao usava
particionamento por DIA sobre uma data derivada do ano da eleicao, para trocar
so' a particao do ano com o decorador `tabela$YYYYMMDD`. **Isso nao sobrevive ao
BigQuery sandbox** (ADR-009): o sandbox impoe expiracao de 60 dias por particao,
contada a partir da DATA DA PARTICAO — uma particao datada de 2026-01-01 nasce com
mais de 200 dias e e' descartada na hora. Conferido em 27/08/2026: 20.765 linhas
carregadas, 0 linhas na tabela.

Desenho atual: particionamento por INTERVALO DE INTEIROS sobre `ano_eleicao`, que
nao tem expiracao por data, e carga que **substitui a tabela inteira** a partir de
todos os NDJSON presentes em `data/staging`. Continua idempotente e continua sem
nenhum SQL fora do dbt (SPEC 9); o preco e' que a carga de um ano precisa dos
NDJSON dos demais anos em disco — por isso `load_ndjson` avisa em log exatamente
quais anos entraram na tabela.

Se `google-cloud-bigquery` nao estiver instalado, o import falha apenas quando a
carga e' de fato pedida — `--target local` e `--dry-run` seguem funcionando sem
nenhuma dependencia externa.
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

# Colunas de procedencia acrescentadas a TODA tabela raw (Constituicao 0.3).
META_COLUMNS: tuple[tuple[str, str], ...] = (
    ("_extracted_at", "TIMESTAMP"),
    ("_source_url", "STRING"),
    ("_source_file", "STRING"),
    ("_source_sha256", "STRING"),
)

# Faixa do particionamento por inteiro. Um ano por particao, com folga nas pontas
# para nao precisar mexer aqui a cada eleicao.
PARTICAO_INICIO = 1990
PARTICAO_FIM = 2040
PARTICAO_INTERVALO = 1

# Coluna de particionamento por DIA usada pela carga cirurgica por ano (ADR-010).
# Vale 1o de janeiro do ano de referencia, o que permite o decorador `tabela$YYYY0101`.
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


def build_schema(
    campos: Sequence[str], *, inteiros: Sequence[str] = (), particao: bool = False
) -> list[Any]:
    """Schema explicito (nunca autodetect): campos da fonte em STRING + metadados.

    `inteiros` sao colunas de chave que precisam de tipo proprio (ex.: `ano_eleicao`
    como INT64, que e' tambem a coluna de particionamento).
    """
    from google.cloud import bigquery

    schema = [bigquery.SchemaField(nome, "STRING") for nome in campos]
    schema += [bigquery.SchemaField(nome, "INT64") for nome in inteiros]
    if particao:
        schema.append(bigquery.SchemaField(PARTITION_COLUMN, "DATE"))
    schema += [bigquery.SchemaField(nome, tipo) for nome, tipo in META_COLUMNS]
    return schema


def ensure_datasets(settings: Settings | None = None) -> None:
    """Cria os datasets do SPEC 4 se nao existirem. Idempotente."""
    from google.cloud import bigquery

    settings = settings or get_settings()
    client = _client(settings)
    for nome in settings.datasets:
        ref = bigquery.Dataset(f"{settings.project}.{nome}")
        ref.location = settings.location
        ref.description = f"Dossie Eleitoral — camada {nome}"
        client.create_dataset(ref, exists_ok=True)
        log.info("dataset   %s.%s pronto (%s)", settings.project, nome, settings.location)


def load_ano(
    ndjson_path: Path,
    dataset: str,
    tabela: str,
    *,
    schema: list[Any],
    ano: int,
    clustering: Sequence[str] = (),
    settings: Settings | None = None,
) -> int:
    """Substitui APENAS a particao do ano, sem tocar nos demais (ADR-010).

    A tabela e' particionada por DIA sobre `data_particao` (1o de janeiro do ano),
    o que habilita o decorador `tabela$YYYY0101` numa carga WRITE_TRUNCATE. E' o
    unico jeito de recarregar 2026 todo dia sem precisar dos NDJSON de 1998 a 2022
    em disco — e sem nenhum SQL de manutencao fora do dbt.
    """
    from google.cloud import bigquery

    settings = settings or get_settings()
    client = _client(settings)
    table_id = f"{settings.project}.{dataset}.{tabela}"
    nomes = {campo.name for campo in schema}
    clustering = [c for c in clustering if c in nomes]

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
    destino = f"{table_id}${ano:04d}0101"
    with ndjson_path.open("rb") as fh:
        job = client.load_table_from_file(fh, destino, job_config=job_config)
    job.result()
    log.info("carregado %s <- %s (%s linhas)", destino, ndjson_path.name, job.output_rows)
    return int(job.output_rows or 0)


def load_intervalo(
    ndjson_path: Path,
    dataset: str,
    tabela: str,
    *,
    schema: list[Any],
    coluna: str,
    valor: int,
    clustering: Sequence[str] = (),
    settings: Settings | None = None,
) -> int:
    """Substitui UMA particao de tabela particionada por INTERVALO DE INTEIRO.

    Irma de `load_ano`, para o outro esquema de particionamento que o projeto
    usa. `load_ano` vale para tabela particionada por DIA sobre `data_particao`,
    com decorador `$YYYY0101`; esta vale para particionamento por intervalo sobre
    uma coluna inteira, com decorador `$<valor>`.

    Existe por causa das proposicoes da Camara. A tabela ja' era particionada por
    `ano`, e a carga trocava a tabela INTEIRA — o que funcionava enquanto so'
    havia 2023-2026. Com os anos historicos (2003-2022), a carga diaria passaria
    a apagar vinte anos de dado todo dia. Trocar o esquema da tabela para agradar
    `load_ano` seria reescrever o que ja' estava certo; mais simples e' ter o
    carregador do esquema que a tabela tem (ADR-024).
    """
    from google.cloud import bigquery

    settings = settings or get_settings()
    client = _client(settings)
    table_id = f"{settings.project}.{dataset}.{tabela}"
    nomes = {campo.name for campo in schema}
    clustering = [c for c in clustering if c in nomes]

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        range_partitioning=bigquery.RangePartitioning(
            field=coluna,
            range_=bigquery.PartitionRange(start=1990, end=2040, interval=1),
        ),
        clustering_fields=list(clustering) or None,
        ignore_unknown_values=False,
        max_bad_records=0,
    )
    destino = f"{table_id}${valor}"
    with ndjson_path.open("rb") as fh:
        job = client.load_table_from_file(fh, destino, job_config=job_config)
    job.result()
    log.info("carregado %s <- %s (%s linhas)", destino, ndjson_path.name, job.output_rows)
    return int(job.output_rows or 0)


def load_ndjson(
    ndjson_paths: Path | Sequence[Path],
    dataset: str,
    tabela: str,
    *,
    schema: list[Any],
    particionar_por: str | None = None,
    clustering: Sequence[str] = (),
    settings: Settings | None = None,
) -> int:
    """Substitui `dataset.tabela` pelo conteudo de todos os `ndjson_paths`.

    O primeiro arquivo entra com WRITE_TRUNCATE e os demais com WRITE_APPEND, o que
    torna a tabela final exatamente igual ao conjunto de arquivos passado — sem
    duplicata possivel, mesmo reexecutando.
    """
    from google.cloud import bigquery

    settings = settings or get_settings()
    client = _client(settings)
    table_id = f"{settings.project}.{dataset}.{tabela}"

    caminhos = [ndjson_paths] if isinstance(ndjson_paths, Path) else sorted(ndjson_paths)
    if not caminhos:
        raise RuntimeError(f"nenhum NDJSON para carregar em {table_id}")

    # Clustering por coluna inexistente derruba o job inteiro com um 400. Como a
    # lista vem do layout do ano, ela pode legitimamente mudar — entao o pedido e'
    # reduzido ao que existe no schema, com aviso, em vez de falhar uma carga que
    # de resto esta' correta.
    nomes = {campo.name for campo in schema}
    pedidas = list(clustering)
    clustering = [c for c in pedidas if c in nomes]
    if len(clustering) != len(pedidas):
        log.warning(
            "clustering ignorado para %s: %s nao existe(m) no schema",
            tabela,
            [c for c in pedidas if c not in nomes],
        )

    particionamento = None
    if particionar_por and particionar_por in nomes:
        particionamento = bigquery.RangePartitioning(
            field=particionar_por,
            range_=bigquery.PartitionRange(
                start=PARTICAO_INICIO, end=PARTICAO_FIM, interval=PARTICAO_INTERVALO
            ),
        )

    total = 0
    for i, caminho in enumerate(caminhos):
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            schema=schema,
            write_disposition=(
                bigquery.WriteDisposition.WRITE_TRUNCATE
                if i == 0
                else bigquery.WriteDisposition.WRITE_APPEND
            ),
            range_partitioning=particionamento,
            clustering_fields=list(clustering) or None,
            ignore_unknown_values=False,
            max_bad_records=0,
        )
        with caminho.open("rb") as fh:
            job = client.load_table_from_file(fh, table_id, job_config=job_config)
        job.result()
        total += int(job.output_rows or 0)
        log.info(
            "%s %s <- %s (%s linhas)",
            "carregado" if i == 0 else "  anexado",
            table_id,
            caminho.name,
            job.output_rows,
        )

    if len(caminhos) > 1:
        log.info("%s: %d arquivos, %d linhas no total", table_id, len(caminhos), total)
    return total
