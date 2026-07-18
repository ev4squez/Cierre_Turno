"""Dialogo modal para pedir el tecnico que envia el informe.

Antes de generar el correo, esta pantalla obliga al operador a
identificarse: su nombre va a aparecer en el "Enviado por" del HTML
y como firma al pie. Asi el destinatario siempre sabe quien mando el
informe, aunque el sistema sea compartido por varios tecnicos.

UX:

* QComboBox editable con autocomplete de los tecnicos activos de la DB.
* Fallback a texto libre: si el tecnico no esta cargado, se puede
  tipear y se agrega al cerrar (sin persistir en DB, salvo que se
  elija la opcion "Agregar a la lista").
* Preselecciona el "usuario actual" de la DB si existe.
* Botones "Enviar" (accept) y "Cancelar" (reject).
* Validacion: rechaza string vacio o solo whitespace.

Devuelve ``str`` con el nombre (vía ``get_nombre()``) o ``None`` si
se cerro con Cancelar / X.
"""

from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
)


class FirmanteDialog(QDialog):
    """Modal que pide "Quien envia este informe?" antes de mandar."""

    def __init__(
        self,
        *,
        parent=None,
        tecnicos: Iterable[str] | None = None,
        preseleccionado: str = "",
        destinatarios: Iterable[str] = (),
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Quien envia el informe?")
        self.setModal(True)
        self.setMinimumWidth(440)
        self._resultado: str | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        titulo = QLabel("Identifica al tecnico que envia este informe")
        titulo.setStyleSheet("font-size:15px; font-weight:700; color:#1B2430;")
        root.addWidget(titulo)

        sub = QLabel(
            "Tu nombre aparecera en el campo 'Enviado por' del informe "
            "y en la firma al pie. Podes elegir uno de la lista o "
            "tipear uno nuevo."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("color:#64748B; font-size:12px;")
        root.addWidget(sub)

        # Destinatarios (preview, no editables aca)
        dest_list = list(destinatarios or [])
        if dest_list:
            dest_txt = QLabel("Se enviara a: " + ", ".join(dest_list))
            dest_txt.setStyleSheet("color:#475569; font-size:11.5px;")
            dest_txt.setWordWrap(True)
            root.addWidget(dest_txt)

        form = QFormLayout()
        form.setSpacing(10)

        self._cb_nombre = QComboBox()
        self._cb_nombre.setEditable(True)
        self._cb_nombre.setInsertPolicy(QComboBox.NoInsert)
        self._cb_nombre.addItems(sorted({(t or "").strip() for t in (tecnicos or []) if (t or "").strip()}))
        # Si el preseleccionado no esta en la lista, lo agregamos igual
        if preseleccionado and self._cb_nombre.findText(preseleccionado) < 0:
            self._cb_nombre.addItem(preseleccionado)
        if preseleccionado:
            idx = self._cb_nombre.findText(preseleccionado)
            self._cb_nombre.setCurrentIndex(idx if idx >= 0 else 0)
        form.addRow("Tecnico que envia:", self._cb_nombre)

        root.addLayout(form)

        # Botones
        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            parent=self,
        )
        btns.button(QDialogButtonBox.Ok).setText("Enviar informe")
        btns.button(QDialogButtonBox.Cancel).setText("Cancelar")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        # Accesibilidad: Enter dispara accept
        self._cb_nombre.lineEdit().setPlaceholderText(
            "Ej: Elvis Vasquez"
        )

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------

    def get_nombre(self) -> str | None:
        """Devuelve el nombre tipeado o None si se cancelo."""
        return self._resultado

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _on_accept(self) -> None:
        nombre = (self._cb_nombre.currentText() or "").strip()
        if not nombre:
            QMessageBox.warning(
                self,
                "Falta el nombre",
                "Escribe o selecciona el tecnico que envia el informe.",
            )
            return
        self._resultado = nombre
        self.accept()


__all__ = ("FirmanteDialog",)
