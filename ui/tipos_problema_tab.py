"""Tab de gestion de Tipos de Problema (dentro de SettingsDialog).

UI para agregar / renombrar / eliminar las categorias que aparecen
en el combo 'Tipo de problema' del formulario de FDS.

Lee y escribe en la DB via ``services.tipos_problema_db``. Antes los
tipos vivian en ``config.TIPOS_PROBLEMA`` (constante de modulo);
ahora se persisten en una tabla SQLite para que el operador pueda
modificarlos sin reiniciar la app.

Cuando el operador elimina un tipo que tiene incidencias registradas,
la UI le avisa cuantas lo usan y pide confirmacion explicita.
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

from services import tipos_problema_db
from ui.widgets import EditableListWidget


class TiposProblemaTab(QFrame):
    """UI para CRUD de tipos de problema.

    Signals
    -------
    changed: emite cuando la lista cambia (agregar / renombrar /
             eliminar). El controller refresca el combo del form de FDS.
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

        titulo = QLabel("Tipos de problema")
        titulo.setStyleSheet("font-size:15px; font-weight:700; color:#1B2430;")
        sub = QLabel(
            "Categorias que el operador elige en el combo 'Tipo de problema' "
            "del formulario de registro de FDS. Los cambios se reflejan en "
            "vivo (no hace falta reiniciar la app)."
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
            "Sugerencia: mantener entre 6 y 12 tipos para que el combo "
            "siga siendo rapido de usar."
        )
        hint.setStyleSheet("color:#64748B; font-size:11px;")
        cb.addWidget(hint)
        root.addWidget(self._count_box)

        # Lista editable
        self._lista = EditableListWidget(
            titulo="Categorias",
            placeholder="Ej: Falla electrica, Atasco de papel, ...",
        )
        self._lista.changed.connect(self._on_lista_changed)
        # Conectamos el boton 'Quitar' para que avise si hay
        # incidencias usandolo antes de borrar.
        # (EditableListWidget ya tiene 'Quitar seleccionado'; el signal
        # ``changed`` se dispara cuando la lista cambia. Para el caso de
        # eliminar, hacemos la confirmacion dentro de _on_lista_changed.)
        root.addWidget(self._lista, 1)

    def _cargar(self) -> None:
        try:
            tipos = tipos_problema_db.listar(incluir_inactivos=False)
            nombres = [t["nombre"] for t in tipos]
            self._lista.set_items(nombres)
            self._update_count(nombres)
        except Exception as e:
            QMessageBox.warning(
                self, "Error", f"No se pudieron cargar los tipos:\\n{e}"
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

        Comparamos la lista nueva contra la DB y aplicamos diffs:
          - Agregar los que no estaban
          - Renombrar los que cambiaron
          - Soft-delete los que se quitaron
        """
        try:
            actuales = tipos_problema_db.listar(incluir_inactivos=True)
            actuales_activos = {t["nombre"] for t in actuales if t["activo"]}
            entrantes = set(nuevos)

            # Renombres: nombre que esta en actuales y en entrantes pero con texto distinto
            # Lo detectamos mirando las listas en orden: si el operador reordeno
            # la lista, EditableListWidget NO preserva la identidad por ahora
            # (renombra = borrar + agregar). Aca manejamos eso de forma simple:
            # nombres en entrantes que no coinciden exactamente con ningun
            # activo -> son candidatos a agregar O renombres.

            # 1. Detectar renombres: para cada activo, si su nombre NO esta en
            #    entrantes pero su posicion coincide con un entrante que tampoco
            #    estaba -> renombre.
            actuales_orden = [t["nombre"] for t in actuales if t["activo"]]
            for i, viejo in enumerate(actuales_orden):
                if viejo in entrantes:
                    continue  # sigue existiendo igual
                if i >= len(nuevos):
                    # el operador lo elimino
                    tipos_problema_db.eliminar(viejo)
                    continue
                nuevo = nuevos[i]
                # Si 'nuevo' tampoco estaba en activos, es renombre
                if nuevo not in actuales_activos:
                    try:
                        tipos_problema_db.renombrar(viejo, nuevo)
                    except ValueError as ex:
                        QMessageBox.warning(self, "No se pudo renombrar", str(ex))

            # 2. Agregar los que no estaban en ningun momento
            todos_los_activos = set(tipos_problema_db.listar_nombres(solo_activos=True))
            for nombre in entrantes:
                if nombre not in todos_los_activos:
                    try:
                        tipos_problema_db.agregar(nombre)
                    except ValueError as ex:
                        QMessageBox.warning(self, "No se pudo agregar", str(ex))

            # 3. Eliminar los activos que ya no estan en la lista nueva
            actuales_finales = set(tipos_problema_db.listar_nombres(solo_activos=True))
            for nombre in actuales_finales - entrantes:
                # Si hay incidencias usandolo, avisamos y pedimos confirmacion
                usos = tipos_problema_db.contar_incidencias_que_usan(nombre)
                if usos > 0:
                    res = QMessageBox.question(
                        self,
                        "Tipo en uso",
                        f"'{nombre}' esta usado en {usos} incidencia(s) "
                        f"registrada(s). Si lo eliminas, las incidencias "
                        f"viejas seguiran mostrandolo en su historial, pero "
                        f"ya no aparecera en el combo para registrar nuevas.\n\n"
                        f"Eliminar igual?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No,
                    )
                    if res != QMessageBox.Yes:
                        # Devolvemos el item a la lista (recargar)
                        self._cargar()
                        self.changed.emit()
                        return
                try:
                    tipos_problema_db.eliminar(nombre)
                except ValueError as ex:
                    QMessageBox.warning(self, "No se pudo eliminar", str(ex))

            # Refrescar el contador
            self._update_count(list(entrantes))
            self.changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar la lista:\\n{e}")
            # Refrescar para volver al estado consistente con la DB
            self._cargar()

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def refrescar(self) -> None:
        """Recarga desde la DB (util cuando otro tab los modifica)."""
        self._cargar()


__all__ = ("TiposProblemaTab",)
