"""CRUD de Tipos de Actividad en la DB.

Replica el patron de ``tipos_problema_db``:
  - Tipos cerrados con soft-delete (activo=True/False).
  - Configurables desde Settings por el operador.
  - Migracion idempotente desde ``config.TIPOS_ACTIVIDAD``.

Los tipos de actividad son las tareas seleccionables en el combo
'Tarea' del modulo 'Registro de Actividades Diarias'. No son FK
dura en ``ActividadDiaria`` (se guarda el nombre como string) para
que se puedan agregar / renombrar / eliminar sin romper el historial.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from config import TIPOS_ACTIVIDAD
from database.db import get_session
from database.models import TipoActividad


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------


def listar(incluir_inactivos: bool = False) -> list[dict]:
    """Lista los tipos activos (o todos si ``incluir_inactivos``).

    Orden: alfabetico por nombre.
    """
    with get_session() as s:
        stmt = select(TipoActividad).order_by(TipoActividad.nombre.asc())
        if not incluir_inactivos:
            stmt = stmt.where(TipoActividad.activo.is_(True))
        return [t.to_dict() for t in s.scalars(stmt)]


def listar_nombres(solo_activos: bool = True) -> list[str]:
    """Atajo para obtener solo los nombres (como hacia TIPOS_ACTIVIDAD)."""
    return [t["nombre"] for t in listar(incluir_inactivos=not solo_activos)]


def obtener(nombre: str) -> dict | None:
    """Devuelve el tipo activo con ese nombre (case-insensitive), o ``None``."""
    if not nombre:
        return None
    nombre_norm = nombre.strip().lower()
    with get_session() as s:
        stmt = select(TipoActividad).where(TipoActividad.activo.is_(True))
        for t in s.scalars(stmt):
            if t.nombre.lower() == nombre_norm:
                return t.to_dict()
    return None


# ---------------------------------------------------------------------------
# Mutacion
# ---------------------------------------------------------------------------


def agregar(nombre: str) -> dict:
    """Crea un tipo nuevo. Lanza ``ValueError`` si ya existe (case-insensitive)
    o si el nombre esta vacio.
    """
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValueError("El nombre de la tarea no puede estar vacio.")
    existente = obtener(nombre)
    if existente is not None:
        raise ValueError(f"'{nombre}' ya esta en la lista.")
    with get_session() as s:
        # Reactivar si existe pero esta soft-deleted
        inactivos = [
            t for t in s.scalars(select(TipoActividad))
            if t.nombre.lower() == nombre.lower() and not t.activo
        ]
        if inactivos:
            inactivos[0].activo = True
            s.flush()
            return inactivos[0].to_dict()
        t = TipoActividad(nombre=nombre, activo=True)
        s.add(t)
        try:
            s.flush()
        except IntegrityError:
            raise ValueError(f"'{nombre}' ya esta en la lista.")
        return t.to_dict()


def renombrar(nombre_viejo: str, nombre_nuevo: str) -> dict:
    """Cambia el nombre de un tipo. Case-insensitive en ambos extremos."""
    nombre_viejo = (nombre_viejo or "").strip()
    nombre_nuevo = (nombre_nuevo or "").strip()
    if not nombre_viejo:
        raise ValueError("Falta el nombre actual.")
    if not nombre_nuevo:
        raise ValueError("El nuevo nombre no puede estar vacio.")
    if nombre_viejo.lower() == nombre_nuevo.lower():
        actual = obtener(nombre_viejo)
        if actual is None:
            raise ValueError(f"'{nombre_viejo}' no existe.")
        return actual
    otro = obtener(nombre_nuevo)
    if otro is not None:
        raise ValueError(f"'{nombre_nuevo}' ya esta en la lista.")
    with get_session() as s:
        t = next(
            (
                tt for tt in s.scalars(select(TipoActividad).where(
                    TipoActividad.activo.is_(True),
                ))
                if tt.nombre.lower() == nombre_viejo.lower()
            ),
            None,
        )
        if t is None:
            raise ValueError(f"'{nombre_viejo}' no esta en la lista.")
        t.nombre = nombre_nuevo
        s.flush()
        return t.to_dict()


def eliminar(nombre: str) -> dict:
    """Soft-delete: marca ``activo=False``."""
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValueError("Falta el nombre.")
    with get_session() as s:
        t = next(
            (
                tt for tt in s.scalars(select(TipoActividad))
                if tt.nombre.lower() == nombre.lower()
            ),
            None,
        )
        if t is None:
            raise ValueError(f"'{nombre}' no esta en la lista.")
        if not t.activo:
            return t.to_dict()
        t.activo = False
        s.flush()
        return t.to_dict()


def reactivar(nombre: str) -> dict:
    """Revierte el soft-delete."""
    nombre = (nombre or "").strip()
    with get_session() as s:
        t = next(
            (
                tt for tt in s.scalars(select(TipoActividad))
                if tt.nombre.lower() == nombre.lower()
            ),
            None,
        )
        if t is None:
            raise ValueError(f"'{nombre}' no existe.")
        t.activo = True
        s.flush()
        return t.to_dict()


def contar_actividades_que_usan(nombre: str) -> int:
    """Cuenta las actividades que tienen esta tarea registrada.

    Sirve para que la UI muestre un warning al intentar eliminar un
    tipo que esta en uso: '13 actividades lo usan, igual lo elimino?'.
    """
    from sqlalchemy import func
    from database.models import ActividadDiaria

    nombre_norm = (nombre or "").strip()
    if not nombre_norm:
        return 0
    with get_session() as s:
        stmt = select(func.count(ActividadDiaria.id)).where(
            ActividadDiaria.tarea.ilike(nombre_norm),
        )
        return int(s.execute(stmt).scalar() or 0)


# ---------------------------------------------------------------------------
# Migracion desde config.TIPOS_ACTIVIDAD
# ---------------------------------------------------------------------------


def migrar_desde_config(forzar: bool = False) -> dict:
    """Siembra la tabla con los defaults de ``config.TIPOS_ACTIVIDAD``.

    Idempotente: si la tabla ya tiene registros, no hace nada a menos
    que ``forzar=True``. Pensado para llamarse una vez al arranque
    (igual que ``tipos_problema_db.migrar_desde_config``).
    """
    with get_session() as s:
        existentes = s.execute(select(TipoActividad)).scalars().all()
        if existentes and not forzar:
            return {
                "ya_existian": len(existentes),
                "insertadas": 0,
                "defaults_usados": list(TIPOS_ACTIVIDAD),
            }
        if forzar:
            for t in existentes:
                if t.nombre in TIPOS_ACTIVIDAD and t.activo:
                    s.delete(t)
            s.flush()

        insertadas = 0
        for nombre in TIPOS_ACTIVIDAD:
            ya = next(
                (tt for tt in s.scalars(select(TipoActividad))
                 if tt.nombre.lower() == nombre.lower()),
                None,
            )
            if ya is not None:
                if not ya.activo:
                    ya.activo = True
                continue
            s.add(TipoActividad(nombre=nombre, activo=True))
            insertadas += 1
        s.flush()

    return {
        "ya_existian": len(existentes),
        "insertadas": insertadas,
        "defaults_usados": list(TIPOS_ACTIVIDAD),
    }


__all__ = (
    "listar",
    "listar_nombres",
    "obtener",
    "agregar",
    "renombrar",
    "eliminar",
    "reactivar",
    "contar_actividades_que_usan",
    "migrar_desde_config",
)
