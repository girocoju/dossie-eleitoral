"""Escrita do formato intermediario: NDJSON gzip, uma linha por registro.

Por que NDJSON e nao parquet/pandas: a camada `raw_*` e' copia fiel da fonte com
todos os campos em STRING (SPEC §4). NDJSON faz isso com a stdlib, sem pandas nem
pyarrow, e e' o formato que o `load_table_from_file` do BigQuery consome direto.
"""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any

from ingest.common.log import get_logger

log = get_logger("writer")


class NdjsonWriter:
    """Context manager que escreve `.ndjson.gz` e conta linhas."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.rows = 0
        self._fh: gzip.GzipFile | None = None

    def __enter__(self) -> NdjsonWriter:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # mtime=0 deixa o gzip byte-identico entre execucoes com o mesmo conteudo
        self._fh = gzip.GzipFile(self.path, "wb", compresslevel=6, mtime=0)
        return self

    def write(self, row: Mapping[str, Any]) -> None:
        assert self._fh is not None, "use dentro de `with`"
        line = json.dumps(row, ensure_ascii=False, separators=(",", ":"), default=str)
        self._fh.write(line.encode("utf-8"))
        self._fh.write(b"\n")
        self.rows += 1

    def write_all(self, rows: Iterable[Mapping[str, Any]]) -> int:
        for row in rows:
            self.write(row)
        return self.rows

    def __exit__(self, *exc: object) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None
        log.info("gravado   %s (%d linhas)", self.path.name, self.rows)


def read_ndjson(path: Path) -> Iterator[dict[str, Any]]:
    """Le de volta um `.ndjson.gz` — usado pelos testes e pelo `--target local`."""
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as fh:  # type: ignore[operator]
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)
