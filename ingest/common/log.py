"""Logging padronizado: uma linha por evento, legivel no GitHub Actions."""

from __future__ import annotations

import logging
import os
import sys

_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-22s | %(message)s"
_configured = False


def _configure() -> None:
    global _configured
    if _configured:
        return
    level = os.environ.get("RADAR_LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt="%H:%M:%S"))
    root = logging.getLogger("radar")
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)
    root.propagate = False
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Devolve um logger sob o namespace `radar.`."""
    _configure()
    return logging.getLogger(f"radar.{name}")
