"""Dialog modal de alta / edicion de una Actividad Diaria.

UX (mismo patron que ``FirmanteDialog`` + ``IncidenciaForm``):
  - Fecha / Turno autollenados al abrir (editables).
  - Tarea y Area en combo (Area es lista cerrada; Tarea viene de
    services.tipos_actividad_db).
  - Tecnico en combo editable (autocomplete de la lista de tecnicos).
  - Maquina opcional (buscador con resultados live + boton "Limpiar"
    para vaciarla = tarea general del area).
  - Isla, Detalle, Numero ticket Jira segun corresponda.
  - Ticket Jira: combo si/no + textbox condicional.
  - Pendiente: combo si/no.
  - Botones "Guardar" (accept) y "Cancelar" (reject).
  - Devuelve dict con los datos via ``get_data()``, o None si cancelo.

Modos:
  - Alta: pasar ``actividad=None`` (o no pasar nada).
  - Edicion: pasar ``actividad=dict`` con los campos a editar.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Iterable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QDate

from config import AREAS


class ActividadFormDialog(QDialog):
    """Modal para alta / edicion de una Actividad Diaria."""

    def __init__(
        self,
        *,
        parent: QWidget | None = None,
        tecnicos: Iterable[str] = (),
        tareas: Iterable[str] = (),
        preseleccion_tecnico: str = "",
        turno_actual: str = "",
        usuario: str = "",
        actividad: dict | None = None,
        maquinas: Iterable[dict] = (),
    ) -> None:
        super().__init__(parent)
        self._resultado: dict | None = None
        self._usuario = usuario
        self._modo_edicion = actividad is not None
        self._actividad_id = (actividad or {}).get("id")

        titulo = "Editar Actividad" if self._modo_edicion else "Nueva Actividad Diaria"
        self.setWindowTitle(titulo)
        self.setModal(True)
        self.setMinimumSize(720, 620)
        self.resize(760, 660)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # Header
        head = QFrame()
        hl = QHBoxLayout(head)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)
        head_titulo = QLabel(
            "Registra lo que hizo el tecnico durante la jornada. "
            "Reemplaza la planilla Excel diaria."
        )
        head_titulo.setStyleSheet("font-size:13px; color:#475569;")
        head_titulo.setWordWrap(True)
        hl.addWidget(head_titulo)
        root.addWidget(head)

        # Form
        form_frame = QFrame()
        ffl = QVBoxLayout(form_frame)
        ffl.setContentsMargins(0, 0, 0, 0)
        ffl.setSpacing(10)

        # --- Fila 1: Fecha + Turno
        row1 = QFrame()
        r1l = QHBoxLayout(row1)
        r1l.setContentsMargins(0, 0, 0, 0)
        r1l.setSpacing(10)

        fecha_lbl = QLabel("Fecha")
        fecha_lbl.setStyleSheet(
            "color:#1B2430; font-size:12px; font-weight:600;"
        )
        r1l.addWidget(fecha_lbl)
        self._de_fecha = QDateEdit()
        self._de_fecha.setCalendarPopup(True)
        self._de_fecha.setDisplayFormat("dd/MM/yyyy")
        self._de_fecha.setDate(QDate.currentDate())
        r1l.addWidget(self._de_fecha)

        r1l.addSpacing(12)
        turno_lbl = QLabel("Turno")
        turno_lbl.setStyleSheet(
            "color:#1B2430; font-size:12px; font-weight:600;"
        )
        r1l.addWidget(turno_lbl)
        self._cb_turno = QComboBox()
        self._cb_turno.setEditable(True)
        self._cb_turno.addItems(["Manana", "Tarde", "Noche"])
        if turno_actual:
            idx = self._cb_turno.findText(turno_actual)
            if idx >= 0:
                self._cb_turno.setCurrentIndex(idx)
            else:
                self._cb_turno.setCurrentText(turno_actual)
        r1l.addWidget(self._cb_turno, 1)
        ffl.addWidget(row1)

        # --- Fila 2: Tarea + Area
        row2 = QFrame()
        r2l = QHBoxLayout(row2)
        r2l.setContentsMargins(0, 0, 0, 0)
        r2l.setSpacing(10)

        tarea_lbl = QLabel("Tarea *")
        tarea_lbl.setStyleSheet(
            "color:#1B2430; font-size:12px; font-weight:600;"
        )
        r2l.addWidget(tarea_lbl)
        self._cb_tarea = QComboBox()
        self._cb_tarea.setEditable(True)
        # Cargamos los tipos de actividad (los configurables). El placeholder
        # se mete al final para que si el operador quiere tipear uno nuevo
        # no choque con el orden alfabetico.
        lista_tareas = sorted({(t or "").strip() for t in tareas if (t or "").strip()})
        self._cb_tarea.addItem("Seleccionar tarea...")
        self._cb_tarea.addItems(lista_tareas)
        r2l.addWidget(self._cb_tarea, 2)

        r2l.addSpacing(6)
        area_lbl = QLabel("Area *")
        area_lbl.setStyleSheet(
            "color:#1B2430; font-size:12px; font-weight:600;"
        )
        r2l.addWidget(area_lbl)
        self._cb_area = QComboBox()
        self._cb_area.addItem("Seleccionar area...")
        self._cb_area.addItems(list(AREAS))
        r2l.addWidget(self._cb_area, 1)
        ffl.addWidget(row2)

        # --- Fila 3: Maquina (opcional) + Isla
        row3 = QFrame()
        r3l = QHBoxLayout(row3)
        r3l.setContentsMargins(0, 0, 0, 0)
        r3l.setSpacing(10)

        maq_lbl = QLabel("Maquina (opcional)")
        maq_lbl.setStyleSheet(
            "color:#1B2430; font-size:12px; font-weight:600;"
        )
        r3l.addWidget(maq_lbl)
        self._cb_maquina = QComboBox()
        self._cb_maquina.setEditable(True)
        self._cb_maquina.addItem("")  # vacio = tarea general del area
        for m in maquinas:
            label = f"{m.get('numero_maquina', '')} - {m.get('marca', '')} {m.get('modelo', '')}".strip()
            self._cb_maquina.addItem(label, m.get("numero_maquina", ""))
        self._cb_maquina.setCurrentIndex(0)
        self._cb_maquina.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        r3l.addWidget(self._cb_maquina, 2)

        r3l.addSpacing(6)
        isla_lbl = QLabel("Isla")
        isla_lbl.setStyleSheet(
            "color:#1B2430; font-size:12px; font-weight:600;"
        )
        r3l.addWidget(isla_lbl)
        self._in_isla = QLineEdit()
        self._in_isla.setPlaceholderText("Ej: Isla 05")
        self._in_isla.setMaximumWidth(140)
        r3l.addWidget(self._in_isla, 1)
        ffl.addWidget(row3)

        # Hint "tarea general del area"
        self._lbl_maq_hint = QLabel(
            "Si la tarea es para todo el area, deja Maquina vacio."
        )
        self._lbl_maq_hint.setStyleSheet(
            "color:#94A3B8; font-size:11px; font-style:italic;"
        )
        ffl.addWidget(self._lbl_maq_hint)

        # --- Detalle
        det_lbl = QLabel("Detalle *")
        det_lbl.setStyleSheet(
            "color:#1B2430; font-size:12px; font-weight:600;"
        )
        ffl.addWidget(det_lbl)
        self._ta_detalle = QPlainTextEdit()
        self._ta_detalle.setPlaceholderText(
            "Describe lo que se realizo. Ej: 'Se realiza reposicion de "
            "papel, asistencia al cliente, retiro de errores, reinicio "
            "de MDC, retiro de tickets atascados, pagos manuales, "
            "cambios de stacker, se manipula el audio de la sala, etc.'"
        )
        self._ta_detalle.setFixedHeight(130)
        ffl.addWidget(self._ta_detalle)

        # --- Fila 4: Ticket Jira (si/no + numero) + Pendiente + Tecnico
        row4 = QFrame()
        r4l = QHBoxLayout(row4)
        r4l.setContentsMargins(0, 0, 0, 0)
        r4l.setSpacing(10)

        tkt_lbl = QLabel("Ticket Jira?")
        tkt_lbl.setStyleSheet(
            "color:#1B2430; font-size:12px; font-weight:600;"
        )
        r4l.addWidget(tkt_lbl)
        self._cb_ticket_sn = QComboBox()
        self._cb_ticket_sn.addItems(["no", "si"])
        self._cb_ticket_sn.currentTextChanged.connect(self._on_ticket_changed)
        r4l.addWidget(self._cb_ticket_sn)
        self._in_ticket_num = QLineEdit()
        self._in_ticket_num.setPlaceholderText("Numero de ticket")
        self._in_ticket_num.setEnabled(False)
        self._in_ticket_num.setMaximumWidth(180)
        r4l.addWidget(self._in_ticket_num)

        r4l.addSpacing(6)
        pend_lbl = QLabel("Pendiente?")
        pend_lbl.setStyleSheet(
            "color:#1B2430; font-size:12px; font-weight:600;"
        )
        r4l.addWidget(pend_lbl)
        self._cb_pendiente = QComboBox()
        self._cb_pendiente.addItems(["no", "si"])
        r4l.addWidget(self._cb_pendiente)

        r4l.addSpacing(6)
        tec_lbl = QLabel("Tecnico *")
        tec_lbl.setStyleSheet(
            "color:#1B2430; font-size:12px; font-weight:600;"
        )
        r4l.addWidget(tec_lbl)
        self._cb_tecnico = QComboBox()
        self._cb_tecnico.setEditable(True)
        lista_tecs = sorted({(t or "").strip() for t in tecnicos if (t or "").strip()})
        self._cb_tecnico.addItem("Seleccionar tecnico...")
        self._cb_tecnico.addItems(lista_tecs)
        if preseleccion_tecnico:
            idx = self._cb_tecnico.findText(preseleccion_tecnico)
            if idx >= 0:
                self._cb_tecnico.setCurrentIndex(idx)
            else:
                self._cb_tecnico.insertItem(0, preseleccion_tecnico)
                self._cb_tecnico.setCurrentIndex(0)
        r4l.addWidget(self._cb_tecnico, 1)
        ffl.addWidget(row4)

        root.addWidget(form_frame, 1)

        # Botones
        btns = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel,
            parent=self,
        )
        btns.button(QDialogButtonBox.Save).setText("  Guardar actividad")
        btns.button(QDialogButtonBox.Cancel).setText("Cancelar")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        # Si es edicion, precargar campos
        if self._modo_edicion and actividad is not None:
            self._cargar_actividad(actividad)

        # Foco inicial en Tarea
        QTimer.singleShot(50, self._cb_tarea.setFocus)

    # ------------------------------------------------------------------
    # Edicion
    # ------------------------------------------------------------------

    def _cargar_actividad(self, a: dict) -> None:
        """Rellena el form con los datos de una actividad existente."""
        try:
            f = date.fromisoformat(a["fecha"])
            self._de_fecha.setDate(QDate(f.year, f.month, f.day))
        except (KeyError, ValueError, TypeError):
            pass
        # Tarea
        idx = self._cb_tarea.findText(a.get("tarea", ""))
        if idx >= 0:
            self._cb_tarea.setCurrentIndex(idx)
        # Area
        idx = self._cb_area.findText(a.get("area", ""))
        if idx >= 0:
            self._cb_area.setCurrentIndex(idx)
        # Turno
        idx = self._cb_turno.findText(a.get("turno", ""))
        if idx >= 0:
            self._cb_turno.setCurrentIndex(idx)
        else:
            self._cb_turno.setCurrentText(a.get("turno", ""))
        # Maquina
        num_maq = a.get("numero_maquina", "")
        if num_maq:
            # Buscar el item cuyo data == num_maq
            for i in range(self._cb_maquina.count()):
                if self._cb_maquina.itemData(i) == num_maq:
                    self._cb_maquina.setCurrentIndex(i)
                    break
            else:
                # No estaba en la lista del catalogo: la agregamos al inicio
                self._cb_maquina.insertItem(0, f"{num_maq} (manual)", num_maq)
                self._cb_maquina.setCurrentIndex(0)
        # Isla
        self._in_isla.setText(a.get("isla", "") or "")
        # Detalle
        self._ta_detalle.setPlainText(a.get("detalle", "") or "")
        # Ticket Jira
        self._cb_ticket_sn.setCurrentText("si" if a.get("ticket_jira_sn") else "no")
        self._in_ticket_num.setText(a.get("numero_ticket_jira", "") or "")
        self._in_ticket_num.setEnabled(bool(a.get("ticket_jira_sn")))
        # Pendiente
        self._cb_pendiente.setCurrentText("si" if a.get("pendiente_sn") else "no")
        # Tecnico
        idx = self._cb_tecnico.findText(a.get("tecnico", ""))
        if idx >= 0:
            self._cb_tecnico.setCurrentIndex(idx)
        else:
            t = a.get("tecnico", "")
            if t:
                self._cb_tecnico.insertItem(0, t)
                self._cb_tecnico.setCurrentIndex(0)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _on_ticket_changed(self, val: str) -> None:
        self._in_ticket_num.setEnabled(val == "si")
        if val != "si":
            self._in_ticket_num.clear()

    def _on_accept(self) -> None:
        # Validaciones basicas
        tarea = (self._cb_tarea.currentText() or "").strip()
        if not tarea or tarea == "Seleccionar tarea...":
            self._err("Falta la Tarea", "Selecciona o escribe la tarea realizada.")
            self._cb_tarea.setFocus()
            return
        area = (self._cb_area.currentText() or "").strip()
        if not area or area == "Seleccionar area...":
            self._err("Falta el Area", "Selecciona el area a la que se asocia la tarea.")
            self._cb_area.setFocus()
            return
        detalle = (self._ta_detalle.toPlainText() or "").strip()
        if not detalle:
            self._err("Falta el Detalle",
                      "Describe brevemente lo que se realizo.")
            self._ta_detalle.setFocus()
            return
        tecnico = (self._cb_tecnico.currentText() or "").strip()
        if not tecnico or tecnico == "Seleccionar tecnico...":
            self._err("Falta el Tecnico",
                      "Selecciona o escribe el nombre del tecnico.")
            self._cb_tecnico.setFocus()
            return

        # Maquina: si el operador eligio un item del catalogo, sacamos
        # el numero; si tipeo texto libre, usamos el texto.
        maq_text = (self._cb_maquina.currentText() or "").strip()
        maq_data = self._cb_maquina.currentData()
        if maq_data:
            numero_maquina = str(maq_data)
        else:
            # El operador escribio "1234 - Aristocrat MarsX" o similar.
            # Tomamos solo el primer token que parezca numero de maquina.
            numero_maquina = maq_text.split(" - ")[0].strip() if maq_text else ""

        # Ticket Jira
        ticket_sn = (self._cb_ticket_sn.currentText() == "si")
        ticket_num = (self._in_ticket_num.text() or "").strip()
        if not ticket_sn:
            ticket_num = ""

        pendiente = (self._cb_pendiente.currentText() == "si")

        # Fecha
        qd = self._de_fecha.date()
        f = date(qd.year(), qd.month(), qd.day())

        self._resultado = {
            "id": self._actividad_id,
            "fecha": f,
            "hora": datetime.now().time().replace(microsecond=0),
            "tarea": tarea,
            "area": area,
            "numero_maquina": numero_maquina,
            "detalle": detalle,
            "isla": (self._in_isla.text() or "").strip(),
            "ticket_jira_sn": ticket_sn,
            "numero_ticket_jira": ticket_num,
            "pendiente_sn": pendiente,
            "tecnico": tecnico,
            "turno": (self._cb_turno.currentText() or "").strip(),
            "usuario": self._usuario or "",
        }
        self.accept()

    def _err(self, titulo: str, msg: str) -> None:
        QMessageBox.warning(self, titulo, msg)

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def get_data(self) -> dict | None:
        """Devuelve el dict de la actividad o None si se cancelo."""
        return self._resultado


__all__ = ("ActividadFormDialog",)
