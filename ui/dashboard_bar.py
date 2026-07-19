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

from PySide6.QtCore import QByteArray, Qt
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
}


class _KpiCard(QFrame):
    """Una card individual del dashboard."""

    def __init__(self, *, color_key: str, label_text: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(f"kpiCard_{color_key}")
        self.setProperty("class", "kpiCard")
        self.setProperty("kpiColor", color_key)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(70)

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


class DashboardBar(QFrame):
    """Barra horizontal con 4 KPI cards grandes.

    Distribucion (de izquierda a derecha):
      TOTAL MAQUINAS | OPERATIVAS | EN OBSERVACION | PENDIENTES

    Todas las cards cuentan el ESTADO ACTUAL del parque de maquinas
    (no las incidencias del turno). Las metricas de productividad del
    turno viven en el footer.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dashboardBar")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 4)
        layout.setSpacing(14)

        # Orden: Total / Operativas / Obs / Pendientes
        self._total = _KpiCard(color_key="dark", label_text="Total maquinas")
        self._operativas = _KpiCard(color_key="green", label_text="Operativas")
        self._obs = _KpiCard(color_key="blue", label_text="En observacion")
        self._pend = _KpiCard(color_key="amber", label_text="Pendientes")

        layout.addWidget(self._total, 1)
        layout.addWidget(self._operativas, 1)
        layout.addWidget(self._obs, 1)
        layout.addWidget(self._pend, 1)

    def set_estado_catalogo(self, *, total: int, operativas: int,
                            en_observacion: int, pendientes: int) -> None:
        """Actualiza las 4 cards con el estado actual del parque.

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
        """
        self._total.set_value(total)
        self._operativas.set_value(operativas)
        self._obs.set_value(en_observacion)
        self._pend.set_value(pendientes)

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
