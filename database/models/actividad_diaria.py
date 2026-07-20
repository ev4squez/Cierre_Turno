"""Modelo ``ActividadDiaria``.

Registro de una tarea / actividad del tecnico durante la jornada.
Distinto de ``Incidencia`` (que modela FDS de maquinas): una
ActividadDiaria es cualquier cosa que el tecnico hizo, no
necesariamente una salida de servicio.

Campos:
  - id: PK
  - fecha / hora / turno: cuando se registro
  - tarea: nombre de la tarea (FK logica a tipos_actividad.nombre)
  - area: sector del casino (Slots, Mesas, Caja, etc)
  - numero_maquina: OPCIONAL. Si la tarea es para una maquina especifica
    se guarda el numero; si es general del area queda vacio.
  - detalle: descripcion larga en lenguaje libre (obligatorio)
  - isla: sub-ubicacion dentro del area (opcional)
  - ticket_jira_sn: bool, 'si' / 'no' (la columna en el Excel era asi)
  - numero_ticket_jira: str opcional, habilitado solo si ticket_jira_sn
  - pendiente_sn: bool, 'si' / 'no' - queda como tarea abierta?
  - tecnico: quien la registro
  - usuario: usuario del sistema (auditoria)
  - timestamps

La asociacion con ``Maquina`` y ``TipoActividad`` es por string (no FK)
para soportar maquinas reportadas sin estar en el catalogo y tipos
soft-deleted. Mismo patron que ``Incidencia``.
"""

from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from database.db import Base


class ActividadDiaria(Base):
    """Registro de una actividad / tarea del tecnico durante la jornada."""

    __tablename__ = "actividades_diarias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    hora: Mapped[time] = mapped_column(Time, nullable=False)

    tarea: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    area: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    numero_maquina: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", index=True,
    )
    detalle: Mapped[str] = mapped_column(Text, nullable=False)
    isla: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    ticket_jira_sn: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
    )
    numero_ticket_jira: Mapped[str] = mapped_column(
        String(64), nullable=False, default="",
    )
    pendiente_sn: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True,
    )

    tecnico: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    turno: Mapped[str] = mapped_column(String(32), nullable=False, default="", index=True)
    usuario: Mapped[str] = mapped_column(String(96), nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_actividad_fecha_turno", "fecha", "turno"),
        Index("ix_actividad_tecnico_fecha", "tecnico", "fecha"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug
        return (
            f"<ActividadDiaria #{self.id} {self.fecha} {self.hora} "
            f"tarea={self.tarea!r} tecnico={self.tecnico!r}>"
        )

    def to_dict(self) -> dict:
        """Serializa para usar en UI / reporte / Excel."""
        return {
            "id": self.id,
            "fecha": self.fecha.isoformat() if self.fecha else None,
            "hora": self.hora.strftime("%H:%M:%S") if self.hora else None,
            "tarea": self.tarea,
            "area": self.area,
            "numero_maquina": self.numero_maquina,
            "detalle": self.detalle,
            "isla": self.isla,
            "ticket_jira_sn": self.ticket_jira_sn,
            "numero_ticket_jira": self.numero_ticket_jira,
            "pendiente_sn": self.pendiente_sn,
            "tecnico": self.tecnico,
            "turno": self.turno,
            "usuario": self.usuario,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
