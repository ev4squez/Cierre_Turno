"""Helpers de UI.

Carga el QSS, expone iconos SVG inline (los mismos del HTML) como
``QIcon``, y pequenas utilidades de formato.

Los SVG son versiones simplificadas de los del HTML, sin dependencias
externas. Se cargan como bytes en un ``QByteArray`` y se envuelven en
``QPixmap`` para usarlos como icono de ``QPushButton``.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from config import STYLES_DIR


# ---------------------------------------------------------------------------
# Estilos
# ---------------------------------------------------------------------------


def load_stylesheet(app) -> None:
    """Carga ``resources/styles/app.qss`` y lo aplica a ``app``.

    Si el archivo no existe (instalacion rota), no rompe la app: la
    aplicacion funciona sin estilos, solo menos bonita.
    """
    qss_path = STYLES_DIR / "app.qss"
    if not qss_path.exists():
        return
    app.setStyleSheet(qss_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Iconos SVG inline
#
# Mismo set de iconos que usa el HTML, exportados a una constante para no
# escribirlos cada vez. ``svg(name, size)`` devuelve un ``QIcon``.
# ---------------------------------------------------------------------------

_ICONS: dict[str, str] = {
    # ----- busqueda y filtros -----
    "search": '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.3-4.3"/></svg>',
    # Embudo: filtrar lista por criterio. ANTES era identico a 'trash' (bug).
    "filter": '<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 4h18l-7 9v6l-4 2v-8z"/></svg>',
    # ----- acciones sobre filas / formularios -----
    "plus": '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>',
    "edit": '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.1 2.1 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>',
    "trash": '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2"/><path d="M6 6v14a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V6M10 11v6M14 11v6"/></svg>',
    "eye": '<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12z"/><circle cx="12" cy="12" r="3"/></svg>',
    # Dos hojas superpuestas: 'copiar / duplicar'. ANTES era 'clipboard' (confundible
    # con el boton de Actividades Diarias del topbar).
    "copy": '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>',
    # ----- navegacion y sistema -----
    "settings": '<svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.2a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.2a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.2a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.2a1.6 1.6 0 0 0-1.5 1z"/></svg>',
    "logout": '<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/></svg>',
    "calendar": '<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="3"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>',
    # Calendario con check: 'tareas del dia' (Actividades Diarias).
    # ANTES era el mismo clipboard que 'Duplicar' (confundible).
    "calendar-check": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="3"/><path d="M16 2v4M8 2v4M3 10h18"/><path d="M9 16l2 2 4-4"/></svg>',
    # Base de datos (cilindro): chip 'Backup' del topbar.
    "database": '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v6c0 1.7 4 3 9 3s9-1.3 9-3V5"/><path d="M3 11v6c0 1.7 4 3 9 3s9-1.3 9-3v-6"/></svg>',
    # Sobre cerrado: enviar correo (Outlook).
    "mail": '<svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 6L12 13 2 6"/><path d="M2 6h20v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6z"/></svg>',
    # Flecha hacia abajo + caja: 'descargar / exportar a Excel'. ANTES era un
    # rectangulo con 'M' adentro que parecia un logo de Excel pero no
    # indicaba la accion de descarga.
    "download": '<svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg>',
    # Triangulo de alerta: maquinas con problemas / FDS.
    "alert": '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
    # Disquete: 'guardar borrador' / 'guardar como'. Hoy no se usa pero
    # queda para uso futuro. Si no se usa en 6 meses lo borramos.
    "save": '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><path d="M17 21v-8H7v8M7 3v5h8"/></svg>',
}


def svg(name: str, size: int = 18) -> QIcon:
    """Devuelve un ``QIcon`` desde el SVG embebido ``_ICONS[name]``.

    Renderiza el SVG a ``size x size`` pixeles. ``currentColor`` se
    reemplaza por ``#64748B`` (gris sub) por defecto.

    Nota: el template puede tener cualquier ``width="N" height="N"``
    en su declaracion; el helper usa regex para reescribir ambos
    atributos juntos al size pedido. Asi agregar un icono nuevo con
    cualquier tamano (12, 16, 22, ...) no requiere tocar este codigo.
    """
    template = _ICONS.get(name, "")
    if not template:
        return QIcon()

    import re
    # Reemplaza width="X" y height="X" en la declaracion del <svg>
    # por el size pedido. Solo la primera ocurrencia (la del root).
    svg_text = re.sub(
        r'width="\d+"\s+height="\d+"',
        f'width="{size}" height="{size}"',
        template,
        count=1,
    )

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    from PySide6.QtSvg import QSvgRenderer
    renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


# ---------------------------------------------------------------------------
# Utilidades de formato
# ---------------------------------------------------------------------------


def initials(nombre: str) -> str:
    """Devuelve hasta 2 iniciales en mayuscula para avatares."""
    partes = [p for p in nombre.replace(".", " ").split() if p]
    if not partes:
        return "?"
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[-1][0]).upper()


def severity_for_estado(estado: str) -> str:
    """Mapea un estado de maquina a la 'severidad' del badge."""
    return {
        "Operativa": "ok",
        "Fuera de Servicio": "critical",
        "Pendiente Repuesto": "warning",
        "Espera Servicio Tecnico": "warning",
        "En Observacion": "info",
    }.get(estado, "info")


def clear_layout(widget) -> None:  # type: ignore[no-untyped-def]
    """Elimina todos los hijos de un QFrame/QWidget (no de un layout).

    Acepta un QWidget (lee ``widget.layout()``) o un ``QLayout``
    directamente. Borra los widgets hijos con ``deleteLater()`` y remueve
    los spacers/stretches. Necesario al repoblar listas dinamicas.
    """
    from PySide6.QtWidgets import QLayout, QWidget

    layout = widget.layout() if isinstance(widget, QWidget) else widget
    if not isinstance(layout, QLayout):
        return
    while layout.count():
        item = layout.takeAt(0)
        child = item.widget()
        if child is not None:
            child.setParent(None)
            child.deleteLater()
        # spacers/stretch se descartan solos al takeAt


__all__ = (
    "load_stylesheet",
    "svg",
    "initials",
    "severity_for_estado",
    "clear_layout",
)