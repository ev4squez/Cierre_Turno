"""Modelos ORM del Sistema FDS.

Re-exporta ``Maquina`` e ``Incidencia`` para que ``database.db.init_db``
los encuentre via ``from database import models``.
"""

from __future__ import annotations

from .incidencia import Incidencia
from .maquina import Maquina

__all__ = ["Maquina", "Incidencia"]