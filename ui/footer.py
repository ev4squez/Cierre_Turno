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
        layout.setSpacing(22)

        # Stats del TURNO (izquierda)
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

        # Separador mas ancho entre los stats del turno y los del catalogo
        layout.addSpacing(12)
        div2 = QFrame()
        div2.setProperty("class", "footDividerStrong")
        div2.setFixedSize(1, 32)
        div2.setStyleSheet("background-color: #CBD5E1;")
        layout.addWidget(div2)
        layout.addSpacing(12)

        # Stats del CATALOGO (centro) - estado actual del parque de maquinas
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

    def _stat(self, label: str, value: str, *, accent: bool = False,
              color: str | None = None) -> dict:
        host = QFrame()
        v = QVBoxLayout(host)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        l = QLabel(label)
        l.setProperty("class", "fsLabel")
        val = QLabel(value)
        val.setProperty("class", "fsValue")
        # Compat: `accent` mantiene el azul por defecto (legado).
        # `color` permite sobrescribir: "green" para Operativas,
        # "blue" para En Observacion.
        if color:
            val.setProperty("color", color)
            val.setProperty("accent", "false")
        else:
            val.setProperty("color", "accent" if accent else "default")
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

    def set_estado_catalogo(self, *, total: int, operativas: int,
                            en_observacion: int) -> None:
        """Actualiza los contadores del estado actual del catalogo.

        Estos valores NO son del turno: reflejan el estado REAL de cada
        maquina en el parque. Asi el operador ve si hay maquinas en
        observacion que arrastran de turnos anteriores.
        """
        self._total_maquinas["value"].setText(str(total))
        self._operativas["value"].setText(str(operativas))
        self._en_obs["value"].setText(str(en_observacion))

    def set_enviando(self, on: bool) -> None:
        self._btn.setEnabled(not on)
        self._btn.setText("  Enviando..." if on else "  Enviar Informe por Outlook")


__all__ = ("Footer",)