"""Entry point del Sistema FDS.

Arranca ``QApplication``, carga el QSS, inicializa el schema SQLite y
muestra ``MainWindow`` orquestada por ``MainController``.
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout

from controllers.main_controller import MainController
from database.db import init_db
from ui.helpers import load_stylesheet
from ui.logger import setup_logging
from ui.main_window import MainWindow


# Version del sistema. La primera estable para distribucion a la VM
# del casino es 1.0.0. Se muestra en el splash, en el titulo de la
# ventana y en el chip del topbar (para que el operador y vos
# siempre sepan que version estan corriendo).
__version__ = "1.0.0"


class _SplashScreen(QWidget):
    """Splash minimalista que se muestra mientras carga la app.

    Los .exe de PyInstaller tardan 2-3 segundos en mostrar la ventana
    (imports de PySide6 + SQLAlchemy + openpyxl + jinja2 + win32com).
    Sin splash, el operador abre el icono y ve una pantalla vacia,
    piensa que se rompio. Con splash ve feedback inmediato.

    Implementado como QWidget normal con show(), NO como QSplashScreen
    nativo: queremos full control visual (colores corporativos,
    version) y QSplashScreen no soporta pixmap custom con QSS.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | Qt.SplashScreen | Qt.FramelessWindowHint
        )
        # Centrar en la pantalla
        screen = QApplication.primaryScreen().geometry()
        w, h = 420, 240
        self.setGeometry(
            (screen.width() - w) // 2,
            (screen.height() - h) // 2,
            w, h,
        )
        self.setStyleSheet(
            "QWidget#splashRoot {"
            " background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
            "  stop:0 #1E5AA8, stop:1 #164788);"
            " border-radius: 12px;"
            "}"
            "QLabel#splashTitle { color: #FFFFFF; font-size: 24px; font-weight: 800; }"
            "QLabel#splashSub { color: #DCE9FA; font-size: 13px; font-weight: 500; }"
            "QLabel#splashVer { color: #94A3B8; font-size: 11px; }"
        )
        self.setObjectName("splashRoot")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 28, 28, 24)
        lay.setSpacing(8)
        title = QLabel("Sistema FDS")
        title.setObjectName("splashTitle")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)
        sub = QLabel("Casino Ovalle")
        sub.setObjectName("splashSub")
        sub.setAlignment(Qt.AlignCenter)
        lay.addWidget(sub)
        lay.addStretch(1)
        ver = QLabel(f"v{__version__} - cargando...")
        ver.setObjectName("splashVer")
        ver.setAlignment(Qt.AlignCenter)
        lay.addWidget(ver)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    app = QApplication(argv)
    app.setApplicationName("SistemaFDS")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("CasinoOvalle")

    # Splash: feedback inmediato mientras la app carga. Se muestra
    # apenas QApplication existe, antes de importar nada pesado.
    splash = _SplashScreen()
    splash.show()
    app.processEvents()  # fuerza el paint del splash

    # Logging estructurado antes de cualquier otra cosa, asi capturamos
    # logs de inicializacion tambien
    setup_logging()
    logging.getLogger(__name__).info(
        "Iniciando Sistema FDS v%s", __version__
    )

    # Asegurar schema antes de levantar la UI
    init_db()
    load_stylesheet(app)

    win = MainWindow()
    # Version en el titulo de la ventana (asi aparece en la taskbar)
    win.setWindowTitle(f"Sistema de Registro de Maquinas Fuera de Servicio v{__version__}")
    controller = MainController(win)
    controller.wire()
    controller.start()
    win.show()
    # Cerrar el splash cuando la ventana real ya esta visible
    splash.close()
    splash.deleteLater()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())