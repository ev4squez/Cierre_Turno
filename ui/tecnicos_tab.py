"""Tab de gestion de Tecnicos (dentro de SettingsDialog).

Lee y escribe en la DB via ``services.tecnicos_db``. Antes vivia en
config.json; ahora es una tabla SQLite para que los cambios se
reflejen en vivo en el topbar sin reiniciar la app.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services import tecnicos_db
from ui.widgets import EditableListWidget


class TecnicosTab(QFrame):
    """UI para editar la lista de tecnicos y elegir el usuario actual.

    Signals
    -------
    changed: emite cuando la lista o el usuario actual cambia.
    """

    changed = Signal()

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
            "registro de FDS. El marcado con estrella es el operador actual "
            "del sistema (se muestra en el topbar)."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("color:#64748B; font-size:12px;")
        root.addWidget(titulo)
        root.addWidget(sub)

        # Banda del usuario actual
        self._actual_box = QFrame()
        self._actual_box.setStyleSheet(
            "QFrame{background:#EAF1FB; border:1px solid #C7DBF5; border-radius:8px; padding:6px 10px;}"
            "QLabel{color:#1E5AA8; font-size:12px;}"
        )
        ab = QHBoxLayout(self._actual_box)
        ab.setContentsMargins(10, 6, 10, 6)
        self._lbl_actual = QLabel("Operador actual: (sin definir)")
        self._lbl_actual.setStyleSheet("font-weight:700; color:#1B2430;")
        ab.addWidget(self._lbl_actual)
        ab.addStretch(1)
        self._btn_hacer_actual = QPushButton("Marcar como operador actual")
        self._btn_hacer_actual.setObjectName("btnPrimary")
        self._btn_hacer_actual.setEnabled(False)
        self._btn_hacer_actual.clicked.connect(self._on_hacer_actual)
        ab.addWidget(self._btn_hacer_actual)
        root.addWidget(self._actual_box)

        # Lista editable
        self._lista = EditableListWidget(
            titulo="Tecnicos",
            placeholder="Ej: Juan Perez",
        )
        self._lista.changed.connect(self._on_lista_changed)
        self._lista._lista.itemSelectionChanged.connect(self._on_seleccion_tecnico)
        root.addWidget(self._lista, 1)

    def _cargar(self) -> None:
        try:
            tecnicos = tecnicos_db.listar(incluir_inactivos=False)
            self._lista.set_items([t["nombre"] for t in tecnicos])
            actual = tecnicos_db.obtener_usuario_actual()
            if actual is not None:
                self._lbl_actual.setText(f"Operador actual: {actual['nombre']}")
            else:
                self._lbl_actual.setText("Operador actual: (sin definir)")
        except Exception as e:
            QMessageBox.warning(
                self, "Error", f"No se pudieron cargar los tecnicos:\n{e}"
            )

    def _on_lista_changed(self, nuevos: list[str]) -> None:
        """Sincroniza los cambios de la lista con la DB."""
        try:
            actuales = {t["nombre"] for t in tecnicos_db.listar(incluir_inactivos=True)}
            entrantes = set(nuevos)
            # Agregar los nuevos
            for nombre in entrantes - actuales:
                tecnicos_db.agregar(nombre)
            # Soft-delete los que se quitaron
            for nombre in actuales - entrantes:
                tecnicos_db.eliminar(nombre)
            self.changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar la lista:\n{e}")

    def _on_seleccion_tecnico(self) -> None:
        """Habilita el boton 'Marcar como operador actual' cuando hay seleccion."""
        self._btn_hacer_actual.setEnabled(self._lista._lista.currentRow() >= 0)

    def _on_hacer_actual(self) -> None:
        """Marca el tecnico seleccionado como el operador actual del sistema."""
        item = self._lista._lista.currentItem()
        if item is None:
            return
        nombre = item.text()
        try:
            tecnicos_db.marcar_como_usuario_actual(nombre)
            self._cargar()
            self.changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def refrescar(self) -> None:
        """Recarga desde la DB (util cuando otro tab los modifica)."""
        self._cargar()


__all__ = ("TecnicosTab",)