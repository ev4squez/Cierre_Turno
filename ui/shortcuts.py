"""Helper de atajos de teclado para la MainWindow.

Centraliza la configuracion de QShortcut y QKeySequence para que
la MainWindow solo tenga que declarar cada atajo con su semantica.

Atajos definidos:
  Ctrl+E   -> enviar informe por Outlook (enviarInformeRequested)
  Ctrl+N   -> nueva incidencia: limpia form + foco en maquina
              (limpiarForm + foco)
  Ctrl+I   -> alta rapida: limpia form + foco en maquina
              (idem Ctrl+N, agregado para consistencia con
              "I" de Incidencia. Algunas personas lo descubren
              primero que Ctrl+N.)
  Ctrl+F   -> foco en el buscador de maquinas
  Ctrl+L   -> refrescar lista de maquinas (searchQueryChanged con "")
  Ctrl+A   -> abrir dialog de Registro de Actividades Diarias
  Ctrl+T   -> abrir dialog de Maquinas con problemas ahora
              (T = Trouble, alterna al boton del panel central)
  Esc      -> cancelar edicion / cerrar dialogs activos

Cada atajo se monta en ``attach(parent, signals)`` donde parent es
la ventana que recibe los shortcuts y ``signals`` es un dict con
los nombres y callable a ejecutar.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget


def attach_shortcuts(parent: QWidget) -> dict[str, QShortcut]:
    """Crea los atajos y los monta en ``parent``.

    Retorna un dict ``{nombre: QShortcut}`` para que el caller pueda
    conectar las senales o desactivarlos en runtime si hace falta.

    Por defecto las shortcuts se crean INACTIVAS (context=WidgetShortcut,
    sin senales conectadas). El caller las enchufa via ``shortcut.activated``.

    Uso:
        from ui.shortcuts import attach_shortcuts, attach_to_signals
        sc = attach_shortcuts(self)
        sc["enviar"].activated.connect(self.enviarInformeRequested.emit)
    """
    return {
        # Ctrl+E: enviar informe por Outlook
        "enviar": QShortcut(QKeySequence("Ctrl+E"), parent,
                            context=Qt.WindowShortcut),
        # Ctrl+N: nueva incidencia (limpia form + foco)
        "nueva": QShortcut(QKeySequence("Ctrl+N"), parent,
                           context=Qt.WindowShortcut),
        # Ctrl+I: alias de "nueva" (atajo paralelo, mas descubrible)
        "alta": QShortcut(QKeySequence("Ctrl+I"), parent,
                          context=Qt.WindowShortcut),
        # Ctrl+F: foco en el buscador
        "buscar": QShortcut(QKeySequence("Ctrl+F"), parent,
                            context=Qt.WindowShortcut),
        # Ctrl+L: refrescar lista de maquinas
        "refrescar": QShortcut(QKeySequence("Ctrl+L"), parent,
                               context=Qt.WindowShortcut),
        # Ctrl+A: dialog de Actividades Diarias
        "actividades": QShortcut(QKeySequence("Ctrl+A"), parent,
                                 context=Qt.WindowShortcut),
        # Ctrl+T: dialog de Maquinas con problemas ahora
        "problematicas": QShortcut(QKeySequence("Ctrl+T"), parent,
                                   context=Qt.WindowShortcut),
        # Esc: cancelar edicion / cerrar dialogs
        "cancelar": QShortcut(QKeySequence("Escape"), parent,
                              context=Qt.ApplicationShortcut),
    }


def get_tooltip_suffix(nombre: str) -> str:
    """Devuelve el sufijo de tooltip con el shortcut.

    Para anadir a los tooltips de los botones: ' (Ctrl+E)'.
    """
    return {
        "enviar": "Ctrl+E",
        "nueva": "Ctrl+N",
        "alta": "Ctrl+I",
        "buscar": "Ctrl+F",
        "refrescar": "Ctrl+L",
        "actividades": "Ctrl+A",
        "problematicas": "Ctrl+T",
    }.get(nombre, "")


def attach_to_signals(shortcuts: dict[str, QShortcut],
                      handlers: dict[str, Callable]) -> None:
    """Conecta cada shortcut a su handler.

    Uso:
        attach_to_signals(sc, {
            "enviar": lambda: print("enviar"),
            "nueva": lambda: print("nueva"),
            ...
        })
    """
    for nombre, handler in handlers.items():
        if nombre in shortcuts and callable(handler):
            shortcuts[nombre].activated.connect(handler)


def disable_all(shortcuts: dict[str, QShortcut]) -> None:
    """Desactiva todos los shortcuts (util mientras hay un dialog modal)."""
    for sc in shortcuts.values():
        sc.setEnabled(False)


def enable_all(shortcuts: dict[str, QShortcut]) -> None:
    """Reactiva los shortcuts (util al cerrar dialogs modales)."""
    for sc in shortcuts.values():
        sc.setEnabled(True)


__all__ = (
    "attach_shortcuts",
    "attach_to_signals",
    "disable_all",
    "enable_all",
    "get_tooltip_suffix",
)
