"""Historial del buscador de maquinas.

Guarda las ultimas N busquedas del operador en un archivo JSON en
la carpeta de configuracion (persistente entre sesiones). Cuando el
operador enfoca el buscador, un QCompleter le sugiere las busquedas
previas ademas de las maquinas que coincidan.

Pensado para que el operador que tipea "1045" seguido pueda elegirlo
sin tener que recordar el codigo completo: el historial muestra las
N ultimas consultas exitosas.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QObject, QStringListModel, Qt, Signal
from PySide6.QtWidgets import QCompleter

from config import BASE_DIR


HISTORY_FILE: str = "search_history.json"
MAX_HISTORY: int = 10


class SearchHistory(QObject):
    """Historial persistente de busquedas del buscador de maquinas.

    Persiste en ``DATA_DIR/search_history.json``. Mantiene solo las
    ultimas ``MAX_HISTORY`` entradas, deduplicadas case-insensitive.

    Signals
    -------
    changed: emite cuando se agrega o limpia una entrada.
    """

    changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._entries: list[str] = []
        self._path = BASE_DIR / "data" / HISTORY_FILE
        self._cargar()

    def _cargar(self) -> None:
        try:
            if self._path.exists():
                self._entries = json.loads(
                    self._path.read_text(encoding="utf-8")
                )[:MAX_HISTORY]
        except Exception:
            self._entries = []

    def _persistir(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._entries, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass  # best-effort

    def agregar(self, query: str) -> None:
        """Agrega una busqueda al historial. Deduplica case-insensitive."""
        q = query.strip()
        if not q:
            return
        # Saco duplicados case-insensitive
        self._entries = [
            e for e in self._entries if e.lower() != q.lower()
        ]
        # Inserto al inicio
        self._entries.insert(0, q)
        # Trunco al maximo
        self._entries = self._entries[:MAX_HISTORY]
        self._persistir()
        self.changed.emit()

    def limpiar(self) -> None:
        """Borra todo el historial."""
        self._entries = []
        self._persistir()
        self.changed.emit()

    def entries(self) -> list[str]:
        return list(self._entries)

    def install_completer(self, line_edit) -> None:
        """Instala un QCompleter en un QLineEdit con el historial actual."""
        completer = QCompleter(self.entries(), line_edit)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        line_edit.setCompleter(completer)


__all__ = ("SearchHistory",)
