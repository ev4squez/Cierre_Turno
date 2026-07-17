"""Modelo ``Tecnico``.

Vive en la DB (no en config.json como antes). Razon: el operador que
usa el sistema puede cambiar su nombre y el topbar tiene que reflejar
el cambio en vivo, no solo al reiniciar la app.

Campos:
  - id: PK
  - nombre: nombre completo del tecnico (UNIQUE)
  - email: opcional, para usarlo despues en el informe
  - activo: soft-delete (papelera). Por defecto True.
  - es_usuario_actual: marca al tecnico que esta operando el sistema
    en esta maquina. Solo uno puede tener este flag = True.
  - timestamps de auditoria
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from database.db import Base


class Tecnico(Base):
    """Tecnicos disponibles para registrar FDS."""

    __tablename__ = "tecnicos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(128), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    es_usuario_actual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Tecnico #{self.id} nombre={self.nombre!r} actual={self.es_usuario_actual}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nombre": self.nombre,
            "email": self.email or "",
            "activo": self.activo,
            "es_usuario_actual": self.es_usuario_actual,
        }