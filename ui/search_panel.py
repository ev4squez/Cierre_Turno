"""Panel izquierdo: buscador de maquinas + resumen rapido."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.helpers import clear_layout, svg


class SearchPanel(QFrame):
    """Buscador live + lista de resultados + quick stats.

    Signals
    -------
    machineSelected(dict): emite la maquina elegida (dict con keys
        numero_maquina, sector, isla, marca, modelo, serie, estado, ...)
    queryChanged(str):    emite en cada keystroke (para busqueda live)
    """

    machineSelected = Signal(dict)
    queryChanged = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("panelSearch")
        self.setProperty("class", "panel")
        self.setMinimumWidth(420)
        self.setMaximumWidth(520)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self._result_widgets: list[QFrame] = []
        self._last_results: list[dict] = []

        self._build_ui()

    # --- UI --------------------------------------------------------------

    def _build_ui(self) -> None:
        # Header
        head = QFrame()
        head.setProperty("class", "panelHead")
        head.setObjectName("panelHeadSearch")
        head_layout = QHBoxLayout(head)
        head_layout.setContentsMargins(18, 12, 18, 12)
        head_layout.setSpacing(8)
        icon = QLabel()
        icon.setPixmap(svg("search", 18).pixmap(18, 18))
        icon.setProperty("class", "panelIcon")
        title = QLabel("Buscar maquina")
        title.setProperty("class", "panelTitle")
        head_layout.addWidget(icon)
        head_layout.addWidget(title)
        head_layout.addStretch(1)

        # Body (scrollable para que entre todo si el monitor es chico)
        body_outer = QFrame()
        body_outer.setProperty("class", "panelBody")
        body = QVBoxLayout(body_outer)
        body.setContentsMargins(18, 16, 18, 16)
        body.setSpacing(8)

        # Search box (icon + input)
        search_wrap = QFrame()
        search_layout = QHBoxLayout(search_wrap)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(8)
        search_icon = QLabel()
        search_icon.setPixmap(svg("search", 18).pixmap(18, 18))
        search_layout.addWidget(search_icon)
        self._search = QLineEdit()
        self._search.setObjectName("searchInput")
        self._search.setPlaceholderText("Ingrese numero de maquina...")
        self._search.textChanged.connect(self._on_text_changed)
        self._search.returnPressed.connect(self._on_enter)
        search_layout.addWidget(self._search, 1)
        body.addWidget(search_wrap)

        self._hint = QLabel("")
        self._hint.setObjectName("searchHint")
        body.addWidget(self._hint)

        self._results_label = QLabel("RESULTADOS")
        self._results_label.setObjectName("resultsLabel")
        body.addWidget(self._results_label)

        # Lista de resultados (dentro de un scroll chico)
        self._results_host = QFrame()
        self._results_layout = QVBoxLayout(self._results_host)
        self._results_layout.setContentsMargins(0, 0, 0, 0)
        self._results_layout.setSpacing(6)
        self._results_layout.addStretch(1)
        body.addWidget(self._results_host, 1)

        # Quick stats (separador + titulo + 3 filas)
        body.addSpacing(14)
        qs_title = QLabel("RESUMEN RAPIDO")
        qs_title.setProperty("class", "qsTitle")
        body.addWidget(qs_title)
        self._qs_red = self._build_qs_row("#DC2626", "Maquinas FDS activas", "0")
        body.addWidget(self._qs_red)
        self._qs_amber = self._build_qs_row("#D97706", "Pendientes de revision", "0")
        body.addWidget(self._qs_amber)
        self._qs_green = self._build_qs_row("#16A34A", "Resueltas hoy", "0")
        body.addWidget(self._qs_green)

        # Layout final
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body_outer)
        scroll.setFrameShape(QFrame.NoFrame)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(head)
        root.addWidget(scroll, 1)

    def _build_qs_row(self, color: str, label_text: str, value: str) -> QFrame:
        row = QFrame()
        row.setProperty("class", "qsRow")
        h = QHBoxLayout(row)
        h.setContentsMargins(12, 10, 12, 10)
        h.setSpacing(8)

        dot = QFrame()
        dot.setFixedSize(8, 8)
        if color == "#DC2626":
            dot.setObjectName("tagDotRed")
        elif color == "#D97706":
            dot.setObjectName("tagDotAmber")
        else:
            dot.setObjectName("tagDotGreen")

        label = QLabel(label_text)
        label.setProperty("class", "qsLabel")
        value_label = QLabel(value)
        value_label.setProperty("class", "qsValue")
        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        setattr(value_label, "_qs_key", label_text)

        h.addWidget(dot)
        h.addWidget(label, 1)
        h.addWidget(value_label)
        return row

    # --- API --------------------------------------------------------------

    def set_quick_stats(self, fds: int, pendientes: int, resueltas: int) -> None:
        """Actualiza las tres tarjetas del resumen rapido."""
        for row in (self._qs_red, self._qs_amber, self._qs_green):
            label = row.findChild(QLabel, "", Qt.FindDirectChildrenOnly)  # noop
        # Localizar los QLabel con clase qsValue
        def _set(row: QFrame, val: int) -> None:
            for child in row.findChildren(QLabel):
                if child.property("class") == "qsValue":
                    child.setText(str(val))
                    return
        _set(self._qs_red, fds)
        _set(self._qs_amber, pendientes)
        _set(self._qs_green, resueltas)

    def set_results(self, maquinas: list[dict]) -> None:
        """Reemplaza los resultados mostrados."""
        self._last_results = list(maquinas)
        clear_layout(self._results_host)

        if not maquinas:
            self._hint.setText("Sin coincidencias")
            spacer = QFrame()
            self._results_layout.addWidget(spacer)
            self._results_layout.addStretch(1)
            return

        self._hint.setText(f"{len(maquinas)} coincidencias encontradas")
        self._results_label.setVisible(True)

        for idx, m in enumerate(maquinas):
            item = self._build_result_item(m, active=(idx == 0))
            self._result_widgets.append(item)
            self._results_layout.addWidget(item)
        self._results_layout.addStretch(1)

    def _build_result_item(self, m: dict, *, active: bool) -> QFrame:
        item = QFrame()
        item.setProperty("class", "resultItem")
        item.setProperty("active", "true" if active else "false")
        item.setCursor(Qt.PointingHandCursor)
        item.setProperty("maquina", m)

        h = QHBoxLayout(item)
        h.setContentsMargins(10, 8, 10, 8)
        h.setSpacing(12)

        num = QLabel(str(m.get("numero_maquina", "")))
        num.setProperty("class", "resultNum")
        num.setAlignment(Qt.AlignCenter)
        num.setFixedSize(44, 36)

        text = QFrame()
        text_v = QVBoxLayout(text)
        text_v.setContentsMargins(0, 0, 0, 0)
        text_v.setSpacing(2)
        title = QLabel(f"{m.get('marca','')} {m.get('modelo','')}".strip())
        title.setProperty("class", "resultTitle")
        sub = QLabel(f"{m.get('isla','')} - Sector {m.get('sector','')}".strip(" -"))
        sub.setProperty("class", "resultSub")
        text_v.addWidget(title)
        text_v.addWidget(sub)

        h.addWidget(num)
        h.addWidget(text, 1)

        item.mousePressEvent = lambda _e, mm=m: self._on_item_clicked(mm)  # type: ignore[assignment]
        return item

    def _on_item_clicked(self, m: dict) -> None:
        # Marcar visualmente el item activo
        for w in self._result_widgets:
            w.setProperty("active", "false")
            w.style().unpolish(w)
            w.style().polish(w)
        # Encontrar el widget de la maquina seleccionada y marcarlo
        for w in self._result_widgets:
            if w.property("maquina") is m:
                w.setProperty("active", "true")
                w.style().unpolish(w)
                w.style().polish(w)
        # Limpiar el focus del search box para que las flechas funcionen
        self._search.clearFocus()
        self.machineSelected.emit(m)

    def _on_text_changed(self, text: str) -> None:
        self.queryChanged.emit(text)

    def _on_enter(self) -> None:
        # Enter selecciona el primer resultado si hay
        if self._last_results:
            self.machineSelected.emit(self._last_results[0])

    def focus_search(self) -> None:
        self._search.setFocus()
        self._search.selectAll()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: D401
        if event.key() in (Qt.Key_Down, Qt.Key_Up):
            self._navigate_results(event.key())
            return
        super().keyPressEvent(event)

    def _navigate_results(self, key: int) -> None:
        if not self._last_results:
            return
        actual_id = next(
            (
                i
                for i, w in enumerate(self._result_widgets)
                if w.property("active") == "true"
            ),
            -1,
        )
        if key == Qt.Key_Down:
            new = min(actual_id + 1, len(self._result_widgets) - 1)
        else:
            new = max(actual_id - 1, 0)
        if new < 0:
            return
        for w in self._result_widgets:
            w.setProperty("active", "false")
            w.style().unpolish(w)
            w.style().polish(w)
        chosen = self._result_widgets[new]
        chosen.setProperty("active", "true")
        chosen.style().unpolish(chosen)
        chosen.style().polish(chosen)
        self.machineSelected.emit(self._last_results[new])


__all__ = ("SearchPanel",)