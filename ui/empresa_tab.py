"""Tab Empresa: nombre, departamento, color corporativo, logo."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QColorDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services import configuracion as svc_cfg


class EmpresaTab(QFrame):
    """Tab para editar los datos de la empresa."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._cargar()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        titulo = QLabel("Datos de la empresa")
        titulo.setStyleSheet("font-size:15px; font-weight:700; color:#1B2430;")
        sub = QLabel("Estos datos aparecen en el informe HTML enviado por Outlook.")
        sub.setStyleSheet("color:#64748B; font-size:12px;")
        root.addWidget(titulo)
        root.addWidget(sub)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        self._in_nombre = QLineEdit()
        self._in_nombre.setPlaceholderText("Ej: Casino Ovalle Resort")
        form.addRow("Nombre:", self._in_nombre)

        self._in_dept = QLineEdit()
        self._in_dept.setPlaceholderText("Ej: Departamento Tecnico y Sistemas")
        form.addRow("Departamento:", self._in_dept)

        # Color + boton
        color_row = QFrame()
        cl = QHBoxLayout(color_row)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(8)
        self._in_color = QLineEdit()
        self._in_color.setPlaceholderText("#1E5AA8")
        self._in_color.setMaximumWidth(120)
        self._color_swatch = QFrame()
        self._color_swatch.setFixedSize(28, 28)
        self._color_swatch.setStyleSheet(
            "background:#1E5AA8; border:1px solid #E1E6ED; border-radius:4px;"
        )
        cl.addWidget(self._in_color)
        cl.addWidget(self._color_swatch)
        cl.addStretch(1)
        btn_pick = QPushButton("Elegir color...")
        btn_pick.setObjectName("btnSecondary")
        btn_pick.clicked.connect(self._on_pick_color)
        cl.addWidget(btn_pick)
        form.addRow("Color corporativo:", color_row)

        # Logo path
        logo_row = QFrame()
        ll = QHBoxLayout(logo_row)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(8)
        self._in_logo = QLineEdit()
        self._in_logo.setPlaceholderText("Ruta al archivo de logo (opcional)")
        ll.addWidget(self._in_logo, 1)
        btn_logo = QPushButton("Seleccionar...")
        btn_logo.setObjectName("btnSecondary")
        btn_logo.clicked.connect(self._on_pick_logo)
        ll.addWidget(btn_logo)
        form.addRow("Logo:", logo_row)

        root.addLayout(form)
        root.addStretch(1)

        # Boton guardar
        btn_save = QPushButton("Guardar cambios")
        btn_save.setObjectName("btnPrimary")
        btn_save.clicked.connect(self._on_save)
        root.addWidget(btn_save)

        # Conectar cambios del color en vivo
        self._in_color.textChanged.connect(self._on_color_changed)

    def _cargar(self) -> None:
        cfg = svc_cfg.obtener()
        emp = cfg.get("empresa", {})
        self._in_nombre.setText(emp.get("nombre", ""))
        self._in_dept.setText(emp.get("departamento", ""))
        self._in_color.setText(emp.get("color_corporativo", "#1E5AA8"))
        self._in_logo.setText(emp.get("logo_path", ""))

    def _on_color_changed(self, color: str) -> None:
        if color.startswith("#") and len(color) in (4, 7):
            self._color_swatch.setStyleSheet(
                f"background:{color}; border:1px solid #E1E6ED; border-radius:4px;"
            )

    def _on_pick_color(self) -> None:
        actual = self._in_color.text() or "#1E5AA8"
        color = QColorDialog.getColor(initial=actual, parent=self)
        if color.isValid():
            self._in_color.setText(color.name())

    def _on_pick_logo(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar logo",
            str(Path.home()),
            "Imagenes (*.png *.jpg *.jpeg *.bmp);;Todos los archivos (*)",
        )
        if ruta:
            self._in_logo.setText(ruta)

    def _on_save(self) -> None:
        try:
            cfg = svc_cfg.obtener()
            cfg["empresa"] = {
                **cfg.get("empresa", {}),
                "nombre": self._in_nombre.text().strip(),
                "departamento": self._in_dept.text().strip(),
                "color_corporativo": self._in_color.text().strip() or "#1E5AA8",
                "logo_path": self._in_logo.text().strip(),
            }
            svc_cfg.guardar(cfg)
            QMessageBox.information(self, "Guardado", "Datos de la empresa actualizados.")
            self.changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


__all__ = ("EmpresaTab",)