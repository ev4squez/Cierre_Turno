"""Servicio de auditoria del sistema.

Registra y consulta acciones del usuario para trazabilidad y
cumplimiento SCJ. Cada accion relevante (registrar FDS, editar,
eliminar, enviar informe, importar maquinas, etc.) deja una entrada
en la tabla ``auditoria`` con timestamp, tecnico, accion y detalle.

API principal:
  - ``registrar(accion, tecnico, objetivo_tipo, objetivo_id, detalle)``
  - ``listar_recientes(limit)``
  - ``listar_por_tecnico(tecnico, limit)``
  - ``listar_por_accion(accion, limit)``
  - ``contar_por_accion()`` (para reporteria: top acciones)
  - ``contar_por_tecnico()`` (para reporteria: actividad por tecnico)
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable

from sqlalchemy import func, select

from database.db import get_session
from database.models import Auditoria


def registrar(
    *,
    accion: str,
    tecnico: str,
    objetivo_tipo: str,
    objetivo_id: str,
    detalle: str = "",
) -> dict:
    """Inserta una entrada en el log de auditoria.

    Parametros
    ----------
    accion:
        Codigo de la accion (ej: 'registrar_incidencia',
        'editar_incidencia', 'eliminar_incidencia',
        'enviar_informe', 'importar_maquinas').
    tecnico:
        Nombre del tecnico que realizo la accion. Si esta vacio, se
        usa 'desconocido' para no bloquear el flujo.
    objetivo_tipo:
        'incidencia', 'maquina', 'tecnico', 'informe', etc.
    objetivo_id:
        ID o nombre del objeto afectado. Para Incidencia es el ID
        numerico, para Maquina es el numero de maquina, etc.
    detalle:
        Texto libre con info adicional.

    Retorna el dict de la entrada insertada.

    Nota: ``registrar`` es best-effort. Si la DB falla (ej: tabla no
    existe), captura el error y loguea pero NO rompe el flujo
    principal del operador. La auditoria nunca debe bloquear el trabajo.
    """
    if not tecnico:
        tecnico = "desconocido"
    try:
        with get_session() as s:
            entry = Auditoria(
                accion=accion,
                tecnico=tecnico,
                objetivo_tipo=objetivo_tipo,
                objetivo_id=str(objetivo_id),
                detalle=detalle or "",
            )
            s.add(entry)
            s.flush()
            return entry.to_dict()
    except Exception:
        # No propagamos el error: la auditoria es importante pero
        # no debe impedir que el operador cargue una FDS.
        # En el log del sistema queda registrado el fallo.
        import logging
        logging.getLogger(__name__).exception(
            "No se pudo escribir auditoria: accion=%s objetivo=%s:%s",
            accion, objetivo_tipo, objetivo_id,
        )
        return {
            "id": -1,
            "accion": accion,
            "tecnico": tecnico,
            "objetivo_tipo": objetivo_tipo,
            "objetivo_id": str(objetivo_id),
            "detalle": detalle or "",
            "timestamp": datetime.now().isoformat(),
            "error": "no persistido",
        }


def listar_recientes(limit: int = 100) -> list[dict]:
    """Devuelve las ultimas ``limit`` acciones, ordenadas por timestamp desc."""
    with get_session() as s:
        stmt = select(Auditoria).order_by(Auditoria.timestamp.desc()).limit(limit)
        return [a.to_dict() for a in s.scalars(stmt)]


def listar_por_tecnico(tecnico: str, limit: int = 50) -> list[dict]:
    """Acciones realizadas por un tecnico especifico."""
    with get_session() as s:
        stmt = (
            select(Auditoria)
            .where(Auditoria.tecnico == tecnico)
            .order_by(Auditoria.timestamp.desc())
            .limit(limit)
        )
        return [a.to_dict() for a in s.scalars(stmt)]


def listar_por_accion(accion: str, limit: int = 50) -> list[dict]:
    """Acciones de un tipo especifico (ej: todas las eliminaciones)."""
    with get_session() as s:
        stmt = (
            select(Auditoria)
            .where(Auditoria.accion == accion)
            .order_by(Auditoria.timestamp.desc())
            .limit(limit)
        )
        return [a.to_dict() for a in s.scalars(stmt)]


def listar_entre_fechas(desde: date, hasta: date,
                        limit: int = 500) -> list[dict]:
    """Acciones en un rango de fechas (inclusivo en desde, exclusivo en hasta+1)."""
    desde_dt = datetime.combine(desde, datetime.min.time())
    hasta_dt = datetime.combine(hasta + timedelta(days=1), datetime.min.time())
    with get_session() as s:
        stmt = (
            select(Auditoria)
            .where(Auditoria.timestamp >= desde_dt)
            .where(Auditoria.timestamp < hasta_dt)
            .order_by(Auditoria.timestamp.desc())
            .limit(limit)
        )
        return [a.to_dict() for a in s.scalars(stmt)]


def contar_por_accion() -> dict[str, int]:
    """Cuenta acciones agrupadas por tipo. Util para reporteria."""
    with get_session() as s:
        stmt = select(Auditoria.accion, func.count(Auditoria.id)).group_by(
            Auditoria.accion
        )
        return {accion: int(n) for accion, n in s.execute(stmt).all()}


def contar_por_tecnico() -> dict[str, int]:
    """Cuenta acciones agrupadas por tecnico. Util para reporteria."""
    with get_session() as s:
        stmt = select(Auditoria.tecnico, func.count(Auditoria.id)).group_by(
            Auditoria.tecnico
        )
        return {tecnico: int(n) for tecnico, n in s.execute(stmt).all()}


__all__ = (
    "registrar",
    "listar_recientes",
    "listar_por_tecnico",
    "listar_por_accion",
    "listar_entre_fechas",
    "contar_por_accion",
    "contar_por_tecnico",
)
