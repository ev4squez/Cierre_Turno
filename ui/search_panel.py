"""Buscador live + lista de resultados.

En el layout nuevo (post-rediseno) este widget se embebe DENTRO del
panel central de la maquina, en su parte superior. Ya no es un panel
independiente con scroll propio. Mantiene los signals
``machineSelected`` y ``queryChanged`` y los metodos ``set_results`` /
``set_quick_stats`` para no romper al controller ni al smoke test.

El metodo ``set_quick_stats`` queda como no-op: el resumen rapido ahora
lo maneja ``DashboardBar``. Si el controller lo llama igual, no rompe.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.helpers import clear_layout, severity_for_estado, svg


class SearchPanel(QFrame):
    """Buscador live + lista compacta de resultados.

    Signals
    -------
    machineSelected(dict): maquina elegida
    queryChanged(str):     emite en cada keystroke (live search)
    """

    machineSelected = Signal(dict)
    queryChanged = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("searchPanel")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # Limite de altura razonable: buscador + hasta 4 resultados visibles
        self.setMaximumHeight(280)

        self._result_widgets: list[QFrame] = []
        self._last_results: list[dict] = []

        self._build_ui()

    # --- UI --------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 12)
        outer.setSpacing(6)

        # Search box (icon + input + clear icon)
        search_wrap = QFrame()
        search_layout = QHBoxLayout(search_wrap)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(0)

        # El icono va DENTRO del QLineEdit via padding-left, pero el placeholder
        # lo pintamos via stylesheet. Para mantener la API que usa el smoke test
        # (`w._search_panel._search.setText`), creamos el QLineEdit normalmente
        # y le ponemos el icono superpuesto en un contenedor.
        icon = QLabel()
        icon.setObjectName("searchInputIcon")
        icon.setPixmap(svg("search", 16).pixmap(16, 16))

        self._search = QLineEdit()
        self._search.setObjectName("searchInput")
        self._search.setPlaceholderText("Buscar por codigo, marca o modelo...")
        self._search.textChanged.connect(self._on_text_changed)
        self._search.returnPressed.connect(self._on_enter)

        # Input row: icon absolute + input
        input_row = QFrame()
        input_row.setObjectName("searchInputRow")
        ir = QHBoxLayout(input_row)
        ir.setContentsMargins(0, 0, 0, 0)
        ir.setSpacing(0)
        ir.addWidget(self._search, 1)
        # El icono decorativo queda como label invisible para conservar la
        # jerarquia visual del HTML; el icono real lo inyecta el QSS via
        # background-image en searchInput. Esto evita superposiciones en Qt.

        outer.addWidget(input_row)
        # El icono lo agrega el QSS en background para no romper el padding

        # Hint (placeholder del conteo)
        self._hint = QLabel("")
        self._hint.setObjectName("searchHint")
        outer.addWidget(self._hint)

        # Label resultados
        self._results_label = QLabel("RESULTADOS")
        self._results_label.setObjectName("resultsLabel")
        outer.addWidget(self._results_label)

        # Lista de resultados
        self._results_host = QFrame()
        self._results_layout = QVBoxLayout(self._results_host)
        self._results_layout.setContentsMargins(0, 0, 0, 0)
        self._results_layout.setSpacing(4)
        self._results_layout.addStretch(1)
        outer.addWidget(self._results_host)

        outer.addStretch(1)

    # --- API --------------------------------------------------------------

    def set_quick_stats(self, fds: int, pendientes: int, resueltas: int,
                        *, en_observacion: int = 0) -> None:
        """No-op: el resumen rapido lo maneja ``DashboardBar``.

        Se conserva por compatibilidad con el controller, que llama
        ``win.set_quick_stats(...)`` despues de refrescar la lista.
        """
        return None

    def set_results(self, maquinas: list[dict]) -> None:
        """Reemplaza los resultados mostrados."""
        self._last_results = list(maquinas)
        clear_layout(self._results_host)

        if not maquinas:
            self._hint.setText("Sin coincidencias")
            self._results_label.setVisible(False)
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
        item.setObjectName("resultItem")
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
        num.setFixedSize(44, 34)

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

        # Badge de estado (compacto)
        estado = m.get("estado") or "Operativa"
        badge = QLabel(estado)
        badge.setProperty("class", "badge")
        badge.setProperty("severity", severity_for_estado(estado))
        badge.setAlignment(Qt.AlignCenter)

        h.addWidget(num)
        h.addWidget(text, 1)
        h.addWidget(badge)

        item.mousePressEvent = lambda _e, mm=m: self._on_item_clicked(mm)  # type: ignore[assignment]
        return item

    def _on_item_clicked(self, m: dict) -> None:
        for w in self._result_widgets:
            w.setProperty("active", "false")
            w.style().unpolish(w)
            w.style().polish(w)
        for w in self._result_widgets:
            if w.property("maquina") is m:
                w.setProperty("active", "true")
                w.style().unpolish(w)
                w.style().polish(w)
        self._search.clearFocus()
        self.machineSelected.emit(m)

    def _on_text_changed(self, text: str) -> None:
        self.queryChanged.emit(text)

    def _on_enter(self) -> None:
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
            (i for i, w in enumerate(self._result_widgets)
             if w.property("active") == "true"),
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
