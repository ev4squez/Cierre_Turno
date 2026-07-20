"""Dashboard bar: 4 KPI cards grandes (estado actual del catalogo).

Replica del bloque ``.dashboard-bar`` de ``templates/fds_ui.html``.

Cards (de izquierda a derecha):
  1. TOTAL MAQUINAS   - slate    - total del parque
  2. OPERATIVAS        - green    - maquinas operativas ahora
  3. EN OBSERVACION    - blue     - maquinas en seguimiento
  4. PENDIENTES        - amber    - FDS + Pend Rep + Esp Tecnico

Reemplaza al set anterior (FDS / Pend / Obs / Resueltas) que mezclaba
metricas del turno y del catalogo. Ahora las 4 cards reflejan el
estado ACTUAL del parque; las metricas de productividad del turno
viven en el footer.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt, Signal
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


# Iconos SVG inline (mismos del HTML). Un set por color de card.
_KPI_ICONS: dict[str, str] = {
    # slate / dark - icono de "parque/cuadricula" (cuadros de maquinas)
    "dark": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/>'
        '<path d="M9 3v18M3 9h18"/></svg>'
    ),
    # green - check (operativa)
    "green": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>'
        '<path d="M22 4 12 14.01l-3-3"/></svg>'
    ),
    # blue - ojo (observacion)
    "blue": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2"><circle cx="12" cy="12" r="3"/>'
        '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7S2 12 2 12z"/></svg>'
    ),
    # amber - alerta (pendientes)
    "amber": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2"><path d="M10.3 3.86 1.82 18a2 2 0 0 0 1.71 '
        '3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>'
        '<path d="M12 9v4M12 17h.01"/></svg>'
    ),
    # red - clipboard con check (tareas pendientes de actividades)
    "red": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2"><rect x="8" y="2" width="8" height="4" rx="1"/>'
        '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 '
        '1-2-2V6a2 2 0 0 1 2-2h2"/>'
        '<path d="M9 12l2 2 4-4"/></svg>'
    ),
}


class _KpiCard(QFrame):
    """Una card individual del dashboard."""

    clicked = Signal(str)  # emite el color_key al hacer click

    def __init__(self, *, color_key: str, label_text: str,
                 tooltip_text: str = "",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(f"kpiCard_{color_key}")
        self.setProperty("class", "kpiCard")
        self.setProperty("kpiColor", color_key)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(70)
        # Tooltip explicativo: la card es clickeable, asi que el
        # operador necesita saber que hace antes de tocar. El texto
        # esta en DashboardBar.__init__ cuando se crea cada card.
        if tooltip_text:
            self.setToolTip(tooltip_text)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(14)

        # Icono coloreado
        icon = QLabel()
        icon.setObjectName("kpiIcon")
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedSize(42, 42)
        icon.setPixmap(_render_kpi_icon(color_key).pixmap(22, 22))
        layout.addWidget(icon)

        # Texto: label + numero grande
        text = QFrame()
        text_v = QVBoxLayout(text)
        text_v.setContentsMargins(0, 0, 0, 0)
        text_v.setSpacing(2)

        lbl = QLabel(label_text.upper())
        lbl.setObjectName("kpiLabel")
        self._value = QLabel("0")
        self._value.setObjectName("kpiValue")
        text_v.addWidget(lbl)
        text_v.addWidget(self._value)
        layout.addWidget(text, 1)

    def set_value(self, val: int) -> None:
        self._value.setText(str(val))
        # Cero no es alerta: bajamos la opacidad visual.
        self._value.setProperty("zero", "true" if val == 0 else "false")
        self._value.style().unpolish(self._value)
        self._value.style().polish(self._value)

    def mousePressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        # Las cards son clickeables: el DashboardBar escucha esto y
        # mapea el color_key a la accion correspondiente.
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.property("kpiColor") or "")
        super().mousePressEvent(event)

    def enterEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        # Cursor pointer para que se note que es clickeable.
        self.setCursor(Qt.PointingHandCursor)
        super().enterEvent(event)


class DashboardBar(QFrame):
    """Barra horizontal con 5 KPI cards grandes.

    Distribucion (de izquierda a derecha):
      TOTAL MAQUINAS | OPERATIVAS | EN OBSERVACION | PENDIENTES (FDS)
      | TAREAS PENDIENTES (actividades diarias)

    Las 4 primeras cuentan el ESTADO ACTUAL del parque de maquinas.
    La quinta cuenta las actividades diarias marcadas con
    pendiente_sn=True (las que el tecnico dejo abiertas). Al hacer
    click en cualquier card, se emite ``cardClicked(color_key)`` para
    que el controller mapee la accion correspondiente.

    Signals
    -------
    cardClicked(str): color_key de la card clickeada
        ("dark" / "green" / "blue" / "amber" / "red").
    """

    cardClicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dashboardBar")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 4)
        layout.setSpacing(14)

        # Orden: Total / Operativas / Obs / Pendientes / Tareas pendientes
        # Cada card lleva un tooltip que explica que hace el click,
        # asi el operador descubre la funcionalidad sin tener que probar.
        self._total = _KpiCard(
            color_key="dark", label_text="Total maquinas",
            tooltip_text="Total de maquinas activas en el casino.\n"
                         "Click: muestra todas las maquinas en el buscador.",
        )
        self._operativas = _KpiCard(
            color_key="green", label_text="Operativas",
            tooltip_text="Cantidad de maquinas Operativas ahora mismo.\n"
                         "Click: filtra el buscador por 'Operativa'.",
        )
        self._obs = _KpiCard(
            color_key="blue", label_text="En observacion",
            tooltip_text="Cantidad de maquinas marcadas 'En Observacion'.\n"
                         "Click: filtra el buscador por 'En Observacion'.",
        )
        self._pend = _KpiCard(
            color_key="amber", label_text="Pendientes",
            tooltip_text="Cantidad de maquinas que requieren accion:\n"
                         "Fuera de Servicio + Pendiente Repuesto + Espera Tecnico.\n"
                         "Click: abre la lista de maquinas con problemas.",
        )
        self._tareas_pend = _KpiCard(
            color_key="red", label_text="Tareas pendientes",
            tooltip_text="Cantidad de actividades diarias marcadas como pendientes.\n"
                         "Click: abre el modulo de Actividades Diarias con el\n"
                         "filtro 'Solo pendientes' activado.",
        )

        # Re-emitimos los clicks de cada card como una sola signal del
        # DashboardBar, con el color_key como payload.
        for card in (self._total, self._operativas, self._obs,
                     self._pend, self._tareas_pend):
            card.clicked.connect(self.cardClicked.emit)

        layout.addWidget(self._total, 1)
        layout.addWidget(self._operativas, 1)
        layout.addWidget(self._obs, 1)
        layout.addWidget(self._pend, 1)
        layout.addWidget(self._tareas_pend, 1)

    def set_estado_catalogo(self, *, total: int, operativas: int,
                            en_observacion: int, pendientes: int,
                            tareas_pendientes: int = 0) -> None:
        """Actualiza las 5 cards con el estado actual del parque y
        las tareas pendientes del modulo de Actividades Diarias.

        Parametros
        ----------
        total:
            Cantidad de maquinas activas en el catalogo.
        operativas:
            Cantidad con estado == 'Operativa'.
        en_observacion:
            Cantidad con estado == 'En Observacion'.
        pendientes:
            Suma de FDS + Pendiente Repuesto + Espera Servicio Tecnico.
            Es la cantidad de maquinas que requieren accion.
        tareas_pendientes:
            Cantidad de actividades diarias con pendiente_sn=True.
        """
        self._total.set_value(total)
        self._operativas.set_value(operativas)
        self._obs.set_value(en_observacion)
        self._pend.set_value(pendientes)
        self._tareas_pend.set_value(tareas_pendientes)

    # Backward compat: el controller viejo llama ``set_quick_stats`` con
    # fds / pendientes / resueltas / en_observacion. Si alguien todavia
    # usa esa firma, la aceptamos y re-mapeamos los parametros.
    def set_quick_stats(self, *, fds: int, pendientes: int,
                        resueltas: int, en_observacion: int = 0) -> None:
        """Compat: remapea set_quick_stats(fds, pendientes, resueltas, en_observacion).

        Como ahora el dashboard cuenta el estado del catalogo (no del
        turno), algunos parametros se descartan:
          * ``resueltas``: era del turno; ahora va solo al footer.
          * ``fds``: ya esta dentro de ``pendientes`` (que es la suma).
        """
        # No conocemos el total del parque aca; el caller debe usar
        # set_estado_catalogo si quiere que la card 'Total' se actualice.
        # En este fallback la dejamos en 0 para que sea visible.
        self._pend.set_value(pendientes)
        self._obs.set_value(en_observacion)


def _render_kpi_icon(color_key: str) -> QIcon:
    """Renderiza el SVG del color pedido a un QIcon."""
    svg_text = _KPI_ICONS.get(color_key, "")
    if not svg_text:
        return QIcon()
    pixmap = QPixmap(22, 22)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


__all__ = ("DashboardBar",)
