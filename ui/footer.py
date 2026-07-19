"""Footer con stats del catalogo + boton Enviar Informe.

Layout limpio: a la izquierda los 3 contadores del estado actual del
parque de maquinas (los mismos que el dashboard, repetidos aca para
que el operador los tenga a la vista mientras arma el informe), y
el boton "Enviar Informe por Outlook" a la derecha.

Los stats del turno (Total Incidencias / Maquinas Registradas /
Hora de Inicio / Pendientes) se quitaron porque vivian duplicados
con el dashboard y resultaban ruido visual.
"""

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
    """Pie con stats del catalogo + boton de envio."""

    enviarInforme = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("footer")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(64)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(24)

        # Stats del CATALOGO (izquierda) - estado actual del parque
        self._total_maquinas = self._stat("TOTAL MAQUINAS", "0")
        layout.addWidget(self._total_maquinas["host"])
        layout.addWidget(self._divider())
        self._operativas = self._stat("OPERATIVAS", "0", color="green")
        layout.addWidget(self._operativas["host"])
        layout.addWidget(self._divider())
        self._en_obs = self._stat("EN OBSERVACION", "0", color="blue")
        layout.addWidget(self._en_obs["host"])

        layout.addItem(QSpacerItem(20, 1, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self._btn = QPushButton("  Enviar Informe por Outlook")
        self._btn.setObjectName("btnReport")
        self._btn.setIcon(svg("mail", 17))
        self._btn.setCursor(Qt.PointingHandCursor)
        self._btn.clicked.connect(self.enviarInforme.emit)
        layout.addWidget(self._btn)

    def _stat(self, label: str, value: str, *, color: str | None = None) -> dict:
        host = QFrame()
        v = QVBoxLayout(host)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        l = QLabel(label)
        l.setProperty("class", "fsLabel")
        val = QLabel(value)
        val.setProperty("class", "fsValue")
        # Color custom del valor (green / blue / amber / red / accent).
        if color:
            val.setProperty("color", color)
        else:
            val.setProperty("color", "default")
        v.addWidget(l)
        v.addWidget(val)
        return {"host": host, "value": val}

    def _divider(self) -> QWidget:
        d = QFrame()
        d.setProperty("class", "footDivider")
        d.setFixedSize(1, 32)
        return d

    # --- API --------------------------------------------------------------

    def set_estado_catalogo(self, *, total: int, operativas: int,
                            en_observacion: int) -> None:
        """Actualiza los contadores del estado actual del catalogo.

        Reflejan el estado REAL de cada maquina en el parque, no las
        incidencias del turno. Asi el operador ve si hay maquinas en
        observacion que arrastran de turnos anteriores.
        """
        self._total_maquinas["value"].setText(str(total))
        self._operativas["value"].setText(str(operativas))
        self._en_obs["value"].setText(str(en_observacion))

    def set_enviando(self, on: bool) -> None:
        self._btn.setEnabled(not on)
        self._btn.setText("  Enviando..." if on else "  Enviar Informe por Outlook")


__all__ = ("Footer",)
