"""Tab de gestion de Tecnicos (dentro de SettingsDialog)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from services import admin as svc_admin
from ui.widgets import EditableListWidget


class TecnicosTab(QFrame):
    """UI para editar la lista de tecnicos disponibles.

    Signals
    -------
    changed: emite cuando la lista cambia (lista de strings).
    """

    changed = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._cargar()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        titulo = QLabel("Tecnicos disponibles")
        titulo.setStyleSheet("font-size:15px; font-weight:700; color:#1B2430;")
        sub = QLabel(
            "Lista de tecnicos que aparecen en el combo del formulario de "
            "registro de FDS. Tambien se usan en el informe final."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("color:#64748B; font-size:12px;")
        root.addWidget(titulo)
        root.addWidget(sub)

        self._lista = EditableListWidget(
            titulo="Tecnicos",
            placeholder="Ej: Juan Perez",
        )
        self._lista.changed.connect(self._on_lista_changed)
        root.addWidget(self._lista, 1)

    def _cargar(self) -> None:
        try:
            self._lista.set_items(svc_admin.listar_tecnicos())
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudieron cargar los tecnicos:\n{e}")

    def _on_lista_changed(self, nuevos: list[str]) -> None:
        # El widget maneja duplicados y renombre visualmente.
        # Aqui sincronizamos contra la config.
        from services import configuracion as svc_cfg
        cfg = svc_cfg.obtener()
        cfg["tecnicos"] = list(nuevos)
        svc_cfg.guardar(cfg)
        self.changed.emit(nuevos)

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def refrescar(self) -> None:
        """Recarga desde la config (util cuando otro tab los modifica)."""
        self._cargar()


__all__ = ("TecnicosTab",)