"""Buscador live + lista de resultados.

En el layout nuevo (post-rediseno) este widget se embebe DENTRO del
panel central de la maquina, en su parte superior. Ya no es un panel
independiente con scroll propio. Mantiene los signals
``machineSelected`` y ``queryChanged`` y los metodos ``set_results`` /
``set_quick_stats`` para no romper al controller ni al smoke test.

El metodo ``set_quick_stats`` queda como no-op: el resumen rapido ahora
lo maneja ``DashboardBar``. Si el controller lo llama igual, no rompe.

Implementacion: los resultados se muestran en un ``QListWidget`` con
items de altura fija (44px) y un widget custom por item (num + titulo
+ sub + badge de estado). Esto resuelve el problema de la lista
anterior: el QVBoxLayout con QFrame(items) crecia sin control cuando
habia 25+ maquinas y los labels wrappeaban a 4-5 lineas, volviendo
la UI ilegible.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from config import ESTADOS_MAQUINA
from ui.helpers import clear_layout, severity_for_estado, svg


# Altura fija de cada item de la lista. Suficiente para que entren
# titulo + sub + badge en una sola linea, sin wrap.
ITEM_HEIGHT = 44


class SearchPanel(QFrame):
    """Buscador live + lista compacta de resultados.

    Signals
    -------
    machineSelected(dict): maquina elegida
    queryChanged(str):     emite en cada keystroke (live search)
    filterChanged(str):     emite cuando cambia el filtro de estado.
        El string es "Todos" o uno de ``config.ESTADOS_MAQUINA``.
    """

    machineSelected = Signal(dict)
    queryChanged = Signal(str)
    filterChanged = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("searchPanel")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # Limite de altura razonable: filtro + buscador + hasta 6
        # items visibles (6 * 44 = 264px). El resto es scroll nativo
        # del QListWidget.
        self.setMaximumHeight(54 + 64 + 6 * ITEM_HEIGHT)  # ~382

        self._last_results: list[dict] = []

        # Historial de busquedas para autocompletar (persistente)
        from ui.search_history import SearchHistory
        self._history = SearchHistory(self)

        self._build_ui()
        # Instala el QCompleter del historial en el QLineEdit
        self._history.install_completer(self._search)

    # --- UI --------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 12)
        outer.setSpacing(6)

        # --- Filtro de estado (combo chico) -------------------------
        filter_row = QFrame()
        fr = QHBoxLayout(filter_row)
        fr.setContentsMargins(0, 0, 0, 0)
        fr.setSpacing(6)
        lbl = QLabel("Estado:")
        lbl.setProperty("class", "searchFilterLabel")
        lbl.setStyleSheet(
            "color:#1B2430; font-size:11.5px; font-weight:600;"
        )
        fr.addWidget(lbl)
        self._cb_filtro_estado = QComboBox()
        self._cb_filtro_estado.addItem("Todos")
        for est in ESTADOS_MAQUINA:
            self._cb_filtro_estado.addItem(est)
        self._cb_filtro_estado.setCurrentIndex(0)
        self._cb_filtro_estado.currentTextChanged.connect(
            self._on_filtro_cambiado
        )
        self._cb_filtro_estado.setMaximumWidth(160)
        fr.addWidget(self._cb_filtro_estado, 1)
        outer.addWidget(filter_row)

        # --- Search box ---------------------------------------------
        search_wrap = QFrame()
        search_layout = QHBoxLayout(search_wrap)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(0)

        icon = QLabel()
        icon.setObjectName("searchInputIcon")
        icon.setPixmap(svg("search", 16).pixmap(16, 16))

        self._search = QLineEdit()
        self._search.setObjectName("searchInput")
        self._search.setPlaceholderText("Buscar por codigo, marca o modelo...")
        self._search.textChanged.connect(self._on_text_changed)
        self._search.returnPressed.connect(self._on_enter)

        input_row = QFrame()
        input_row.setObjectName("searchInputRow")
        ir = QHBoxLayout(input_row)
        ir.setContentsMargins(0, 0, 0, 0)
        ir.setSpacing(0)
        ir.addWidget(self._search, 1)

        outer.addWidget(input_row)

        # Hint
        self._hint = QLabel("")
        self._hint.setObjectName("searchHint")
        outer.addWidget(self._hint)

        # --- Label resultados ---------------------------------------
        self._results_label = QLabel("RESULTADOS")
        self._results_label.setObjectName("resultsLabel")
        outer.addWidget(self._results_label)

        # --- Lista de resultados: QListWidget con scroll nativo ----
        # Reemplaza el QVBoxLayout anterior que crecia sin control.
        self._list = QListWidget()
        self._list.setObjectName("searchResultsList")
        self._list.setUniformItemSizes(True)  # performance + consistencia
        self._list.setWordWrap(False)         # no wrappear titulos
        self._list.setTextElideMode(Qt.ElideRight)  # "..." si no entra
        self._list.setSelectionMode(QListWidget.SingleSelection)
        self._list.setFocusPolicy(Qt.NoFocus)  # el foco es del QLineEdit
        # Scroll bar vertical siempre visible cuando hay overflow
        self._list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # El item clickeado emite machineSelected con la maquina guardada
        # en UserRole. La navegacion con flechas del teclado la maneja
        # el QListWidget nativamente.
        self._list.itemClicked.connect(self._on_item_clicked)
        # Si cambia la seleccion por teclado/flechas, emitimos al toque
        self._list.currentItemChanged.connect(self._on_current_changed)
        outer.addWidget(self._list, 1)

    # --- API --------------------------------------------------------------

    def set_quick_stats(self, fds: int, pendientes: int, resueltas: int,
                        *, en_observacion: int = 0) -> None:
        """No-op: el resumen rapido lo maneja ``DashboardBar``."""
        return None

    def set_results(self, maquinas: list[dict]) -> None:
        """Reemplaza los resultados mostrados."""
        self._last_results = list(maquinas)
        self._list.clear()

        if not maquinas:
            self._hint.setText("Sin coincidencias")
            self._results_label.setVisible(False)
            return

        self._hint.setText(f"{len(maquinas)} coincidencias encontradas")
        self._results_label.setVisible(True)

        for idx, m in enumerate(maquinas):
            item = QListWidgetItem(self._list)
            # Guardamos la maquina en UserRole para recuperarla en click
            item.setData(Qt.UserRole, m)
            # Tamano fijo por item (no wrap)
            item.setSizeHint(QSize(0, ITEM_HEIGHT))
            # El widget custom vive dentro del item
            widget = self._build_result_widget(m, active=(idx == 0))
            self._list.addItem(item)
            self._list.setItemWidget(item, widget)

        # Marcamos el primer item como current (asi las flechas
        # arrancan desde ahi y Enter lo selecciona).
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _build_result_widget(self, m: dict, *, active: bool) -> QFrame:
        """Construye el QFrame que vive dentro de un QListWidgetItem.

        Layout: [numero] [titulo / sub apilados] [badge estado]
        Altura fija (ITEM_HEIGHT), texto sin wrap.
        """
        item = QFrame()
        item.setObjectName("resultItem")
        item.setProperty("class", "resultItem")
        item.setProperty("active", "true" if active else "false")
        item.setCursor(Qt.PointingHandCursor)
        item.setFixedHeight(ITEM_HEIGHT)

        h = QHBoxLayout(item)
        h.setContentsMargins(10, 4, 10, 4)
        h.setSpacing(10)

        # Numero de maquina (chip)
        num = QLabel(str(m.get("numero_maquina", "")))
        num.setProperty("class", "resultNum")
        num.setAlignment(Qt.AlignCenter)
        num.setFixedSize(44, ITEM_HEIGHT - 12)
        # Elitros: si el numero no entra, lo cortamos con "..."
        num.setTextInteractionFlags(Qt.NoTextInteraction)

        # Texto: titulo + sub
        text = QFrame()
        text.setStyleSheet("background: transparent;")
        text_v = QVBoxLayout(text)
        text_v.setContentsMargins(0, 0, 0, 0)
        text_v.setSpacing(0)

        titulo = f"{m.get('marca', '')} {m.get('modelo', '')}".strip()
        sub = f"{m.get('isla', '')} - Sector {m.get('sector', '')}".strip(" -")

        lbl_titulo = QLabel(titulo or "—")
        lbl_titulo.setProperty("class", "resultTitle")
        lbl_titulo.setWordWrap(False)
        lbl_titulo.setTextInteractionFlags(Qt.NoTextInteraction)

        lbl_sub = QLabel(sub or "")
        lbl_sub.setProperty("class", "resultSub")
        lbl_sub.setWordWrap(False)
        lbl_sub.setTextInteractionFlags(Qt.NoTextInteraction)

        text_v.addWidget(lbl_titulo)
        text_v.addWidget(lbl_sub)

        # Badge de estado
        estado = m.get("estado") or "Operativa"
        badge = QLabel(estado)
        badge.setProperty("class", "badge")
        badge.setProperty("severity", severity_for_estado(estado))
        badge.setAlignment(Qt.AlignCenter)
        badge.setWordWrap(False)
        badge.setTextInteractionFlags(Qt.NoTextInteraction)
        badge.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

        h.addWidget(num)
        h.addWidget(text, 1)
        h.addWidget(badge)

        return item

    def _on_text_changed(self, text: str) -> None:
        self.queryChanged.emit(text)

    def _on_filtro_cambiado(self, val: str) -> None:
        """Re-emite el cambio de filtro para que el controller refrezque."""
        self.filterChanged.emit(val or "Todos")

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        """Handler de click: emite machineSelected con el dict del item."""
        m = item.data(Qt.UserRole) if item is not None else None
        if m is None:
            return
        # Historial
        q = self._search.text().strip()
        if q:
            self._history.agregar(q)
        # Sacamos foco del input (la seleccion ya quedo visible)
        self._search.clearFocus()
        self.machineSelected.emit(m)

    def _on_current_changed(self, current, previous) -> None:
        """Cuando cambia la seleccion por teclado, emitimos al toque.

        Asi el operador puede navegar con flechas y ver la maquina
        en el panel central sin tener que hacer click.
        """
        if current is None:
            return
        m = current.data(Qt.UserRole)
        if m is None:
            return
        self.machineSelected.emit(m)

    def set_filtro_estado(self, estado: str) -> None:
        """Cambia el combo de filtro externamente (sin disparar signal)."""
        if not estado:
            estado = "Todos"
        idx = self._cb_filtro_estado.findText(estado)
        if idx < 0:
            return
        self._cb_filtro_estado.blockSignals(True)
        try:
            self._cb_filtro_estado.setCurrentIndex(idx)
        finally:
            self._cb_filtro_estado.blockSignals(False)

    def get_filtro_estado(self) -> str:
        """Devuelve el estado seleccionado en el combo ('Todos' si no hay filtro)."""
        return self._cb_filtro_estado.currentText() or "Todos"

    def _on_enter(self) -> None:
        """Enter en el input: selecciona el item actual de la lista."""
        item = self._list.currentItem()
        if item is None:
            return
        m = item.data(Qt.UserRole)
        if m is None:
            return
        q = self._search.text().strip()
        if q:
            self._history.agregar(q)
        self.machineSelected.emit(m)

    def focus_search(self) -> None:
        self._search.setFocus()
        self._search.selectAll()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: D401
        # Las flechas se manejan nativamente en el QListWidget cuando
        # el foco esta ahi. Si el foco esta en el QLineEdit, no
        # intervenimos: dejamos que Qt haga lo suyo.
        super().keyPressEvent(event)


__all__ = ("SearchPanel",)
