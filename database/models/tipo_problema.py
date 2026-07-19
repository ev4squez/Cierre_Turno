"""Modelo ``TipoProblema``.

Categorias que el operador elige en el combo 'Tipo de problema' del
formulario de registro de FDS.

Vive en la DB (no en config.py como antes) para que el operador
pueda agregar / editar / eliminar tipos desde Settings sin reiniciar
la app. La migracion desde el tuple ``config.TIPOS_PROBLEMA`` se
hace la primera vez (ver ``services.tipos_problema_db.migrar_desde_config``).

Campos:
  - id: PK
  - nombre: nombre visible del tipo (UNIQUE, case-insensitive en la app)
  - activo: soft-delete (papelera). Por defecto True.
  - timestamps de auditoria
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from database.db import Base


class TipoProblema(Base):
    """Tipos de problema seleccionables en el formulario de FDS."""

    __tablename__ = "tipos_problema"

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
        return f"<TipoProblema #{self.id} nombre={self.nombre!r}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nombre": self.nombre,
            "activo": self.activo,
        }
