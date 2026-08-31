"""Configuracao via variaveis de ambiente — nenhum segredo no repo (SPEC §0.6).

Variaveis reconhecidas (todas opcionais para rodar `--dry-run` / `--target local`):

    DOSSIE_GCP_PROJECT       id do projeto GCP        (default: radar-brasil-ddi)
    DOSSIE_BQ_LOCATION       localizacao dos datasets (default: US — ver ADR-003)
    DOSSIE_DATA_DIR          cache local de download  (default: ./data)

O prefixo antigo `RADAR_` continua aceito — ver `ingest/common/env.py`.
    GOOGLE_APPLICATION_CREDENTIALS   caminho da service account
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from ingest.common.env import env

# Datasets do SPEC §4. Nomes fixos: mudar aqui exige ADR.
DATASET_RAW_TSE = "raw_tse"
DATASET_RAW_IBGE = "raw_ibge"
DATASET_RAW_IPEA = "raw_ipea"
DATASET_RAW_TESOURO = "raw_tesouro"
DATASET_RAW_LEGISLATIVO = "raw_legislativo"
DATASET_RAW_INEP = "raw_inep"
DATASET_STG = "stg"
DATASET_MARTS = "marts"

ALL_DATASETS = (
    DATASET_RAW_TSE,
    DATASET_RAW_IBGE,
    DATASET_RAW_IPEA,
    DATASET_RAW_TESOURO,
    DATASET_RAW_LEGISLATIVO,
    DATASET_RAW_INEP,
    DATASET_STG,
    DATASET_MARTS,
)


@dataclass(frozen=True)
class Settings:
    project: str
    location: str
    data_dir: Path
    credentials_path: str | None = None
    datasets: tuple[str, ...] = field(default=ALL_DATASETS)

    @property
    def download_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def staging_dir(self) -> Path:
        """NDJSON gerado localmente antes da carga no BigQuery."""
        return self.data_dir / "staging"

    def ensure_dirs(self) -> None:
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.staging_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    root = Path(__file__).resolve().parents[2]
    data_dir = Path(env("DOSSIE_DATA_DIR") or root / "data").resolve()
    return Settings(
        # O ID DO PROJETO GCP E' IMUTAVEL e continua `radar-brasil-ddi` (ADR-026):
        # o Google nao renomeia project id, so' o nome de exibicao. Trocar exigiria
        # projeto novo e migrar tudo, sem nada em troca — o id nao aparece em
        # lugar nenhum do site.
        project=env("DOSSIE_GCP_PROJECT", "radar-brasil-ddi"),
        location=env("DOSSIE_BQ_LOCATION", "US"),
        data_dir=data_dir,
        credentials_path=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
    )
