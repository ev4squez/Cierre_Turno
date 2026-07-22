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

from PySide6.QtCore import QTimer
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

        # 1b. Migrar tipos de problema desde config.TIPOS_PROBLEMA a la DB
        #     (la primera vez). Mismo patron que tecnicos_db.
        try:
            from services import tipos_problema_db
            tipos_problema_db.migrar_desde_config()
        except Exception as e:
            print(f"[WARN] migrar tipos de problema desde config: {e}")

        # 1c. Migrar tipos de actividad desde config.TIPOS_ACTIVIDAD a
        #     la DB (la primera vez). Mismo patron que tipos de problema.
        try:
            from services import tipos_actividad_db
            tipos_actividad_db.migrar_desde_config()
        except Exception as e:
            print(f"[WARN] migrar tipos de actividad desde config: {e}")

        # 2. Cargar tecnicos y usuario actual desde la DB
        try:
            from services import tecnicos_db
            tecnicos = tecnicos_db.listar(incluir_inactivos=False)
            self.win.set_tecnicos([t["nombre"] for t in tecnicos])
        except Exception as e:
            print(f"[WARN] cargar tecnicos de DB: {e}")
            cfg = svc_cfg.obtener()
            self.win.set_tecnicos(cfg.get("tecnicos", []))

        # 2b. Cargar tipos de problema desde la DB y popular el combo del form.
        try:
            from services import tipos_problema_db
            tipos = tipos_problema_db.listar_nombres(solo_activos=True)
            self.win.set_tipos_problema(tipos)
        except Exception as e:
            print(f"[WARN] cargar tipos de problema de DB: {e}")
            # Fallback al config si la DB falla
            from config import TIPOS_PROBLEMA
            self.win.set_tipos_problema(list(TIPOS_PROBLEMA))

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
        """Busqueda live del sidebar, respetando el filtro de estado.

        Si el filtro es "Todos" y no hay query, priorizamos las
        problematicas para que el operador las vea al abrir el sistema
        sin tipear nada. Si hay filtro o query, usamos la busqueda
        normal respetando el filtro de estado.
        """
        filtro = self.win._search_panel.get_filtro_estado()
        # Sin query + sin filtro: priorizamos problematicas (UX original)
        if not (query or "").strip() and filtro == "Todos":
            resultados = svc_maq.buscar_maquinas_priorizando_problematicas(
                "", limit=25
            )
        else:
            # Si hay query, primero traemos candidatas y despues
            # filtramos por estado en memoria. Si no hay query,
            # usamos listar_por_estado que es una sola query SQL.
            if filtro == "Todos":
                resultados = svc_maq.buscar_maquinas(query, limit=25)
            else:
                if (query or "").strip():
                    cand = svc_maq.buscar_maquinas(query, limit=200)
                    resultados = [
                        m for m in cand if m.get("estado") == filtro
                    ][:25]
                else:
                    resultados = svc_maq.listar_por_estado(
                        filtro, limit=25
                    )
        self.win.set_search_results(resultados)

    def on_search_filter_changed(self, estado: str) -> None:
        """Handler del cambio de filtro de estado en el search panel.

        Re-usa la logica de ``on_search_query`` pasando el texto
        actual del input (para que el filtro se aplique sobre la
        query que ya estaba tipeada, si la hay).
        """
        texto_actual = self.win._search_panel._search.text() or ""
        self.on_search_query(texto_actual)

    def on_machine_selected(self, m: dict) -> None:
        """Maquina seleccionada: guardar referencia + mostrar form."""
        self._selected_maquina = m
        # La MainWindow ya propaga al panel central y al form via slot interno.
        # Solo necesitamos refrescar datetime del form (lo hace set_form_machine).

    def on_guardar_incidencia(self, data: dict) -> None:
        """Registrar nueva incidencia o actualizar si estamos en modo edicion.

        La distincion se hace via ``self.win._form._editando_id``:
          - None: INSERT (caso normal, alta de FDS nueva)
          - int:  UPDATE de la FDS existente (caso 'Editar' desde la tabla)
        """
        if self._selected_maquina is None:
            QMessageBox.warning(
                self.win,
                "Sin maquina",
                "Selecciona una maquina antes de registrar una incidencia.",
            )
            return

        # Modo edicion?
        editando_id = getattr(self.win._form, "_editando_id", None)

        try:
            cfg = svc_cfg.obtener()
            usuario = self._obtener_usuario_actual()
            if editando_id is not None:
                # UPDATE: la FDS ya existe, la editamos in-place
                inc = svc_inc.editar(
                    editando_id,
                    {
                        "problema": data["problema"],
                        "motivo_fuera_servicio": data["motivo_fuera_servicio"],
                        "accion_realizada": data["accion_realizada"],
                        "estado_final": data["estado_final"],
                        "observaciones": data["observaciones"],
                        "tecnico": data["tecnico"],
                    },
                )
                accion_aud = "editar_incidencia"
            else:
                # INSERT: alta normal
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
                accion_aud = "registrar_incidencia"
        except ValueError as e:
            QMessageBox.warning(self.win, "Datos invalidos", str(e))
            return
        except Exception as e:  # pragma: no cover - errores DB
            QMessageBox.critical(self.win, "Error al guardar", str(e))
            return

        # OK: refrescar lista, totales y limpiar form
        # Si estabamos editando, salimos del modo edicion; el form
        # queda vacio (no se mantiene la maquina, para evitar confusion
        # de cargar otra FDS sobre la editada).
        self.win._form._editando_id = None
        self._selected_maquina = None
        self.win.set_form_machine(None)
        self.win.reset_form()
        self.refrescar_lista_turno()

        # Auditoria: trazabilidad de quien registro/que edito y cuando
        try:
            from services import auditoria as svc_aud
            svc_aud.registrar(
                accion=accion_aud,
                tecnico=data.get("tecnico", "") or "desconocido",
                objetivo_tipo="incidencia",
                objetivo_id=str(inc.get("id", "?")),
                detalle=(
                    f"maquina={self._selected_maquina['numero_maquina'] if self._selected_maquina else '?'} "
                    f"problema={data['problema']} "
                    f"estado_final={data['estado_final']}"
                ),
            )
        except Exception:
            pass  # best-effort

    def on_limpiar_form(self) -> None:
        """El operador toco Cancelar: descarta TODO (incluyendo la maquina)."""
        # Si estamos editando una FDS existente, tambien salimos del modo edicion
        self.win._form._editando_id = None
        self._selected_maquina = None
        self.win.set_form_machine(None)
        self.win.reset_form()
        # El form queda vacio; el operador puede elegir otra maquina o cerrar.

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
        self.win._form._ta_obs.set_text(inc.get("observaciones", ""))
        # Marcamos modo edicion en el FORM (no en el controller) para
        # que on_guardar_incidencia sepa que debe hacer UPDATE en
        # lugar de INSERT.
        self.win._form._editando_id = inc_id

    def on_duplicar_incidencia(self, inc_id: int) -> None:
        """Duplicar una fila: carga los datos al form en modo ALTA
        (no edicion) para que el operador pueda guardar una nueva
        FDS con los mismos datos. Util cuando la misma maquina se
        reincio varias veces en el turno.
        """
        inc = svc_inc.obtener(inc_id)
        if inc is None:
            return
        # Cargar maquina en el buscador (misma logica que editar)
        m = svc_maq.obtener_por_numero(inc["numero_maquina"])
        if m is not None:
            self._selected_maquina = m
            self.win.show_machine(m)
            self.win.set_form_machine(m)
        else:
            self._selected_maquina = None
            self.win.set_form_machine(None)
        # Pre-llenar los mismos campos que en editar
        self.win._form._cb_tecnico["widget"].setCurrentText(inc["tecnico"])
        tipo = inc.get("problema") or ""
        idx_tipo = self.win._form._cb_tipo["widget"].findText(tipo)
        if idx_tipo >= 0:
            self.win._form._cb_tipo["widget"].setCurrentIndex(idx_tipo)
        self.win._form._ta_motivo["widget"].setPlainText(inc.get("motivo_fuera_servicio", ""))
        self.win._form._ta_accion["widget"].setPlainText(inc.get("accion_realizada", ""))
        self.win._form._cb_estado["widget"].setCurrentText(inc.get("estado_final", "Fuera de Servicio"))
        self.win._form._ta_obs.set_text(inc.get("observaciones", ""))
        # CLAVE: en duplicar NO seteamos _editando_id, asi el guardado
        # crea una fila nueva en vez de pisar la original. Y
        # refrescamos la fecha/hora para que sea 'ahora' (no la de
        # la incidencia original que ya quedo atras).
        self.win._form._editando_id = None
        try:
            from datetime import datetime
            self.win._form._in_fecha["widget"].setText(datetime.now().strftime("%d/%m/%Y"))
            # La hora se actualiza en el siguiente Guardar (datetime.now()).
        except Exception:
            pass
        # Foco en motivo para que el operador tipee la variacion y confirme
        self.win._form._ta_motivo["widget"].setFocus()

    def on_eliminar_incidencia(self, inc_id: int) -> None:
        """Eliminar con confirmacion explicita (muestra que se borra)."""
        # Traemos la incidencia para que el mensaje sea especifico:
        # 'Eliminar la FDS de la maquina 1023 (Atasco) del turno Noche?'
        # Asi el operador sabe exactamente que esta borrando.
        inc = svc_inc.obtener(inc_id)
        if inc is None:
            return
        maquina = inc.get("numero_maquina", "?")
        problema = inc.get("problema", "sin problema")
        detalle = ""
        if inc.get("motivo_fuera_servicio"):
            detalle = f" - {inc['motivo_fuera_servicio'][:60]}"
            if len(inc["motivo_fuera_servicio"]) > 60:
                detalle += "..."
        res = QMessageBox.question(
            self.win,
            "Eliminar incidencia",
            f"Eliminar la FDS de la maquina <b>{maquina}</b> "
            f"(<i>{problema}</i>{detalle})?<br><br>"
            f"Esta accion no se puede deshacer.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if res != QMessageBox.Yes:
            return
        svc_inc.eliminar(inc_id)
        self.refrescar_lista_turno()

        # Auditoria: quien elimino que
        try:
            from services import auditoria as svc_aud
            tecnico = self._obtener_usuario_actual()
            svc_aud.registrar(
                accion="eliminar_incidencia",
                tecnico=tecnico,
                objetivo_tipo="incidencia",
                objetivo_id=str(inc_id),
                detalle="",
            )
        except Exception:
            pass

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

            # Actividades Diarias del turno: se renderizan en un bloque
            # aparte arriba de la tabla de FDS. Traemos todas (el operador
            # puede haber registrado varias tareas ademas de las FDS).
            try:
                from services import actividades_db as svc_act
                actividades = svc_act.listar_por_turno(hoy, self._turno_actual)
            except Exception:
                actividades = []

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
                actividades=actividades,
                # Pasamos la config para que el helper elija entre
                # Outlook clasico (win32com) y SMTP directo segun
                # smtp_enabled en config.json. Default: Outlook.
                config=cfg,
            )
        finally:
            self.win.set_sending(False)

        # Si ok: marcamos como correo_enviado y notificamos
        if resultado.get("ok"):
            ids = [r["id"] for r in resumen.registros]
            svc_inc.marcar_correo_enviado(ids)
            self.refrescar_lista_turno()
            # Auditoria: envio exitoso
            try:
                from services import auditoria as svc_aud
                svc_aud.registrar(
                    accion="enviar_informe",
                    tecnico=nombre_firmante,
                    objetivo_tipo="informe",
                    objetivo_id=f"{date.today().isoformat()}-{self._turno_actual}",
                    detalle=(
                        f"incidencias={len(ids)} "
                        f"destinatarios={len(destinatarios)} "
                        f"modo={modo}"
                    ),
                )
            except Exception:
                pass
            QMessageBox.information(
                self.win,
                "Informe enviado",
                resultado.get("mensaje", "Informe enviado."),
            )
        else:
            # Fallback: HTML persistido. Si el motivo fue que Outlook no
            # tiene perfil / archivo de datos configurado, mostramos un
            # dialog accionable con un boton para abrir Panel de control
            # -> Correo. Si es otro error (red, permisos, antivirus),
            # caemos al warning generico de siempre.
            archivo = resultado.get("archivo", "")
            # Auditoria: fallback a archivo
            try:
                from services import auditoria as svc_aud
                svc_aud.registrar(
                    accion="enviar_informe_fallback",
                    tecnico=nombre_firmante,
                    objetivo_tipo="informe",
                    objetivo_id=f"{date.today().isoformat()}-{self._turno_actual}",
                    detalle=f"archivo={archivo} categoria={resultado.get('categoria','otro')}",
                )
            except Exception:
                pass
            if resultado.get("categoria") == "perfil_no_configurado":
                self._mostrar_dialog_perfil_no_configurado(archivo)
            elif resultado.get("modo") == "smtp":
                self._mostrar_dialog_smtp_fallo(resultado, archivo)
            else:
                QMessageBox.warning(
                    self.win,
                    "Outlook no disponible",
                    f"{resultado.get('mensaje','')}\n\nArchivo guardado en:\n{archivo}",
                )

    def _mostrar_dialog_smtp_fallo(
        self, resultado: dict, archivo_html: str
    ) -> None:
        """Dialog accionable cuando falla el envio SMTP.

        El operador ve:
          - Mensaje del error SMTP especifico (auth, timeout, TLS, etc).
          - Boton 'Abrir Settings -> Correo' para corregir la config
            (host, user, password, TLS).
          - Boton 'Abrir HTML guardado' para que pueda enviarlo
            manualmente mientras tanto.
        """
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
        dlg = QDialog(self.win)
        dlg.setWindowTitle("Error al enviar via SMTP")
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        titulo = QLabel("<b>No se pudo enviar el informe via SMTP</b>")
        layout.addWidget(titulo)
        msg = QLabel(resultado.get("smtp_error") or resultado.get("mensaje", ""))
        msg.setWordWrap(True)
        layout.addWidget(msg)
        if archivo_html:
            layout.addWidget(QLabel(f"<i>HTML guardado en: {archivo_html}</i>"))
        # Boton: abrir Settings -> tab Correo
        btn_settings = QPushButton("Abrir Settings -> Correo")
        btn_settings.clicked.connect(lambda: (
            dlg.accept(),
            self.on_settings(),
        ))
        layout.addWidget(btn_settings)
        # Boton: abrir el HTML
        if archivo_html:
            from pathlib import Path as _P
            btn_html = QPushButton("Abrir HTML guardado")
            btn_html.clicked.connect(lambda: (
                dlg.accept(),
                self._abrir_archivo(_P(archivo_html)),
            ))
            layout.addWidget(btn_html)
        # Boton: cerrar
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(dlg.accept)
        layout.addWidget(btn_close)
        dlg.exec()

    def _abrir_archivo(self, path) -> None:
        """Abre un archivo con el programa default del sistema."""
        import os, subprocess, sys
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", str(path)], check=False)
            else:
                subprocess.run(["xdg-open", str(path)], check=False)
        except Exception as e:
            QMessageBox.warning(
                self.win, "No se pudo abrir", f"{path}\n\n{e}"
            )

    def _mostrar_dialog_perfil_no_configurado(self, archivo_html: str) -> None:
        """Muestra un dialog accionable cuando Outlook no tiene perfil.

        El operador ve tres botones:
          * "Abrir Panel de control -> Correo" -> dispara control.exe
            (Microsoft.Mail / mlcfg32.cpl) y Windows muestra el dialogo
            nativo donde puede agregar / seleccionar un perfil.
          * "Abrir HTML guardado" -> abre el .html persistido con el
            visor default (navegador). Sirve para que pueda enviarlo
            manualmente mientras configura el perfil.
          * "Cerrar" -> descarta.
        """
        box = QMessageBox(self.win)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Outlook no tiene perfil configurado")
        box.setText(
            "Outlook rechazo el envio porque no tiene un perfil / "
            "archivo de datos configurado."
        )
        archivo_txt = archivo_html or "(no se persistio)"
        box.setInformativeText(
            "Que hacer:\n"
            "  1. Apreta 'Abrir Panel de control -> Correo'.\n"
            "  2. En la ventana que se abre, anda a 'Mostrar perfiles'.\n"
            "  3. Si no hay ninguno, 'Agregar...' y configura tu cuenta.\n"
            "  4. Si hay varios, marca uno como 'Establecer como\n"
            "     predeterminado'.\n"
            "  5. Volve a esta ventana y reintenta el envio.\n\n"
            f"Mientras tanto, el HTML quedo guardado en:\n{archivo_txt}"
        )
        # Botones (Qt los pone en el orden que los damos)
        btn_panel = box.addButton(
            "Abrir Panel de control -> Correo", QMessageBox.ButtonRole.AcceptRole
        )
        btn_html = box.addButton(
            "Abrir HTML guardado", QMessageBox.ButtonRole.ActionRole
        )
        btn_close = box.addButton(QMessageBox.StandardButton.Close)
        # Default (Enter) -> accion principal
        box.setDefaultButton(btn_panel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is btn_panel:
            ok = svc_outlook.abrir_panel_control_correo()
            if not ok:
                QMessageBox.information(
                    self.win,
                    "No se pudo abrir",
                    "No se encontro 'control.exe' en PATH. "
                    "Abri manualmente: Panel de control -> Correo "
                    "(Mail) -> Mostrar perfiles.",
                )
        elif clicked is btn_html and archivo_html:
            try:
                import os
                os.startfile(archivo_html)  # type: ignore[attr-defined]
            except Exception as e:
                QMessageBox.warning(
                    self.win,
                    "No se pudo abrir",
                    f"Error abriendo el archivo: {e}",
                )
        # btn_close o Esc -> no hace nada

    def on_previsualizar_informe(self) -> None:
        """Muestra el HTML renderizado del informe en un dialog modal.

        No envia nada: solo deja revisar destinatarios, asunto y
        contenido. Si el operador quiere enviar, tiene que cerrar este
        dialog y apretar 'Enviar Informe por Outlook' en el header de
        la tabla (que dispara el flujo normal con confirmacion de
        firmante).
        """
        cfg = svc_cfg.obtener()
        hoy = date.today()
        resumen = svc_inc.resumen_turno(hoy, self._turno_actual)
        registros = self._enriquecer_registros(list(resumen.registros))
        resumen.registros = registros

        correo_cfg = cfg.get("correo", {})
        destinatarios = list(correo_cfg.get("destinatarios", []) or [])
        cc = list(correo_cfg.get("cc", []) or [])
        asunto_tpl = correo_cfg.get(
            "asunto_template", "Informe Diario FDS - {fecha} - {turno}"
        )
        logo_path = cfg.get("empresa", {}).get("logo_path") or None
        turno_cfg = cfg.get("turno", {}).get(self._turno_actual.lower(), {})
        rango = turno_cfg.get("rango", "")
        etiqueta = turno_cfg.get("etiqueta", self._turno_actual)

        from services.email_renderer import render_informe
        from services.incidencias import (
            tiempo_promedio_resolucion_min, total_maquinas_catalogo,
        )
        tiempo_real = tiempo_promedio_resolucion_min(registros)
        total_maquinas = total_maquinas_catalogo(solo_activas=True)
        # Actividades Diarias del turno (mismo bloque que en envio).
        try:
            from services import actividades_db as svc_act
            actividades = svc_act.listar_por_turno(hoy, self._turno_actual)
        except Exception:
            actividades = []
        # Para preview usamos el usuario actual o "Preview" como fallback
        firmante_preview = ""
        try:
            from services import tecnicos_db
            actual = tecnicos_db.obtener_usuario_actual()
            if actual is not None:
                firmante_preview = actual["nombre"]
        except Exception:
            pass
        if not firmante_preview:
            firmante_preview = self._obtener_usuario_actual() or "Preview"

        html = render_informe(
            fecha=hoy,
            turno_etiqueta=etiqueta,
            turno_rango=rango,
            usuario=firmante_preview,
            registros=registros,
            tiempo_promedio_min=tiempo_real,
            empresa=cfg.get("empresa"),
            destinatarios=destinatarios,
            cc=cc,
            firmante=firmante_preview,
            total_maquinas_catalogo=total_maquinas,
            actividades=actividades,
        )
        # Calcular el asunto igual que haria enviar_informe_turno
        from services.outlook import armar_asunto
        asunto = armar_asunto(asunto_tpl, fecha=hoy, turno=etiqueta)

        from ui.preview_dialog import PreviewDialog
        dlg = PreviewDialog(
            parent=self.win,
            html=html,
            asunto=asunto,
            destinatarios=destinatarios,
            cc=cc,
            total_registros=resumen.total,
        )
        dlg.exec()

    def on_exportar_incidencias(self) -> None:
        """Exporta las filas visibles de la tabla a un CSV."""
        from pathlib import Path
        from datetime import date as _date
        from PySide6.QtWidgets import QFileDialog, QMessageBox

        rows = self.win._table.current_rows()
        if not rows:
            QMessageBox.information(
                self.win, "Sin filas",
                "No hay filas para exportar (la tabla esta vacia).",
            )
            return

        # Sugerir nombre por defecto: incidencias_YYYY-MM-DD_turno.csv
        nombre = (
            f"incidencias_{_date.today().isoformat()}_"
            f"{self._turno_actual.lower()}.csv"
        )
        ruta, _ = QFileDialog.getSaveFileName(
            self.win,
            "Exportar a CSV",
            str(Path.home() / "Documents" / nombre),
            "Archivos CSV (*.csv);;Todos los archivos (*)",
        )
        if not ruta:
            return

        try:
            from services import exportar as svc_exp
            n = svc_exp.exportar_csv(rows, Path(ruta))
        except Exception as e:
            QMessageBox.critical(
                self.win, "Error al exportar", str(e)
            )
            return

        # Auditoria
        try:
            from services import auditoria as svc_aud
            svc_aud.registrar(
                accion="exportar_incidencias",
                tecnico=self._obtener_usuario_actual(),
                objetivo_tipo="informe",
                objetivo_id=f"{_date.today().isoformat()}-{self._turno_actual}",
                detalle=f"filas={n} archivo={ruta}",
            )
        except Exception:
            pass

        QMessageBox.information(
            self.win, "Exportacion completa",
            f"Se exportaron {n} filas a:\n{ruta}",
        )

    def on_ver_problematicas(self) -> None:
        """Abre un dialog con todas las maquinas problematicas ahora.

        Sin filtro de tiempo (eso es el tab 'Problematicas' de
        Settings, que muestra las atascadas). El operador puede
        hacer doble click sobre una fila para verla en el panel
        central y tomar accion inmediata.
        """
        from ui.maquinas_problematicas_dialog import (
            MaquinasProblematicasDialog,
        )
        dlg = MaquinasProblematicasDialog(self.win)
        # Si elije una, la mostramos en el panel central como si la
        # hubiera seleccionado del buscador.
        dlg.maquinaSeleccionada.connect(self.on_machine_selected)
        dlg.exec()

    def on_settings(self, maquina_preseleccionada: dict | None = None) -> None:
        """Abrir el dialogo de Configuracion (Empresa, Correo, Maquinas,
        Tecnicos, Tipos de problema).

        Si ``maquina_preseleccionada`` viene, abre directamente el tab
        Maquinas con esa fila seleccionada (uso: boton 'Editar' del
        panel central).
        """
        from ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self.win)
        if maquina_preseleccionada is not None:
            # Abrir directamente el tab Maquinas (index 2) y seleccionar
            # el row correspondiente a la maquina dada.
            try:
                dlg._tabs.setCurrentIndex(2)
                maq_tab = dlg._tabs.widget(2)
                num = str(maquina_preseleccionada.get("numero_maquina", ""))
                if hasattr(maq_tab, "select_by_numero"):
                    maq_tab.select_by_numero(num)
            except Exception:
                pass  # si falla, abre normal
        def _on_changed() -> None:
            # Refrescar tecnicos desde la DB
            try:
                from services import tecnicos_db
                tecnicos = tecnicos_db.listar(incluir_inactivos=False)
                self.win.set_tecnicos([t["nombre"] for t in tecnicos])
            except Exception as e:
                print(f"[WARN] refrescar tecnicos: {e}")
            # Refrescar tipos de problema desde la DB (caso el operador
            # haya agregado / renombrado / eliminado categorias).
            try:
                from services import tipos_problema_db
                tipos = tipos_problema_db.listar_nombres(solo_activos=True)
                self.win.set_tipos_problema(tipos)
            except Exception as e:
                print(f"[WARN] refrescar tipos de problema: {e}")
            # Refrescar el topbar (puede haber cambiado el operador actual)
            self.refrescar_topbar_usuario()
            # Refrescar lista del turno y stats por si modificaron maquinas
            self.refrescar_lista_turno()
            self._refrescar_quick_stats()
            self._refrescar_footer()
            # Si modificaron la config de correo (SMTP / Outlook), el
            # chip del topbar tiene que actualizarse. Esto es clave
            # cuando el operador conecta Gmail por primera vez: lo
            # guarda y el chip pasa de "Sin Outlook" rojo a "SMTP
            # listo: smtp.gmail.com:..." en verde.
            self._refrescar_outlook_status()
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

    def on_actividades(self, pendiente_solo: bool = False) -> None:
        """Abrir el dialogo 'Registro de Actividades Diarias'.

        Esta pantalla reemplaza la planilla Excel que los tecnicos
        llenan a mano: alta, edicion, filtros por fecha / tecnico /
        area / tarea, y export a Excel con el formato que la SCJ
        espera para auditoria.

        Si ``pendiente_solo`` es True (caso: click en la card
        'Tareas pendientes' del dashboard), el dialog abre con el
        filtro 'Solo pendientes' activado y el rango de fechas
        extendido a 90 dias.

        Pasa al dialog la lista actual de maquinas y tecnicos para
        alimentar el combo de 'Maquina' (opcional) y el de 'Tecnico'.
        El dialog lee/escribe directamente en la DB via los services.
        """
        from ui.actividades_dialog import ActividadesDialog
        from services import maquinas as svc_maq
        from services import tecnicos_db
        from services import tipos_actividad_db

        # Maquinas: usamos el mismo listado que el buscador
        try:
            maquinas = svc_maq.buscar_maquinas_priorizando_problematicas(
                "", limit=500
            )
        except Exception:
            maquinas = []

        # Tecnicos: lista de la DB (no el cache del form, asi cubre
        # cambios hechos desde Settings)
        try:
            tecnicos = [t["nombre"] for t in tecnicos_db.listar(incluir_inactivos=False)]
        except Exception:
            tecnicos = []

        # Tipos de actividad: tareas que el tecnico puede elegir
        try:
            tareas = tipos_actividad_db.listar_nombres(solo_activos=True)
        except Exception:
            tareas = []

        # Turno actual: lo que el topbar ya tiene
        turno_actual = ""
        try:
            turno_actual = self.win._topbar._lbl_turno.text() or ""
            # Sacamos el prefijo "Turno " que el topbar le mete
            if turno_actual.lower().startswith("turno "):
                turno_actual = turno_actual[6:].split(" - ")[0].strip()
        except Exception:
            pass

        usuario_actual = ""
        try:
            usuario_actual = self.win._topbar._user_name.text() or ""
        except Exception:
            pass

        dlg = ActividadesDialog(
            parent=self.win,
            usuario=usuario_actual,
            turno_actual=turno_actual,
            maquinas=maquinas,
            tecnicos=tecnicos,
            tareas=tareas,
            pendiente_solo=pendiente_solo,
        )
        dlg.exec()

    def on_dashboard_card_clicked(self, color_key: str) -> None:
        """Handler de clicks en las cards del dashboard.

        Mapeo:
          - 'dark'  (Total maquinas)   -> limpia filtro a "Todos" y refresca
          - 'green' (Operativas)        -> filtra a "Operativa"
          - 'blue'  (En observacion)    -> filtra a "En Observacion"
          - 'amber' (Pendientes FDS)    -> abre MaquinasProblematicasDialog
          - 'red'   (Tareas pendientes) -> abre dialog de Actividades Diarias
                                          con filtro 'Solo pendientes'

        Ademas de filtrar el search panel, las 3 cards de maquinas
        ponen el foco en el buscador para que el operador pueda
        seguir tipeando sin tener que hacer click ahi.
        """
        if color_key == "red":
            self.on_actividades(pendiente_solo=True)
            return
        if color_key == "amber":
            self.on_ver_problematicas()
            return
        # dark/green/blue: filtran el search panel
        filtro_map = {
            "dark":  "Todos",
            "green": "Operativa",
            "blue":  "En Observacion",
        }
        estado = filtro_map.get(color_key)
        if estado is None:
            return
        # Seteamos el filtro (sin disparar filterChanged) y refrescamos
        # usando la query actual (que probablemente sea vacia).
        self.win._search_panel.set_filtro_estado(estado)
        texto_actual = self.win._search_panel._search.text() or ""
        self.on_search_query(texto_actual)
        # Foco en el input del buscador para que el operador pueda
        # tipear y filtrar mas sin tener que mover el mouse.
        try:
            self.win._search_panel.focus_search()
        except Exception:
            pass

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
        """Actualiza el dashboard KPI + footer con el estado REAL del catalogo.

        Las 4 cards del dashboard cuentan el ESTADO de cada maquina en
        el catalogo (no las incidencias del turno). Asi una maquina
        "En Observacion" sigue visible aunque no se haya registrado
        una incidencia hoy.

        Cards (de izquierda a derecha):
          - TOTAL MAQUINAS   - slate   (cantidad del parque)
          - OPERATIVAS        - verde   (maquinas operativas ahora)
          - EN OBSERVACION    - azul    (maquinas en seguimiento)
          - PENDIENTES        - amber   (FDS + Pend Rep + Esp Tecnico)

        El footer recibe los mismos contadores del catalogo en su
        seccion propia (TOTAL MAQUINAS / OPERATIVAS / EN OBSERVACION),
        separada de los stats del turno por un divisor fuerte.

        Fuente:
          * ``services.maquinas.contar_por_estado`` para el desglose
            por estado (Operativa / FDS / Pend Rep / Esp Tecnico /
            En Observacion).
        """
        from services import maquinas as svc_maq

        # Conteos por estado del catalogo (incluye TODAS las activas).
        catalogo = svc_maq.contar_por_estado(solo_activas=True)

        total_maquinas = sum(catalogo.values())
        operativas = catalogo.get("Operativa", 0)
        en_observacion = catalogo.get("En Observacion", 0)
        pendientes = (
            catalogo.get("Fuera de Servicio", 0)
            + catalogo.get("Pendiente Repuesto", 0)
            + catalogo.get("Espera Servicio Tecnico", 0)
        )

        # Tareas pendientes (modulo de Actividades Diarias)
        try:
            from services import actividades_db as svc_act
            tareas_pend = svc_act.contar_pendientes()
        except Exception:
            tareas_pend = 0

        # Llamada unica: la MainWindow reparte al dashboard Y al footer.
        self.win.set_estado_catalogo(
            total=total_maquinas,
            operativas=operativas,
            en_observacion=en_observacion,
            pendientes=pendientes,
            tareas_pendientes=tareas_pend,
        )

    def _refrescar_footer(self) -> None:
        """No-op: el footer ya no tiene stats del turno (solo del catalogo).

        Los unicos stats que quedan en el footer son TOTAL MAQUINAS /
        OPERATIVAS / EN OBSERVACION, que se actualizan via
        ``set_estado_catalogo`` desde ``_refrescar_quick_stats``.

        Mantenemos el metodo por backward compat con el call-graph del
        controller (start, registrar_incidencia, eliminar_incidencia,
        etc. lo llaman); es intencional que sea no-op.
        """

    def _refrescar_outlook_status(self) -> None:
        """Chequea el modo de envio y actualiza el dot del topbar.

        Desde 2026-07 el sistema soporta dos modos (elegido via
        config.correo.smtp_enabled):
          - Outlook clasico (default, via win32com) -> chip 'Outlook'
          - SMTP directo (smtplib) -> chip 'SMTP'
        El chequeo detecta cual esta activo y configura el chip.
        Si ninguno esta OK, muestra el mensaje generico.

        El chequeo es best-effort: si falla (ej. pywin32 no instalado
        o Outlook no responde), marcamos como no disponible. Asi el
        operador sabe de antemano que el informe se guardara como
        archivo .eml/.html en vez de mandarse directamente.

        Tambien detecta el caso comun con Outlook 365 / Win11+
        donde el operador tiene activado el 'New Outlook' (cliente
        web que no expone COM). En ese caso, el tooltip incluye una
        pista de como volver al Outlook clasico, o un hint para
        habilitar SMTP si quiere evitar el problema.
        """
        # Primero chequeamos si SMTP esta configurado y usable
        modo = "outlook"  # default
        try:
            from services import configuracion as svc_cfg_loader
            cfg = svc_cfg_loader.obtener()
            correo_cfg = cfg.get("correo", {})
            if correo_cfg.get("smtp_enabled"):
                modo = "smtp"
        except Exception:
            pass

        if modo == "smtp":
            self._refrescar_smtp_status()
            return

        # Modo Outlook: sigue el flujo original
        try:
            disponible = svc_outlook.outlook_disponible()
        except Exception as e:
            disponible = False
            msg = f"Error al chequear Outlook: {e}"
            self.win.set_outlook_status(False, msg)
            return
        if disponible:
            self.win.set_outlook_status(
                True, "Outlook detectado - listo para enviar"
            )
            return
        # No disponible: chequeamos si es por el "New Outlook" de M365
        # para mostrar un mensaje accionable en vez del mensaje generico.
        is_new = None
        try:
            is_new = svc_outlook.is_new_outlook_active()
        except Exception:
            pass
        if is_new is True:
            self.win.set_outlook_status(
                False,
                "New Outlook activo (no soporta COM). "
                "Ir a Outlook -> esquina superior derecha -> "
                "desactivar 'New Outlook' (icono de switch). "
                "Tambien podes habilitar SMTP en Settings -> Correo. "
                "El informe se guardara como archivo."
            )
        else:
            self.win.set_outlook_status(
                False,
                "Outlook no disponible - el informe se guardara como archivo"
            )

    def _refrescar_smtp_status(self) -> None:
        """Actualiza el chip del topbar segun el estado de SMTP.

        El chip muestra 'Outlook' en verde si SMTP esta bien configurado
        (host + user + password llenos), amarillo si falta algun campo,
        rojo si faltan campos criticos (host o user).

        No envia mail real (eso se hace al apretar 'Enviar Informe').
        Solo refleja el estado de la config persistida.
        """
        try:
            from services import configuracion as svc_cfg_loader
            correo = svc_cfg_loader.obtener().get("correo", {})
        except Exception:
            correo = {}

        host = (correo.get("smtp_host") or "").strip()
        user = (correo.get("smtp_user") or "").strip()
        password = correo.get("smtp_password") or ""
        smtp_enabled = bool(correo.get("smtp_enabled"))

        if not smtp_enabled:
            # SMTP no esta habilitado: caemos al flujo Outlook
            # (que ya fue chequeado por el caller).
            return

        if not host or not user or not password:
            self.win.set_outlook_status(
                False,
                "SMTP habilitado pero falta host / usuario / password. "
                "Completa en Settings -> Correo."
            )
            return

        # Configurado. Marcamos verde con el detalle del servidor.
        # El chip dice el perfil (Gmail/M365/Otro) en el label +
        # host:port + el From en el tooltip. Asi el operador ve en
        # pantalla cual es la config sin tener que abrir Settings.
        from services import smtp_profiles
        perfil = smtp_profiles.find_profile(correo.get("smtp_perfil", "gmail"))
        LABEL_POR_PERFIL = {
            "gmail": "Gmail",
            "m365_app": "M365",
            "m365_oauth": "M365 OAuth2",
            "otro": "SMTP",
        }
        perfil_label = LABEL_POR_PERFIL.get(perfil["key"], "SMTP")
        from_addr = user if "@" in user else user
        self.win.set_outlook_status(
            True,    # disponible
            f"{perfil_label} listo: {host}:{correo.get('smtp_port', 587)} "
            f"como {from_addr}",
            label=perfil_label,
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
        self.win._search_panel.filterChanged.connect(self.on_search_filter_changed)
        self.win.machineSelected.connect(self.on_machine_selected)
        self.win.guardarIncidencia.connect(self.on_guardar_incidencia)
        self.win.limpiarForm.connect(self.on_limpiar_form)
        self.win.editarIncidencia.connect(self.on_editar_incidencia)
        self.win.eliminarIncidencia.connect(self.on_eliminar_incidencia)
        self.win.duplicarIncidencia.connect(self.on_duplicar_incidencia)
        self.win.enviarInformeRequested.connect(self.on_enviar_informe)
        self.win.previsualizarInformeRequested.connect(self.on_previsualizar_informe)
        self.win.editMachineRequested.connect(self.on_settings)
        self.win.exportarIncidenciasRequested.connect(self.on_exportar_incidencias)
        self.win.verProblematicasRequested.connect(self.on_ver_problematicas)
        self.win.settingsRequested.connect(self.on_settings)
        self.win.logoutRequested.connect(self.on_logout)
        self.win.importRequested.connect(self.on_import)
        self.win.actividadesRequested.connect(self.on_actividades)
        self.win.dashboardCardClicked.connect(self.on_dashboard_card_clicked)

        # Chequeo inicial de Outlook: refresca el indicador del topbar.
        self._refrescar_outlook_status()
        # Chequeo inicial del chip de Backup: si hay backup reciente
        # (caso tipico: la app se cerro y volvio a abrir), se muestra
        # en verde apenas arranca. Si no hay ninguno, se muestra rojo
        # hasta que el primer backup periodico (30 min despues).
        self._refrescar_backup_status()

        # Backup periodico de la DB cada 30 minutos.
        # Importante: NO pasamos self como parent porque MainController
        # no es QObject. El QTimer queda sin parent (Qt lo parented
        # implicitamente al QApplication, asi que se libera solo al
        # cerrar la app).
        self._backup_timer = QTimer()
        self._backup_timer.setInterval(30 * 60 * 1000)  # 30 min
        self._backup_timer.timeout.connect(self._backup_periodico)
        self._backup_timer.start()
        # Backup inicial al arrancar (asi hay al menos uno)
        self._backup_periodico()

    def _backup_periodico(self) -> None:
        """Hace un backup automatico de la DB.

        Best-effort: si falla (ej. la DB esta locked), lo logueamos
        pero no interrumpimos el flujo del operador.
        """
        try:
            from services import backup as svc_bkp
            path = svc_bkp.hacer_backup()
            if path is not None:
                # Auditoria del backup
                try:
                    from services import auditoria as svc_aud
                    svc_aud.registrar(
                        accion="backup_automatico",
                        tecnico="sistema",
                        objetivo_tipo="database",
                        objetivo_id=str(path.name),
                        detalle=f"path={path}",
                    )
                except Exception:
                    pass
        except Exception:
            pass
        # Refrescar el chip 'Backup' del topbar con la edad del
        # ultimo backup (independientemente de si este intento fallo
        # o no: si fallo, se muestra el ultimo bueno o rojo si no
        # hay ninguno).
        try:
            self._refrescar_backup_status()
        except Exception:
            pass

    def _refrescar_backup_status(self) -> None:
        """Lee la edad del ultimo backup y actualiza el chip del topbar.

        Verde si < 30 min, amarillo si < 2h, rojo si > 2h o no hay
        ninguno. El texto del chip cambia a 'Sin backup' en el caso
        rojo-sin-backup; en los demas queda 'Backup' (la edad exacta
        se ve en el tooltip al pasar el mouse).
        """
        try:
            from services import backup as svc_bkp
            ultimo = svc_bkp.obtener_ultimo_backup()
        except Exception:
            ultimo = None
        if ultimo is None:
            edad = None
        else:
            edad = ultimo.get("edad_segundos")
        try:
            self.win._topbar.set_backup_status(edad)
        except Exception:
            pass


__all__ = ("MainController",)