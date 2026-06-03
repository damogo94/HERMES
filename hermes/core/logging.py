"""Configuración de logging para HERMES."""

from __future__ import annotations

import logging
import sys

_CONFIGURED = False
_FMT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Inicializa el logging raíz una sola vez. Devuelve el logger 'hermes'."""
    global _CONFIGURED
    if not _CONFIGURED:
        logging.basicConfig(
            level=getattr(logging, level.upper(), logging.INFO),
            format=_FMT,
            stream=sys.stdout,
        )
        _CONFIGURED = True
    return logging.getLogger("hermes")


def get_logger(name: str) -> logging.Logger:
    """Logger hijo namespaced bajo 'hermes.<name>'."""
    return logging.getLogger(f"hermes.{name}")
