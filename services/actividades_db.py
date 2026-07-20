"""Servicios de Actividades Diarias: alta, listado, edicion, borrado.

Convenciones (mismo patron que ``services.incidencias``):
  - ``fecha`` y ``hora`` se llenan al momento del registro.
  - Cada actividad se guarda inmediatamente (no hay "guardar todo").
  - ``numero_maquina`` es OPCIONAL: si la tarea es general del area
    (ej: "Asistencia Slot" sin numero) se guarda vacio.
  - Listados: por turno, por rango, recientes.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Iterable

from sqlalchemy import select

from config import AREAS
from database.db import get_session
from database.models import ActividadDiaria


# ---------------------------------------------------------------------------
# Registro
# ---------------------------------------------------------------------------


def registrar(
    *,
    tarea: str,
    area: str,
    detalle: str,
    numero_maquina: str = "",
    isla: str = "",
    ticket_jira_sn: bool = False,
    numero_ticket_jira: str = "",
    pendiente_sn: bool = False,
    tecnico: str,
    turno: str,
    usuario: str,
    fecha: date | None = None,
    hora: datetime | None = None,
) -> dict:
    """Registra una nueva actividad y la persiste de inmediato.

    Parametros obligatorios: ``tarea``, ``area``, ``detalle``,
    ``tecnico``, ``turno``, ``usuario``. ``numero_maquina``, ``isla`` y
    ``numero_ticket_jira`` son opcionales.

    Si ``fecha``/``hora`` no se pasan, usa ``datetime.now()``.

    Retorna el dict serializado (incluye el id asignado).
    """
    if not tarea or not str(tarea).strip():
        raise ValueError("tarea es obligatorio")
    if not area or not str(area).strip():
        raise ValueError("area es obligatorio")
    if not detalle or not str(detalle).strip():
        raise ValueError("detalle es obligatorio")
    if not tecnico or not tecnico.strip():
        raise ValueError("tecnico es obligatorio")

    # Normalizamos area a las del enum (si llega una que no esta, la
    # aceptamos igual - el operador podria haber editado el combo).
    if area and area not in AREAS:
        # No bloqueamos, solo logueamos via el value en el dict.
        pass

    # Si dice que NO tiene ticket Jira, limpiamos el numero.
    if not ticket_jira_sn:
        numero_ticket_jira = ""

    ahora = hora or datetime.now()
    f = fecha or ahora.date()

    payload = dict(
        fecha=f,
        hora=ahora.time().replace(microsecond=0),
        tarea=str(tarea).strip(),
        area=str(area).strip(),
        numero_maquina=str(numero_maquina or "").strip(),
        detalle=str(detalle).strip(),
        isla=str(isla or "").strip(),
        ticket_jira_sn=bool(ticket_jira_sn),
        numero_ticket_jira=str(numero_ticket_jira or "").strip(),
        pendiente_sn=bool(pendiente_sn),
        tecnico=str(tecnico).strip(),
        turno=str(turno or "").strip(),
        usuario=str(usuario or "").strip(),
    )

    with get_session() as s:
        a = ActividadDiaria(**payload)
        s.add(a)
        s.flush()
        return a.to_dict()


def editar(actividad_id: int, cambios: dict) -> dict:
    """Edita campos de una actividad existente.

    Campos editables: tarea, area, numero_maquina, detalle, isla,
    ticket_jira_sn, numero_ticket_jira, pendiente_sn, tecnico, turno.
    NO se editan fecha/hora/usuario (auditoria).
    """
    campos_editables = {
        "tarea", "area", "numero_maquina", "detalle", "isla",
        "ticket_jira_sn", "numero_ticket_jira", "pendiente_sn",
        "tecnico", "turno",
    }
    with get_session() as s:
        a = s.get(ActividadDiaria, actividad_id)
        if a is None:
            raise ValueError(f"Actividad id={actividad_id} no existe")
        for k, v in (cambios or {}).items():
            if k not in campos_editables:
                continue
            if isinstance(v, str):
                v = v.strip()
            setattr(a, k, v)
        # Si desmarco ticket Jira, limpiamos el numero
        if a.ticket_jira_sn is False:
            a.numero_ticket_jira = ""
        s.flush()
        return a.to_dict()


def eliminar(actividad_id: int) -> None:
    """Elimina una actividad por id."""
    with get_session() as s:
        a = s.get(ActividadDiaria, actividad_id)
        if a is not None:
            s.delete(a)


def obtener(actividad_id: int) -> dict | None:
    """Devuelve una actividad por id, o ``None``."""
    with get_session() as s:
        a = s.get(ActividadDiaria, actividad_id)
        return a.to_dict() if a else None


# ---------------------------------------------------------------------------
# Listados
# ---------------------------------------------------------------------------


def listar_por_turno(fecha: date, turno: str) -> list[dict]:
    """Devuelve las actividades de una jornada (fecha + turno).

    Ordenadas por hora ascendente.
    """
    with get_session() as s:
        stmt = (
            select(ActividadDiaria)
            .where(ActividadDiaria.fecha == fecha)
            .where(ActividadDiaria.turno == turno)
            .order_by(ActividadDiaria.hora.asc())
        )
        return [r.to_dict() for r in s.scalars(stmt)]


def listar_por_rango(
    fecha_desde: date,
    fecha_hasta: date,
    *,
    tecnico: str | None = None,
    tarea: str | None = None,
    area: str | None = None,
    pendiente_solo: bool = False,
) -> list[dict]:
    """Devuelve las actividades en un rango de fechas, con filtros opcionales.

    Filtros (todos opcionales, se aplican AND):
      - tecnico: nombre exacto (case-sensitive). None = todos.
      - tarea: nombre exacto. None = todas.
      - area: nombre exacto. None = todas.
      - pendiente_solo: True = solo las que tienen pendiente_sn=True.

    Orden: fecha desc, hora desc (mas recientes primero - util para
    la tabla y para el export a Excel cronologico inverso).
    """
    with get_session() as s:
        stmt = (
            select(ActividadDiaria)
            .where(ActividadDiaria.fecha >= fecha_desde)
            .where(ActividadDiaria.fecha <= fecha_hasta)
        )
        if tecnico:
            stmt = stmt.where(ActividadDiaria.tecnico == tecnico)
        if tarea:
            stmt = stmt.where(ActividadDiaria.tarea == tarea)
        if area:
            stmt = stmt.where(ActividadDiaria.area == area)
        if pendiente_solo:
            stmt = stmt.where(ActividadDiaria.pendiente_sn.is_(True))
        stmt = stmt.order_by(
            ActividadDiaria.fecha.desc(),
            ActividadDiaria.hora.desc(),
        )
        return [r.to_dict() for r in s.scalars(stmt)]


def listar_recientes(limit: int = 100) -> list[dict]:
    """Devuelve las ultimas ``limit`` actividades registradas."""
    with get_session() as s:
        stmt = (
            select(ActividadDiaria)
            .order_by(ActividadDiaria.created_at.desc())
            .limit(limit)
        )
        return [r.to_dict() for r in s.scalars(stmt)]


def contar_pendientes(fecha_desde: date | None = None,
                      fecha_hasta: date | None = None) -> int:
    """Cuenta actividades marcadas como pendientes (sn=True).

    Si no se pasan fechas, cuenta todas. Util para el dashboard.
    """
    with get_session() as s:
        stmt = select(ActividadDiaria).where(
            ActividadDiaria.pendiente_sn.is_(True)
        )
        if fecha_desde is not None:
            stmt = stmt.where(ActividadDiaria.fecha >= fecha_desde)
        if fecha_hasta is not None:
            stmt = stmt.where(ActividadDiaria.fecha <= fecha_hasta)
        return len(s.scalars(stmt).all())


__all__ = (
    "registrar",
    "editar",
    "eliminar",
    "obtener",
    "listar_por_turno",
    "listar_por_rango",
    "listar_recientes",
    "contar_pendientes",
)
