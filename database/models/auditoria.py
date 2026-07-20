"""Modelo ``Auditoria``.

Registra todas las acciones relevantes del sistema para trazabilidad:

  - 'registrar_incidencia': el operador cargo una FDS en una maquina
  - 'editar_incidencia':    el operador edito una FDS existente
  - 'eliminar_incidencia':  el operador elimino una FDS
  - 'enviar_informe':       se mando el informe diario por Outlook
  - 'importar_maquinas':    se importaron maquinas desde Excel
  - 'agregar_tecnico':      se agrego un tecnico a la DB
  - 'eliminar_tecnico':     se elimino un tecnico (soft-delete)

Cada entrada incluye timestamp, tecnico que realizo la accion,
objeto afectado (incidencia_id / maquina_numero / tecnico_nombre),
y un campo ``detalle`` libre con info adicional (ej: campos modificados).

Para reporteria / cumplimiento SCJ: SELECT * FROM auditoria
WHERE fecha BETWEEN ? ORDER BY timestamp DESC da el log completo.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from database.db import Base


class Auditoria(Base):
    """Log de acciones del sistema para trazabilidad y cumplimiento."""

    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Accion realizada: 'registrar_incidencia', 'editar_incidencia', etc.
    accion: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Tecnico que realizo la accion (libre, sin FK porque puede ser soft-deleted)
    tecnico: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    # Objeto afectado: "incidencia:123", "maquina:1023", "tecnico:Juan Perez"
    objetivo_tipo: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    objetivo_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    # Detalle libre (texto). Para 'editar_incidencia' puede incluir diff;
    # para 'enviar_informe' puede incluir destinatarios y archivos generados.
    detalle: Mapped[str] = mapped_column(Text, nullable=False, default="")
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False, index=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Auditoria #{self.id} {self.accion} "
            f"tecnico={self.tecnico!r} objetivo={self.objeto!r}>"
        )

    @property
    def objeto(self) -> str:
        return f"{self.objetivo_tipo}:{self.objetivo_id}"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "accion": self.accion,
            "tecnico": self.tecnico,
            "objetivo_tipo": self.objetivo_tipo,
            "objetivo_id": self.objetivo_id,
            "detalle": self.detalle,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
