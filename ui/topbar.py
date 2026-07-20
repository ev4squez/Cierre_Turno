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
    importClicked:   el usuario toco el boton de importar Excel
    actividadesClicked: el usuario toco el boton de Registro de
        Actividades Diarias (nuevo, abre la pantalla que reemplaza la
        planilla Excel).
    """

    settingsClicked = Signal()
    logoutClicked = Signal()
    importClicked = Signal()
    actividadesClicked = Signal()

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

        self._lbl_fecha = QLabel(fecha_texto)
        self._lbl_fecha.setObjectName("topInfoValue")
        cal_icon = QLabel()
        cal_icon.setObjectName("topInfoCellIcon")
        cal_icon.setPixmap(svg("calendar", 14).pixmap(14, 14))

        # Dot animado del turno (sustituye al icono)
        self._dot = QLabel()
        self._dot.setObjectName("topInfoCellDot")
        self._dot.setFixedSize(7, 7)

        self._lbl_turno = QLabel(turno_texto)
        self._lbl_turno.setObjectName("topInfoValue")

        # Celda Fecha
        fecha_cell = QFrame()
        fecha_cell.setObjectName("topInfoCell")
        fc_l = QHBoxLayout(fecha_cell)
        fc_l.setContentsMargins(12, 6, 14, 6)
        fc_l.setSpacing(8)
        fc_l.addWidget(cal_icon)
        fecha_lbl_lbl = QLabel("Fecha")
        fecha_lbl_lbl.setObjectName("topInfoLabel")
        fc_l.addWidget(fecha_lbl_lbl)
        fc_l.addWidget(self._lbl_fecha)

        # Celda Turno (separada por divisor)
        turno_cell = QFrame()
        turno_cell.setObjectName("topInfoCell")
        tc_l = QHBoxLayout(turno_cell)
        tc_l.setContentsMargins(12, 6, 14, 6)
        tc_l.setSpacing(8)
        tc_l.addWidget(self._dot)
        turno_lbl_lbl = QLabel("Turno")
        turno_lbl_lbl.setObjectName("topInfoLabel")
        tc_l.addWidget(turno_lbl_lbl)
        tc_l.addWidget(self._lbl_turno)

        top_info = QFrame()
        top_info.setObjectName("topInfoGroup")
        tig = QHBoxLayout(top_info)
        tig.setContentsMargins(0, 0, 0, 0)
        tig.setSpacing(0)
        tig.addWidget(fecha_cell)
        tig.addWidget(turno_cell)
        # NO usar layout.addLayout(tig) aca: el layout ya quedo asociado
        # a top_info via el constructor. Si lo agregamos al layout
        # principal, PySide6 re-parenta tig (y los QLabels que viven
        # dentro de fecha_cell/turno_cell se quedan sin parent visible).
        # En vez de eso, agregamos el FRAME top_info como widget.

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

        # Indicador de Outlook (chip con dot + texto "Outlook").
        # El controller lo refresca via set_outlook_status() segun
        # el resultado de services.outlook.outlook_disponible().
        self._outlook_chip = QFrame()
        self._outlook_chip.setObjectName("outlookChip")
        oc_layout = QHBoxLayout(self._outlook_chip)
        oc_layout.setContentsMargins(8, 0, 10, 0)
        oc_layout.setSpacing(6)
        self._outlook_dot = QLabel()
        self._outlook_dot.setObjectName("outlookDot")
        self._outlook_dot.setFixedSize(8, 8)
        self._outlook_text = QLabel("Outlook")
        self._outlook_text.setObjectName("outlookText")
        oc_layout.addWidget(self._outlook_dot)
        oc_layout.addWidget(self._outlook_text)

        # Indicador de Backup (chip con dot + texto "Backup").
        # El controller lo refresca via set_backup_status() despues
        # de cada backup periodico. Asi el operador ve de un vistazo
        # si su DB tiene un backup reciente (verde < 30 min, amarillo
        # < 2h, rojo > 2h o no hay ninguno).
        self._backup_chip = QFrame()
        self._backup_chip.setObjectName("backupChip")
        bc_layout = QHBoxLayout(self._backup_chip)
        bc_layout.setContentsMargins(8, 0, 10, 0)
        bc_layout.setSpacing(6)
        self._backup_dot = QLabel()
        self._backup_dot.setObjectName("backupDot")
        self._backup_dot.setFixedSize(8, 8)
        self._backup_text = QLabel("Backup")
        self._backup_text.setObjectName("backupText")
        bc_layout.addWidget(self._backup_dot)
        bc_layout.addWidget(self._backup_text)

        # Botones
        btn_import = QPushButton()
        btn_import.setObjectName("btnIconOnly")
        btn_import.setIcon(svg("excel", 17))
        btn_import.setIconSize(btn_import.sizeHint())
        btn_import.setFixedSize(34, 34)
        btn_import.setCursor(Qt.PointingHandCursor)
        btn_import.setToolTip("Importar maquinas desde Excel")
        btn_import.clicked.connect(self.importClicked.emit)

        # Boton 'Registro de Actividades Diarias'. Reemplaza la
        # planilla Excel diaria: alta, edicion, filtros, export a
        # Excel con el formato que pide la SCJ.
        btn_actividades = QPushButton()
        btn_actividades.setObjectName("btnIconOnly")
        btn_actividades.setIcon(svg("clipboard", 17))
        btn_actividades.setIconSize(btn_actividades.sizeHint())
        btn_actividades.setFixedSize(34, 34)
        btn_actividades.setCursor(Qt.PointingHandCursor)
        btn_actividades.setToolTip("Registro de Actividades Diarias")
        btn_actividades.clicked.connect(self.actividadesClicked.emit)

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
        layout.addWidget(top_info)
        layout.addSpacing(6)
        layout.addWidget(user_chip)
        layout.addSpacing(4)
        layout.addWidget(self._outlook_chip)
        layout.addSpacing(4)
        layout.addWidget(self._backup_chip)
        layout.addSpacing(4)
        layout.addWidget(btn_import)
        layout.addWidget(btn_actividades)
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

    def set_outlook_status(self, disponible: bool, mensaje: str = "") -> None:
        """Cambia el indicador de Outlook del topbar.

        Parametros
        ----------
        disponible:
            True si Outlook esta accesible, False si no.
        mensaje:
            Texto opcional que aparece como tooltip al pasar el mouse
            (ej: 'Outlook 2019 detectado' o 'win32com no disponible').
        """
        self._outlook_chip.setProperty("status",
                                        "ok" if disponible else "ko")
        self._outlook_dot.setProperty("status",
                                      "ok" if disponible else "ko")
        self._outlook_chip.style().unpolish(self._outlook_chip)
        self._outlook_chip.style().polish(self._outlook_chip)
        self._outlook_dot.style().unpolish(self._outlook_dot)
        self._outlook_dot.style().polish(self._outlook_dot)
        self._outlook_text.setText("Outlook" if disponible else "Sin Outlook")
        if mensaje:
            self._outlook_chip.setToolTip(mensaje)
            self._outlook_dot.setToolTip(mensaje)
        else:
            self._outlook_chip.setToolTip(
                "Outlook listo para enviar" if disponible
                else "Outlook no detectado - el informe se guardara como archivo"
            )
            self._outlook_dot.setToolTip(self._outlook_chip.toolTip())

    def set_backup_status(self, edad_segundos: int | None,
                          mensaje: str = "") -> None:
        """Cambia el indicador 'Backup' del topbar segun la edad del ultimo.

        Parametros
        ----------
        edad_segundos:
            Segundos desde el ultimo backup. None = no hay backup.
        mensaje:
            Tooltip opcional (ej: 'Ultimo backup: sistema_fds_20260720.db
            (hace 12 min)').
        """
        if edad_segundos is None:
            status = "ko"
            texto = "Sin backup"
        elif edad_segundos < 30 * 60:
            status = "ok"      # < 30 min
            texto = "Backup"
        elif edad_segundos < 2 * 60 * 60:
            status = "warn"    # < 2 h
            texto = "Backup"
        else:
            status = "ko"      # > 2 h
            texto = "Backup"

        self._backup_chip.setProperty("status", status)
        self._backup_dot.setProperty("status", status)
        self._backup_chip.style().unpolish(self._backup_chip)
        self._backup_chip.style().polish(self._backup_chip)
        self._backup_dot.style().unpolish(self._backup_dot)
        self._backup_dot.style().polish(self._backup_dot)
        self._backup_text.setText(texto)

        if mensaje:
            self._backup_chip.setToolTip(mensaje)
            self._backup_dot.setToolTip(mensaje)
        else:
            if edad_segundos is None:
                self._backup_chip.setToolTip(
                    "Aun no se genero ningun backup automatico. "
                    "Se hace uno cada 30 minutos."
                )
            else:
                mins = edad_segundos // 60
                self._backup_chip.setToolTip(
                    f"Ultimo backup hace {mins} min. "
                    f"Se renueva automaticamente cada 30 min."
                )
            self._backup_dot.setToolTip(self._backup_chip.toolTip())