"""Dialogo principal de Configuracion (boton de engranaje del topbar).

Tiene 4 tabs:
  1. Empresa  - datos de la empresa
  2. Correo   - destinatarios / CC / firma / modo
  3. Maquinas - CRUD completo con papelera
  4. Tecnicos - CRUD de la lista de tecnicos

Al cerrarse, emite ``finished_with_changes`` para que el controller
refresque la UI principal (form de FDS, quick stats, etc).
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ui.correo_tab import CorreoTab
from ui.empresa_tab import EmpresaTab
from ui.maquinas_tab import MaquinasTab
from ui.tecnicos_tab import TecnicosTab
from ui.tipos_problema_tab import TiposProblemaTab


class SettingsDialog(QDialog):
    """Dialogo modal con tabs de configuracion."""

    finished_with_changes = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configuracion del Sistema")
        self.setMinimumSize(1100, 720)
        self.setModal(True)

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        head = QWidget()
        head.setStyleSheet("background:#FFFFFF; border-bottom:1px solid #E1E6ED;")
        hl = QVBoxLayout(head)
        hl.setContentsMargins(20, 16, 20, 16)
        hl.setSpacing(2)
        titulo = QLabel("Configuracion del Sistema FDS")
        titulo.setStyleSheet("font-size:16px; font-weight:700; color:#1B2430;")
        sub = QLabel("Cambios se guardan al apretar 'Guardar cambios' en cada tab.")
        sub.setStyleSheet("color:#64748B; font-size:12px;")
        hl.addWidget(titulo)
        hl.addWidget(sub)
        root.addWidget(head)

        # Tabs
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setTabPosition(QTabWidget.North)

        self._empresa_tab = EmpresaTab()
        self._empresa_tab.changed.connect(self._on_any_change)
        self._tabs.addTab(self._empresa_tab, "Empresa")

        self._correo_tab = CorreoTab()
        self._correo_tab.changed.connect(self._on_any_change)
        self._tabs.addTab(self._correo_tab, "Correo")

        self._maquinas_tab = MaquinasTab()
        self._maquinas_tab.changed.connect(self._on_maquinas_changed)
        self._tabs.addTab(self._maquinas_tab, "Maquinas")

        self._tecnicos_tab = TecnicosTab()
        self._tecnicos_tab.changed.connect(self._on_any_change)
        self._tabs.addTab(self._tecnicos_tab, "Tecnicos")

        self._tipos_problema_tab = TiposProblemaTab()
        self._tipos_problema_tab.changed.connect(self._on_any_change)
        self._tabs.addTab(self._tipos_problema_tab, "Tipos de problema")

        root.addWidget(self._tabs, 1)

        # Footer con botones
        foot = QWidget()
        foot.setStyleSheet("background:#FFFFFF; border-top:1px solid #E1E6ED;")
        fl = QVBoxLayout(foot)
        fl.setContentsMargins(20, 12, 20, 12)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.button(QDialogButtonBox.Close).setText("Cerrar")
        bb.button(QDialogButtonBox.Close).setObjectName("btnSecondary")
        bb.rejected.connect(self.accept)
        bb.accepted.connect(self.accept)
        fl.addWidget(bb)
        root.addWidget(foot)

    def _on_any_change(self) -> None:
        self.finished_with_changes.emit()

    def _on_maquinas_changed(self) -> None:
        # Si modificaron maquinas, los tecnicos no se afectan, pero
        # el main controller deberia refrescar stats y buscador.
        self.finished_with_changes.emit()


__all__ = ("SettingsDialog",)