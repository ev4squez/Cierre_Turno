"""Modelo ``Incidencia``.

Una fila por cada registro de FDS realizado por un tecnico durante
la jornada. Se almacena inmediatamente (no hay "guardar todo"), por
eso la fecha/hora se llenan al crear el registro.

La asociacion con ``Maquina`` es por ``numero_maquina`` (string) y no
por FK, para soportar maquinas reportadas sin estar en el catalogo.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, Index, Integer, String, Text, Time, func
from sqlalchemy.orm import Mapped, mapped_column

from database.db import Base

if TYPE_CHECKING:
    pass


class Incidencia(Base):
    """Registro de una incidencia / FDS durante la jornada."""

    __tablename__ = "incidencias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fecha: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    hora: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    numero_maquina: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    problema: Mapped[str] = mapped_column(String(128), nullable=False)
    motivo_fuera_servicio: Mapped[str] = mapped_column(Text, nullable=False)
    accion_realizada: Mapped[str] = mapped_column(Text, nullable=False, default="")
    estado_final: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Fuera de Servicio", index=True
    )
    observaciones: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tecnico: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    correo_enviado: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )

    # Turno + usuario que registro (para identificar la jornada)
    turno: Mapped[str] = mapped_column(String(32), nullable=False, default="", index=True)
    usuario: Mapped[str] = mapped_column(String(96), nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_incid_fecha_turno", "fecha", "turno"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug
        return (
            f"<Incidencia #{self.id} {self.fecha} {self.hora} "
            f"maq={self.numero_maquina!r} estado={self.estado_final!r}>"
        )

    def to_dict(self) -> dict:
        """Serializa para usar en UI / reporte / JSON."""
        return {
            "id": self.id,
            "fecha": self.fecha.isoformat() if self.fecha else None,
            "hora": self.hora.strftime("%H:%M") if self.hora else None,
            "numero_maquina": self.numero_maquina,
            "problema": self.problema,
            "motivo_fuera_servicio": self.motivo_fuera_servicio,
            "accion_realizada": self.accion_realizada,
            "estado_final": self.estado_final,
            "observaciones": self.observaciones,
            "tecnico": self.tecnico,
            "correo_enviado": self.correo_enviado,
            "turno": self.turno,
            "usuario": self.usuario,
        }