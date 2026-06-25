"""Utilitários: logging, formatação de resultados, validação."""
from __future__ import annotations
import logging
import sys
from pathlib import Path


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )


def format_source(source: str, page: int | None = None) -> str:
    name = Path(source).name
    return f"{name} (p. {page})" if page is not None else name


def validate_data_dir(data_dir: Path) -> bool:
    files = list(data_dir.rglob("*.pdf")) + list(data_dir.rglob("*.txt"))
    return len(files) > 0
