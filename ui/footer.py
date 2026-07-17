"""Footer con totales + boton Enviar Informe."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from ui.helpers import svg


class Footer(QFrame):
    """Pie con totales y boton de envio."""

    enviarInforme = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("footer")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(68)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(28)

        self._total = self._stat("TOTAL DE INCIDENCIAS", "0")
        layout.addWidget(self._total["host"])
        layout.addWidget(self._divider())
        self._maquinas = self._stat("MAQUINAS REGISTRADAS", "0")
        layout.addWidget(self._maquinas["host"])
        layout.addWidget(self._divider())
        self._inicio = self._stat("HORA DE INICIO DEL TURNO", "14:00")
        layout.addWidget(self._inicio["host"])
        layout.addWidget(self._divider())
        self._pendientes = self._stat("PENDIENTES", "0", accent=True)
        layout.addWidget(self._pendientes["host"])

        layout.addItem(QSpacerItem(20, 1, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self._btn = QPushButton("  Enviar Informe por Outlook")
        self._btn.setObjectName("btnReport")
        self._btn.setIcon(svg("mail", 17))
        self._btn.setCursor(Qt.PointingHandCursor)
        self._btn.clicked.connect(self.enviarInforme.emit)
        layout.addWidget(self._btn)

    def _stat(self, label: str, value: str, *, accent: bool = False) -> dict:
        host = QFrame()
        v = QVBoxLayout(host)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        l = QLabel(label)
        l.setProperty("class", "fsLabel")
        val = QLabel(value)
        val.setProperty("class", "fsValue")
        val.setProperty("accent", "true" if accent else "false")
        v.addWidget(l)
        v.addWidget(val)
        return {"host": host, "value": val}

    def _divider(self) -> QWidget:
        d = QFrame()
        d.setProperty("class", "footDivider")
        d.setFixedSize(1, 32)
        return d

    # --- API --------------------------------------------------------------

    def set_totales(self, *, total: int, maquinas: int, pendientes: int) -> None:
        self._total["value"].setText(str(total))
        self._maquinas["value"].setText(str(maquinas))
        self._pendientes["value"].setText(str(pendientes))

    def set_inicio_turno(self, hora: str) -> None:
        self._inicio["value"].setText(hora)

    def set_enviando(self, on: bool) -> None:
        self._btn.setEnabled(not on)
        self._btn.setText("  Enviando..." if on else "  Enviar Informe por Outlook")


__all__ = ("Footer",)