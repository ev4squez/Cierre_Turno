"""Panel central: buscador embebido + info de la maquina + historial.

Layout (post-rediseno):
  [ Panel head: titulo + boton importar ]
  [ Body scrollable ]
    - SearchPanel (buscador + resultados live, max 280px alto)
    - Cabecera maquina: N.° + modelo + pill de estado
    - Grid 4x2 con campos de la maquina
    - Historico de incidencias previas
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.helpers import severity_for_estado, svg
from ui.search_panel import SearchPanel


class MachinePanel(QFrame):
    """Muestra los datos de la maquina seleccionada + ultimas incidencias.

    Signals
    -------
    editRequested(dict):   el operador aprieta 'Editar' en el panel.
                           Emite la maquina seleccionada.
    """

    editRequested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "panel")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumWidth(500)

        self._current_maquina: dict | None = None
        self._build_ui()
        self.show_empty()

    # --- UI ---------------------------------------------------------------

    def _build_ui(self) -> None:
        head = QFrame()
        head.setProperty("class", "panelHead")
        h = QHBoxLayout(head)
        h.setContentsMargins(18, 12, 18, 12)
        h.setSpacing(8)
        icon = QLabel()
        icon.setPixmap(svg("info", 18).pixmap(18, 18))
        icon.setProperty("class", "panelIcon")
        title = QLabel("Informacion de la maquina")
        title.setProperty("class", "panelTitle")
        h.addWidget(icon)
        h.addWidget(title)
        h.addStretch(1)
        # Boton para editar los datos de la maquina desde aca mismo
        # (abre el tab Maquinas de Settings con esta maquina preseleccionada)
        self._btn_editar = QPushButton("  Editar datos")
        self._btn_editar.setObjectName("btnSecondary")
        self._btn_editar.setIcon(svg("edit", 14))
        self._btn_editar.setCursor(Qt.PointingHandCursor)
        self._btn_editar.setToolTip(
            "Editar los datos de esta maquina (Settings > Maquinas)"
        )
        self._btn_editar.setEnabled(False)
        self._btn_editar.clicked.connect(self._on_editar_clicked)
        h.addWidget(self._btn_editar)

        # Body
        body = QFrame()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(18, 14, 18, 16)
        bl.setSpacing(12)

        # 1. Buscador embebido
        self._search_panel = SearchPanel()
        bl.addWidget(self._search_panel)

        # Separador sutil
        sep = QFrame()
        sep.setObjectName("panelDivider")
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #EBEEF3;")
        bl.addWidget(sep)

        # 2. Cabecera de la maquina (num grande + subtexto + pill)
        machine_header = QFrame()
        mh_layout = QHBoxLayout(machine_header)
        mh_layout.setContentsMargins(0, 4, 0, 4)
        mh_layout.setSpacing(12)

        machine_id_wrap = QFrame()
        mid_l = QVBoxLayout(machine_id_wrap)
        mid_l.setContentsMargins(0, 0, 0, 0)
        mid_l.setSpacing(2)
        self._big_num = QLabel("N.\u00ba -")
        self._big_num.setProperty("class", "machineBigNum")
        self._machine_sub = QLabel("")
        self._machine_sub.setProperty("class", "machineSub")
        self._machine_sub.setStyleSheet("color:#64748B; font-size:13px; font-weight:500;")
        mid_l.addWidget(self._big_num)
        mid_l.addWidget(self._machine_sub)

        self._status_pill = QFrame()
        self._status_pill.setProperty("class", "statusPill")
        sp_layout = QHBoxLayout(self._status_pill)
        sp_layout.setContentsMargins(12, 6, 12, 6)
        sp_layout.setSpacing(7)
        self._status_dot = QFrame()
        self._status_dot.setProperty("class", "statusPillDot")
        self._status_dot.setFixedSize(7, 7)
        self._status_text = QLabel("Sin seleccionar")
        self._status_text.setProperty("class", "statusPillText")
        sp_layout.addWidget(self._status_dot)
        sp_layout.addWidget(self._status_text)
        sp_layout.addStretch(1)

        mh_layout.addWidget(machine_id_wrap, 1)
        mh_layout.addWidget(self._status_pill, 0, Qt.AlignVCenter)
        bl.addWidget(machine_header)

        # 3. Grid 4 columnas x 2 filas (compacto, todos los campos en una vista)
        grid_host = QFrame()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        self._fields: dict[str, QLabel] = {}
        # 8 campos: mismo set que antes, ahora 4x2 en vez de 2x4
        labels = [
            ("numero_maquina", "Numero"),
            ("sector", "Sector"),
            ("isla", "Isla"),
            ("marca", "Marca"),
            ("modelo", "Modelo"),
            ("serie", "Serie"),
            ("denominacion", "Denominacion"),
            ("estado", "Estado actual"),
        ]
        for i, (key, lbl) in enumerate(labels):
            row, col = divmod(i, 4)
            cell = QFrame()
            cell.setProperty("class", "field")
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(12, 10, 12, 10)
            cl.setSpacing(4)
            lbl_top = QLabel(lbl.upper())
            lbl_top.setProperty("class", "fieldLabel")
            val = QLabel("-")
            val.setProperty("class", "fieldValue")
            cl.addWidget(lbl_top)
            cl.addWidget(val)
            self._fields[key] = val
            grid.addWidget(cell, row, col)
        for c in range(4):
            grid.setColumnStretch(c, 1)
        bl.addWidget(grid_host)

        # 4. Historico mini
        bl.addSpacing(4)
        hist_title = QLabel("ULTIMAS INCIDENCIAS DE ESTA MAQUINA")
        hist_title.setProperty("class", "historyTitle")
        bl.addWidget(hist_title)

        self._history_host = QFrame()
        self._history_layout = QVBoxLayout(self._history_host)
        self._history_layout.setContentsMargins(0, 0, 0, 0)
        self._history_layout.setSpacing(0)
        bl.addWidget(self._history_host)

        bl.addStretch(1)

        # Scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        scroll.setFrameShape(QFrame.NoFrame)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(head)
        root.addWidget(scroll, 1)

    # --- API --------------------------------------------------------------

    @property
    def search_panel(self) -> SearchPanel:
        """Acceso al sub-widget buscador (util para tests y controller)."""
        return self._search_panel

    def show_empty(self) -> None:
        self._big_num.setText("N.\u00ba -")
        self._machine_sub.setText("")
        self._set_status("Sin seleccionar", "info")
        for key, lbl in self._fields.items():
            lbl.setText("-")
        self._clear_history()
        self._current_maquina = None
        self._btn_editar.setEnabled(False)

    def show_machine(self, m: dict) -> None:
        self._current_maquina = m
        self._btn_editar.setEnabled(True)
        num = str(m.get("numero_maquina") or "-")
        self._big_num.setText(f"N.\u00ba {num}")
        sub = f"{m.get('marca','')} {m.get('modelo','')}".strip()
        self._machine_sub.setText(sub if sub else "")
        estado = m.get("estado") or "Operativa"
        self._set_status(estado, severity_for_estado(estado))
        for key, lbl in self._fields.items():
            v = m.get(key)
            lbl.setText(str(v) if v not in (None, "") else "-")
        if self._history_layout.count() == 0:
            # Mostrar mensaje vacio (el historial real lo carga el
            # controller via set_history() despues de consultar la DB).
            self._set_history([{
                "fecha": "",
                "texto": "Sin incidencias previas registradas.",
                "resuelta": True,
            }])

    def _set_status(self, text: str, severity: str) -> None:
        self._status_text.setText(text)
        self._status_pill.setProperty("severity", severity)
        self._status_pill.style().unpolish(self._status_pill)
        self._status_pill.style().polish(self._status_pill)

    def _on_editar_clicked(self) -> None:
        """Apretaron 'Editar datos': emite la maquina actual para que el
        controller abra Settings > Maquinas con esta preseleccionada."""
        if self._current_maquina is not None:
            self.editRequested.emit(self._current_maquina)

    def current_maquina(self) -> dict | None:
        """Devuelve la maquina actualmente mostrada (o None)."""
        return self._current_maquina

    def set_history(self, items: list[dict]) -> None:
        """items: lista de {'fecha', 'texto', 'resuelta': bool}."""
        self._clear_history()
        self._set_history(items)

    def _clear_history(self) -> None:
        while self._history_layout.count():
            item = self._history_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _set_history(self, items: list[dict]) -> None:
        if not items:
            empty = QLabel("Sin incidencias previas registradas.")
            empty.setProperty("class", "historyLine")
            self._history_layout.addWidget(empty)
            return
        for it in items:
            line = QFrame()
            h = QHBoxLayout(line)
            h.setContentsMargins(0, 8, 0, 8)
            h.setSpacing(10)
            date_lbl = QLabel(f"<b>{it.get('fecha','')}</b>")
            date_lbl.setStyleSheet("color:#1B2430; font-weight:600; font-size:12.5px;")
            txt_lbl = QLabel(it.get("texto", ""))
            txt_lbl.setStyleSheet("color:#64748B; font-size:12.5px;")
            resuelta = bool(it.get("resuelta"))
            tag = QLabel("Resuelta" if resuelta else "Pendiente")
            tag.setProperty("class", "hStatus")
            tag.setProperty("severity", "ok" if resuelta else "warning")
            tag.setAlignment(Qt.AlignCenter)
            h.addWidget(date_lbl)
            h.addWidget(txt_lbl, 1)
            h.addWidget(tag)
            line.setStyleSheet("QFrame{border-bottom:1px solid #EBEEF3;}")
            self._history_layout.addWidget(line)


__all__ = ("MachinePanel",)
