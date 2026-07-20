"""Panel derecho: formulario de registro de FDS."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from config import ESTADOS_MAQUINA, TIPOS_PROBLEMA


class IncidenciaForm(QFrame):
    """Formulario de 'Registrar Fuera de Servicio'.

    Signals
    -------
    guardar(dict):  se emite con los datos cuando el usuario confirma
    limpiar():      se emite cuando toca 'Limpiar'
    """

    guardar = Signal(dict)
    limpiar = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "panel")
        self.setObjectName("panelForm")
        self.setMinimumWidth(440)
        self.setMaximumWidth(560)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self._build_ui()
        self.set_disabled(True)
        # ID de la incidencia en modo edicion. None = modo alta nueva.
        self._editando_id: int | None = None

        # Autosave: cuando el operador escribe, guardamos un borrador
        # en la DB (con debounce de 2 segundos). Asi si la app se
        # cierra / crashea / el operador se olvida de 'Guardar Registro',
        # el borrador queda y se le ofrece restaurar al volver.
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(2000)
        self._autosave_timer.timeout.connect(self._autosave_borrador)
        # Disparamos autosave cuando cambian los combos o textareas
        self._cb_tecnico["widget"].currentTextChanged.connect(self._schedule_autosave)
        self._cb_tipo["widget"].currentTextChanged.connect(self._schedule_autosave)
        self._cb_estado["widget"].currentTextChanged.connect(self._schedule_autosave)
        self._ta_motivo["widget"].textChanged.connect(self._schedule_autosave)
        self._ta_accion["widget"].textChanged.connect(self._schedule_autosave)
        self._ta_obs.changed.connect(self._schedule_autosave)

    def _schedule_autosave(self, *_args) -> None:
        """Reinicia el timer (debounce)."""
        self._autosave_timer.start()

    def _autosave_borrador(self) -> None:
        """Persiste el form actual como borrador (si hay maquina cargada)."""
        self._on_borrador_cambia({})

    def _on_borrador_cambia(self, _data: dict) -> None:
        """Escribe el estado actual del form en la tabla borradores."""
        if self._editando_id is not None:
            return  # en modo edicion no guardamos borrador
        maquina = self._in_maquina["widget"].text().strip()
        tecnico = self._cb_tecnico["widget"].currentText().strip()
        if not maquina or not tecnico or tecnico == "Seleccionar tecnico...":
            return
        try:
            from services import borradores as svc_bor
            svc_bor.guardar(
                maquina_numero=maquina,
                tecnico=tecnico,
                data={
                    "problema": self._cb_tipo["widget"].currentText(),
                    "motivo_fuera_servicio": self._ta_motivo["widget"].toPlainText(),
                    "accion_realizada": self._ta_accion["widget"].toPlainText(),
                    "estado_final": self._cb_estado["widget"].currentText(),
                    "observaciones": self._ta_obs.get_text(),
                },
            )
        except Exception:
            pass  # best-effort

    def _cargar_borrador(self, maquina: str, tecnico: str) -> bool:
        """Si hay un borrador guardado para esta maquina + tecnico,
        lo restaura en el form. Retorna True si restauro algo.
        """
        try:
            from services import borradores as svc_bor
            b = svc_bor.obtener(maquina, tecnico)
        except Exception:
            return False
        if not b:
            return False
        # Solo restauramos si los campos no estan vacios
        if not (b.get("motivo_fuera_servicio") or b.get("accion_realizada")
                or b.get("observaciones")):
            return False
        # Restaurar combos primero
        idx = self._cb_tipo["widget"].findText(b.get("problema", ""))
        if idx >= 0:
            self._cb_tipo["widget"].setCurrentIndex(idx)
        idx = self._cb_estado["widget"].findText(b.get("estado_final", ""))
        if idx >= 0:
            self._cb_estado["widget"].setCurrentIndex(idx)
        self._ta_motivo["widget"].setPlainText(
            b.get("motivo_fuera_servicio", "")
        )
        self._ta_accion["widget"].setPlainText(b.get("accion_realizada", ""))
        self._ta_obs.set_text(b.get("observaciones", ""))
        return True

    # --- UI --------------------------------------------------------------

    def _build_ui(self) -> None:
        head = QFrame()
        head.setProperty("class", "panelHead")
        h = QHBoxLayout(head)
        h.setContentsMargins(18, 12, 18, 12)
        h.setSpacing(8)
        icon_lbl = QLabel()
        icon_lbl.setText("+")
        icon_lbl.setStyleSheet("color:#1E5AA8; font-weight:700; font-size:18px;")
        icon_lbl.setProperty("class", "panelIcon")
        title = QLabel("Registrar Fuera de Servicio")
        title.setProperty("class", "panelTitle")
        h.addWidget(icon_lbl)
        h.addWidget(title)
        h.addStretch(1)

        body = QFrame()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(18, 16, 18, 16)
        bl.setSpacing(14)

        # Fecha / Hora (autollenados, disabled)
        row_fh = QFrame()
        rfh = QHBoxLayout(row_fh)
        rfh.setContentsMargins(0, 0, 0, 0)
        rfh.setSpacing(10)
        self._in_fecha = self._field_text("Fecha", "", disabled=True)
        self._in_hora = self._field_text("Hora", "", disabled=True)
        rfh.addWidget(self._in_fecha["host"], 1)
        rfh.addWidget(self._in_hora["host"], 1)
        bl.addWidget(row_fh)

        # Maquina (autollenada, disabled)
        self._in_maquina = self._field_text("Maquina", "", disabled=True)
        bl.addWidget(self._in_maquina["host"])

        # Tecnico
        self._cb_tecnico = self._field_combo("Tecnico responsable *", [])
        bl.addWidget(self._cb_tecnico["host"])

        # Tipo de problema: se llena por API (set_tipos_problema) desde
        # el controller, que lee de la DB. El fallback a TIPOS_PROBLEMA
        # (constante de modulo) sirve para cuando se construye el form
        # sin DB todavia disponible (ej. tests offscreen sin DB).
        self._cb_tipo = self._field_combo(
            "Tipo de problema *",
            ["Seleccionar tipo..."] + list(TIPOS_PROBLEMA),
        )
        bl.addWidget(self._cb_tipo["host"])

        # Motivo FDS
        self._ta_motivo = self._field_textarea(
            "Motivo Fuera de Servicio *",
            "Ej: Reinicio constante de la maquina",
        )
        bl.addWidget(self._ta_motivo["host"])

        # Accion realizada
        self._ta_accion = self._field_textarea(
            "Accion realizada",
            "Detalle que hizo el tecnico",
        )
        bl.addWidget(self._ta_accion["host"])

        # Estado final
        self._cb_estado = self._field_combo(
            "Estado final *",
            ["Seleccionar estado..."] + list(ESTADOS_MAQUINA),
        )
        bl.addWidget(self._cb_estado["host"])

        # Observaciones: nuevo widget con plantillas + texto libre
        from ui.obs_widget import ObservacionWidget
        obs_host = QFrame()
        obs_layout = QVBoxLayout(obs_host)
        obs_layout.setContentsMargins(0, 0, 0, 0)
        obs_layout.setSpacing(6)
        obs_label = QLabel("Observaciones")
        obs_label.setProperty("class", "formLabel")
        obs_layout.addWidget(obs_label)
        self._ta_obs = ObservacionWidget()
        obs_layout.addWidget(self._ta_obs)
        bl.addWidget(obs_host)

        # Botones
        actions = QFrame()
        al = QHBoxLayout(actions)
        al.setContentsMargins(0, 4, 0, 0)
        al.setSpacing(10)
        self._btn_limpiar = QPushButton("Cancelar")
        self._btn_limpiar.setObjectName("btnSecondary")
        self._btn_limpiar.setCursor(Qt.PointingHandCursor)
        self._btn_limpiar.setToolTip("Descartar cambios y volver al estado inicial")
        self._btn_limpiar.clicked.connect(self._on_limpiar)

        self._btn_guardar = QPushButton("  Guardar Registro (Enter)")
        self._btn_guardar.setObjectName("btnPrimary")
        self._btn_guardar.setCursor(Qt.PointingHandCursor)
        self._btn_guardar.setShortcut("Ctrl+Return")  # atajo bonus
        self._btn_guardar.clicked.connect(self._on_guardar)
        al.addWidget(self._btn_limpiar)
        al.addWidget(self._btn_guardar, 1)
        bl.addWidget(actions)

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

    # --- helpers de campos ----------------------------------------------

    def _field_text(self, label: str, value: str, *, disabled: bool = False) -> dict:
        host = QFrame()
        v = QVBoxLayout(host)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        lbl = QLabel(label)
        lbl.setProperty("class", "formLabel")
        from PySide6.QtWidgets import QLineEdit
        le = QLineEdit(value)
        le.setDisabled(disabled)
        v.addWidget(lbl)
        v.addWidget(le)
        return {"host": host, "widget": le}

    def _field_combo(self, label: str, options: list[str]) -> dict:
        host = QFrame()
        v = QVBoxLayout(host)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        lbl = QLabel(label)
        lbl.setProperty("class", "formLabel")
        cb = QComboBox()
        cb.addItems(options)
        v.addWidget(lbl)
        v.addWidget(cb)
        return {"host": host, "widget": cb}

    def _field_textarea(self, label: str, placeholder: str) -> dict:
        host = QFrame()
        v = QVBoxLayout(host)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        lbl = QLabel(label)
        lbl.setProperty("class", "formLabel")
        ta = QPlainTextEdit()
        ta.setPlaceholderText(placeholder)
        ta.setFixedHeight(70 if "Motivo" in label or "Accion" in label or "Obser" in label else 90)
        v.addWidget(lbl)
        v.addWidget(ta)
        return {"host": host, "widget": ta}

    # --- API --------------------------------------------------------------

    def set_tecnicos(self, tecnicos: list[str]) -> None:
        cb = self._cb_tecnico["widget"]
        cb.clear()
        cb.addItem("Seleccionar tecnico...")
        cb.addItems(tecnicos)

    def set_tipos_problema(self, tipos: list[str]) -> None:
        """Reemplaza los items del combo 'Tipo de problema'.

        Llamado por el controller cuando arranca la app o cuando el
        operador modifica los tipos desde Settings. Si ``tipos`` viene
        vacio (caso raro), cae al default de ``config.TIPOS_PROBLEMA``
        asi el combo nunca queda sin opciones.
        """
        cb = self._cb_tipo["widget"]
        actual = cb.currentText()
        cb.blockSignals(True)
        try:
            cb.clear()
            cb.addItem("Seleccionar tipo...")
            opciones = tipos if tipos else list(TIPOS_PROBLEMA)
            cb.addItems(opciones)
            # Si el valor que estaba seleccionado sigue existiendo, lo
            # restauramos. Si no, dejamos el placeholder.
            if actual and actual != "Seleccionar tipo...":
                idx = cb.findText(actual)
                if idx >= 0:
                    cb.setCurrentIndex(idx)
        finally:
            cb.blockSignals(False)

    def set_machine(self, m: dict | None) -> None:
        """Carga la maquina seleccionada. Si es None, deshabilita."""
        if m is None:
            self.set_disabled(True)
            self._in_maquina["widget"].setText("")
            return
        self.set_disabled(False)
        self._in_maquina["widget"].setText(str(m.get("numero_maquina", "")))
        # Sugerir estado actual de la maquina
        idx = self._cb_estado["widget"].findText(m.get("estado", "Fuera de Servicio"))
        if idx >= 0:
            self._cb_estado["widget"].setCurrentIndex(idx)

        # Si hay un borrador guardado para esta maquina + tecnico
        # actual, lo restauramos silenciosamente.
        tecnico = self._cb_tecnico["widget"].currentText().strip()
        if (tecnico and tecnico != "Seleccionar tecnico..."
                and not self._editando_id):
            self._cargar_borrador(str(m.get("numero_maquina", "")), tecnico)

    def has_data(self) -> bool:
        """True si el operador ya empezo a cargar algo (para Esc)."""
        # Maquina cargada Y alguno de los campos de texto tiene contenido
        maquina = self._in_maquina["widget"].text().strip()
        motivo = self._ta_motivo["widget"].toPlainText().strip()
        accion = self._ta_accion["widget"].toPlainText().strip()
        obs = self._ta_obs.get_text().strip()
        return bool(maquina and (motivo or accion or obs))

    def focus_maquina(self) -> None:
        """Pone el foco en el primer campo del form (util para Ctrl+N)."""
        # El campo maquina es disabled hasta que se selecciona una del buscador.
        # Asi que el foco va al buscador (que ya existe via _search_panel).
        try:
            self._search_panel.focus_search()
        except Exception:
            pass

    def set_disabled(self, disabled: bool) -> None:
        for cb in (self._cb_tecnico["widget"], self._cb_tipo["widget"], self._cb_estado["widget"]):
            cb.setEnabled(not disabled)
        for ta in (self._ta_motivo["widget"], self._ta_accion["widget"]):
            ta.setReadOnly(disabled)
        self._btn_guardar.setEnabled(not disabled)
        self._btn_limpiar.setEnabled(True)

    def refresh_datetime(self) -> None:
        now = datetime.now()
        self._in_fecha["widget"].setText(now.strftime("%d/%m/%Y"))
        self._in_hora["widget"].setText(now.strftime("%H:%M"))

    def reset_fields(self, *, borrar_borrador: bool = True) -> None:
        """Limpia el form a su estado inicial.

        Si ``borrar_borrador`` es True (default), elimina el borrador
        asociado a la maquina actual. Eso pasa cuando se limpia el form
        despues de un 'Guardar Registro' exitoso o cuando el operador
        aprieta 'Limpiar'. Si el caller quiere NO borrar el borrador
        (ej: cambios temporales), pasa False.
        """
        maquina = self._in_maquina["widget"].text().strip()
        tecnico = self._cb_tecnico["widget"].currentText().strip()
        self._cb_tecnico["widget"].setCurrentIndex(0)
        self._cb_tipo["widget"].setCurrentIndex(0)
        self._cb_estado["widget"].setCurrentIndex(0)
        self._ta_motivo["widget"].clear()
        self._ta_accion["widget"].clear()
        self._ta_obs.set_text("")
        self.refresh_datetime()
        # Borrar borrador persistido si hay maquina + tecnico
        if borrar_borrador and maquina and tecnico and tecnico != "Seleccionar tecnico...":
            try:
                from services import borradores as svc_bor
                svc_bor.eliminar(maquina, tecnico)
            except Exception:
                pass
        # Salir del modo edicion
        self._editando_id = None

    # --- handlers ---------------------------------------------------------

    def _on_guardar(self) -> None:
        tipo = self._cb_tipo["widget"].currentText()
        motivo = self._ta_motivo["widget"].toPlainText().strip()
        estado = self._cb_estado["widget"].currentText()
        tecnico = self._cb_tecnico["widget"].currentText()
        problema = (
            tipo if tipo and tipo != "Seleccionar tipo..." else ""
        )
        if not motivo:
            self._mark_error(self._ta_motivo["widget"], True)
            return
        self._mark_error(self._ta_motivo["widget"], False)
        if not estado or estado == "Seleccionar estado...":
            self._mark_error(self._cb_estado["widget"], True)
            return
        self._mark_error(self._cb_estado["widget"], False)
        if not tecnico or tecnico == "Seleccionar tecnico...":
            self._mark_error(self._cb_tecnico["widget"], True)
            return
        self._mark_error(self._cb_tecnico["widget"], False)
        if not problema:
            self._mark_error(self._cb_tipo["widget"], True)
            return
        self._mark_error(self._cb_tipo["widget"], False)

        data = {
            "problema": problema,
            "motivo_fuera_servicio": motivo,
            "accion_realizada": self._ta_accion["widget"].toPlainText().strip(),
            "estado_final": estado,
            "observaciones": self._ta_obs.get_text().strip(),
            "tecnico": tecnico,
        }
        # Feedback auditivo nativo del sistema (sin archivos externos)
        from PySide6.QtWidgets import QApplication
        QApplication.beep()
        self.guardar.emit(data)

    def _mark_error(self, widget, on: bool) -> None:
        if on:
            widget.setStyleSheet("border: 1.5px solid #DC2626;")
        else:
            widget.setStyleSheet("")

    def _on_limpiar(self) -> None:
        self.reset_fields()
        self.limpiar.emit()


__all__ = ("IncidenciaForm",)