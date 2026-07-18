"""Dashboard bar: 4 KPI cards grandes (FDS, Pendientes, En Observacion, Resueltas).

Replica del bloque ``.dashboard-bar`` de ``templates/fds_ui.html``.
Reemplaza a las "filas simples" que vivian al fondo del SearchPanel
(quedaban escondidas en el scroll). Las cards son grandes, visibles
de un vistazo y usan el patron canonico "icono de color + label +
numero grande".
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


# Set de iconos nuevos para los KPI. Son distintos a los del HTML
# original para reflejar el contenido: alerta (FDS), reloj (Pend),
# ojo (Observacion), check (Resueltas).
_KPI_ICONS = {
    "red": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2"><path d="M10.3 3.86 1.82 18a2 2 0 0 0 1.71 '
        '3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>'
        '<path d="M12 9v4M12 17h.01"/></svg>'
    ),
    "amber": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2"><circle cx="12" cy="12" r="10"/>'
        '<path d="M12 6v6l4 2"/></svg>'
    ),
    "blue": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2"><circle cx="12" cy="12" r="3"/>'
        '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7S2 12 2 12z"/></svg>'
    ),
    "green": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>'
        '<path d="M22 4 12 14.01l-3-3"/></svg>'
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
        icon.setText("")  # usamos pixmap
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
        # Si el contador es 0, baja la opacidad visual (cero no es "alerta")
        self._value.setProperty("zero", "true" if val == 0 else "false")
        self._value.style().unpolish(self._value)
        self._value.style().polish(self._value)


class DashboardBar(QFrame):
    """Barra horizontal con 4 KPI cards grandes.

    Visualmente reemplaza las "filas simples" que vivian al fondo
    del SearchPanel. Las cards quedan siempre visibles arriba de
    los paneles centrales, no se esconden en un scroll.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dashboardBar")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 4)
        layout.setSpacing(14)

        self._fds = _KpiCard(color_key="red", label_text="FDS activas")
        self._pend = _KpiCard(color_key="amber", label_text="Pendientes")
        self._obs = _KpiCard(color_key="blue", label_text="En observacion")
        self._res = _KpiCard(color_key="green", label_text="Resueltas hoy")

        layout.addWidget(self._fds, 1)
        layout.addWidget(self._pend, 1)
        layout.addWidget(self._obs, 1)
        layout.addWidget(self._res, 1)

    def set_quick_stats(self, *, fds: int, pendientes: int, resueltas: int,
                        en_observacion: int = 0) -> None:
        """Actualiza los 4 contadores. Orden: FDS, Pend, Obs, Res."""
        self._fds.set_value(fds)
        self._pend.set_value(pendientes)
        self._obs.set_value(en_observacion)
        self._res.set_value(resueltas)


# ------------------------------------------------------------------
# Helper para renderizar el icono del KPI (no usa el set generico
# ``svg()`` porque estos SVGs son inline del HTML y solo se usan aca).
# ------------------------------------------------------------------


def _render_kpi_icon(color_key: str):
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
