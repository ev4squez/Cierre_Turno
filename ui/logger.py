"""Configuracion del logging estructurado del sistema.

Inicializa un logger raiz con:
  - Salida a stderr (nivel INFO por defecto)
  - Rotacion diaria en ``logs/sistema_fds.log`` (nivel DEBUG)

Pensado para que si la app crashea, el operador tenga info util
para mandarnos. Los logs rotan automaticamente para no llenar
disco (mantiene 30 dias).
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

from config import LOGS_DIR


def setup_logging(level: int = logging.INFO) -> None:
    """Inicializa el sistema de logging una sola vez al arranque."""
    # Si ya esta configurado (test runner, hot-reload), no hacer nada
    if logging.getLogger().handlers:
        return

    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler a stderr (consola)
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)
    console.setFormatter(formatter)
    root.addHandler(console)

    # Handler rotativo (1 archivo por dia, 30 dias de retencion)
    log_file = LOGS_DIR / "sistema_fds.log"
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # Silenciar librerias ruidosas
    logging.getLogger("PySide6").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Atajo: ``from ui.logger import get_logger; log = get_logger(__name__)``."""
    return logging.getLogger(name)


__all__ = ("setup_logging", "get_logger")
