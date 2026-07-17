"""Modelo ``Maquina``.

Representa una maquina tragamonica del casino. Es la entidad estable
del sistema; las ``Incidencia`` se asocian a una maquina por
``numero_maquina`` (string, tal cual figura en el casino) en vez de por
FK, para soportar maquinas que aun no estan cargadas en el catalogo.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from database.db import Base

if TYPE_CHECKING:
    pass


class Maquina(Base):
    """Catalogo de maquinas del casino."""

    __tablename__ = "maquinas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    numero_maquina: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    sector: Mapped[str | None] = mapped_column(String(64), nullable=True)
    isla: Mapped[str | None] = mapped_column(String(64), nullable=True)
    marca: Mapped[str | None] = mapped_column(String(64), nullable=True)
    modelo: Mapped[str | None] = mapped_column(String(64), nullable=True)
    serie: Mapped[str | None] = mapped_column(String(64), nullable=True)
    denominacion: Mapped[str | None] = mapped_column(String(32), nullable=True)
    estado: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Operativa", index=True
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover - utilidad de debug
        return (
            f"<Maquina #{self.id} num={self.numero_maquina!r} "
            f"marca={self.marca!r} estado={self.estado!r}>"
        )

    def to_dict(self) -> dict:
        """Serializa para usar en UI / JSON."""
        return {
            "id": self.id,
            "numero_maquina": self.numero_maquina,
            "sector": self.sector or "",
            "isla": self.isla or "",
            "marca": self.marca or "",
            "modelo": self.modelo or "",
            "serie": self.serie or "",
            "denominacion": self.denominacion or "",
            "estado": self.estado,
            "activo": self.activo,
        }