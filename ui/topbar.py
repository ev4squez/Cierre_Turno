"""Topbar del Sistema FDS."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from ui.helpers import initials, svg


class TopBar(QFrame):
    """Barra superior: logo, marca, fecha, turno, usuario, salir.

    Signals
    -------
    settingsClicked: el usuario toco el boton de configuracion
    logoutClicked:   el usuario toco el boton salir
    """

    settingsClicked = Signal()
    logoutClicked = Signal()
    importClicked = Signal()

    def __init__(
        self,
        *,
        empresa_nombre: str,
        sistema_nombre: str,
        usuario_nombre: str,
        usuario_rol: str,
        fecha_texto: str,
        turno_texto: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("topbar")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Logo + marca
        logo = QLabel("OC")
        logo.setObjectName("logoBadge")

        brand = QFrame()
        brand.setObjectName("brand")
        brand_layout = QVBoxLayout(brand)
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(0)
        self._brand_dept = QLabel(empresa_nombre.upper())
        self._brand_dept.setObjectName("brandDept")
        self._brand_system = QLabel(sistema_nombre)
        self._brand_system.setObjectName("brandSystem")
        brand_layout.addWidget(self._brand_dept)
        brand_layout.addWidget(self._brand_system)

        divider1 = QFrame()
        divider1.setObjectName("topDivider")
        divider1.setFixedSize(1, 28)

        spacer = QSpacerItem(20, 1, QSizePolicy.Expanding, QSizePolicy.Minimum)

        # Chips de info
        self._lbl_fecha = QLabel(fecha_texto)
        self._lbl_fecha.setObjectName("infoChip")
        cal_icon = QLabel()
        cal_icon.setPixmap(svg("calendar", 15).pixmap(15, 15))
        fecha_layout = QHBoxLayout()
        fecha_layout.setContentsMargins(0, 0, 0, 0)
        fecha_layout.setSpacing(6)
        fecha_layout.addWidget(cal_icon)
        fecha_layout.addWidget(self._lbl_fecha)
        fecha_w = QFrame()
        fecha_w.setLayout(fecha_layout)

        self._lbl_turno = QLabel(turno_texto)
        self._lbl_turno.setObjectName("turnoChip")
        self._dot = QLabel()
        self._dot.setObjectName("statusDot")
        self._dot.setFixedSize(6, 6)
        turno_layout = QHBoxLayout()
        turno_layout.setContentsMargins(0, 0, 0, 0)
        turno_layout.setSpacing(8)
        turno_layout.addWidget(self._dot)
        turno_layout.addWidget(self._lbl_turno)
        turno_w = QFrame()
        turno_w.setLayout(turno_layout)

        top_info = QHBoxLayout()
        top_info.setContentsMargins(0, 0, 0, 0)
        top_info.setSpacing(18)
        top_info.addWidget(fecha_w)
        top_info.addWidget(turno_w)

        # User chip
        self._avatar = QLabel(initials(usuario_nombre))
        self._avatar.setObjectName("userAvatar")
        self._avatar.setAlignment(Qt.AlignCenter)
        self._avatar.setFixedSize(26, 26)

        self._user_name = QLabel(usuario_nombre)
        self._user_name.setObjectName("userName")
        self._user_role = QLabel(usuario_rol)
        self._user_role.setObjectName("userRole")
        user_text = QVBoxLayout()
        user_text.setContentsMargins(0, 0, 0, 0)
        user_text.setSpacing(0)
        user_text.addWidget(self._user_name)
        user_text.addWidget(self._user_role)

        user_chip = QFrame()
        user_chip.setObjectName("userChip")
        user_layout = QHBoxLayout(user_chip)
        user_layout.setContentsMargins(6, 0, 10, 0)
        user_layout.setSpacing(9)
        user_layout.addWidget(self._avatar)
        user_layout.addLayout(user_text)

        # Botones
        btn_import = QPushButton()
        btn_import.setObjectName("btnIconOnly")
        btn_import.setIcon(svg("excel", 17))
        btn_import.setIconSize(btn_import.sizeHint())
        btn_import.setFixedSize(34, 34)
        btn_import.setCursor(Qt.PointingHandCursor)
        btn_import.setToolTip("Importar maquinas desde Excel")
        btn_import.clicked.connect(self.importClicked.emit)

        btn_settings = QPushButton()
        btn_settings.setObjectName("btnIconOnly")
        btn_settings.setIcon(svg("settings", 17))
        btn_settings.setIconSize(btn_settings.sizeHint())
        btn_settings.setFixedSize(34, 34)
        btn_settings.setCursor(Qt.PointingHandCursor)
        btn_settings.setToolTip("Configuracion")
        btn_settings.clicked.connect(self.settingsClicked.emit)

        btn_logout = QPushButton("  Salir")
        btn_logout.setObjectName("btnDangerGhost")
        btn_logout.setIcon(svg("logout", 15))
        btn_logout.setCursor(Qt.PointingHandCursor)
        btn_logout.clicked.connect(self.logoutClicked.emit)

        # Layout principal
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(16)
        layout.addWidget(logo)
        layout.addWidget(brand)
        layout.addSpacing(10)
        layout.addWidget(divider1)
        layout.addItem(spacer)
        layout.addLayout(top_info)
        layout.addSpacing(6)
        layout.addWidget(user_chip)
        layout.addWidget(btn_import)
        layout.addWidget(btn_settings)
        layout.addWidget(btn_logout)

    # --- API publica -------------------------------------------------------

    def set_turno(self, texto: str) -> None:
        self._lbl_turno.setText(texto)

    def set_fecha(self, texto: str) -> None:
        self._lbl_fecha.setText(texto)

    def set_usuario(self, nombre: str, rol: str) -> None:
        self._user_name.setText(nombre)
        self._user_role.setText(rol)
        self._avatar.setText(initials(nombre))