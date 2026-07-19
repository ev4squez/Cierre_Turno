"""Panel inferior: tabla de incidencias del turno."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from config import ESTADOS_MAQUINA
from ui.helpers import severity_for_estado, svg


COLS = ["Hora", "Maquina", "Sector", "Marca", "Problema", "Estado", "Tecnico", "Acciones"]


class BottomTablePanel(QFrame):
    """Tabla de incidencias del turno + acciones por fila.

    El header de la tabla ahora incluye el boton 'Enviar Informe por
    Outlook' (antes vivia en el footer). Asi la accion principal del
    cierre de turno queda visible justo arriba de las incidencias que
    va a enviar.

    Signals
    -------
    editar(int):            id de la incidencia a editar
    eliminar(int):          id de la incidencia a eliminar
    enviarInformeClicked(): cuando el operador aprieta 'Enviar Informe'
    """

    editar = Signal(int)
    eliminar = Signal(int)
    enviarInformeClicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "bottomPanel")
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._build_ui()

    def _build_ui(self) -> None:
        head = QFrame()
        head.setProperty("class", "panelHead")
        h = QHBoxLayout(head)
        h.setContentsMargins(18, 10, 18, 10)
        h.setSpacing(8)

        title = QLabel("Incidencias del turno")
        title.setProperty("class", "panelTitle")
        self._count_badge = QLabel("0 registros")
        self._count_badge.setProperty("class", "countBadge")
        h.addWidget(title)
        h.addWidget(self._count_badge)
        h.addStretch(1)

        # Acciones del header: Filtrar (placeholder) + Enviar Informe.
        # El boton 'Filtrar' queda disabled porque todavia no esta
        # implementado, pero dejamos el slot visible para consistencia
        # con el HTML de referencia.
        btn_filter = QPushButton("  Filtrar")
        btn_filter.setObjectName("btnGhost")
        btn_filter.setIcon(svg("filter", 15))
        btn_filter.setCursor(Qt.PointingHandCursor)
        btn_filter.setEnabled(False)
        h.addWidget(btn_filter)

        # Boton principal: Enviar Informe por Outlook.
        # El footer ya no existe; este boton toma su lugar.
        self._btn_send = QPushButton("  Enviar Informe por Outlook")
        self._btn_send.setObjectName("btnReportSm")
        self._btn_send.setIcon(svg("mail", 15))
        self._btn_send.setCursor(Qt.PointingHandCursor)
        self._btn_send.clicked.connect(self.enviarInformeClicked.emit)
        h.addWidget(self._btn_send)

        # Tabla
        self._tabla = QTableWidget(0, len(COLS))
        self._tabla.setObjectName("tablaIncidencias")
        self._tabla.setHorizontalHeaderLabels(COLS)
        self._tabla.verticalHeader().setVisible(False)
        self._tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self._tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tabla.setAlternatingRowColors(False)
        self._tabla.setShowGrid(False)
        header = self._tabla.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(head)
        root.addWidget(self._tabla, 1)

    # --- API --------------------------------------------------------------

    def set_rows(self, registros: list[dict]) -> None:
        """Reemplaza el contenido de la tabla."""
        self._tabla.setRowCount(0)
        for r in registros:
            self._add_row(r)
        n = len(registros)
        self._count_badge.setText(f"{n} {'registro' if n == 1 else 'registros'}")

    def set_enviando(self, on: bool) -> None:
        """Cambia el boton 'Enviar Informe' entre normal / 'Enviando...'."""
        self._btn_send.setEnabled(not on)
        self._btn_send.setText(
            "  Enviando..." if on else "  Enviar Informe por Outlook"
        )

    def _add_row(self, r: dict) -> None:
        row = self._tabla.rowCount()
        self._tabla.insertRow(row)

        # Id oculto (para emitir senales). Lo guardamos en la primera celda como UserRole.
        hora_item = QTableWidgetItem(str(r.get("hora") or ""))
        hora_item.setData(Qt.UserRole, r.get("id"))
        self._tabla.setItem(row, 0, hora_item)
        self._tabla.setItem(row, 1, QTableWidgetItem(str(r.get("numero_maquina") or "")))
        self._tabla.setItem(row, 2, QTableWidgetItem(str(r.get("sector") or "")))
        self._tabla.setItem(row, 3, QTableWidgetItem(str(r.get("marca") or "")))
        self._tabla.setItem(row, 4, QTableWidgetItem(str(r.get("problema") or "")))

        # Estado (badge)
        estado = r.get("estado_final") or "Fuera de Servicio"
        if estado not in ESTADOS_MAQUINA:
            estado = "Fuera de Servicio"
        badge = QLabel(estado)
        badge.setProperty("class", "badge")
        badge.setProperty("severity", severity_for_estado(estado))
        badge.setAlignment(Qt.AlignCenter)
        # Wrap en un contenedor para centrado
        badge_wrap = QFrame()
        bw = QHBoxLayout(badge_wrap)
        bw.setContentsMargins(0, 0, 0, 0)
        bw.setSpacing(0)
        bw.addStretch(1)
        bw.addWidget(badge)
        bw.addStretch(1)
        self._tabla.setCellWidget(row, 5, badge_wrap)

        self._tabla.setItem(row, 6, QTableWidgetItem(str(r.get("tecnico") or "")))

        # Acciones (edit / delete)
        actions_wrap = QFrame()
        aw = QHBoxLayout(actions_wrap)
        aw.setContentsMargins(0, 0, 0, 0)
        aw.setSpacing(6)
        btn_edit = QToolButton()
        btn_edit.setProperty("class", "iconBtn")
        btn_edit.setIcon(svg("edit", 14))
        btn_edit.setCursor(Qt.PointingHandCursor)
        btn_edit.setToolTip("Editar")
        btn_edit.clicked.connect(lambda _=False, i=r.get("id"): self.editar.emit(int(i)))

        btn_del = QToolButton()
        btn_del.setProperty("class", "iconBtn")
        btn_del.setProperty("role", "danger")
        btn_del.setIcon(svg("trash", 14))
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.setToolTip("Eliminar")
        btn_del.clicked.connect(lambda _=False, i=r.get("id"): self.eliminar.emit(int(i)))

        aw.addWidget(btn_edit)
        aw.addWidget(btn_del)
        aw.addStretch(1)
        self._tabla.setCellWidget(row, 7, actions_wrap)

        # Altura consistente
        self._tabla.setRowHeight(row, 44)


__all__ = ("BottomTablePanel",)