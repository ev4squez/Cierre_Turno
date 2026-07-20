"""Servicio de borradores de incidencia.

Un borrador es una copia temporal de un form de FDS que el operador
empiezo a llenar pero no confirmo con 'Guardar Registro'. Se guarda
automaticamente en la DB mientras el operador escribe, asi si la app
se cierra / crashea / el operador se olvida, el borrador queda y se
puede restaurar al volver a abrir el form.

Estructura: una sola fila en la tabla ``borradores_incidencia`` con
todos los campos del form + timestamp. Cuando se confirma el 'Guardar
Registro' real, el borrador se borra.

Si el operador edita una FDS existente (modo edicion), el borrador
no se usa: la FDS ya esta persistida.
"""

from __future__ import annotations

from sqlalchemy import delete, select

from database.db import get_session
from database.models import BorradorIncidencia


def guardar(maquina_numero: str, tecnico: str, data: dict) -> dict | None:
    """Guarda (o reemplaza) el borrador para una maquina + tecnico.

    Solo hay UN borrador activo por (maquina, tecnico). Si ya existe,
    lo reemplaza.
    """
    try:
        with get_session() as s:
            existente = s.execute(
                select(BorradorIncidencia).where(
                    BorradorIncidencia.maquina_numero == str(maquina_numero),
                    BorradorIncidencia.tecnico == tecnico,
                )
            ).scalar_one_or_none()
            if existente is not None:
                # Reemplazar
                existente.problema = data.get("problema", "")
                existente.motivo_fuera_servicio = data.get(
                    "motivo_fuera_servicio", ""
                )
                existente.accion_realizada = data.get(
                    "accion_realizada", ""
                )
                existente.estado_final = data.get("estado_final", "")
                existente.observaciones = data.get("observaciones", "")
                s.flush()
                return existente.to_dict()
            else:
                nuevo = BorradorIncidencia(
                    maquina_numero=str(maquina_numero),
                    tecnico=tecnico,
                    problema=data.get("problema", ""),
                    motivo_fuera_servicio=data.get("motivo_fuera_servicio", ""),
                    accion_realizada=data.get("accion_realizada", ""),
                    estado_final=data.get("estado_final", ""),
                    observaciones=data.get("observaciones", ""),
                )
                s.add(nuevo)
                s.flush()
                return nuevo.to_dict()
    except Exception:
        # best-effort: si la DB falla, no rompemos el flujo del operador
        import logging
        logging.getLogger(__name__).exception(
            "No se pudo guardar borrador para %s/%s",
            maquina_numero, tecnico,
        )
        return None


def obtener(maquina_numero: str, tecnico: str) -> dict | None:
    """Devuelve el borrador activo para una maquina + tecnico, o None."""
    try:
        with get_session() as s:
            row = s.execute(
                select(BorradorIncidencia).where(
                    BorradorIncidencia.maquina_numero == str(maquina_numero),
                    BorradorIncidencia.tecnico == tecnico,
                )
            ).scalar_one_or_none()
            return row.to_dict() if row else None
    except Exception:
        return None


def eliminar(maquina_numero: str, tecnico: str) -> bool:
    """Borra el borrador (cuando se confirma el 'Guardar Registro' real)."""
    try:
        with get_session() as s:
            s.execute(
                delete(BorradorIncidencia).where(
                    BorradorIncidencia.maquina_numero == str(maquina_numero),
                    BorradorIncidencia.tecnico == tecnico,
                )
            )
            return True
    except Exception:
        return False


__all__ = ("guardar", "obtener", "eliminar")
