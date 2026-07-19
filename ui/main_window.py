"""Ventana principal del Sistema FDS.

Replica el layout de ``fds_ui.html`` en PySide6:

* Topbar
* Dashboard bar (4 KPI cards: FDS, Pend, Obs, Res)
* 2 paneles lado a lado: Machine (con buscador embebido) | Form
* Tabla inferior
* Footer

Los widgets son 'tontos': emiten senales. Toda la logica vive en
``controllers/main_controller.py``.
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
from ui.dashboard_bar import DashboardBar
from ui.footer import Footer
from ui.form_panel import IncidenciaForm
from ui.helpers import load_stylesheet
from ui.machine_panel import MachinePanel
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
        self._usuario = ""
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

        # Dashboard bar (4 KPI cards grandes)
        self._dashboard = DashboardBar()
        outer.addWidget(self._dashboard)

        # Main area: 2 panels (Machine+Search / Form)
        self._machine_panel = MachinePanel()
        self._form = IncidenciaForm()

        # Alias de compatibilidad: el smoke test y el controller acceden
        # ``w._search_panel``. Ahora el search vive embebido dentro del
        # MachinePanel, asi que exponemos la misma API via property.
        self._search_panel = self._machine_panel.search_panel

        panels = QFrame()
        ph = QHBoxLayout(panels)
        ph.setContentsMargins(16, 6, 16, 0)
        ph.setSpacing(16)
        ph.addWidget(self._machine_panel, 1)
        ph.addWidget(self._form)
        outer.addWidget(panels, 1)

        # Bottom table
        table_wrap = QFrame()
        tw = QVBoxLayout(table_wrap)
        tw.setContentsMargins(16, 16, 16, 16)
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
            return
        self.show_machine(m)
        self.set_form_machine(m)
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

    def set_estado_catalogo(self, *, total: int, operativas: int,
                             en_observacion: int, pendientes: int) -> None:
        """Actualiza las 4 cards KPI del dashboard top Y el footer con
        el estado actual del catalogo de maquinas.

        Es la API principal para refrescar el resumen visual. La usan:
          - controllers/main_controller._refrescar_quick_stats
          - settings (cuando se importa un Excel nuevo)
          - el smoke test

        Cards del dashboard:
          - Total maquinas   (slate)
          - Operativas       (verde)
          - En observacion   (azul)
          - Pendientes       (amber: FDS + Pend Rep + Esp Tec)

        Footer (separado por divisor fuerte):
          - TOTAL MAQUINAS, OPERATIVAS, EN OBSERVACION
        """
        # Dashboard (4 cards grandes arriba)
        self._dashboard.set_estado_catalogo(
            total=total,
            operativas=operativas,
            en_observacion=en_observacion,
            pendientes=pendientes,
        )
        # Footer (3 stats del estado del catalogo, separadas de las del turno)
        self._footer.set_estado_catalogo(
            total=total,
            operativas=operativas,
            en_observacion=en_observacion,
        )

    def set_quick_stats(self, *, fds: int, pendientes: int, resueltas: int,
                        en_observacion: int = 0) -> None:
        """Compat con la firma anterior. Internamente usa set_estado_catalogo.

        ``resueltas`` (metrica del turno) ya no se refleja en el dashboard;
        vive en el footer. ``fds`` se descarta: el dashboard cuenta
        "Pendientes" agregado (no solo FDS).
        """
        # Sin dato de total aqui, el caller deberia usar set_estado_catalogo
        # directamente. Dejamos total en 0 como placeholder visible.
        self._dashboard.set_quick_stats(
            fds=fds,
            pendientes=pendientes,
            resueltas=resueltas,
            en_observacion=en_observacion,
        )

    def set_tecnicos(self, tecnicos: list[str]) -> None:
        self._form.set_tecnicos(tecnicos)

    def set_topbar_usuario(self, nombre: str, rol: str) -> None:
        self._topbar.set_usuario(nombre, rol)

    def set_form_machine(self, m: dict | None) -> None:
        self._form.set_machine(m)
        if m is not None:
            self._form.refresh_datetime()

    def reset_form(self) -> None:
        self._form.reset_fields()

    def set_table_rows(self, rows: list[dict]) -> None:
        self._table.set_rows(rows)

    def set_sending(self, on: bool) -> None:
        self._footer.set_enviando(on)


__all__ = ("MainWindow",)