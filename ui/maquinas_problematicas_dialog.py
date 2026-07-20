"""Dialog de maquinas problematicas actuales (sin filtro de tiempo).

Muestra todas las maquinas que estan en estado problematico AHORA
(no las que llevan N dias, eso es el tab Problematicas de Settings
que ya existe). Pensado para que el operador pueda ver de un vistazo
cuales son las que necesitan atencion inmediata.

Diferencia vs. el tab 'Problematicas' de Settings:
  - Tab Problematicas: muestra las que llevan >= N dias (reporteria)
  - Este dialog: muestra TODAS las problematicas (operacion diaria)

Funcionalidad:
  - Tabla con: Maquina, Marca, Modelo, Estado, Sector, Dias
  - Doble click o boton 'Ver' -> cierra el dialog y emite la
    maquina seleccionada para que el controller la muestre en el
    panel central.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.helpers import svg


class MaquinasProblematicasDialog(QDialog):
    """Dialog modal con el listado de maquinas problematicas actuales.

    Signals
    -------
    maquinaSeleccionada(dict): el operador hizo doble click o
        aprieta 'Ver' sobre una fila. Emite la maquina completa.
    """

    maquinaSeleccionada = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("maquinasProblematicasDialog")
        self.setWindowTitle("Maquinas con problemas ahora")
        self.setMinimumSize(820, 420)
        self.setModal(True)

        self._all: list[dict] = []  # cache para acceder desde callbacks
        self._build_ui()
        self._refrescar()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Header
        head = QFrame()
        hl = QHBoxLayout(head)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)
        icon = QLabel()
        icon.setPixmap(svg("alert", 18).pixmap(18, 18))
        hl.addWidget(icon)
        titulo = QLabel("Maquinas con problemas ahora")
        titulo.setStyleSheet(
            "font-size:15px; font-weight:700; color:#1B2430;"
        )
        hl.addWidget(titulo)
        hl.addStretch(1)
        # Boton refrescar
        btn_refresh = QPushButton("  Refrescar")
        btn_refresh.setObjectName("btnSecondary")
        btn_refresh.setIcon(svg("filter", 14))
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.clicked.connect(self._refrescar)
        hl.addWidget(btn_refresh)
        layout.addWidget(head)

        sub = QLabel(
            "Todas las maquinas en estado problematico (Fuera de Servicio, "
            "Pendiente Repuesto, Espera Tecnico, En Observacion). "
            "Doble click sobre una fila para verla en el panel central."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("color:#64748B; font-size:12px;")
        layout.addWidget(sub)

        # Tabla
        self._tabla = QTableWidget(0, 6)
        self._tabla.setHorizontalHeaderLabels([
            "Maquina", "Marca", "Modelo", "Estado", "Sector", "Dias",
        ])
        self._tabla.verticalHeader().setVisible(False)
        self._tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self._tabla.setSelectionMode(QTableWidget.SingleSelection)
        self._tabla.setAlternatingRowColors(True)
        self._tabla.setShowGrid(False)
        header = self._tabla.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self._tabla.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self._tabla, 1)

        # Footer
        self._lbl_count = QLabel("Cargando...")
        self._lbl_count.setStyleSheet("color:#64748B; font-size:12px;")
        layout.addWidget(self._lbl_count)

        # Botones Cerrar / Ver
        buttons = QDialogButtonBox()
        self._btn_ver = QPushButton("  Ver maquina")
        self._btn_ver.setObjectName("btnPrimary")
        self._btn_ver.setIcon(svg("eye", 14))
        self._btn_ver.setCursor(Qt.PointingHandCursor)
        self._btn_ver.setEnabled(False)
        self._btn_ver.clicked.connect(self._on_ver_clicked)
        self._tabla.itemSelectionChanged.connect(
            lambda: self._btn_ver.setEnabled(
                bool(self._tabla.selectedItems())
            )
        )
        buttons.addButton(self._btn_ver, QDialogButtonBox.AcceptRole)
        buttons.addButton(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _refrescar(self) -> None:
        """Recarga la lista desde la DB."""
        try:
            from services import maquinas as svc_maq
            self._all = svc_maq.listar_problematicas()
        except Exception as e:
            self._lbl_count.setText(f"Error al cargar: {e}")
            self._tabla.setRowCount(0)
            return

        self._tabla.setRowCount(0)
        for m in self._all:
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

        n = len(self._all)
        if n == 0:
            self._lbl_count.setText(
                "No hay maquinas problematicas ahora. Buen momento para el cafe."
            )
        else:
            self._lbl_count.setText(
                f"{n} {'maquina' if n == 1 else 'maquinas'} con problemas ahora."
            )

    def _get_selected_maquina(self) -> dict | None:
        rows = self._tabla.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        if 0 <= row < len(self._all):
            return self._all[row]
        return None

    def _on_double_click(self, _index) -> None:
        m = self._get_selected_maquina()
        if m is not None:
            self.maquinaSeleccionada.emit(m)
            self.accept()

    def _on_ver_clicked(self) -> None:
        m = self._get_selected_maquina()
        if m is not None:
            self.maquinaSeleccionada.emit(m)
            self.accept()


__all__ = ("MaquinasProblematicasDialog",)
