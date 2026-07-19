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
        # 1. Migrar tecnicos desde config.json a la DB (la primera vez).
        #    Es idempotente: si ya estan en la DB, no hace nada.
        try:
            from services import tecnicos_db
            tecnicos_db.migrar_desde_config()
        except Exception as e:
            # Si falla la migracion, logueamos pero seguimos
            print(f"[WARN] migrar tecnicos desde config: {e}")

        # 2. Cargar tecnicos y usuario actual desde la DB
        try:
            from services import tecnicos_db
            tecnicos = tecnicos_db.listar(incluir_inactivos=False)
            self.win.set_tecnicos([t["nombre"] for t in tecnicos])
        except Exception as e:
            print(f"[WARN] cargar tecnicos de DB: {e}")
            cfg = svc_cfg.obtener()
            self.win.set_tecnicos(cfg.get("tecnicos", []))

        # 3. Refrescar el chip del topbar con el usuario actual de la DB
        self.refrescar_topbar_usuario()

        cfg = svc_cfg.obtener()
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

    def refrescar_topbar_usuario(self) -> None:
        """Recarga el nombre y rol del topbar desde la DB.

        Llamado en el startup y cada vez que el usuario modifica la lista
        de tecnicos en Settings (para que el chip refleje el cambio
        en vivo, sin reiniciar la app).
        """
        try:
            from services import tecnicos_db
            actual = tecnicos_db.obtener_usuario_actual()
            if actual is not None:
                self.win.set_topbar_usuario(
                    nombre=actual["nombre"],
                    rol="Operador de sala",
                )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Handlers de signals
    # ------------------------------------------------------------------

    def on_search_query(self, query: str) -> None:
        """Busqueda live del sidebar."""
        # Si no hay query, priorizamos maquinas problematicas (En
        # Observacion, FDS, etc.) para que el operador las vea al
        # abrir el sistema sin tipear nada.
        if not (query or "").strip():
            resultados = svc_maq.buscar_maquinas_priorizando_problematicas("", limit=25)
        else:
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
            usuario = self._obtener_usuario_actual()
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
        """Genera HTML + Outlook (o fallback a archivo).

        Antes de armar el correo, abre un dialogo modal que obliga a
        identificar al tecnico que envia. Ese nombre se usa en el campo
        "Enviado por" del informe y como firma al pie (sobreescribiendo
        la firma por defecto del config).
        """
        from ui.firmante_dialog import FirmanteDialog

        cfg = svc_cfg.obtener()
        hoy = date.today()
        resumen = svc_inc.resumen_turno(hoy, self._turno_actual)

        # Parametros del correo (los calculamos aca para mostrarlos en el
        # dialogo y para usarlos en el envio).
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

        # Tecnicos disponibles para el dialogo (de la DB si se puede)
        from services import tecnicos_db
        try:
            tecnicos_lista = [t["nombre"] for t in tecnicos_db.listar(incluir_inactivos=False)]
        except Exception:
            tecnicos_lista = list(cfg.get("tecnicos", []) or [])
        # Preseleccion: usuario actual de la DB, si existe
        preselect = ""
        try:
            actual = tecnicos_db.obtener_usuario_actual()
            if actual is not None:
                preselect = actual["nombre"]
        except Exception:
            pass
        if not preselect:
            preselect = self._obtener_usuario_actual()

        # Dialogo modal: si cancela, no enviamos nada
        dlg = FirmanteDialog(
            parent=self.win,
            tecnicos=tecnicos_lista,
            preseleccionado=preselect,
            destinatarios=destinatarios,
        )
        if dlg.exec() != FirmanteDialog.Accepted:
            return
        nombre_firmante = dlg.get_nombre()
        if not nombre_firmante:
            return

        if resumen.total == 0:
            res = QMessageBox.question(
                self.win,
                "Sin incidencias",
                f"No hay incidencias registradas en este turno. "
                f"Enviar informe vacio firmado por '{nombre_firmante}'?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if res != QMessageBox.Yes:
                return

        self.win.set_sending(True)
        try:
            # Enriquecer registros con datos de maquinas para que el informe
            # muestre marca/modelo/sector/isla/denominacion en la tabla.
            registros_enriquecidos = self._enriquecer_registros(list(resumen.registros))
            # Reemplazar registros en el resumen para el envio (sin perder
            # los conteos ya calculados).
            resumen.registros = registros_enriquecidos

            # Calcular tiempo promedio real desde la DB
            from services.incidencias import tiempo_promedio_resolucion_min, total_maquinas_catalogo
            tiempo_real = tiempo_promedio_resolucion_min(resumen.registros)
            total_maquinas = total_maquinas_catalogo(solo_activas=True)

            # El nombre del firmante va tanto al "Enviado por" del HTML
            # (parametro ``usuario``) como al bloque firma al pie
            # (parametro ``firmante``). Asi el destinatario sabe de
            # quien viene aunque el sistema lo usen varios tecnicos.
            resultado = svc_outlook.enviar_informe_turno(
                resumen=resumen,
                usuario=nombre_firmante,
                firmante=nombre_firmante,
                turno_etiqueta=etiqueta,
                turno_rango=rango,
                destinatarios=destinatarios,
                cc=cc,
                modo=modo,
                asunto_template=asunto_tpl,
                logo_path=logo_path,
                tiempo_promedio_min=tiempo_real,
                total_maquinas_catalogo=total_maquinas,
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
            # Refrescar tecnicos desde la DB
            try:
                from services import tecnicos_db
                tecnicos = tecnicos_db.listar(incluir_inactivos=False)
                self.win.set_tecnicos([t["nombre"] for t in tecnicos])
            except Exception as e:
                print(f"[WARN] refrescar tecnicos: {e}")
            # Refrescar el topbar (puede haber cambiado el operador actual)
            self.refrescar_topbar_usuario()
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

    def _enriquecer_registros(self, registros: list[dict]) -> list[dict]:
        """Agrega sector/isla/marca/modelo/denominacion a cada registro.

        Los registros vienen de ``incidencias`` que no tienen join con
        ``maquinas``. Para que la tabla y el informe muestren info completa,
        cruzamos con el catalogo de maquinas.
        """
        for r in registros:
            m = svc_maq.obtener_por_numero(r["numero_maquina"])
            if m:
                r["sector"] = m["sector"]
                r["isla"] = m["isla"]
                r["marca"] = m["marca"]
                r["modelo"] = m["modelo"]
                r["denominacion"] = m["denominacion"]
        return registros

    def refrescar_lista_turno(self) -> None:
        registros = svc_inc.listar_turno(date.today(), self._turno_actual)
        self._enriquecer_registros(registros)
        self.win.set_table_rows(registros)

    def _refrescar_quick_stats(self) -> None:
        """Actualiza el dashboard KPI con el estado REAL del catalogo.

        Cambio conceptual: las 4 cards ahora cuentan el ESTADO de cada
        maquina en el catalogo (no las incidencias del turno). Asi
        una maquina "En Observacion" sigue visible aunque no se haya
        registrado una incidencia hoy. Esto es lo que el operador
        espera ver: el estado actual del parque de maquinas.

        Fuentes:
          * ``services.maquinas.contar_por_estado`` para el desglose
            por estado (Operativa / FDS / Pend Rep / Esp Tecnico /
            En Observacion).
          * ``services.incidencias.resumen_turno`` para contar las
            Operativas RESUELTAS en el turno actual (caso verde:
            "Resueltas hoy" sigue siendo metric de productividad
            del turno, no del catalogo).
        """
        from services import maquinas as svc_maq

        # Conteos por estado del catalogo (incluye TODAS las activas).
        catalogo = svc_maq.contar_por_estado(solo_activas=True)

        fds = catalogo.get("Fuera de Servicio", 0)
        pendientes = (
            catalogo.get("Pendiente Repuesto", 0)
            + catalogo.get("Espera Servicio Tecnico", 0)
        )
        en_observacion = catalogo.get("En Observacion", 0)
        operativas = catalogo.get("Operativa", 0)
        total_maquinas = sum(catalogo.values())

        # "Resueltas hoy" sigue siendo una metrica del turno:
        # las incidencias Operativas registradas en este turno.
        resumen = svc_inc.resumen_turno(date.today(), self._turno_actual)
        resueltas = resumen.operativas

        self.win.set_quick_stats(
            fds=fds,
            pendientes=pendientes,
            resueltas=resueltas,
            en_observacion=en_observacion,
        )
        # Tambien actualizamos el footer con los contadores del catalogo.
        self.win.set_estado_catalogo(
            total=total_maquinas,
            operativas=operativas,
            en_observacion=en_observacion,
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

    def _obtener_usuario_actual(self) -> str:
        """Devuelve el nombre del tecnico marcado como usuario actual.

        Lee de la DB. Si no hay ninguno marcado, usa el del config o
        'Operador' como fallback.
        """
        try:
            from services import tecnicos_db
            actual = tecnicos_db.obtener_usuario_actual()
            if actual is not None:
                return actual["nombre"]
        except Exception:
            pass
        cfg = svc_cfg.obtener()
        return cfg.get("usuario_actual", "Operador")
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