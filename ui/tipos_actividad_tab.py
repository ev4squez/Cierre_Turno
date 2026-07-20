"""Tab de gestion de Tipos de Actividad (dentro de SettingsDialog).

UI para agregar / renombrar / eliminar las tareas que aparecen en el
combo 'Tarea' del modulo 'Registro de Actividades Diarias'.

Replica el patron de ``TiposProblemaTab``:
  - Lee y escribe en la DB via ``services.tipos_actividad_db``.
  - Los tipos viven en la DB (no en ``config.TIPOS_ACTIVIDAD``)
    para que el operador los modifique sin reiniciar la app.
  - Cuando se elimina un tipo que esta en uso, avisa cuantas
    actividades lo registran y pide confirmacion explicita.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from services import tipos_actividad_db
from ui.widgets import EditableListWidget


class TiposActividadTab(QFrame):
    """UI para CRUD de tipos de actividad.

    Signals
    -------
    changed: emite cuando la lista cambia (agregar / renombrar /
             eliminar). El controller puede refrescar el combo del
             dialog de Actividades para que se vea el cambio en vivo.
    """

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._cargar()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        titulo = QLabel("Tipos de actividad")
        titulo.setStyleSheet("font-size:15px; font-weight:700; color:#1B2430;")
        sub = QLabel(
            "Tareas que el operador elige en el combo 'Tarea' del modulo "
            "Registro de Actividades Diarias. Los cambios se reflejan en "
            "vivo (no hace falta reiniciar la app). Las actividades ya "
            "registradas mantienen el nombre que tenian al cargarse, "
            "incluso si despues renombras o eliminas el tipo."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("color:#64748B; font-size:12px;")
        root.addWidget(titulo)
        root.addWidget(sub)

        # Banda informativa: cuantos tipos hay
        self._count_box = QFrame()
        self._count_box.setStyleSheet(
            "QFrame{background:#EAF1FB; border:1px solid #C7DBF5; "
            "border-radius:8px; padding:6px 10px;}"
            "QLabel{color:#1E5AA8; font-size:12px;}"
        )
        cb = QVBoxLayout(self._count_box)
        cb.setContentsMargins(10, 6, 10, 6)
        cb.setSpacing(2)
        self._lbl_count = QLabel("0 tipos activos")
        self._lbl_count.setStyleSheet("font-weight:700; color:#1B2430;")
        cb.addWidget(self._lbl_count)
        hint = QLabel(
            "Sugerencia: mantener entre 8 y 15 tipos para que el combo "
            "siga siendo rapido de usar."
        )
        hint.setStyleSheet("color:#64748B; font-size:11px;")
        cb.addWidget(hint)
        root.addWidget(self._count_box)

        # Lista editable
        self._lista = EditableListWidget(
            titulo="Tareas",
            placeholder="Ej: Asistencia Slot, Reposicion de papel, ...",
        )
        self._lista.changed.connect(self._on_lista_changed)
        root.addWidget(self._lista, 1)

    def _cargar(self) -> None:
        try:
            tipos = tipos_actividad_db.listar(incluir_inactivos=False)
            nombres = [t["nombre"] for t in tipos]
            self._lista.set_items(nombres)
            self._update_count(nombres)
        except Exception as e:
            QMessageBox.warning(
                self, "Error", f"No se pudieron cargar los tipos:\n{e}"
            )

    def _update_count(self, nombres: list[str]) -> None:
        n = len(nombres)
        if n == 0:
            self._lbl_count.setText("Sin tipos definidos (los operadores no veran opciones)")
            self._lbl_count.setStyleSheet("font-weight:700; color:#DC2626;")
        elif n == 1:
            self._lbl_count.setText("1 tipo activo")
            self._lbl_count.setStyleSheet("font-weight:700; color:#1B2430;")
        else:
            self._lbl_count.setText(f"{n} tipos activos")
            self._lbl_count.setStyleSheet("font-weight:700; color:#1B2430;")

    def _on_lista_changed(self, nuevos: list[str]) -> None:
        """Sincroniza los cambios de la lista con la DB.

        Mismo algoritmo que TiposProblemaTab: detecta renombres vs
        altas vs bajas comparando orden y presencia.
        """
        try:
            actuales = tipos_actividad_db.listar(incluir_inactivos=True)
            actuales_activos = {t["nombre"] for t in actuales if t["activo"]}
            entrantes = set(nuevos)

            # 1. Detectar renombres / bajas
            actuales_orden = [t["nombre"] for t in actuales if t["activo"]]
            for i, viejo in enumerate(actuales_orden):
                if viejo in entrantes:
                    continue
                if i >= len(nuevos):
                    tipos_actividad_db.eliminar(viejo)
                    continue
                nuevo = nuevos[i]
                if nuevo not in actuales_activos:
                    try:
                        tipos_actividad_db.renombrar(viejo, nuevo)
                    except ValueError as ex:
                        QMessageBox.warning(self, "No se pudo renombrar", str(ex))

            # 2. Agregar los que no estaban
            todos_los_activos = set(tipos_actividad_db.listar_nombres(solo_activos=True))
            for nombre in entrantes:
                if nombre not in todos_los_activos:
                    try:
                        tipos_actividad_db.agregar(nombre)
                    except ValueError as ex:
                        QMessageBox.warning(self, "No se pudo agregar", str(ex))

            # 3. Eliminar los activos que ya no estan
            actuales_finales = set(tipos_actividad_db.listar_nombres(solo_activos=True))
            for nombre in actuales_finales - entrantes:
                usos = tipos_actividad_db.contar_actividades_que_usan(nombre)
                if usos > 0:
                    res = QMessageBox.question(
                        self,
                        "Tipo en uso",
                        f"'{nombre}' esta usado en {usos} actividad(es) "
                        f"registrada(s). Si lo eliminas, las actividades "
                        f"viejas seguiran mostrandolo en su historial, pero "
                        f"ya no aparecera en el combo para registrar nuevas.\n\n"
                        f"Eliminar igual?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No,
                    )
                    if res != QMessageBox.Yes:
                        self._cargar()
                        self.changed.emit()
                        return
                try:
                    tipos_actividad_db.eliminar(nombre)
                except ValueError as ex:
                    QMessageBox.warning(self, "No se pudo eliminar", str(ex))

            self._update_count(list(entrantes))
            self.changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar la lista:\n{e}")
            self._cargar()

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def refrescar(self) -> None:
        """Recarga desde la DB (util cuando otro tab los modifica)."""
        self._cargar()


__all__ = ("TiposActividadTab",)
