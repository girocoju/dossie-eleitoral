"""Logging padronizado: uma linha por evento, legivel no GitHub Actions."""

from __future__ import annotations

import logging
import sys

from ingest.common.env import env

_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-22s | %(message)s"
_configured = False


def _configure() -> None:
    global _configured
    if _configured:
        return
    level = (env("DOSSIE_LOG_LEVEL") or "INFO").upper()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt="%H:%M:%S"))
    root = logging.getLogger("dossie")
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)
    root.propagate = False
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Devolve um logger sob o namespace `dossie.`."""
    _configure()
    return logging.getLogger(f"dossie.{name}")
