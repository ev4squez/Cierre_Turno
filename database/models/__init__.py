"""Modelos ORM del Sistema FDS.

Re-exporta ``Maquina``, ``Incidencia``, ``Tecnico``, ``TipoProblema``,
``Auditoria`` y ``BorradorIncidencia`` para que ``database.db.init_db``
los encuentre via ``from database import models``.
"""

from __future__ import annotations

from .auditoria import Auditoria
from .borrador_incidencia import BorradorIncidencia
from .incidencia import Incidencia
from .maquina import Maquina
from .tecnico import Tecnico
from .tipo_problema import TipoProblema

__all__ = [
    "Maquina", "Incidencia", "Tecnico", "TipoProblema",
    "Auditoria", "BorradorIncidencia",
]