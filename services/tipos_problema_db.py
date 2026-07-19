"""CRUD de Tipos de Problema en la DB.

Los tipos de problema (Falla electronica, Falla mecanica, Software,
etc.) viven en una tabla SQLite, no en ``config.TIPOS_PROBLEMA``.
Esto permite que el operador agregue / edite / elimine categorias
desde Settings sin reiniciar la app.

Tambien expone un helper de migracion: si la tabla esta vacia en el
arranque, siembra los defaults de ``config.TIPOS_PROBLEMA``.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from config import TIPOS_PROBLEMA
from database.db import get_session
from database.models import TipoProblema


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------


def listar(incluir_inactivos: bool = False) -> list[dict]:
    """Lista los tipos de problema activos (o todos si ``incluir_inactivos``).

    Orden: alfabetico por nombre.
    """
    with get_session() as s:
        stmt = select(TipoProblema).order_by(TipoProblema.nombre.asc())
        if not incluir_inactivos:
            stmt = stmt.where(TipoProblema.activo.is_(True))
        return [t.to_dict() for t in s.scalars(stmt)]


def listar_nombres(solo_activos: bool = True) -> list[str]:
    """Atajo para obtener solo los nombres (como hacia TIPOS_PROBLEMA)."""
    return [t["nombre"] for t in listar(incluir_inactivos=not solo_activos)]


def obtener(nombre: str) -> dict | None:
    """Devuelve el tipo activo con ese nombre (case-insensitive), o ``None``."""
    if not nombre:
        return None
    nombre_norm = nombre.strip().lower()
    with get_session() as s:
        stmt = select(TipoProblema).where(
            TipoProblema.activo.is_(True),
        )
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
        raise ValueError("El nombre del tipo no puede estar vacio.")
    # Reactivar si existe pero esta soft-deleted
    existente = obtener(nombre)
    if existente is not None:
        raise ValueError(f"'{nombre}' ya esta en la lista.")
    with get_session() as s:
        existentes_inactivos = [
            t for t in s.scalars(select(TipoProblema))
            if t.nombre.lower() == nombre.lower() and not t.activo
        ]
        if existentes_inactivos:
            existentes_inactivos[0].activo = True
            s.flush()
            return existentes_inactivos[0].to_dict()
        t = TipoProblema(nombre=nombre, activo=True)
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
        # No-op si es el mismo nombre
        actual = obtener(nombre_viejo)
        if actual is None:
            raise ValueError(f"'{nombre_viejo}' no existe.")
        return actual
    # Verificar que el nuevo no choque con otro existente
    otro = obtener(nombre_nuevo)
    if otro is not None:
        raise ValueError(f"'{nombre_nuevo}' ya esta en la lista.")
    with get_session() as s:
        t = next(
            (
                tt for tt in s.scalars(select(TipoProblema).where(
                    TipoProblema.activo.is_(True),
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
    """Soft-delete: marca ``activo=False``.

    Si hay incidencias registradas con este tipo, igual lo desactiva
    pero el controller recibe un warning al refrescar el combo (lo
    muestra igual que los activos existentes, asi no se rompe el
    historial).
    """
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValueError("Falta el nombre.")
    with get_session() as s:
        t = next(
            (
                tt for tt in s.scalars(select(TipoProblema))
                if tt.nombre.lower() == nombre.lower()
            ),
            None,
        )
        if t is None:
            raise ValueError(f"'{nombre}' no esta en la lista.")
        if not t.activo:
            return t.to_dict()  # ya estaba borrado
        t.activo = False
        s.flush()
        return t.to_dict()


def reactivar(nombre: str) -> dict:
    """Revierte el soft-delete."""
    nombre = (nombre or "").strip()
    with get_session() as s:
        t = next(
            (
                tt for tt in s.scalars(select(TipoProblema))
                if tt.nombre.lower() == nombre.lower()
            ),
            None,
        )
        if t is None:
            raise ValueError(f"'{nombre}' no existe.")
        t.activo = True
        s.flush()
        return t.to_dict()


def contar_incidencias_que_usan(nombre: str) -> int:
    """Cuenta las incidencias que tienen este problema registrado.

    Sirve para que la UI muestre un warning al intentar eliminar un
    tipo que esta en uso: '13 incidencias lo usan, igual lo elimino?'.
    """
    from sqlalchemy import func
    from database.models import Incidencia
    nombre_norm = (nombre or "").strip()
    if not nombre_norm:
        return 0
    with get_session() as s:
        stmt = select(func.count(Incidencia.id)).where(
            Incidencia.problema.ilike(nombre_norm),
        )
        return int(s.execute(stmt).scalar() or 0)


# ---------------------------------------------------------------------------
# Migracion desde config.TIPOS_PROBLEMA
# ---------------------------------------------------------------------------


def migrar_desde_config(forzar: bool = False) -> dict:
    """Siembra la tabla con los defaults de ``config.TIPOS_PROBLEMA``.

    Idempotente: si la tabla ya tiene registros (activos o no), no
    hace nada a menos que ``forzar=True``.

    Pensado para llamarse una vez al arranque (igual que
    ``tecnicos_db.migrar_desde_config``).
    """
    with get_session() as s:
        existentes = s.execute(select(TipoProblema)).scalars().all()
        if existentes and not forzar:
            return {
                "ya_existian": len(existentes),
                "insertadas": 0,
                "defaults_usados": list(TIPOS_PROBLEMA),
            }
        # Si forzamos, vaciamos primero (solo los activos que coincidan
        # con los defaults para no pisar tipos custom del usuario).
        if forzar:
            for t in existentes:
                if t.nombre in TIPOS_PROBLEMA and t.activo:
                    s.delete(t)
            s.flush()

        insertadas = 0
        for nombre in TIPOS_PROBLEMA:
            ya = next(
                (tt for tt in s.scalars(select(TipoProblema))
                 if tt.nombre.lower() == nombre.lower()),
                None,
            )
            if ya is not None:
                if not ya.activo:
                    ya.activo = True
                continue
            s.add(TipoProblema(nombre=nombre, activo=True))
            insertadas += 1
        s.flush()

    return {
        "ya_existian": len(existentes),
        "insertadas": insertadas,
        "defaults_usados": list(TIPOS_PROBLEMA),
    }


__all__ = (
    "listar",
    "listar_nombres",
    "obtener",
    "agregar",
    "renombrar",
    "eliminar",
    "reactivar",
    "contar_incidencias_que_usan",
    "migrar_desde_config",
)
