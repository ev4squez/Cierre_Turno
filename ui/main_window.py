"""Ventana principal del Sistema FDS.

Replica exacta de ``fds_ui.html`` en PySide6:

* Topbar
* 3 paneles: Search | Machine | Form
* Tabla inferior
* Footer

Los widgets son 'tontos': emiten senales. Toda la logica vive en
``controllers/main_controller.py`` (fase siguiente).
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from config import load_config
from ui.bottom_table import BottomTablePanel
from ui.footer import Footer
from ui.form_panel import IncidenciaForm
from ui.helpers import load_stylesheet
from ui.machine_panel import MachinePanel
from ui.search_panel import SearchPanel
from ui.topbar import TopBar


class MainWindow(QMainWindow):
    """Ventana principal."""

    settingsRequested = Signal()
    logoutRequested = Signal()
    enviarInformeRequested = Signal()
    searchQueryChanged = Signal(str)
    machineSelected = Signal(dict)
    guardarIncidencia = Signal(dict)
    limpiarForm = Signal()
    editarIncidencia = Signal(int)
    eliminarIncidencia = Signal(int)
    importRequested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Sistema de Registro de Maquinas Fuera de Servicio")
        self.setMinimumSize(1400, 900)

        cfg = load_config()
        self._empresa = cfg["empresa"]["nombre"]
        self._sistema = cfg["empresa"]["departamento"]
        self._usuario = ""  # se completa con set_topbar_usuario() desde el controller
        self._rol = "Operador de sala"

        self._build_ui()
        self._wire_signals()
        self.refresh_header()

    # --- UI ---------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("appRoot")
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Topbar
        self._topbar = TopBar(
            empresa_nombre=self._empresa,
            sistema_nombre="Sistema de Registro de Maquinas Fuera de Servicio",
            usuario_nombre=self._usuario,
            usuario_rol=self._rol,
            fecha_texto="",
            turno_texto="Turno en curso",
        )
        outer.addWidget(self._topbar)

        # Main area: 3 panels + tabla inferior
        self._search_panel = SearchPanel()
        self._machine_panel = MachinePanel()
        self._form = IncidenciaForm()

        panels = QFrame()
        ph = QHBoxLayout(panels)
        ph.setContentsMargins(16, 16, 16, 0)
        ph.setSpacing(16)
        ph.addWidget(self._search_panel)
        ph.addWidget(self._machine_panel, 1)
        ph.addWidget(self._form)
        outer.addWidget(panels, 1)

        # Bottom table
        table_wrap = QFrame()
        tw = QVBoxLayout(table_wrap)
        tw.setContentsMargins(16, 0, 16, 16)
        tw.setSpacing(0)
        self._table = BottomTablePanel()
        tw.addWidget(self._table)
        outer.addWidget(table_wrap, 1)

        # Footer
        self._footer = Footer()
        outer.addWidget(self._footer)

    def _wire_signals(self) -> None:
        self._topbar.settingsClicked.connect(self.settingsRequested.emit)
        self._topbar.logoutClicked.connect(self._confirm_logout)
        self._topbar.importClicked.connect(self.importRequested.emit)
        self._footer.enviarInforme.connect(self.enviarInformeRequested.emit)
        self._search_panel.queryChanged.connect(self.searchQueryChanged.emit)
        self._search_panel.machineSelected.connect(self._on_machine_selected)
        self._form.guardar.connect(self.guardarIncidencia.emit)
        self._form.limpiar.connect(self.limpiarForm.emit)
        self._table.editar.connect(self.editarIncidencia.emit)
        self._table.eliminar.connect(self.eliminarIncidencia.emit)

    def _on_machine_selected(self, m: dict) -> None:
        """Slot interno: propaga la seleccion al panel central y al form."""
        if not isinstance(m, dict) or "numero_maquina" not in m:
            # Si llega algo raro, ignorar en vez de romper la UI
            return
        self.show_machine(m)
        self.set_form_machine(m)
        # Tambien emite al exterior por si el controller quiere hacer algo mas
        self.machineSelected.emit(m)

    def _confirm_logout(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        res = QMessageBox.question(
            self,
            "Salir",
            "Cerrar el sistema? Los registros del turno quedan guardados.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if res == QMessageBox.Yes:
            self.logoutRequested.emit()

    # --- API --------------------------------------------------------------

    def refresh_header(self) -> None:
        now = datetime.now()
        dias = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
        meses = [
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
        ]
        fecha_txt = f"{dias[now.weekday()].capitalize()}, {now.day} de {meses[now.month-1]} de {now.year}"
        self._topbar.set_fecha(fecha_txt)
        cfg = load_config()
        turno_cfg = cfg.get("turno", {})
        # Determinar turno por hora
        h = now.hour
        if 8 <= h < 14:
            t = turno_cfg.get("manana", {"etiqueta": "Manana", "rango": "08:00-14:00"})
        elif 14 <= h < 22:
            t = turno_cfg.get("tarde", {"etiqueta": "Tarde", "rango": "14:00-22:00"})
        else:
            t = turno_cfg.get("noche", {"etiqueta": "Noche", "rango": "22:00-06:00"})
        self._topbar.set_turno(f"Turno {t.get('etiqueta','Tarde')} - {t.get('rango','')}")

    def set_search_results(self, maquinas: Iterable[dict]) -> None:
        self._search_panel.set_results(list(maquinas))

    def show_machine(self, m: dict | None) -> None:
        if m is None:
            self._machine_panel.show_empty()
        else:
            self._machine_panel.show_machine(m)

    def set_quick_stats(self, *, fds: int, pendientes: int, resueltas: int) -> None:
        self._search_panel.set_quick_stats(fds, pendientes, resueltas)

    def set_tecnicos(self, tecnicos: list[str]) -> None:
        self._form.set_tecnicos(tecnicos)

    def set_topbar_usuario(self, nombre: str, rol: str) -> None:
        """Actualiza el chip de usuario del topbar (avatar + nombre + rol).

        Llamado por el controller cuando detecta cambios en la DB
        (ej. el operador cambio su nombre en Settings). Asi el topbar
        refleja el cambio sin tener que reiniciar la app.
        """
        self._topbar.set_usuario(nombre, rol)

    def set_form_machine(self, m: dict | None) -> None:
        self._form.set_machine(m)
        if m is not None:
            self._form.refresh_datetime()

    def reset_form(self) -> None:
        self._form.reset_fields()

    def set_table_rows(self, rows: list[dict]) -> None:
        self._table.set_rows(rows)

    def set_footer(self, *, total: int, maquinas: int, pendientes: int, inicio_turno: str) -> None:
        self._footer.set_totales(total=total, maquinas=maquinas, pendientes=pendientes)
        self._footer.set_inicio_turno(inicio_turno)

    def set_sending(self, on: bool) -> None:
        self._footer.set_enviando(on)


__all__ = ("MainWindow",)