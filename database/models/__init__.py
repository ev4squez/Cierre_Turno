"""Modelos ORM del Sistema FDS.

Re-exporta ``Maquina``, ``Incidencia`` y ``TipoProblema`` para que
``database.db.init_db`` los encuentre via ``from database import models``.
"""

from __future__ import annotations

from .incidencia import Incidencia
from .maquina import Maquina
from .tecnico import Tecnico
from .tipo_problema import TipoProblema

__all__ = ["Maquina", "Incidencia", "Tecnico", "TipoProblema"]