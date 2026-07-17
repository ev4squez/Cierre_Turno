"""Servicios de configuracion del sistema.

Wrapper delgado sobre ``config.load_config`` / ``save_config`` para que
la UI no importe el modulo ``config`` directamente.
"""

from __future__ import annotations

from typing import Any

from config import DEFAULT_CONFIG, load_config, save_config


def obtener() -> dict[str, Any]:
    """Devuelve la configuracion actual (defaults + persistida)."""
    return load_config()


def guardar(data: dict[str, Any]) -> None:
    """Reemplaza la configuracion persistida con ``data``."""
    save_config(data)


def actualizar_empresa(datos: dict[str, Any]) -> dict[str, Any]:
    """Actualiza la seccion ``empresa`` y persiste."""
    cfg = load_config()
    cfg["empresa"] = {**cfg["empresa"], **datos}
    save_config(cfg)
    return cfg


def actualizar_correo(datos: dict[str, Any]) -> dict[str, Any]:
    """Actualiza la seccion ``correo`` y persiste."""
    cfg = load_config()
    cfg["correo"] = {**cfg["correo"], **datos}
    save_config(cfg)
    return cfg


def actualizar_tecnicos(tecnicos: list[str]) -> dict[str, Any]:
    """Reemplaza la lista de tecnicos disponibles."""
    cfg = load_config()
    cfg["tecnicos"] = [t.strip() for t in tecnicos if t and t.strip()]
    save_config(cfg)
    return cfg


def reset_a_defaults() -> dict[str, Any]:
    """Restaura la configuracion a defaults (util para 'volver a fabrica')."""
    save_config(DEFAULT_CONFIG)
    return dict(DEFAULT_CONFIG)


__all__ = (
    "obtener",
    "guardar",
    "actualizar_empresa",
    "actualizar_correo",
    "actualizar_tecnicos",
    "reset_a_defaults",
)