"""Dialog modal principal: Registro de Actividades Diarias.

Esta es la pantalla que reemplaza la planilla Excel. Muestra una tabla
con todas las actividades (filtrables por fecha, tecnico, area, tarea)
y permite:

  - Registrar una nueva actividad (boton "Nueva")
  - Editar / eliminar actividades existentes
  - Exportar a Excel (.xlsx) para auditoria SCJ (boton "Exportar Excel")
  - Filtrar por rango de fechas y tecnico

Diseno:
  - Patron similar a ``MaquinasProblematicasDialog`` (modal grande con
    tabla + filtros arriba + botones de accion).
  - La tabla tiene 11 columnas, mismo orden que el Excel.
  - Doble click sobre una fila -> abre el form en modo edicion.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Callable, Iterable

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.actividades_db import (
    editar as svc_editar,
    eliminar as svc_eliminar,
    listar_por_rango as svc_listar_rango,
    listar_por_turno as svc_listar_turno,
    registrar as svc_registrar,
)
from services.exportar_actividades import exportar_excel
from services.tecnicos_db import listar as svc_tecnicos_listar
from services.tipos_actividad_db import listar_nombres as svc_tareas_listar
from ui.actividad_form_dialog import ActividadFormDialog
from ui.helpers import svg


# 11 columnas en el mismo orden que el Excel original del operador
COLS: list[str] = [
    "Fecha",          # 0
    "Hora",           # 1
    "Tarea",          # 2
    "Area",           # 3
    "Maquina",        # 4
    "Detalle",        # 5
    "Isla",           # 6
    "Ticket Jira",    # 7
    "N° Ticket",      # 8
    "Pendiente",      # 9
    "Tecnico",        # 10
]
COL_TICKET = COLS.index("Ticket Jira")
COL_PENDIENTE = COLS.index("Pendiente")


def _sn(b) -> str:
    """Bool -> 'si' / 'no' (formato que usa el Excel original)."""
    return "si" if b else "no"


class ActividadesDialog(QDialog):
    """Dialog modal: tabla + filtros + alta/edicion/borrado + export Excel.

    Signals propios: ninguno. El dialog trabaja contra la DB directamente
    via services.actividades_db. Si el controller quiere enterarse de
    cambios, lo hace refrescando sus propios datos.
    """

    def __init__(
        self,
        *,
        parent: QWidget | None = None,
        usuario: str = "",
        turno_actual: str = "",
        maquinas: Iterable[dict] = (),
        tecnicos: Iterable[str] = (),
        tareas: Iterable[str] = (),
        pendiente_solo: bool = False,
    ) -> None:
        super().__init__(parent)
        self._usuario = usuario
        self._turno_actual = turno_actual
        self._maquinas = list(maquinas)
        self._tecnicos = list(tecnicos) or [t["nombre"] if isinstance(t, dict) else t
                                            for t in svc_tecnicos_listar()]
        self._tareas = list(tareas) or svc_tareas_listar()
        self._cache: list[dict] = []  # copia local de las filas mostradas

        self.setObjectName("actividadesDialog")
        self.setWindowTitle("Registro de Actividades Diarias")
        # Tamano generoso: 11 columnas, algunas largas (Detalle).
        self.setMinimumSize(1280, 720)
        self.resize(1400, 780)
        self.setModal(True)

        self._build_ui(pendiente_solo=pendiente_solo)
        # Si el caller abrio el dialog con el filtro "solo pendientes"
        # activado (caso: click en la card 'Tareas pendientes' del
        # dashboard), lo aplicamos antes del primer _refrescar().
        if pendiente_solo:
            self._chk_pendientes.setChecked(True)
        self._refrescar()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self, *, pendiente_solo: bool = False) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Header
        head = QFrame()
        hl = QHBoxLayout(head)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)
        icon = QLabel()
        icon.setPixmap(svg("clipboard", 20).pixmap(20, 20))
        hl.addWidget(icon)
        titulo = QLabel("Registro de Actividades Diarias")
        titulo.setStyleSheet(
            "font-size:15px; font-weight:700; color:#1B2430;"
        )
        hl.addWidget(titulo)
        hl.addStretch(1)
        # Boton nueva
        btn_nueva = QPushButton("  Nueva actividad")
        btn_nueva.setObjectName("btnPrimary")
        btn_nueva.setIcon(svg("plus", 14))
        btn_nueva.setCursor(Qt.PointingHandCursor)
        btn_nueva.clicked.connect(self._on_nueva)
        hl.addWidget(btn_nueva)
        # Boton editar
        self._btn_editar = QPushButton("  Editar")
        self._btn_editar.setObjectName("btnSecondary")
        self._btn_editar.setIcon(svg("edit", 14))
        self._btn_editar.setCursor(Qt.PointingHandCursor)
        self._btn_editar.setEnabled(False)
        self._btn_editar.clicked.connect(self._on_editar)
        hl.addWidget(self._btn_editar)
        # Boton eliminar
        self._btn_eliminar = QPushButton("  Eliminar")
        self._btn_eliminar.setObjectName("btnDanger")
        self._btn_eliminar.setIcon(svg("trash", 14))
        self._btn_eliminar.setCursor(Qt.PointingHandCursor)
        self._btn_eliminar.setEnabled(False)
        self._btn_eliminar.clicked.connect(self._on_eliminar)
        hl.addWidget(self._btn_eliminar)
        # Boton exportar
        btn_export = QPushButton("  Exportar a Excel")
        btn_export.setObjectName("btnSecondary")
        btn_export.setIcon(svg("excel", 14))
        btn_export.setCursor(Qt.PointingHandCursor)
        btn_export.clicked.connect(self._on_exportar)
        hl.addWidget(btn_export)
        layout.addWidget(head)

        sub = QLabel(
            "Reemplaza la planilla Excel diaria. Doble click sobre una "
            "fila para editarla. El export a Excel mantiene el mismo "
            "formato que la SCJ espera."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("color:#64748B; font-size:12px;")
        layout.addWidget(sub)

        # Filtros
        filtros = QFrame()
        fl = QHBoxLayout(filtros)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(10)

        f1 = QLabel("Desde")
        f1.setStyleSheet("color:#1B2430; font-size:12px; font-weight:600;")
        fl.addWidget(f1)
        self._de_desde = QDateEdit()
        self._de_desde.setCalendarPopup(True)
        self._de_desde.setDisplayFormat("dd/MM/yyyy")
        # Default: hace 30 dias. Si el operador entra con el filtro
        # 'Solo pendientes' activado (caso tipico: click en la card del
        # dashboard), extendemos a 90 dias para que se vean tambien
        # las tareas abiertas mas viejas.
        d = date.today()
        self._de_desde.setDate(QDate(d.year, d.month, d.day))
        if pendiente_solo:
            try:
                hace_90 = d.toordinal() - 90
                hace_90_d = date.fromordinal(hace_90)
                self._de_desde.setDate(
                    QDate(hace_90_d.year, hace_90_d.month, hace_90_d.day)
                )
            except Exception:
                pass
        fl.addWidget(self._de_desde)

        f2 = QLabel("Hasta")
        f2.setStyleSheet("color:#1B2430; font-size:12px; font-weight:600;")
        fl.addWidget(f2)
        self._de_hasta = QDateEdit()
        self._de_hasta.setCalendarPopup(True)
        self._de_hasta.setDisplayFormat("dd/MM/yyyy")
        self._de_hasta.setDate(QDate(d.year, d.month, d.day))
        fl.addWidget(self._de_hasta)

        f3 = QLabel("Tecnico")
        f3.setStyleSheet("color:#1B2430; font-size:12px; font-weight:600;")
        fl.addWidget(f3)
        self._cb_filtro_tecnico = QComboBox()
        self._cb_filtro_tecnico.addItem("(Todos)")
        for t in sorted(set(self._tecnicos)):
            if t:
                self._cb_filtro_tecnico.addItem(t)
        fl.addWidget(self._cb_filtro_tecnico)

        f4 = QLabel("Area")
        f4.setStyleSheet("color:#1B2430; font-size:12px; font-weight:600;")
        fl.addWidget(f4)
        self._cb_filtro_area = QComboBox()
        self._cb_filtro_area.addItem("(Todas)")
        from config import AREAS
        for a in AREAS:
            self._cb_filtro_area.addItem(a)
        fl.addWidget(self._cb_filtro_area)

        f5 = QLabel("Tarea")
        f5.setStyleSheet("color:#1B2430; font-size:12px; font-weight:600;")
        fl.addWidget(f5)
        self._cb_filtro_tarea = QComboBox()
        self._cb_filtro_tarea.addItem("(Todas)")
        for ta in sorted(set(self._tareas)):
            if ta:
                self._cb_filtro_tarea.addItem(ta)
        fl.addWidget(self._cb_filtro_tarea)

        chk_pend = QLabel("")
        fl.addWidget(chk_pend)
        from PySide6.QtWidgets import QCheckBox
        self._chk_pendientes = QCheckBox("Solo pendientes")
        fl.addWidget(self._chk_pendientes)

        fl.addStretch(1)

        btn_refrescar = QPushButton("  Refrescar")
        btn_refrescar.setObjectName("btnSecondary")
        btn_refrescar.setIcon(svg("filter", 14))
        btn_refrescar.setCursor(Qt.PointingHandCursor)
        btn_refrescar.clicked.connect(self._refrescar)
        fl.addWidget(btn_refrescar)
        layout.addWidget(filtros)

        # Tabla
        self._tabla = QTableWidget(0, len(COLS))
        self._tabla.setHorizontalHeaderLabels(COLS)
        self._tabla.verticalHeader().setVisible(False)
        self._tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self._tabla.setSelectionMode(QTableWidget.SingleSelection)
        self._tabla.setAlternatingRowColors(True)
        self._tabla.setShowGrid(False)
        self._tabla.verticalHeader().setDefaultSectionSize(32)
        header = self._tabla.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        # Anchos pensados para que el Detalle (largo) y la Fecha se lean bien
        for i, mode in enumerate([
            QHeaderView.ResizeToContents,  # Fecha
            QHeaderView.ResizeToContents,  # Hora
            QHeaderView.ResizeToContents,  # Tarea
            QHeaderView.ResizeToContents,  # Area
            QHeaderView.ResizeToContents,  # Maquina
            QHeaderView.Stretch,           # Detalle (la mas larga)
            QHeaderView.ResizeToContents,  # Isla
            QHeaderView.ResizeToContents,  # Ticket Jira
            QHeaderView.ResizeToContents,  # N° Ticket
            QHeaderView.ResizeToContents,  # Pendiente
            QHeaderView.ResizeToContents,  # Tecnico
        ]):
            header.setSectionResizeMode(i, mode)
        # La columna Hora ahora muestra HH:MM:SS, pero ResizeToContents
        # se ajusta sola al contenido mas largo.
        self._tabla.doubleClicked.connect(self._on_double_click)
        self._tabla.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._tabla, 1)

        # Footer / contador
        self._lbl_count = QLabel("Cargando...")
        self._lbl_count.setStyleSheet("color:#64748B; font-size:12px;")
        layout.addWidget(self._lbl_count)

        # Cerrar
        from PySide6.QtWidgets import QDialogButtonBox
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText("Cerrar")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _refrescar(self) -> None:
        """Recarga la lista aplicando los filtros activos."""
        try:
            qd = self._de_desde.date()
            qh = self._de_hasta.date()
            d_desde = date(qd.year(), qd.month(), qd.day())
            d_hasta = date(qh.year(), qh.month(), qh.day())
            tecnico = self._cb_filtro_tecnico.currentText()
            tecnico = None if tecnico == "(Todos)" else tecnico
            area = self._cb_filtro_area.currentText()
            area = None if area == "(Todas)" else area
            tarea = self._cb_filtro_tarea.currentText()
            tarea = None if tarea == "(Todas)" else tarea
            pendiente_solo = self._chk_pendientes.isChecked()
            self._cache = svc_listar_rango(
                d_desde, d_hasta,
                tecnico=tecnico, area=area, tarea=tarea,
                pendiente_solo=pendiente_solo,
            )
        except Exception as e:
            QMessageBox.warning(self, "Error al cargar", str(e))
            self._cache = []

        self._poblar_tabla()
        n = len(self._cache)
        if n == 0:
            self._lbl_count.setText(
                "Sin actividades en el rango seleccionado. "
                "Podes registrar una con 'Nueva actividad'."
            )
        else:
            self._lbl_count.setText(
                f"{n} {'actividad' if n == 1 else 'actividades'} en el rango."
            )

    def _poblar_tabla(self) -> None:
        self._tabla.setRowCount(0)
        for r in self._cache:
            row = self._tabla.rowCount()
            self._tabla.insertRow(row)

            # Fecha dd/mm/aaaa
            self._set_cell(row, 0, self._fmt_fecha(r.get("fecha")))
            # Hora HH:MM
            self._set_cell(row, 1, r.get("hora", "") or "")
            self._set_cell(row, 2, r.get("tarea", "") or "")
            self._set_cell(row, 3, r.get("area", "") or "")
            self._set_cell(row, 4, r.get("numero_maquina", "") or "")
            self._set_cell(row, 5, r.get("detalle", "") or "")
            self._set_cell(row, 6, r.get("isla", "") or "")
            self._set_cell(row, 7, _sn(r.get("ticket_jira_sn")))
            self._set_cell(row, 8, r.get("numero_ticket_jira", "") or "")
            self._set_cell(row, 9, _sn(r.get("pendiente_sn")))
            self._set_cell(row, 10, r.get("tecnico", "") or "")
            # Guardamos el id en la primera celda (UserRole) para lookup
            self._tabla.item(row, 0).setData(Qt.UserRole, r.get("id"))

        # Autoseleccionar / deshabilitar botones
        self._on_selection_changed()

    def _set_cell(self, row: int, col: int, text: str) -> None:
        item = QTableWidgetItem(str(text))
        # Permitir tooltip largo en el detalle
        if col == 5 and text:
            item.setToolTip(text)
        self._tabla.setItem(row, col, item)

    @staticmethod
    def _fmt_fecha(s) -> str:
        if not s:
            return ""
        if isinstance(s, date):
            return s.strftime("%d/%m/%Y")
        try:
            d = date.fromisoformat(str(s)[:10])
            return d.strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            return str(s)

    # ------------------------------------------------------------------
    # Slots / handlers
    # ------------------------------------------------------------------

    def _on_selection_changed(self) -> None:
        has = bool(self._tabla.selectedItems())
        self._btn_editar.setEnabled(has)
        self._btn_eliminar.setEnabled(has)

    def _on_double_click(self, _index) -> None:
        self._on_editar()

    def _on_nueva(self) -> None:
        dlg = ActividadFormDialog(
            parent=self,
            tecnicos=self._tecnicos,
            tareas=self._tareas,
            preseleccion_tecnico=self._usuario,
            turno_actual=self._turno_actual,
            usuario=self._usuario,
            maquinas=self._maquinas,
        )
        if dlg.exec() != QDialog.Accepted:
            return
        data = dlg.get_data()
        if data is None:
            return
        try:
            svc_registrar(
                tarea=data["tarea"],
                area=data["area"],
                detalle=data["detalle"],
                numero_maquina=data.get("numero_maquina", ""),
                isla=data.get("isla", ""),
                ticket_jira_sn=data.get("ticket_jira_sn", False),
                numero_ticket_jira=data.get("numero_ticket_jira", ""),
                pendiente_sn=data.get("pendiente_sn", False),
                tecnico=data["tecnico"],
                turno=data.get("turno", ""),
                usuario=data.get("usuario", ""),
                fecha=data["fecha"],
                hora=data["hora"],
            )
        except ValueError as e:
            QMessageBox.warning(self, "No se pudo guardar", str(e))
            return
        self._refrescar()

    def _get_selected_id(self) -> int | None:
        rows = self._tabla.selectionModel().selectedRows()
        if not rows:
            return None
        item = self._tabla.item(rows[0].row(), 0)
        if item is None:
            return None
        return item.data(Qt.UserRole)

    def _on_editar(self) -> None:
        aid = self._get_selected_id()
        if aid is None:
            return
        from services.actividades_db import obtener as svc_obtener
        a = svc_obtener(aid)
        if a is None:
            return
        dlg = ActividadFormDialog(
            parent=self,
            tecnicos=self._tecnicos,
            tareas=self._tareas,
            preseleccion_tecnico=a.get("tecnico", ""),
            turno_actual=a.get("turno", ""),
            usuario=self._usuario,
            actividad=a,
            maquinas=self._maquinas,
        )
        if dlg.exec() != QDialog.Accepted:
            return
        data = dlg.get_data()
        if data is None:
            return
        cambios = {
            "tarea": data["tarea"],
            "area": data["area"],
            "numero_maquina": data.get("numero_maquina", ""),
            "detalle": data["detalle"],
            "isla": data.get("isla", ""),
            "ticket_jira_sn": data.get("ticket_jira_sn", False),
            "numero_ticket_jira": data.get("numero_ticket_jira", ""),
            "pendiente_sn": data.get("pendiente_sn", False),
            "tecnico": data["tecnico"],
            "turno": data.get("turno", ""),
        }
        try:
            svc_editar(aid, cambios)
        except ValueError as e:
            QMessageBox.warning(self, "No se pudo guardar", str(e))
            return
        self._refrescar()

    def _on_eliminar(self) -> None:
        aid = self._get_selected_id()
        if aid is None:
            return
        res = QMessageBox.question(
            self,
            "Eliminar actividad",
            "Esta seguro? La fila se borra de la base y no se puede "
            "recuperar.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if res != QMessageBox.Yes:
            return
        try:
            svc_eliminar(aid)
        except Exception as e:
            QMessageBox.warning(self, "No se pudo eliminar", str(e))
            return
        self._refrescar()

    def _on_exportar(self) -> None:
        if not self._cache:
            QMessageBox.information(
                self, "Nada para exportar",
                "No hay actividades en el rango seleccionado.",
            )
            return
        # Nombre de archivo default
        d = date.today()
        default_name = f"actividades_diarias_{d.strftime('%Y%m%d')}.xlsx"
        # Path por defecto: el escritorio si existe, sino la home
        home = Path(os.path.expanduser("~"))
        initial_dir = home / "Desktop" if (home / "Desktop").exists() else home
        initial_path = str(initial_dir / default_name)
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar a Excel", initial_path,
            "Archivos Excel (*.xlsx)",
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        try:
            n = exportar_excel(self._cache, Path(path))
        except OSError as e:
            QMessageBox.critical(
                self, "Error al exportar",
                f"No se pudo escribir el archivo:\n{e}",
            )
            return
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        QMessageBox.information(
            self, "Exportacion OK",
            f"Se exportaron {n} filas a:\n{path}",
        )


__all__ = ("ActividadesDialog",)
