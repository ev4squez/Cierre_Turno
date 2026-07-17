"""Servicios de incidencias: registrar, listar turno, editar, eliminar.

Convenciones:

* ``fecha`` y ``hora`` se llenan al momento del registro (no las pasa
  el operador).
* Cada registro se guarda *inmediatamente* (no hay "guardar todo"),
  por eso ``registrar()`` hace commit en cada llamada.
* ``listar_turno(fecha, turno)`` devuelve los registros de la jornada
  para alimentar la tabla inferior de la UI y el informe final.
* ``resumen_turno(fecha, turno)`` agrega metricas para las tarjetas
  del correo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Iterable

from sqlalchemy import select

from config import ESTADOS_MAQUINA
from database.db import get_session
from database.models import Incidencia, Maquina


# ---------------------------------------------------------------------------
# Dataclass de retorno (para UI / reporte)
# ---------------------------------------------------------------------------


@dataclass
class ResumenTurno:
    """Conteos agregados de un turno para alimentar el informe."""

    fecha: date
    turno: str
    total: int = 0
    operativas: int = 0
    fds: int = 0
    pendientes_repuesto: int = 0
    en_observacion: int = 0
    espera_soporte: int = 0
    registros: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "fecha": self.fecha.isoformat(),
            "turno": self.turno,
            "total": self.total,
            "operativas": self.operativas,
            "fds": self.fds,
            "pendientes_repuesto": self.pendientes_repuesto,
            "en_observacion": self.en_observacion,
            "espera_soporte": self.espera_soporte,
            "registros": self.registros,
        }


# ---------------------------------------------------------------------------
# Registro
# ---------------------------------------------------------------------------


def registrar(
    *,
    numero_maquina: str,
    problema: str,
    motivo_fuera_servicio: str,
    accion_realizada: str = "",
    estado_final: str = "Fuera de Servicio",
    observaciones: str = "",
    tecnico: str,
    turno: str,
    usuario: str,
    fecha: date | None = None,
    hora: datetime | None = None,
    correo_enviado: bool = False,
) -> dict:
    """Registra una nueva incidencia y la persiste de inmediato.

    Parametros obligatorios: ``numero_maquina``, ``problema``,
    ``motivo_fuera_servicio``, ``tecnico``, ``turno``, ``usuario``.

    Si ``fecha``/``hora`` no se pasan, usa ``datetime.now()``.

    Retorna el dict serializado (incluye el id asignado).
    """
    if not numero_maquina or not str(numero_maquina).strip():
        raise ValueError("numero_maquina es obligatorio")
    if not problema or not problema.strip():
        raise ValueError("problema es obligatorio")
    if not motivo_fuera_servicio or not motivo_fuera_servicio.strip():
        raise ValueError("motivo_fuera_servicio es obligatorio")
    if not tecnico or not tecnico.strip():
        raise ValueError("tecnico es obligatorio")

    if estado_final not in ESTADOS_MAQUINA:
        estado_final = "Fuera de Servicio"

    ahora = hora or datetime.now()
    f = fecha or ahora.date()

    payload = dict(
        fecha=f,
        hora=ahora.time().replace(microsecond=0),
        numero_maquina=str(numero_maquina).strip(),
        problema=str(problema).strip(),
        motivo_fuera_servicio=str(motivo_fuera_servicio).strip(),
        accion_realizada=(accion_realizada or "").strip(),
        estado_final=estado_final,
        observaciones=(observaciones or "").strip(),
        tecnico=str(tecnico).strip(),
        correo_enviado=bool(correo_enviado),
        turno=str(turno or "").strip(),
        usuario=str(usuario or "").strip(),
    )

    with get_session() as s:
        # Si la maquina existe, sincronizamos su estado al estado_final
        maquina = s.scalars(
            select(Maquina).where(
                Maquina.numero_maquina == payload["numero_maquina"]
            )
        ).first()
        if maquina is not None:
            maquina.estado = estado_final

        inc = Incidencia(**payload)
        s.add(inc)
        s.flush()
        return inc.to_dict()


def editar(incidencia_id: int, cambios: dict) -> dict:
    """Edita campos de una incidencia existente."""
    campos_editables = {
        "problema", "motivo_fuera_servicio", "accion_realizada",
        "estado_final", "observaciones", "tecnico",
        "numero_maquina", "correo_enviado",
    }
    with get_session() as s:
        inc = s.get(Incidencia, incidencia_id)
        if inc is None:
            raise ValueError(f"Incidencia id={incidencia_id} no existe")
        nuevo_estado = cambios.get("estado_final")
        for k, v in (cambios or {}).items():
            if k not in campos_editables:
                continue
            if k == "estado_final" and v not in ESTADOS_MAQUINA:
                continue
            if isinstance(v, str):
                v = v.strip()
            setattr(inc, k, v)
        # Sincronizar el estado de la maquina asociada si cambio el estado_final
        if nuevo_estado and nuevo_estado in ESTADOS_MAQUINA:
            maquina = s.scalars(
                select(Maquina).where(
                    Maquina.numero_maquina == inc.numero_maquina
                )
            ).first()
            if maquina is not None:
                maquina.estado = nuevo_estado
        s.flush()
        return inc.to_dict()


def eliminar(incidencia_id: int) -> None:
    """Elimina una incidencia por id."""
    with get_session() as s:
        inc = s.get(Incidencia, incidencia_id)
        if inc is not None:
            s.delete(inc)


def obtener(incidencia_id: int) -> dict | None:
    """Devuelve una incidencia por id, o ``None``."""
    with get_session() as s:
        inc = s.get(Incidencia, incidencia_id)
        return inc.to_dict() if inc else None


# ---------------------------------------------------------------------------
# Listados y resumen
# ---------------------------------------------------------------------------


def listar_turno(fecha: date, turno: str) -> list[dict]:
    """Devuelve las incidencias de una jornada (fecha + turno).

    Ordenadas por hora ascendente.
    """
    with get_session() as s:
        stmt = (
            select(Incidencia)
            .where(Incidencia.fecha == fecha)
            .where(Incidencia.turno == turno)
            .order_by(Incidencia.hora.asc())
        )
        return [r.to_dict() for r in s.scalars(stmt)]


def listar_recientes(limit: int = 100) -> list[dict]:
    """Devuelve las ultimas ``limit`` incidencias registradas."""
    with get_session() as s:
        stmt = (
            select(Incidencia)
            .order_by(Incidencia.created_at.desc())
            .limit(limit)
        )
        return [r.to_dict() for r in s.scalars(stmt)]


def resumen_turno(fecha: date, turno: str) -> ResumenTurno:
    """Calcula el resumen agregado de un turno."""
    registros = listar_turno(fecha, turno)
    resumen = ResumenTurno(fecha=fecha, turno=turno, registros=registros)
    resumen.total = len(registros)

    for r in registros:
        e = r["estado_final"]
        if e == "Operativa":
            resumen.operativas += 1
        elif e == "Fuera de Servicio":
            resumen.fds += 1
        elif e == "Pendiente Repuesto":
            resumen.pendientes_repuesto += 1
        elif e == "Espera Servicio Tecnico":
            resumen.espera_soporte += 1
        elif e == "En Observacion":
            resumen.en_observacion += 1

    return resumen


def tiempo_promedio_resolucion_min(registros: list[dict]) -> int | None:
    """Calcula el tiempo promedio de resolucion real.

    Para cada incidencia Operativa del turno, resta ``updated_at - created_at``
    y devuelve el promedio en minutos. Devuelve ``None`` si no hay datos
    suficientes (sin Operativas, o sin timestamps).

    Parametros
    ----------
    registros:
        Lista de dicts de incidencias (los que devuelve ``listar_turno``
        enriquecidos con ``created_at`` y ``updated_at``).
    """
    from datetime import datetime

    tiempos: list[float] = []
    for r in registros:
        if r.get("estado_final") != "Operativa":
            continue
        ca = r.get("created_at")
        ua = r.get("updated_at")
        if not ca or not ua:
            continue
        # Si vienen como string ISO, parseamos
        if isinstance(ca, str):
            try:
                ca = datetime.fromisoformat(ca)
            except ValueError:
                continue
        if isinstance(ua, str):
            try:
                ua = datetime.fromisoformat(ua)
            except ValueError:
                continue
        diff = (ua - ca).total_seconds() / 60.0
        # Filtrar diffs negativos o absurdos (>24h)
        if 0 < diff < 1440:
            tiempos.append(diff)
    if not tiempos:
        return None
    return int(sum(tiempos) / len(tiempos))


def total_maquinas_catalogo(solo_activas: bool = True) -> int:
    """Cuenta el total de maquinas en el catalogo.

    Por defecto cuenta solo las activas (las que el operador ve en el
    buscador). Con ``solo_activas=False`` incluye la papelera.
    """
    from services import admin as svc_admin
    return len(svc_admin.listar_todas(incluir_inactivas=not solo_activas))


def marcar_correo_enviado(ids: Iterable[int]) -> int:
    """Marca un lote de incidencias como ``correo_enviado=True``.

    Retorna la cantidad efectivamente actualizada.
    """
    ids = list(ids)
    if not ids:
        return 0
    with get_session() as s:
        rows = s.scalars(select(Incidencia).where(Incidencia.id.in_(ids))).all()
        for r in rows:
            r.correo_enviado = True
        s.flush()
        return len(rows)


__all__: Iterable[str] = (
    "registrar",
    "editar",
    "eliminar",
    "obtener",
    "listar_turno",
    "listar_recientes",
    "resumen_turno",
    "marcar_correo_enviado",
    "ResumenTurno",
)