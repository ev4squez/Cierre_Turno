"""Controller principal: conecta la UI con los services.

Toda la logica de coordinacion vive aca:

* Buscador live -> services.maquinas.buscar_maquinas
* Seleccion de maquina -> propagar a panel central y form
* Guardar incidencia -> services.incidencias.registrar + refrescar tabla
* Editar / eliminar -> services + refrescar
* Enviar informe -> services.email_renderer + services.outlook
* Refresh de totales / quick stats / footer

La UI nunca importa services directamente: solo emite signals, el
controller los escucha y decide que hacer.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Callable

from PySide6.QtWidgets import QMessageBox

from services import (
    configuracion as svc_cfg,
    incidencias as svc_inc,
    maquinas as svc_maq,
    outlook as svc_outlook,
)
from ui.main_window import MainWindow


class MainController:
    """Pega ``MainWindow`` con la capa de services.

    Uso::

        win = MainWindow()
        ctrl = MainController(win)
        ctrl.start()
        win.show()
    """

    def __init__(self, win: MainWindow) -> None:
        self.win = win
        self._selected_maquina: dict | None = None
        self._turno_actual: str = "Tarde"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Carga estado inicial (tecnicos, lista del dia, totales)."""
        cfg = svc_cfg.obtener()
        self.win.set_tecnicos(cfg.get("tecnicos", []))
        self._turno_actual = self._detectar_turno(cfg)
        # Carga lista del turno en curso
        self.refrescar_lista_turno()
        # Quick stats
        self._refrescar_quick_stats()
        # Footer
        self._refrescar_footer()
        # Setea el form en estado "sin maquina"
        self.win.set_form_machine(None)
        self.win.refresh_header()

    # ------------------------------------------------------------------
    # Handlers de signals
    # ------------------------------------------------------------------

    def on_search_query(self, query: str) -> None:
        """Busqueda live del sidebar."""
        resultados = svc_maq.buscar_maquinas(query, limit=25)
        self.win.set_search_results(resultados)

    def on_machine_selected(self, m: dict) -> None:
        """Maquina seleccionada: guardar referencia + mostrar form."""
        self._selected_maquina = m
        # La MainWindow ya propaga al panel central y al form via slot interno.
        # Solo necesitamos refrescar datetime del form (lo hace set_form_machine).

    def on_guardar_incidencia(self, data: dict) -> None:
        """Registrar nueva incidencia y refrescar la UI."""
        if self._selected_maquina is None:
            QMessageBox.warning(
                self.win,
                "Sin maquina",
                "Selecciona una maquina antes de registrar una incidencia.",
            )
            return
        try:
            cfg = svc_cfg.obtener()
            usuario = cfg.get("usuario_actual", "Operador")
            inc = svc_inc.registrar(
                numero_maquina=self._selected_maquina["numero_maquina"],
                problema=data["problema"],
                motivo_fuera_servicio=data["motivo_fuera_servicio"],
                accion_realizada=data["accion_realizada"],
                estado_final=data["estado_final"],
                observaciones=data["observaciones"],
                tecnico=data["tecnico"],
                turno=self._turno_actual,
                usuario=usuario,
            )
        except ValueError as e:
            QMessageBox.warning(self.win, "Datos invalidos", str(e))
            return
        except Exception as e:  # pragma: no cover - errores DB
            QMessageBox.critical(self.win, "Error al guardar", str(e))
            return

        # OK: refrescar lista, totales y limpiar form (manteniendo maquina)
        self.win.reset_form()
        # Re-seleccionar la maquina para no perder el contexto (rapido flujo)
        self.win.set_form_machine(self._selected_maquina)
        self.refrescar_lista_turno()
        self._refrescar_quick_stats()
        self._refrescar_footer()
        self._toast(f"Incidencia #{inc['id']} registrada.")

    def on_limpiar_form(self) -> None:
        """El operador toco Limpiar."""
        self.win.reset_form()
        if self._selected_maquina is not None:
            self.win.set_form_machine(self._selected_maquina)

    def on_editar_incidencia(self, inc_id: int) -> None:
        """Editar una fila: cargar al form y guardar actualiza en lugar de crear."""
        inc = svc_inc.obtener(inc_id)
        if inc is None:
            return
        # Cargar maquina en el buscador para mantener coherencia
        m = svc_maq.obtener_por_numero(inc["numero_maquina"])
        if m is not None:
            self._selected_maquina = m
            self.win.show_machine(m)
            self.win.set_form_machine(m)
        else:
            # Maquina no en catalogo: igual dejamos el form con el numero
            self._selected_maquina = None
            self.win.set_form_machine(None)
        # Pre-llenar campos
        self.win._form._cb_tecnico["widget"].setCurrentText(inc["tecnico"])
        # Buscar el problema en TIPOS_PROBLEMA
        tipo = inc.get("problema") or ""
        idx_tipo = self.win._form._cb_tipo["widget"].findText(tipo)
        if idx_tipo >= 0:
            self.win._form._cb_tipo["widget"].setCurrentIndex(idx_tipo)
        self.win._form._ta_motivo["widget"].setPlainText(inc.get("motivo_fuera_servicio", ""))
        self.win._form._ta_accion["widget"].setPlainText(inc.get("accion_realizada", ""))
        self.win._form._cb_estado["widget"].setCurrentText(inc.get("estado_final", "Fuera de Servicio"))
        self.win._form._ta_obs["widget"].setPlainText(inc.get("observaciones", ""))
        # Marcamos modo edicion via property del form (simple: cambiamos titulo)
        self._editando_id = inc_id

    def on_eliminar_incidencia(self, inc_id: int) -> None:
        """Eliminar con confirmacion."""
        res = QMessageBox.question(
            self.win,
            "Eliminar incidencia",
            f"Eliminar la incidencia #{inc_id}? Esta accion no se puede deshacer.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if res != QMessageBox.Yes:
            return
        svc_inc.eliminar(inc_id)
        self.refrescar_lista_turno()
        self._refrescar_quick_stats()
        self._refrescar_footer()
        self._toast(f"Incidencia #{inc_id} eliminada.")

    def on_enviar_informe(self) -> None:
        """Genera HTML + Outlook (o fallback a archivo)."""
        cfg = svc_cfg.obtener()
        hoy = date.today()
        resumen = svc_inc.resumen_turno(hoy, self._turno_actual)

        if resumen.total == 0:
            res = QMessageBox.question(
                self.win,
                "Sin incidencias",
                "No hay incidencias registradas en este turno. Enviar informe vacio?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if res != QMessageBox.Yes:
                return

        # Preparamos parametros del correo
        correo_cfg = cfg.get("correo", {})
        destinatarios = correo_cfg.get("destinatarios", []) or []
        cc = correo_cfg.get("cc", []) or []
        modo = correo_cfg.get("modo_envio", "display")
        asunto_tpl = correo_cfg.get(
            "asunto_template", "Informe Diario FDS - {fecha} - {turno}"
        )
        logo_path = cfg.get("empresa", {}).get("logo_path") or None

        turno_cfg = cfg.get("turno", {}).get(self._turno_actual.lower(), {})
        rango = turno_cfg.get("rango", "")
        etiqueta = turno_cfg.get("etiqueta", self._turno_actual)

        self.win.set_sending(True)
        try:
            resultado = svc_outlook.enviar_informe_turno(
                resumen=resumen,
                usuario=cfg.get("usuario_actual", "Operador"),
                turno_etiqueta=etiqueta,
                turno_rango=rango,
                destinatarios=destinatarios,
                cc=cc,
                modo=modo,
                asunto_template=asunto_tpl,
                logo_path=logo_path,
            )
        finally:
            self.win.set_sending(False)

        # Si ok: marcamos como correo_enviado y notificamos
        if resultado.get("ok"):
            ids = [r["id"] for r in resumen.registros]
            svc_inc.marcar_correo_enviado(ids)
            self.refrescar_lista_turno()
            QMessageBox.information(
                self.win,
                "Informe enviado",
                resultado.get("mensaje", "Informe enviado."),
            )
        else:
            # Fallback: HTML persistido
            archivo = resultado.get("archivo", "")
            QMessageBox.warning(
                self.win,
                "Outlook no disponible",
                f"{resultado.get('mensaje','')}\n\nArchivo guardado en:\n{archivo}",
            )

    def on_settings(self) -> None:
        """Abrir el dialogo de Configuracion (Empresa, Correo, Maquinas, Tecnicos)."""
        from ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self.win)
        def _on_changed() -> None:
            # Refrescar tecnicos en el form principal por si modificaron la lista
            cfg = svc_cfg.obtener()
            self.win.set_tecnicos(cfg.get("tecnicos", []))
            # Refrescar lista del turno y stats por si modificaron maquinas
            self.refrescar_lista_turno()
            self._refrescar_quick_stats()
            self._refrescar_footer()
            self._toast("Configuracion actualizada")
        dlg.finished_with_changes.connect(_on_changed)
        dlg.exec()

    def on_import(self) -> None:
        """Abrir el asistente de importacion desde Excel."""
        from ui.import_dialog import ImportDialog
        dlg = ImportDialog(self.win)
        # Cuando termina, refrescar buscador y stats por si se agregaron maquinas
        def _on_finished(resultado: dict) -> None:
            insertadas = resultado.get("insertadas", 0)
            actualizadas = resultado.get("actualizadas", 0)
            if insertadas > 0 or actualizadas > 0:
                # Re-poblar resultados del buscador y refrescar maquinas
                self.refrescar_lista_turno()
                self._refrescar_quick_stats()
                self._toast(
                    f"Importacion: {insertadas} nuevas, {actualizadas} actualizadas"
                )
        dlg.finished_with_result.connect(_on_finished)
        dlg.exec()

    def on_logout(self) -> None:
        """Cerrar la app (QApplication.quit)."""
        from PySide6.QtWidgets import QApplication
        QApplication.instance().quit() if QApplication.instance() else None

    # ------------------------------------------------------------------
    # Refresco de widgets
    # ------------------------------------------------------------------

    def refrescar_lista_turno(self) -> None:
        registros = svc_inc.listar_turno(date.today(), self._turno_actual)
        # Enriquecer con sector/marca para la tabla
        for r in registros:
            m = svc_maq.obtener_por_numero(r["numero_maquina"])
            if m:
                r["sector"] = m["sector"]
                r["marca"] = m["marca"]
        self.win.set_table_rows(registros)

    def _refrescar_quick_stats(self) -> None:
        resumen = svc_inc.resumen_turno(date.today(), self._turno_actual)
        # FDS activas en el sistema (catalogo): no necesariamente del turno
        # Mostramos del turno actual para coherencia.
        self.win.set_quick_stats(
            fds=resumen.fds,
            pendientes=resumen.pendientes_repuesto + resumen.en_observacion + resumen.espera_soporte,
            resueltas=resumen.operativas,
        )

    def _refrescar_footer(self) -> None:
        resumen = svc_inc.resumen_turno(date.today(), self._turno_actual)
        maquinas_unicas = len({r["numero_maquina"] for r in resumen.registros})
        cfg = svc_cfg.obtener()
        turno_cfg = cfg.get("turno", {}).get(self._turno_actual.lower(), {})
        # Hora de inicio del turno: el primer valor del rango
        inicio = (turno_cfg.get("rango") or "14:00-22:00").split("-")[0].strip() or "14:00"
        pendientes = resumen.fds + resumen.pendientes_repuesto + resumen.espera_soporte + resumen.en_observacion
        self.win.set_footer(
            total=resumen.total,
            maquinas=maquinas_unicas,
            pendientes=pendientes,
            inicio_turno=inicio,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _detectar_turno(self, cfg: dict) -> str:
        h = datetime.now().hour
        if 8 <= h < 14:
            return "Manana"
        if 14 <= h < 22:
            return "Tarde"
        return "Noche"

    def _toast(self, mensaje: str) -> None:
        """Mini-feedback en el status bar (placeholder simple)."""
        self.win.statusBar().showMessage(mensaje, 4000) if hasattr(self.win, "statusBar") else None

    # ------------------------------------------------------------------
    # Wire signals
    # ------------------------------------------------------------------

    def wire(self) -> None:
        """Conecta los signals de la ventana a los handlers de este controller."""
        self.win.searchQueryChanged.connect(self.on_search_query)
        self.win.machineSelected.connect(self.on_machine_selected)
        self.win.guardarIncidencia.connect(self.on_guardar_incidencia)
        self.win.limpiarForm.connect(self.on_limpiar_form)
        self.win.editarIncidencia.connect(self.on_editar_incidencia)
        self.win.eliminarIncidencia.connect(self.on_eliminar_incidencia)
        self.win.enviarInformeRequested.connect(self.on_enviar_informe)
        self.win.settingsRequested.connect(self.on_settings)
        self.win.logoutRequested.connect(self.on_logout)
        self.win.importRequested.connect(self.on_import)


__all__ = ("MainController",)