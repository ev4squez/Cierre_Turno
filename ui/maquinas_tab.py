"""Tab de gestion de Maquinas (CRUD + papelera) dentro de SettingsDialog.

UI:
  - Arriba: campo de busqueda + botones [Nueva] [Editar] [Eliminar/Reactivar]
  - Centro: tabla con todas las maquinas (incluyendo inactivas)
  - Abajo: sub-tab "Activas" / "Papelera" para filtrar la vista
  - Dialogo modal para crear/editar una maquina
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from config import ESTADOS_MAQUINA
from services import admin as svc_admin
from services import maquinas as svc_maq


COLS = [
    "Numero",
    "Sector",
    "Isla",
    "Marca",
    "Modelo",
    "Serie",
    "Juego",
    "Estado",
    "Acciones",
]


class MaquinaEditorDialog(QDialog):
    """Dialogo modal para crear o editar una maquina."""

    def __init__(self, *, maquina: Optional[dict] = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar maquina" if maquina else "Nueva maquina")
        self.setMinimumWidth(520)
        self.setModal(True)

        self._build_ui()
        if maquina:
            self._cargar(maquina)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        titulo = QLabel("Datos de la maquina")
        titulo.setStyleSheet("font-size:14px; font-weight:700; color:#1B2430;")
        root.addWidget(titulo)

        form = QFormLayout()
        form.setSpacing(10)

        # Numero (obligatorio)
        self._in_numero = QLineEdit()
        self._in_numero.setPlaceholderText("Ej: 5001, 5002, 5238")
        form.addRow("Codigo Casino *", self._in_numero)

        # Sector
        self._in_sector = QLineEdit()
        self._in_sector.setPlaceholderText("Ej: TERRAZA, SALA TOKIKURA")
        form.addRow("Sector", self._in_sector)

        # Isla
        self._in_isla = QLineEdit()
        self._in_isla.setPlaceholderText("Numero de isla")
        form.addRow("Isla", self._in_isla)

        # Codigo SCJ
        self._in_scj = QLineEdit()
        self._in_scj.setPlaceholderText("Codigo de homologacion SCJ (opcional)")
        form.addRow("Codigo SCJ", self._in_scj)

        # Marca
        self._in_marca = QLineEdit()
        self._in_marca.setPlaceholderText("Ej: ARISTOCRAT Technologies, Inc")
        form.addRow("Fabricante", self._in_marca)

        # Modelo
        self._in_modelo = QLineEdit()
        self._in_modelo.setPlaceholderText("Ej: HELIX UPRIGHT")
        form.addRow("Modelo", self._in_modelo)

        # Serie
        self._in_serie = QLineEdit()
        self._in_serie.setPlaceholderText("Nro de serie del gabinete")
        form.addRow("Serie", self._in_serie)

        # Denominacion (juego)
        self._in_denom = QLineEdit()
        self._in_denom.setPlaceholderText("Ej: GOLDEN AMULET")
        form.addRow("Programa de juego", self._in_denom)

        # Estado
        self._cb_estado = QComboBox()
        self._cb_estado.addItems(ESTADOS_MAQUINA)
        form.addRow("Estado actual", self._cb_estado)

        root.addLayout(form)

        # Botones
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Save).setText("Guardar")
        bb.button(QDialogButtonBox.Save).setObjectName("btnPrimary")
        bb.button(QDialogButtonBox.Cancel).setText("Cancelar")
        bb.button(QDialogButtonBox.Cancel).setObjectName("btnSecondary")
        bb.accepted.connect(self._on_save)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def _cargar(self, m: dict) -> None:
        self._in_numero.setText(str(m.get("numero_maquina") or ""))
        self._in_numero.setReadOnly(True)  # numero es PK, no se puede cambiar
        self._in_sector.setText(str(m.get("sector") or ""))
        self._in_isla.setText(str(m.get("isla") or ""))
        self._in_scj.setText(str(m.get("codigo_scj") or ""))
        self._in_marca.setText(str(m.get("marca") or ""))
        self._in_modelo.setText(str(m.get("modelo") or ""))
        self._in_serie.setText(str(m.get("serie") or ""))
        self._in_denom.setText(str(m.get("denominacion") or ""))
        idx = self._cb_estado.findText(str(m.get("estado") or "Operativa"))
        if idx >= 0:
            self._cb_estado.setCurrentIndex(idx)

    def _on_save(self) -> None:
        try:
            payload = {
                "numero_maquina": self._in_numero.text().strip(),
                "sector": self._in_sector.text().strip(),
                "isla": self._in_isla.text().strip(),
                "codigo_scj": self._in_scj.text().strip(),
                "marca": self._in_marca.text().strip(),
                "modelo": self._in_modelo.text().strip(),
                "serie": self._in_serie.text().strip(),
                "denominacion": self._in_denom.text().strip(),
                "estado": self._cb_estado.currentText(),
            }
            # Validacion basica
            if not payload["numero_maquina"]:
                QMessageBox.warning(self, "Falta dato", "Codigo Casino es obligatorio.")
                return
            # Si el numero es readonly (modo edicion), no lo cambiamos
            if self._in_numero.isReadOnly():
                # Edicion via actualizar_maquina por id
                id_ = self._maquina_id
                svc_maq.actualizar_maquina(id_, payload)
            else:
                # Crear nueva
                try:
                    svc_maq.crear_maquina(payload)
                except ValueError as ve:
                    # Si ya existe, caemos a actualizar (upsert)
                    if "ya existe" in str(ve).lower() or "existe" in str(ve).lower():
                        m = svc_maq.obtener_por_numero(payload["numero_maquina"])
                        if m:
                            svc_maq.actualizar_maquina(m["id"], payload)
                        else:
                            raise ve
                    else:
                        raise ve
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error al guardar", str(e))

    def set_id(self, maquina_id: int) -> None:
        """Usado por el caller para saber sobre que ID editar."""
        self._maquina_id = maquina_id


class MaquinasTab(QFrame):
    """UI completa: buscador + sub-tabs (Activas / Papelera) + tabla."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._cargar()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Header
        head = QFrame()
        hl = QHBoxLayout(head)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)
        titulo = QLabel("Catalogo de maquinas")
        titulo.setStyleSheet("font-size:15px; font-weight:700; color:#1B2430;")
        hl.addWidget(titulo)
        hl.addStretch(1)

        # Buscador
        from PySide6.QtWidgets import QLineEdit
        self._buscar = QLineEdit()
        self._buscar.setPlaceholderText("Buscar por numero, marca o modelo...")
        self._buscar.setMaximumWidth(280)
        self._buscar.textChanged.connect(self._refrescar)
        hl.addWidget(self._buscar)

        btn_nueva = QPushButton("Nueva")
        btn_nueva.setObjectName("btnPrimary")
        btn_nueva.clicked.connect(self._on_nueva)
        hl.addWidget(btn_nueva)
        root.addWidget(head)

        # Sub-tabs Activas / Papelera
        self._subtabs = QTabWidget()
        self._tabla_activas = self._build_tabla()
        self._tabla_papelera = self._build_tabla()
        self._subtabs.addTab(self._tabla_activas, "Activas")
        self._subtabs.addTab(self._tabla_papelera, "Papelera")
        self._subtabs.currentChanged.connect(self._refrescar)
        root.addWidget(self._subtabs, 1)

        # Contador
        self._lbl_count = QLabel("")
        self._lbl_count.setStyleSheet("color:#64748B; font-size:12px;")
        root.addWidget(self._lbl_count)

    def _build_tabla(self) -> QTableWidget:
        tabla = QTableWidget(0, len(COLS))
        tabla.setHorizontalHeaderLabels(COLS)
        tabla.verticalHeader().setVisible(False)
        tabla.setSelectionBehavior(QTableWidget.SelectRows)
        tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        tabla.setAlternatingRowColors(True)
        header = tabla.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        for c in (0, 1, 3, 5, 7):
            header.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        return tabla

    def _cargar(self) -> None:
        self._refrescar()

    def refrescar_publico(self) -> None:
        """Recarga desde la DB (util cuando otros tabs la modifican)."""
        self._refrescar()

    def select_by_numero(self, numero_maquina: str) -> bool:
        """Selecciona la fila de la maquina con ese numero.

        Usado por el boton 'Editar datos' del panel central: el
        controller abre este tab con la maquina preseleccionada y
        nosotros marcamos su fila para que el operador la vea
        inmediatamente. Retorna True si encontro la fila.
        """
        if not numero_maquina:
            return False
        # Asegurarnos de que el tab 'Activas' este visible y refrescado
        try:
            self._subtabs.setCurrentIndex(0)
        except Exception:
            pass
        self._refrescar()
        # Buscar en la tabla de activas
        for row in range(self._tabla_activas.rowCount()):
            num_item = self._tabla_activas.item(row, 0)
            if num_item and num_item.text() == numero_maquina:
                self._tabla_activas.selectRow(row)
                self._tabla_activas.scrollToItem(
                    num_item, self._tabla_activas.PositionAtCenter
                )
                return True
        return False

    def _refrescar(self) -> None:
        self._tabla_activas.setRowCount(0)
        self._tabla_papelera.setRowCount(0)

        filtro = (self._buscar.text() or "").strip()

        # Activas
        try:
            activas = svc_admin.listar_todas(incluir_inactivas=False)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudieron cargar las maquinas:\n{e}")
            return

        if filtro:
            fl = filtro.lower()
            activas = [
                m for m in activas
                if fl in str(m.get("numero_maquina", "")).lower()
                or fl in str(m.get("marca", "")).lower()
                or fl in str(m.get("modelo", "")).lower()
            ]
        for m in activas:
            self._add_fila(self._tabla_activas, m, inactiva=False)

        # Papelera
        try:
            inactivas = svc_admin.listar_todas(incluir_inactivas=True)
            inactivas = [m for m in inactivas if not m["activo"]]
        except Exception:
            inactivas = []
        for m in inactivas:
            self._add_fila(self._tabla_papelera, m, inactiva=True)

        self._lbl_count.setText(
            f"{len(activas)} maquinas activas, "
            f"{len(inactivas)} en papelera"
        )

    def _add_fila(self, tabla: QTableWidget, m: dict, *, inactiva: bool) -> None:
        row = tabla.rowCount()
        tabla.insertRow(row)

        tabla.setItem(row, 0, QTableWidgetItem(str(m.get("numero_maquina") or "")))
        tabla.setItem(row, 1, QTableWidgetItem(str(m.get("sector") or "")))
        tabla.setItem(row, 2, QTableWidgetItem(str(m.get("isla") or "")))
        tabla.setItem(row, 3, QTableWidgetItem(str(m.get("marca") or "")))
        tabla.setItem(row, 4, QTableWidgetItem(str(m.get("modelo") or "")))
        tabla.setItem(row, 5, QTableWidgetItem(str(m.get("serie") or "")))
        tabla.setItem(row, 6, QTableWidgetItem(str(m.get("denominacion") or "")))
        tabla.setItem(row, 7, QTableWidgetItem(str(m.get("estado") or "")))

        # Acciones
        acciones = QFrame()
        al = QHBoxLayout(acciones)
        al.setContentsMargins(4, 2, 4, 2)
        al.setSpacing(6)
        from ui.helpers import svg

        if inactiva:
            btn_react = QPushButton("Reactivar")
            btn_react.setObjectName("btnGhost")
            btn_react.clicked.connect(lambda _=False, mid=m["id"]: self._on_reactivar(mid))
            al.addWidget(btn_react)
        else:
            btn_edit = QPushButton("Editar")
            btn_edit.setObjectName("btnGhost")
            btn_edit.clicked.connect(lambda _=False, mm=m: self._on_editar(mm))
            al.addWidget(btn_edit)
            btn_del = QPushButton("Eliminar")
            btn_del.setObjectName("btnDangerGhost")
            btn_del.clicked.connect(lambda _=False, mid=m["id"]: self._on_eliminar(mid, m.get("numero_maquina", "")))
            al.addWidget(btn_del)
        tabla.setCellWidget(row, 8, acciones)
        tabla.setRowHeight(row, 36)

    # ----- Handlers -----

    def _on_nueva(self) -> None:
        dlg = MaquinaEditorDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._refrescar()
            self.changed.emit()

    def _on_editar(self, m: dict) -> None:
        dlg = MaquinaEditorDialog(maquina=m, parent=self)
        dlg.set_id(m["id"])
        if dlg.exec() == QDialog.Accepted:
            self._refrescar()
            self.changed.emit()

    def _on_eliminar(self, maquina_id: int, numero: str) -> None:
        res = QMessageBox.question(
            self,
            "Eliminar maquina",
            f"Eliminar la maquina {numero}?\n"
            "Queda en la papelera (soft-delete). La podes reactivar despues.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if res != QMessageBox.Yes:
            return
        try:
            svc_maq.eliminar_maquina(maquina_id, soft=True)
            self._refrescar()
            self.changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_reactivar(self, maquina_id: int) -> None:
        try:
            svc_admin.reactivar_maquina(maquina_id)
            self._refrescar()
            self.changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


__all__ = ("MaquinasTab", "MaquinaEditorDialog")