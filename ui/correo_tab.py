"""Tab Correo: destinatarios, CC, firma, asunto template, modo."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services import configuracion as svc_cfg
from ui.widgets import EditableListWidget


class CorreoTab(QFrame):
    """Tab para configurar el envio del informe por Outlook."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._cargar()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        titulo = QLabel("Configuracion del correo")
        titulo.setStyleSheet("font-size:15px; font-weight:700; color:#1B2430;")
        sub = QLabel(
            "Destinatarios del informe HTML. Soporta varias direcciones "
            "(separadas con ; al enviar). Modo 'Display' muestra el correo "
            "para que revises antes de enviar; 'Send' lo manda directo."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("color:#64748B; font-size:12px;")
        root.addWidget(titulo)
        root.addWidget(sub)

        # Listas de destinatarios y CC
        listas = QFrame()
        ll = QHBoxLayout(listas)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(12)
        self._lista_dest = EditableListWidget(
            titulo="Destinatarios (Para:)",
            placeholder="email@casino.local",
        )
        self._lista_dest.changed.connect(self._on_listas_changed)
        self._lista_cc = EditableListWidget(
            titulo="Copia (CC:)",
            placeholder="email@casino.local",
        )
        self._lista_cc.changed.connect(self._on_listas_changed)
        ll.addWidget(self._lista_dest)
        ll.addWidget(self._lista_cc)
        root.addWidget(listas, 1)

        # Modo de envio
        form = QFormLayout()
        form.setSpacing(10)

        self._cb_modo = QComboBox()
        self._cb_modo.addItems(["display", "send"])
        form.addRow("Modo de envio:", self._cb_modo)

        self._in_asunto = QLineEdit()
        self._in_asunto.setPlaceholderText("Informe Diario FDS - {fecha} - {turno}")
        form.addRow("Plantilla del asunto:", self._in_asunto)

        # Firma
        self._ta_firma = QPlainTextEdit()
        self._ta_firma.setPlaceholderText("Departamento Tecnico y Sistemas\\nCasino Ovalle")
        self._ta_firma.setFixedHeight(80)
        form.addRow("Firma:", self._ta_firma)

        root.addLayout(form)

        btn_save = QPushButton("Guardar cambios")
        btn_save.setObjectName("btnPrimary")
        btn_save.clicked.connect(self._on_save)
        root.addWidget(btn_save)

    def _cargar(self) -> None:
        cfg = svc_cfg.obtener()
        correo = cfg.get("correo", {})
        self._lista_dest.set_items(correo.get("destinatarios", []) or [])
        self._lista_cc.set_items(correo.get("cc", []) or [])
        self._cb_modo.setCurrentText(correo.get("modo_envio", "display"))
        self._in_asunto.setText(correo.get("asunto_template", "Informe Diario FDS - {fecha} - {turno}"))
        self._ta_firma.setPlainText(correo.get("firma", ""))

    def _on_listas_changed(self, *args) -> None:
        # El save real se hace al apretar "Guardar cambios".
        pass

    def _on_save(self) -> None:
        try:
            cfg = svc_cfg.obtener()
            cfg["correo"] = {
                **cfg.get("correo", {}),
                "destinatarios": self._lista_dest.get_items(),
                "cc": self._lista_cc.get_items(),
                "modo_envio": self._cb_modo.currentText(),
                "asunto_template": self._in_asunto.text().strip(),
                "firma": self._ta_firma.toPlainText().strip(),
            }
            svc_cfg.guardar(cfg)
            QMessageBox.information(self, "Guardado", "Configuracion de correo actualizada.")
            self.changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


__all__ = ("CorreoTab",)