"""Entry point del Sistema FDS.

Arranca ``QApplication``, carga el QSS, inicializa el schema SQLite y
muestra ``MainWindow`` orquestada por ``MainController``.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from controllers.main_controller import MainController
from database.db import init_db
from ui.helpers import load_stylesheet
from ui.logger import setup_logging
from ui.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    app = QApplication(argv)
    app.setApplicationName("SistemaFDS")
    app.setOrganizationName("CasinoOvalle")

    # Logging estructurado antes de cualquier otra cosa, asi capturamos
    # logs de inicializacion tambien
    setup_logging()
    import logging
    logging.getLogger(__name__).info("Iniciando Sistema FDS")

    # Asegurar schema antes de levantar la UI
    init_db()
    load_stylesheet(app)

    win = MainWindow()
    controller = MainController(win)
    controller.wire()
    controller.start()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())