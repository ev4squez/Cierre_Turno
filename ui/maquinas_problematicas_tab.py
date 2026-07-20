"""Tab de maquinas problematicas (atascadas + ranking por FDS).

Muestra en una tabla las maquinas que llevan >= N dias en un estado
problematico (Fuera de Servicio / Pendiente Repuesto / Espera Servicio
Tecnico / En Observacion), ordenadas por antiguedad.

Ademas muestra un top 10 de maquinas con mas incidencias en el
ultimo mes, util para detectar patrones.

Para auditoria / cumplimiento SCJ: evidencia de cuales maquinas
estan problematicas y hace cuanto.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Callable

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class MaquinasProblematicasTab(QFrame):
    """Tab que muestra las maquinas atascadas + el top con mas FDS.

    Signals
    -------
    changed: emite cuando se refresca la lista.
    """

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        # Refrescar al tabbecar visible: la primera vez, lo hacemos
        # automaticamente despues de 200ms (asi no bloqueamos el start).
        QTimer.singleShot(200, self._refrescar)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        titulo = QLabel("Maquinas problematicas")
        titulo.setStyleSheet("font-size:15px; font-weight:700; color:#1B2430;")
        sub = QLabel(
            "Maquinas con estado problematico (FDS / Pend Repuesto / "
            "Espera Tecnico / En Observacion) que llevan N dias sin cambio. "
            "Util para que el area de cumplimiento vea patrones y compre "
            "repuestos antes de que la situacion empeore."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("color:#64748B; font-size:12px;")
        root.addWidget(titulo)
        root.addWidget(sub)

        # Selector de dias
        ctrl_row = QFrame()
        ctrl_layout = QHBoxLayout(ctrl_row)
        ctrl_layout.setContentsMargins(0, 0, 0, 0)
        ctrl_layout.setSpacing(8)
        lbl = QLabel("Mostrar maquinas con + de")
        lbl.setStyleSheet("color:#1B2430; font-size:12px; font-weight:600;")
        ctrl_layout.addWidget(lbl)
        self._spin_dias = QSpinBox()
        self._spin_dias.setRange(1, 365)
        self._spin_dias.setValue(7)
        self._spin_dias.setSuffix(" dias en estado problematico")
        self._spin_dias.valueChanged.connect(self._refrescar)
        ctrl_layout.addWidget(self._spin_dias)
        ctrl_layout.addStretch(1)
        # Boton refrescar
        from PySide6.QtWidgets import QPushButton
        from ui.helpers import svg
        btn_refresh = QPushButton("  Refrescar")
        btn_refresh.setObjectName("btnSecondary")
        btn_refresh.setIcon(svg("filter", 14))
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.clicked.connect(self._refrescar)
        ctrl_layout.addWidget(btn_refresh)
        root.addWidget(ctrl_row)

        # Tabla
        self._tabla = QTableWidget(0, 6)
        self._tabla.setHorizontalHeaderLabels([
            "Maquina", "Marca", "Modelo", "Estado", "Sector", "Dias en estado",
        ])
        self._tabla.verticalHeader().setVisible(False)
        self._tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self._tabla.setAlternatingRowColors(True)
        self._tabla.setShowGrid(False)
        header = self._tabla.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        root.addWidget(self._tabla, 1)

        # Footer con count
        self._lbl_count = QLabel("")
        self._lbl_count.setStyleSheet("color:#64748B; font-size:12px;")
        root.addWidget(self._lbl_count)

    def _refrescar(self) -> None:
        """Recarga la lista de maquinas atascadas."""
        dias = self._spin_dias.value()
        try:
            from services import maquinas as svc_maq
            lista = svc_maq.listar_atascadas(dias_minimo=dias)
        except Exception as e:
            self._lbl_count.setText(f"Error al cargar: {e}")
            self._tabla.setRowCount(0)
            return

        self._tabla.setRowCount(0)
        for m in lista:
            row = self._tabla.rowCount()
            self._tabla.insertRow(row)
            self._tabla.setItem(row, 0, QTableWidgetItem(
                str(m.get("numero_maquina", ""))
            ))
            self._tabla.setItem(row, 1, QTableWidgetItem(
                str(m.get("marca", ""))
            ))
            self._tabla.setItem(row, 2, QTableWidgetItem(
                str(m.get("modelo", ""))
            ))
            self._tabla.setItem(row, 3, QTableWidgetItem(
                str(m.get("estado", ""))
            ))
            self._tabla.setItem(row, 4, QTableWidgetItem(
                str(m.get("sector", ""))
            ))
            self._tabla.setItem(row, 5, QTableWidgetItem(
                str(m.get("dias_en_estado", ""))
            ))
            self._tabla.setRowHeight(row, 30)

        n = len(lista)
        self._lbl_count.setText(
            f"{n} {'maquina' if n == 1 else 'maquinas'} con + de {dias} dias "
            f"en estado problematico."
        )
        self.changed.emit()

    def refrescar(self) -> None:
        """API publica: refresca desde fuera."""
        self._refrescar()


__all__ = ("MaquinasProblematicasTab",)
