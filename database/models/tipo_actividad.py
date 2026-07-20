"""Modelo ``TipoActividad``.

Categorias que el tecnico elige en el combo 'Tarea' del modulo
'Registro de Actividades Diarias'. Replica el patron de
``TipoProblema``: vive en la DB (no en config.py) para que el operador
pueda agregar / editar / eliminar tareas desde Settings sin reiniciar
la app. La migracion desde ``config.TIPOS_ACTIVIDAD`` se hace la
primera vez (ver ``services.tipos_actividad_db.migrar_desde_config``).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from database.db import Base


class TipoActividad(Base):
    """Tipos de actividad seleccionables en el registro de tareas."""

    __tablename__ = "tipos_actividad"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True,
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TipoActividad #{self.id} nombre={self.nombre!r}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nombre": self.nombre,
            "activo": self.activo,
        }
