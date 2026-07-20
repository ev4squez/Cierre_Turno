"""Modelo ``BorradorIncidencia``.

Un borrador es el estado parcial de un form de FDS que el operador
empiezo a llenar pero no confirmo. Se persiste en la DB mientras el
operador escribe (autosave), asi si la app se cierra / crashea / el
operador se olvida de 'Guardar Registro', el borrador queda y se le
ofrece restaurar al volver a abrir la misma maquina.

Estructura: una sola fila en ``borradores_incidencia`` por
(maquina_numero, tecnico). Cuando se confirma el 'Guardar Registro'
real, el borrador se borra.

Si el operador abre una maquina distinta, ve el borrador de ESA
maquina. Si no hay borrador, el form arranca vacio (igual que antes).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from database.db import Base


class BorradorIncidencia(Base):
    """Borrador de una incidencia en proceso (autosave)."""

    __tablename__ = "borradores_incidencia"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    maquina_numero: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True,
    )
    tecnico: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True,
    )
    problema: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    motivo_fuera_servicio: Mapped[str] = mapped_column(
        Text, nullable=False, default="",
    )
    accion_realizada: Mapped[str] = mapped_column(
        Text, nullable=False, default="",
    )
    estado_final: Mapped[str] = mapped_column(
        String(64), nullable=False, default="",
    )
    observaciones: Mapped[str] = mapped_column(
        Text, nullable=False, default="",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<BorradorIncidencia #{self.id} "
            f"maquina={self.maquina_numero!r} tecnico={self.tecnico!r}>"
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "maquina_numero": self.maquina_numero,
            "tecnico": self.tecnico,
            "problema": self.problema,
            "motivo_fuera_servicio": self.motivo_fuera_servicio,
            "accion_realizada": self.accion_realizada,
            "estado_final": self.estado_final,
            "observaciones": self.observaciones,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
