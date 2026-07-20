"""Widget de observacion con plantillas + texto libre.

El operador elige de una lista de plantillas predefinidas (chips
seleccionables) y puede agregar texto libre al final. Esto sirve
para reporteria: el area de cumplimiento puede agrupar/filtrar
por tipo de observacion (ej: 'Sin repuesto', 'Cliente informado').

Si el operador elige "Otro", se muestra el campo de texto libre.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


# Plantillas canonicas. Si el operador quiere mas, las puede
# agregar via Settings (TODO). Por ahora son las que el casino
# usa segun tu memoria.
PLANTILLAS_OBS: tuple[str, ...] = (
    "Sin repuesto",
    "En garantia",
    "Cliente informado",
    "Esperando tecnico externo",
    "Requiere limpieza",
    "Documentacion al dia",
    "Otro",
)


class ObservacionWidget(QFrame):
    """Combo de plantillas + campo de texto libre.

    Signals
    -------
    changed(str): emite el texto completo (plantillas + nota libre).
    """

    changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected: list[str] = []
        self._otro_text: str = ""
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Chips de seleccion multiple
        chips_row = QFrame()
        chips_layout = QHBoxLayout(chips_row)
        chips_layout.setContentsMargins(0, 0, 0, 0)
        chips_layout.setSpacing(4)
        chips_layout.addStretch(1)
        self._chip_btns: dict[str, QFrame] = {}
        for plantilla in PLANTILLAS_OBS:
            btn = self._make_chip(plantilla)
            chips_layout.addWidget(btn)
            self._chip_btns[plantilla] = btn
        layout.addWidget(chips_row)

        # Campo de texto libre (siempre visible para que el operador
        # pueda agregar nota ademas de las plantillas)
        self._free_text = QPlainTextEdit()
        self._free_text.setPlaceholderText(
            "Nota adicional (opcional). Si elegiste 'Otro', "
            "describe aca."
        )
        self._free_text.setFixedHeight(60)
        self._free_text.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._free_text)

    def _make_chip(self, plantilla: str) -> QFrame:
        """Crea un chip clickeable con estado toggle."""
        from PySide6.QtWidgets import QPushButton
        btn = QPushButton(plantilla)
        btn.setCheckable(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setObjectName("obsChip")
        # Estilo depende del estado selected/no
        btn.toggled.connect(lambda checked, p=plantilla: self._on_chip_toggled(p, checked))
        return btn

    def _on_chip_toggled(self, plantilla: str, checked: bool) -> None:
        if checked and plantilla not in self._selected:
            self._selected.append(plantilla)
        elif not checked and plantilla in self._selected:
            self._selected.remove(plantilla)
        self._emit_text()

    def _on_text_changed(self) -> None:
        self._emit_text()

    def _emit_text(self) -> None:
        """Combina plantillas + texto libre en una sola string."""
        partes = list(self._selected)
        libre = self._free_text.toPlainText().strip()
        if libre:
            partes.append(libre)
        # Formato: "Sin repuesto | Cliente informado | nota libre"
        texto = " | ".join(partes)
        self.changed.emit(texto)

    def get_text(self) -> str:
        partes = list(self._selected)
        libre = self._free_text.toPlainText().strip()
        if libre:
            partes.append(libre)
        return " | ".join(partes)

    def set_text(self, texto: str) -> None:
        """Reconstruye el estado desde una string previamente serializada.

        Formato esperado: 'plantilla1 | plantilla2 | nota libre'.
        Si una plantilla no esta en PLANTILLAS_OBS, va al texto libre.
        """
        self._selected.clear()
        self._free_text.clear()
        if not texto:
            return
        for parte in (p.strip() for p in texto.split("|")):
            if not parte:
                continue
            if parte in PLANTILLAS_OBS:
                self._selected.append(parte)
                btn = self._chip_btns.get(parte)
                if btn is not None:
                    btn.blockSignals(True)
                    btn.setChecked(True)
                    btn.blockSignals(False)
            else:
                # Texto libre (puede tener varias partes separadas)
                actual = self._free_text.toPlainText()
                self._free_text.setPlainText(
                    (actual + "\n" + parte).strip() if actual else parte
                )


__all__ = ("ObservacionWidget", "PLANTILLAS_OBS")
