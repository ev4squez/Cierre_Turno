"""Panel central: informacion de la maquina seleccionada + historial."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.helpers import severity_for_estado, svg


class MachinePanel(QFrame):
    """Muestra los datos de la maquina seleccionada + ultimas incidencias."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "panel")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumWidth(420)

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

        # Body
        body = QFrame()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(18, 16, 18, 16)
        bl.setSpacing(12)

        # Machine header (num grande + pill estado)
        machine_header = QFrame()
        mh_layout = QHBoxLayout(machine_header)
        mh_layout.setContentsMargins(0, 0, 0, 0)
        mh_layout.setSpacing(12)
        self._big_num = QLabel("N.\u00ba -")
        self._big_num.setProperty("class", "machineBigNum")

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

        mh_layout.addWidget(self._big_num)
        mh_layout.addStretch(1)
        mh_layout.addWidget(self._status_pill)
        bl.addWidget(machine_header)

        # Info grid 2x4
        grid_host = QFrame()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        self._fields: dict[str, QLabel] = {}
        labels = [
            ("numero_maquina", "Numero de maquina"),
            ("sector", "Sector"),
            ("isla", "Isla"),
            ("marca", "Marca"),
            ("modelo", "Modelo"),
            ("serie", "Serie"),
            ("denominacion", "Denominacion"),
            ("estado", "Estado actual"),
        ]
        for i, (key, lbl) in enumerate(labels):
            row, col = divmod(i, 2)
            cell = QFrame()
            cell.setProperty("class", "field")
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(14, 11, 14, 11)
            cl.setSpacing(5)
            lbl_top = QLabel(lbl.upper())
            lbl_top.setProperty("class", "fieldLabel")
            val = QLabel("-")
            val.setProperty("class", "fieldValue")
            cl.addWidget(lbl_top)
            cl.addWidget(val)
            self._fields[key] = val
            grid.addWidget(cell, row, col)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        bl.addWidget(grid_host)

        # Photo row
        photo = QFrame()
        photo.setProperty("class", "photoRow")
        ph = QHBoxLayout(photo)
        ph.setContentsMargins(14, 14, 14, 14)
        ph.setSpacing(12)
        thumb = QLabel()
        thumb.setPixmap(svg("image", 22).pixmap(22, 22))
        thumb_text = QLabel(
            "Sin fotografia asociada - el operador puede adjuntar una "
            "imagen de referencia de la incidencia."
        )
        thumb_text.setWordWrap(True)
        thumb_text.setStyleSheet("color:#94A3B8; font-size:12px;")
        ph.addWidget(thumb)
        ph.addWidget(thumb_text, 1)
        bl.addWidget(photo)

        # History mini
        bl.addSpacing(8)
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

    def show_empty(self) -> None:
        self._big_num.setText("N.\u00ba -")
        self._set_status("Sin seleccionar", "info")
        for key, lbl in self._fields.items():
            lbl.setText("-")
        self._clear_history()

    def show_machine(self, m: dict) -> None:
        num = str(m.get("numero_maquina") or "-")
        self._big_num.setText(f"N.\u00ba {num}")
        estado = m.get("estado") or "Operativa"
        self._set_status(estado, severity_for_estado(estado))
        for key, lbl in self._fields.items():
            v = m.get(key)
            lbl.setText(str(v) if v not in (None, "") else "-")
        # Por ahora el historial se completa desde fuera (controller).
        # Si no se setea, dejamos el placeholder.
        if self._history_layout.count() == 0:
            self._set_history([
                {"fecha": "10/07/2026", "texto": "Falla en lector de billetes", "resuelta": True},
                {"fecha": "28/06/2026", "texto": "Pantalla intermitente", "resuelta": True},
                {"fecha": "02/06/2026", "texto": "Atasco de impresora de tickets", "resuelta": True},
            ])

    def _set_status(self, text: str, severity: str) -> None:
        self._status_text.setText(text)
        self._status_pill.setProperty("severity", severity)
        self._status_pill.style().unpolish(self._status_pill)
        self._status_pill.style().polish(self._status_pill)

    def set_history(self, items: list[dict]) -> None:
        """items: lista de {'fecha': 'DD/MM/YYYY', 'texto': '...', 'resuelta': bool}."""
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
            date_lbl.setStyleSheet("color:#1B2430; font-weight:600; font-size:12px;")
            txt_lbl = QLabel(f"{it.get('texto','')} - {'Resuelta' if it.get('resuelta') else 'Pendiente'}")
            txt_lbl.setStyleSheet("color:#64748B; font-size:12px;")
            h.addWidget(date_lbl)
            h.addWidget(txt_lbl, 1)
            line.setStyleSheet(
                "QFrame{border-bottom:1px solid #EBEEF3;}"
            )
            self._history_layout.addWidget(line)


__all__ = ("MachinePanel",)