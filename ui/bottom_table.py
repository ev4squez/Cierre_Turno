"""Panel inferior: tabla de incidencias del turno + filtros + acciones.

Layout (post-rediseno):
  - Header: titulo + count badge + [Filtrar toggle] + [Enviar Informe]
  - Filters (oculto por default): 3 combos (Estado / Tecnico / Maquina)
    + boton Limpiar filtros
  - Tabla

Filtros funcionan en vivo: cada cambio en un combo filtra la tabla
inmediatamente. La barra muestra "N de M" cuando hay filtros activos.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
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


# Orden de columnas pensado para que el "Fuera de Servicio" sea
# lo PRIMERO que vea el operador al mirar la tabla: arranca con
# Estado, luego Hora, Maquina, Problema, Marca, Sector, Tecnico, Acciones.
COLS = ["Estado", "Hora", "Maquina", "Problema", "Marca", "Sector", "Tecnico", "Acciones"]

# Estados por los que se puede filtrar. Incluye un placeholder 'Todos'.
ESTADOS_FILTRO: tuple[str, ...] = ("Todos",) + ESTADOS_MAQUINA


class BottomTablePanel(QFrame):
    """Tabla de incidencias del turno + filtros + acciones por fila.

    Signals
    -------
    editar(int):            id de la incidencia a editar
    eliminar(int):          id de la incidencia a eliminar
    enviarInformeClicked(): cuando el operador aprieta 'Enviar Informe'
    """

    editar = Signal(int)
    eliminar = Signal(int)
    # Duplicar(int): el operador quiere clonar una incidencia del mismo
    # turno (caso tipico: la misma maquina se reincio 4 veces). El
    # controller arma un form pre-llenado con los datos de la original
    # para que el operador solo cambie la hora y confirme.
    duplicar = Signal(int)
    enviarInformeClicked = Signal()
    previsualizarClicked = Signal()
    exportarClicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "bottomPanel")
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Almacenes: las filas 'puras' que vienen del controller y las
        # que actualmente se ven (filtradas). Asi los filtros no mutan
        # los datos originales y se pueden limpiar.
        self._all_rows: list[dict] = []

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Header: titulo + count badge + acciones
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

        # Toggle de filtros: el boton Filtrar ahora abre/cierra la barra
        btn_filter = QPushButton("  Filtrar")
        btn_filter.setObjectName("btnGhost")
        btn_filter.setIcon(svg("filter", 15))
        btn_filter.setCursor(Qt.PointingHandCursor)
        btn_filter.setCheckable(True)
        btn_filter.clicked.connect(self._toggle_filters)
        h.addWidget(btn_filter)

        # Boton de previsualizacion (muestra el HTML antes de mandar)
        self._btn_preview = QPushButton("  Previsualizar")
        self._btn_preview.setObjectName("btnGhost")
        self._btn_preview.setIcon(svg("eye", 15))
        self._btn_preview.setCursor(Qt.PointingHandCursor)
        self._btn_preview.setToolTip("Ver el HTML antes de enviarlo")
        self._btn_preview.clicked.connect(self.previsualizarClicked.emit)
        h.addWidget(self._btn_preview)

        # Boton exportar a CSV (auditorias externas)
        self._btn_exportar = QPushButton("  Exportar")
        self._btn_exportar.setObjectName("btnGhost")
        self._btn_exportar.setIcon(svg("excel", 15))
        self._btn_exportar.setCursor(Qt.PointingHandCursor)
        self._btn_exportar.setToolTip(
            "Exportar las filas visibles a CSV (para auditoria)"
        )
        self._btn_exportar.clicked.connect(self.exportarClicked.emit)
        h.addWidget(self._btn_exportar)

        # Boton principal: Enviar Informe por Outlook
        self._btn_send = QPushButton("  Enviar Informe por Outlook")
        self._btn_send.setObjectName("btnReportSm")
        self._btn_send.setIcon(svg("mail", 15))
        self._btn_send.setCursor(Qt.PointingHandCursor)
        self._btn_send.setToolTip("Enviar informe por Outlook (Ctrl+E)")
        self._btn_send.clicked.connect(self.enviarInformeClicked.emit)
        h.addWidget(self._btn_send)

        # Barra de filtros (oculta por default)
        self._filters_bar = self._build_filters_bar()

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
        root.addWidget(self._filters_bar)
        root.addWidget(self._tabla, 1)

        self._filters_bar.setVisible(False)

    def _build_filters_bar(self) -> QFrame:
        """Barra con combos de filtro (estado/tecnico/maquina) + boton limpiar."""
        bar = QFrame()
        bar.setObjectName("filtersBar")
        bar.setProperty("class", "filtersBar")

        row = QHBoxLayout(bar)
        row.setContentsMargins(18, 10, 18, 10)
        row.setSpacing(10)

        # Estado
        row.addWidget(QLabel("Estado:"))
        self._f_estado = QComboBox()
        self._f_estado.setObjectName("filterEstado")
        self._f_estado.addItems(list(ESTADOS_FILTRO))
        self._f_estado.currentIndexChanged.connect(self._aplicar_filtros)
        row.addWidget(self._f_estado)

        # Tecnico
        row.addSpacing(10)
        row.addWidget(QLabel("Tecnico:"))
        self._f_tecnico = QComboBox()
        self._f_tecnico.setObjectName("filterTecnico")
        self._f_tecnico.addItem("Todos")
        self._f_tecnico.currentIndexChanged.connect(self._aplicar_filtros)
        row.addWidget(self._f_tecnico)

        # Maquina
        row.addSpacing(10)
        row.addWidget(QLabel("Maquina:"))
        self._f_maquina = QComboBox()
        self._f_maquina.setObjectName("filterMaquina")
        self._f_maquina.addItem("Todas")
        self._f_maquina.currentIndexChanged.connect(self._aplicar_filtros)
        row.addWidget(self._f_maquina)

        row.addStretch(1)

        # Boton limpiar
        btn_clear = QPushButton("  Limpiar filtros")
        btn_clear.setObjectName("btnGhost")
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.clicked.connect(self._limpiar_filtros)
        row.addWidget(btn_clear)

        return bar

    # ------------------------------------------------------------------
    # Filtros
    # ------------------------------------------------------------------

    def _toggle_filters(self) -> None:
        """Muestra/oculta la barra de filtros."""
        sender = self.sender()
        visible = sender.isChecked() if isinstance(sender, QPushButton) else False
        self._filters_bar.setVisible(visible)
        # Si la acabamos de mostrar, poblar los combos con los valores
        # unicos de las filas actuales.
        if visible:
            self._populate_filter_options()

    def _populate_filter_options(self) -> None:
        """Llena los combos de Tecnico y Maquina con los valores unicos
        de las filas actuales. Idempotente: si ya estan poblados no los
        duplica.
        """
        # Tecnicos unicos
        tecnicos_actuales = {str(r.get("tecnico") or "") for r in self._all_rows}
        tecnicos_actuales.discard("")
        tecnicos_en_combo = {
            self._f_tecnico.itemData(i) or self._f_tecnico.itemText(i)
            for i in range(self._f_tecnico.count())
        }
        for t in sorted(tecnicos_actuales):
            if t not in tecnicos_en_combo:
                self._f_tecnico.addItem(t)

        # Maquinas unicas
        maquinas_actuales = {str(r.get("numero_maquina") or "") for r in self._all_rows}
        maquinas_actuales.discard("")
        maquinas_en_combo = {
            self._f_maquina.itemData(i) or self._f_maquina.itemText(i)
            for i in range(self._f_maquina.count())
        }
        for m in sorted(maquinas_actuales):
            if m not in maquinas_en_combo:
                self._f_maquina.addItem(m)

    def _aplicar_filtros(self) -> None:
        """Filtra la tabla segun los combos actuales."""
        estado = self._f_estado.currentText()
        tecnico = self._f_tecnico.currentText()
        maquina = self._f_maquina.currentText()

        filtradas = []
        for r in self._all_rows:
            if estado != "Todos" and r.get("estado_final") != estado:
                continue
            if tecnico != "Todos" and r.get("tecnico") != tecnico:
                continue
            if maquina != "Todas" and str(r.get("numero_maquina") or "") != maquina:
                continue
            filtradas.append(r)

        self._render_rows(filtradas)

    def _limpiar_filtros(self) -> None:
        """Vuelve los combos a 'Todos' y re-renderiza la tabla completa."""
        # blockSignals para no disparar _aplicar_filtros 3 veces
        for cb in (self._f_estado, self._f_tecnico, self._f_maquina):
            cb.blockSignals(True)
            cb.setCurrentIndex(0)
            cb.blockSignals(False)
        self._render_rows(list(self._all_rows))

    def _render_rows(self, rows: list[dict]) -> None:
        """Renderiza la lista de filas en la tabla (no toca el cache)."""
        self._visible_rows = list(rows)
        self._tabla.setRowCount(0)
        for r in rows:
            self._add_row(r)
        n = len(rows)
        total = len(self._all_rows)
        if n == total:
            self._count_badge.setText(
                f"{n} {'registro' if n == 1 else 'registros'}"
            )
        else:
            self._count_badge.setText(f"{n} de {total} registros")

    def current_rows(self) -> list[dict]:
        """Devuelve las filas actualmente visibles (post-filtros).

        Usado por el handler de exportarClicked en el controller.
        """
        return list(getattr(self, "_visible_rows", []))

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def set_rows(self, registros: list[dict]) -> None:
        """Reemplaza TODAS las filas (cache + render). Reaplica filtros."""
        self._all_rows = list(registros)
        # Si los combos de filtros ya estaban poblados y la lista nueva
        # no tiene algunos valores, podrian quedar opciones 'fantasma'.
        # Por simplicidad las dejamos: si el operador las elige, no
        # aparecera nada (comportamiento esperado).
        self._aplicar_filtros()

    def set_enviando(self, on: bool) -> None:
        """Cambia el boton 'Enviar Informe' entre normal / 'Enviando...'."""
        self._btn_send.setEnabled(not on)
        self._btn_send.setText(
            "  Enviando..." if on else "  Enviar Informe por Outlook"
        )

    # ------------------------------------------------------------------
    # Renderizado de filas
    # ------------------------------------------------------------------

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
        badge_wrap = QFrame()
        bw = QHBoxLayout(badge_wrap)
        bw.setContentsMargins(0, 0, 0, 0)
        bw.setSpacing(0)
        bw.addStretch(1)
        bw.addWidget(badge)
        bw.addStretch(1)
        self._tabla.setCellWidget(row, 5, badge_wrap)

        self._tabla.setItem(row, 6, QTableWidgetItem(str(r.get("tecnico") or "")))

        # Acciones (edit / duplicate / delete)
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

        # Duplicar: clona la fila en un form pre-llenado. El icono es
        # un 'copy' (dos hojas) para diferenciarlo del lapiz de editar.
        btn_dup = QToolButton()
        btn_dup.setProperty("class", "iconBtn")
        btn_dup.setIcon(svg("clipboard", 14))  # mismo icono que el topbar
        btn_dup.setCursor(Qt.PointingHandCursor)
        btn_dup.setToolTip("Duplicar (abre el form pre-llenado para re-registrar)")
        btn_dup.clicked.connect(lambda _=False, i=r.get("id"): self.duplicar.emit(int(i)))

        btn_del = QToolButton()
        btn_del.setProperty("class", "iconBtn")
        btn_del.setProperty("role", "danger")
        btn_del.setIcon(svg("trash", 14))
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.setToolTip("Eliminar")
        btn_del.clicked.connect(lambda _=False, i=r.get("id"): self.eliminar.emit(int(i)))

        aw.addWidget(btn_edit)
        aw.addWidget(btn_dup)
        aw.addWidget(btn_del)
        aw.addStretch(1)
        self._tabla.setCellWidget(row, 7, actions_wrap)

        # Altura consistente
        self._tabla.setRowHeight(row, 44)


__all__ = ("BottomTablePanel",)
