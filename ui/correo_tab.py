"""Tab Correo: destinatarios, CC, firma, asunto template, modo,
y desde 2026-07: servidor SMTP directo (alternativa a Outlook clasico
para el operador que trabaja con el 'Nuevo Outlook' / app Mail de
Win11 - que no expone COM).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
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

        # --- Seccion SMTP (alternativa a Outlook clasico) ---
        separador = QFrame()
        separador.setFrameShape(QFrame.HLine)
        separador.setFrameShadow(QFrame.Sunken)
        root.addWidget(separador)

        smtp_titulo = QLabel("Servidor SMTP (alternativa a Outlook)")
        smtp_titulo.setStyleSheet(
            "font-size:13px; font-weight:700; color:#1B2430;"
        )
        root.addWidget(smtp_titulo)

        smtp_sub = QLabel(
            "Si tu Outlook clasico no esta instalado (ej. usas el 'Nuevo "
            "Outlook' / app Mail de Windows 11), podes configurar un SMTP "
            "para enviar el informe directamente. Para M365: host "
            "smtp.office365.com, puerto 587, y como password usa un "
            "'App Password' (no la password normal)."
        )
        smtp_sub.setWordWrap(True)
        smtp_sub.setStyleSheet("color:#64748B; font-size:12px;")
        root.addWidget(smtp_sub)

        smtp_form = QFormLayout()
        smtp_form.setSpacing(8)

        # Dropdown: proveedor SMTP. Al cambiar, autocompleta host/puerto/
        # TLS y muestra las instrucciones para generar el App Password.
        from services import smtp_profiles
        self._cb_perfil = QComboBox()
        self._perfiles = {p["key"]: p for p in smtp_profiles.get_profiles()}
        for p in smtp_profiles.get_profiles():
            self._cb_perfil.addItem(p["label"], p["key"])
        self._cb_perfil.currentIndexChanged.connect(self._on_perfil_changed)
        smtp_form.addRow("Proveedor:", self._cb_perfil)

        # Help text: instrucciones por proveedor (cambia al cambiar dropdown)
        self._lb_smtp_help = QLabel("")
        self._lb_smtp_help.setWordWrap(True)
        self._lb_smtp_help.setStyleSheet(
            "color:#475569; font-size:11px; padding:6px; "
            "background:#F1F5F9; border-radius:4px;"
        )
        self._lb_smtp_help.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        smtp_form.addRow(self._lb_smtp_help)

        self._chk_smtp_enabled = QCheckBox(
            "Enviar via SMTP en lugar de Outlook clasico"
        )
        self._chk_smtp_enabled.toggled.connect(self._on_smtp_toggle)
        smtp_form.addRow(self._chk_smtp_enabled)

        self._in_smtp_host = QLineEdit()
        self._in_smtp_host.setPlaceholderText("smtp.gmail.com o smtp.office365.com")
        smtp_form.addRow("Servidor SMTP:", self._in_smtp_host)

        self._sp_smtp_port = QSpinBox()
        self._sp_smtp_port.setRange(1, 65535)
        self._sp_smtp_port.setValue(587)
        smtp_form.addRow("Puerto:", self._sp_smtp_port)

        self._in_smtp_user = QLineEdit()
        self._in_smtp_user.setPlaceholderText("email-del-casino@gmail.com")
        smtp_form.addRow("Usuario:", self._in_smtp_user)

        self._in_smtp_password = QLineEdit()
        self._in_smtp_password.setEchoMode(QLineEdit.Password)
        self._in_smtp_password.setPlaceholderText("App Password (16 chars)")
        smtp_form.addRow("Password:", self._in_smtp_password)

        self._chk_smtp_tls = QCheckBox(
            "Usar TLS/STARTTLS (recomendado para puerto 587)"
        )
        smtp_form.addRow(self._chk_smtp_tls)

        # Botones: 'Probar conexion' + 'Guardar cambios'
        smtp_btns = QHBoxLayout()
        smtp_btns.setContentsMargins(0, 0, 0, 0)
        smtp_btns.setSpacing(8)
        self._btn_probar_smtp = QPushButton("  Probar conexion")
        self._btn_probar_smtp.setObjectName("btnSecondary")
        self._btn_probar_smtp.clicked.connect(self._on_probar_smtp)
        smtp_btns.addWidget(self._btn_probar_smtp)
        smtp_btns.addStretch(1)
        smtp_form.addRow(smtp_btns)

        root.addLayout(smtp_form)
        # Inicialmente deshabilitado (se habilita al tildar el check)
        self._on_smtp_toggle(False)

        # Recordamos si SMTP esta habilitado para mostrar feedback
        self._smtp_enabled_state = False

        # Boton guardar (abajo de TODO, queda al final del tab)
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
        # Perfil SMTP: si esta persistido y existe, lo seleccionamos.
        # Si no, default = 'gmail' (mas facil para el operador).
        perfil_key = correo.get("smtp_perfil", "gmail")
        idx = self._cb_perfil.findData(perfil_key)
        if idx >= 0:
            self._cb_perfil.setCurrentIndex(idx)
        # SMTP
        self._chk_smtp_enabled.setChecked(bool(correo.get("smtp_enabled", False)))
        self._in_smtp_host.setText(correo.get("smtp_host", "smtp.gmail.com"))
        self._sp_smtp_port.setValue(int(correo.get("smtp_port", 587)))
        self._in_smtp_user.setText(correo.get("smtp_user", ""))
        self._in_smtp_password.setText(correo.get("smtp_password", ""))
        self._chk_smtp_tls.setChecked(bool(correo.get("smtp_use_tls", True)))
        # Ajustamos el estado enabled/disabled de los campos
        self._on_smtp_toggle(self._chk_smtp_enabled.isChecked())
        # Forzar el handler de perfil para que setee los defaults si
        # el campo host esta vacio (caso primera carga).
        self._on_perfil_changed(self._cb_perfil.currentIndex())

    def _on_listas_changed(self, *args) -> None:
        # El save real se hace al apretar "Guardar cambios".
        pass

    def _on_smtp_toggle(self, checked: bool) -> None:
        """Habilita/deshabilita los campos SMTP segun el checkbox."""
        for w in (
            self._cb_perfil,
            self._lb_smtp_help,
            self._in_smtp_host,
            self._sp_smtp_port,
            self._in_smtp_user,
            self._in_smtp_password,
            self._chk_smtp_tls,
            self._btn_probar_smtp,
        ):
            w.setEnabled(checked)

    def _on_perfil_changed(self, index: int) -> None:
        """Autocompleta host/puerto/TLS/instrucciones segun el proveedor.

        Solo lo hace si el campo host esta vacio o coincide con el del
        perfil anterior (asi no pisamos si el operador ya tipeo una
        direccion custom). Lo check 'enabled' lo respeta el handler
        '_on_smtp_toggle' al haber pasado por el toggle del proveedor.
        """
        key = self._cb_perfil.itemData(index)
        perfil = self._perfiles.get(key)
        if not perfil:
            return
        self._lb_smtp_help.setText(perfil["instructions"])
        # Si el host actual coincide con algun perfil conocido, lo
        # actualizamos; si es custom, lo dejamos en paz (caso 'otro').
        cur_host = (self._in_smtp_host.text() or "").strip()
        host_changes = not cur_host or any(
            cur_host == p["host"] for p in self._perfiles.values() if p["host"]
        )
        if host_changes or perfil["key"] == "otro":
            if perfil["host"]:  # dejar vacio si es 'otro' (el operador tipea)
                self._in_smtp_host.setText(perfil["host"])
            self._sp_smtp_port.setValue(perfil["puerto"])
            self._chk_smtp_tls.setChecked(bool(perfil["uso_tls"]))

    def _on_probar_smtp(self) -> None:
        """Prueba la conexion SMTP sin enviar nada."""
        try:
            from services import smtp_sender  # noqa: late import
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo cargar el modulo SMTP: {e}")
            return
        cfg = svc_cfg.obtener()
        correo = cfg.get("correo", {})
        resultado = smtp_sender.probar_conexion(
            host=correo.get("smtp_host", "smtp.office365.com"),
            port=int(correo.get("smtp_port", 587)),
            user=correo.get("smtp_user", ""),
            password=correo.get("smtp_password", ""),
            use_tls=bool(correo.get("smtp_use_tls", True)),
        )
        if resultado.get("ok"):
            QMessageBox.information(
                self,
                "Conexion OK",
                f"Se conecto a {correo.get('smtp_host')} como "
                f"{correo.get('smtp_user')}.\n\n"
                "Recorda apretar 'Guardar cambios' para que la config "
                "quede persistida.",
            )
        else:
            QMessageBox.warning(
                self,
                "Conexion fallo",
                f"No se pudo conectar:\n\n{resultado.get('error', '?')}",
            )

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
                "smtp_perfil": self._cb_perfil.itemData(
                    self._cb_perfil.currentIndex()
                ) or "gmail",
                "smtp_enabled": self._chk_smtp_enabled.isChecked(),
                "smtp_host": self._in_smtp_host.text().strip(),
                "smtp_port": self._sp_smtp_port.value(),
                "smtp_user": self._in_smtp_user.text().strip(),
                "smtp_password": self._in_smtp_password.text(),
                "smtp_use_tls": self._chk_smtp_tls.isChecked(),
            }
            svc_cfg.guardar(cfg)
            QMessageBox.information(self, "Guardado", "Configuracion de correo actualizada.")
            self.changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


__all__ = ("CorreoTab",)