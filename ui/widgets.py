"""Widgets reutilizables para los dialogos de Settings."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class EditableListWidget(QFrame):
    """Lista vertical con input + botones agregar/quitar/renombrar.

    Signals
    -------
    changed: emite la lista actualizada como ``list[str]`` cada vez
             que el operador la modifica.
    """

    changed = Signal(list)

    def __init__(
        self,
        *,
        titulo: str,
        placeholder: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("class", "panel")
        self._items: list[str] = []
        self._placeholder = placeholder

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        head = QLabel(titulo)
        head.setProperty("class", "formLabel")
        root.addWidget(head)

        self._lista = QListWidget()
        self._lista.setAlternatingRowColors(True)
        self._lista.itemDoubleClicked.connect(self._on_rename)
        root.addWidget(self._lista, 1)

        # Input + botones
        row = QFrame()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(6)
        self._input = QLineEdit()
        self._input.setPlaceholderText(placeholder or "Escribi y presiona Enter...")
        self._input.returnPressed.connect(self._on_add)
        rl.addWidget(self._input, 1)
        btn_add = QPushButton("Agregar")
        btn_add.setObjectName("btnPrimary")
        btn_add.clicked.connect(self._on_add)
        rl.addWidget(btn_add)
        root.addWidget(row)

        # Botones de la lista
        row2 = QFrame()
        r2 = QHBoxLayout(row2)
        r2.setContentsMargins(0, 0, 0, 0)
        r2.setSpacing(6)
        btn_rename = QPushButton("Renombrar seleccionado")
        btn_rename.setObjectName("btnSecondary")
        btn_rename.clicked.connect(self._on_rename)
        btn_del = QPushButton("Quitar seleccionado")
        btn_del.setObjectName("btnDangerGhost")
        btn_del.clicked.connect(self._on_remove)
        r2.addWidget(btn_rename)
        r2.addWidget(btn_del)
        r2.addStretch(1)
        root.addWidget(row2)

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------

    def set_items(self, items: Iterable[str]) -> None:
        """Reemplaza todos los items de la lista."""
        self._items = list(items)
        self._refrescar()

    def get_items(self) -> list[str]:
        """Devuelve la lista actual de strings (copia)."""
        return list(self._items)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _on_add(self) -> None:
        texto = self._input.text().strip()
        if not texto:
            return
        # Evitar duplicados case-insensitive
        if any(t.lower() == texto.lower() for t in self._items):
            QMessageBox.information(
                self, "Duplicado", f"'{texto}' ya esta en la lista."
            )
            return
        self._items.append(texto)
        self._input.clear()
        self._refrescar()
        self.changed.emit(self.get_items())

    def _on_remove(self) -> None:
        row = self._lista.currentRow()
        if row < 0 or row >= len(self._items):
            return
        del self._items[row]
        self._refrescar()
        self.changed.emit(self.get_items())

    def _on_rename(self) -> None:
        item = self._lista.currentItem()
        if item is None:
            return
        viejo = item.text()
        from PySide6.QtWidgets import QInputDialog
        nuevo, ok = QInputDialog.getText(
            self,
            "Renombrar",
            "Nuevo nombre:",
            text=viejo,
        )
        if not ok or not nuevo.strip():
            return
        nuevo = nuevo.strip()
        if nuevo == viejo:
            return
        # Evitar duplicado
        if any(t.lower() == nuevo.lower() for t in self._items if t != viejo):
            QMessageBox.information(
                self, "Duplicado", f"'{nuevo}' ya esta en la lista."
            )
            return
        idx = self._items.index(viejo)
        self._items[idx] = nuevo
        self._refrescar()
        self.changed.emit(self.get_items())

    def _refrescar(self) -> None:
        self._lista.clear()
        for it in self._items:
            QListWidgetItem(it, self._lista)


__all__ = ("EditableListWidget",)