"""Dialog de vista previa del informe antes de enviar.

Muestra el HTML renderizado tal cual se va a mandar por Outlook.
El operador puede revisar:
  - Destinatarios y CC (panel lateral)
  - Asunto del correo
  - Contenido del informe (en un QTextBrowser que renderiza HTML)
  - Cantidad de incidencias que se van a incluir

Botones:
  - Cerrar (no envia)
  - Enviar (confirma y cierra con Accepted; el controller dispara el envio)
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from config import load_config


class PreviewDialog(QDialog):
    """Vista previa del informe HTML antes de enviar.

    Parameters
    ----------
    parent:
        Widget padre.
    html:
        HTML ya renderizado por ``email_renderer.render_informe``.
    asunto:
        Asunto del correo (lo muestra en el header lateral).
    destinatarios:
        Lista de strings que se usaran como TO.
    cc:
        Lista de strings que se usaran como CC.
    total_registros:
        Cantidad de incidencias que se incluyen.
    """

    def __init__(
        self,
        *,
        parent: QWidget | None,
        html: str,
        asunto: str,
        destinatarios: list[str],
        cc: list[str],
        total_registros: int,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Vista previa del informe")
        self.setMinimumSize(1100, 760)
        self.setModal(True)

        self._html = html
        self._asunto = asunto
        self._destinatarios = destinatarios
        self._cc = cc
        self._total_registros = total_registros

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        head = QWidget()
        head.setStyleSheet(
            "background:#FFFFFF; border-bottom:1px solid #E1E6ED;"
        )
        hl = QVBoxLayout(head)
        hl.setContentsMargins(20, 16, 20, 16)
        hl.setSpacing(2)
        titulo = QLabel("Vista previa del informe")
        titulo.setStyleSheet("font-size:16px; font-weight:700; color:#1B2430;")
        sub = QLabel(
            f"Revisa el contenido antes de enviar. {self._total_registros} "
            f"{'incidencia' if self._total_registros == 1 else 'incidencias'} "
            f"{'incluida' if self._total_registros == 1 else 'incluidas'}."
        )
        sub.setStyleSheet("color:#64748B; font-size:12px;")
        hl.addWidget(titulo)
        hl.addWidget(sub)
        root.addWidget(head)

        # Body: 2 columnas (metadata lateral + preview HTML)
        body = QFrame()
        b_layout = QHBoxLayout(body)
        b_layout.setContentsMargins(0, 0, 0, 0)
        b_layout.setSpacing(0)

        # Lateral: destinatarios, cc, asunto
        side = QFrame()
        side.setObjectName("previewSide")
        side.setStyleSheet(
            "QFrame#previewSide{background:#F8FAFC; "
            "border-right:1px solid #E1E6ED;}"
        )
        side.setFixedWidth(320)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(18, 16, 18, 16)
        sl.setSpacing(14)

        # Destinatarios
        sl.addWidget(self._section_label("DESTINATARIOS"))
        sl.addWidget(self._lista_labels(self._destinatarios,
                                        fallback="(sin destinatarios)"))
        # CC
        sl.addSpacing(4)
        sl.addWidget(self._section_label("CC"))
        sl.addWidget(self._lista_labels(self._cc,
                                        fallback="(sin copia)"))
        # Asunto
        sl.addSpacing(4)
        sl.addWidget(self._section_label("ASUNTO"))
        sl.addWidget(self._wrapped_label(self._asunto or "(sin asunto)"))
        # Resumen
        sl.addSpacing(4)
        sl.addWidget(self._section_label("CONTENIDO"))
        sl.addWidget(self._wrapped_label(
            f"{self._total_registros} {'incidencia' if self._total_registros == 1 else 'incidencias'} "
            f"+ estado del catalogo + metricas del turno"
        ))
        sl.addStretch(1)

        # Fecha de generacion
        fecha_lbl = QLabel(
            f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        fecha_lbl.setStyleSheet(
            "color:#94A3B8; font-size:11px;"
        )
        fecha_lbl.setWordWrap(True)
        sl.addWidget(fecha_lbl)

        b_layout.addWidget(side)

        # Preview HTML
        preview = QFrame()
        pl = QVBoxLayout(preview)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(0)

        # Header del preview (browser)
        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        self._browser.document().setDefaultStyleSheet(_PREVIEW_CSS)
        self._browser.setHtml(self._html)
        pl.addWidget(self._browser, 1)

        b_layout.addWidget(preview, 1)
        root.addWidget(body, 1)

        # Botones
        foot = QFrame()
        foot.setStyleSheet(
            "background:#FFFFFF; border-top:1px solid #E1E6ED;"
        )
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(20, 12, 20, 12)
        fl.setSpacing(10)

        # Re-Generar boton por si el operador quiere ver otra vez
        btn_regen = QPushButton("Re-renderizar")
        btn_regen.setObjectName("btnSecondary")
        btn_regen.setCursor(Qt.PointingHandCursor)
        btn_regen.clicked.connect(self._regenerar)
        fl.addWidget(btn_regen)

        fl.addStretch(1)

        # Boton estandard de dialog
        bb = QDialogButtonBox()
        btn_cancel = bb.addButton("Cerrar (no enviar)", QDialogButtonBox.RejectRole)
        btn_cancel.setObjectName("btnSecondary")
        btn_send = bb.addButton("Enviar ahora", QDialogButtonBox.AcceptRole)
        btn_send.setObjectName("btnPrimary")
        btn_send.setDefault(True)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        fl.addWidget(bb)
        root.addWidget(foot)

    def _regenerar(self) -> None:
        """Re-carga el HTML (util si el operador edito algo externamente)."""
        self._browser.setHtml(self._html)

    @staticmethod
    def _section_label(texto: str) -> QLabel:
        lbl = QLabel(texto)
        lbl.setStyleSheet(
            "color:#94A3B8; font-size:10px; font-weight:700; "
            "letter-spacing:1px;"
        )
        return lbl

    @staticmethod
    def _lista_labels(items: Iterable[str], *, fallback: str) -> QLabel:
        if not items:
            lbl = QLabel(fallback)
            lbl.setStyleSheet("color:#94A3B8; font-size:12px; font-style:italic;")
            lbl.setWordWrap(True)
            return lbl
        texto = "\n".join(f"- {it}" for it in items)
        lbl = QLabel(texto)
        lbl.setStyleSheet("color:#1B2430; font-size:12px; line-height:1.5;")
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        return lbl

    @staticmethod
    def _wrapped_label(texto: str) -> QLabel:
        lbl = QLabel(texto)
        lbl.setStyleSheet("color:#1B2430; font-size:12px;")
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        return lbl


# CSS embebido para que el HTML del informe se vea razonable aunque
# use styles inline que Qt no siempre respeta al 100%.
_PREVIEW_CSS = """
body { font-family: 'Segoe UI', sans-serif; color: #1B2430; background:#FFFFFF; }
table { border-collapse: collapse; }
a { color: #1E5AA8; }
"""


__all__ = ("PreviewDialog",)
