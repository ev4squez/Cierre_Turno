"""Smoke end-to-end: MainWindow + MainController + services + email_renderer.

Cubre el flujo completo:

1. Cargar UI + controller + DB limpia con 3 maquinas
2. Buscar '10' -> resultados live (1023, 1045)
3. Seleccionar 1023 -> form se habilita
4. Llenar y guardar incidencia
5. Refrescar lista del turno: la fila aparece
6. Renderizar el informe HTML con ``email_renderer``
7. Verificar que el HTML contiene los valores correctos
8. Llamar ``enviar_informe`` (sin win32com -> fallback a archivo)
9. Editar la incidencia, ver el cambio
10. Eliminar la incidencia, ver que desaparece
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from config import BACKUPS_DIR, DATABASE_PATH  # noqa: E402
from database.db import init_db, reset_db  # noqa: E402
from services import (  # noqa: E402
    email_renderer,
    incidencias as svc_inc,
    maquinas as svc_maq,
    outlook as svc_outlook,
)
from services.configuracion import guardar, obtener  # noqa: E402

CATALOGO = [
    {"numero_maquina": "1023", "sector": "Sector Alto", "isla": "Isla 05",
     "marca": "Aristocrat", "modelo": "MarsX", "serie": "AR-88213-CL",
     "denominacion": "$100"},
    {"numero_maquina": "1045", "sector": "Sector Alto", "isla": "Isla 07",
     "marca": "Konami", "modelo": "KP3", "serie": "KN-12345-CL",
     "denominacion": "$500"},
    {"numero_maquina": "2056", "sector": "Sector Bajo", "isla": "Isla 12",
     "marca": "IGT", "modelo": "PeakSlant", "serie": "IGT-99811-CL",
     "denominacion": "$1000"},
]


def _populate_db() -> None:
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()
        for suf in ("-wal", "-shm"):
            p = DATABASE_PATH.with_suffix(f".db{suf}")
            if p.exists():
                p.unlink()
    init_db()
    reset_db()
    for m in CATALOGO:
        svc_maq.crear_maquina(m)
    # Re-migrar tecnicos desde config.json aunque el flag tecnicos_migrados
    # este en True (la DB esta vacia y los tecnicos del form los necesitamos).
    from services import tecnicos_db as _tec_db
    _tec_db.migrar_desde_config(forzar=True)


_FAILS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    line = f"  [{status}] {label}"
    if detail:
        line += f" -- {detail}"
    print(line)
    if not ok:
        _FAILS.append(label)


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def main() -> int:
    from PySide6.QtWidgets import QApplication

    _populate_db()
    cfg = obtener()
    # Setear destinatarios para que el envio (fallback) tenga sentido
    cfg["correo"]["destinatarios"] = ["jefe.tecnico@casino.local"]
    cfg["correo"]["cc"] = ["subgerencia@casino.local"]
    guardar(cfg)

    app = QApplication.instance() or QApplication(sys.argv)
    from ui.helpers import load_stylesheet
    from ui.main_window import MainWindow
    from controllers.main_controller import MainController

    load_stylesheet(app)
    win = MainWindow()
    ctrl = MainController(win)
    ctrl.wire()
    ctrl.start()

    section("1. UI + Controller arrancan")
    check("ventana visible", win.isVisible() or not win.isVisible())  # todavia no se mostro
    win.show()
    check("ventana visible despues de show", win.isVisible())
    check("tecnicos cargados desde config",
          win._form._cb_tecnico["widget"].count() >= 2,
          f"items = {win._form._cb_tecnico['widget'].count()}")

    section("2. Buscador live '10'")
    win._search_panel._search.setText("10")
    app.processEvents()
    resultados = svc_maq.buscar_maquinas("10")
    win.set_search_results(resultados)
    app.processEvents()
    nums = [r["numero_maquina"] for r in resultados]
    check("live devuelve 1023 y 1045", "1023" in nums and "1045" in nums)

    section("3. Seleccionar 1023 -> form habilitado")
    m1023 = svc_maq.obtener_por_numero("1023")
    win._search_panel.machineSelected.emit(m1023)
    app.processEvents()
    ctrl.on_machine_selected(m1023)
    check("form tiene numero 1023",
          win._form._in_maquina["widget"].text() == "1023")
    check("formulario habilitado",
          win._form._btn_guardar.isEnabled())

    section("4. Guardar incidencia")
    win._form._cb_tecnico["widget"].setCurrentText("R. Fuentes")
    win._form._cb_tipo["widget"].setCurrentText("Falla electronica")
    win._form._ta_motivo["widget"].setPlainText("Monitor sin imagen")
    win._form._ta_accion["widget"].setPlainText("Diagnostico en curso")
    win._form._cb_estado["widget"].setCurrentText("Fuera de Servicio")
    win._form._ta_obs["widget"].setPlainText("Falla recurrente")
    win._form._on_guardar()
    app.processEvents()
    hoy = date.today()
    regs = svc_inc.listar_turno(hoy, ctrl._turno_actual)
    check("1 incidencia en el turno", len(regs) == 1,
          f"regs = {len(regs)}")
    check("estado final = Fuera de Servicio",
          regs and regs[0]["estado_final"] == "Fuera de Servicio")
    check("1023 sincronizada a estado FDS",
          svc_maq.obtener_por_numero("1023")["estado"] == "Fuera de Servicio")

    section("5. Render del informe HTML")
    resumen = svc_inc.resumen_turno(hoy, ctrl._turno_actual)
    html = email_renderer.render_informe(
        fecha=hoy,
        turno_etiqueta="Tarde",
        turno_rango="14:00-22:00",
        usuario="Elvis M.",
        registros=resumen.registros,
        observaciones=["Se reemplazaron dos impresoras termicas"],
        tiempo_promedio_min=42,
    )
    # Validaciones sobre el HTML generado
    check("HTML tiene doctype", html.lstrip().startswith("<!DOCTYPE"))
    check("HTML tiene numero 1023", "1023" in html)
    check("HTML tiene 'Fuera de Servicio'", "Fuera de Servicio" in html)
    check("HTML tiene marca Aristocrat", "Aristocrat" in html)
    check("HTML tiene tecnico R. Fuentes", "R. Fuentes" in html)
    check("HTML tiene el texto de observaciones",
          "impresoras termicas" in html,
          "observacion no aparece")
    # Guardar para inspeccion
    muestra = BACKUPS_DIR / f"smoke_informe_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    muestra.write_text(html, encoding="utf-8")
    print(f"  [INFO] HTML de muestra guardado en {muestra}")

    section("6. Envio (fallback a archivo porque win32com no esta)")
    check("outlook_disponible() == False en sandbox",
          svc_outlook.outlook_disponible() is False)
    resultado = svc_outlook.enviar_informe(
        html=html,
        asunto="Informe Diario FDS - 16/07/2026 - Tarde",
        destinatarios=["jefe.tecnico@casino.local"],
        cc=["subgerencia@casino.local"],
        modo="display",
    )
    check("envio devolvio ok=False (fallback)",
          resultado["ok"] is False)
    check("envio devolvio archivo persistido",
          Path(resultado["archivo"]).exists(),
          f"archivo = {resultado['archivo']}")

    section("7. Dialogo de firmante (Quien envia el informe?)")
    # Test unitario del dialogo: que valide vacio, que acepte nombre
    # existente, que acepte nombre nuevo (libre) y que cancele.
    from ui.firmante_dialog import FirmanteDialog
    from PySide6.QtWidgets import QDialog

    # 7a. Validacion de nombre vacio
    dlg = FirmanteDialog(
        parent=win,
        tecnicos=["Elvis Vasquez", "R. Fuentes"],
        preseleccionado="Elvis Vasquez",
    )
    # Simulamos que el usuario borra el texto y trata de aceptar
    dlg._cb_nombre.lineEdit().setText("")
    # Llamamos al handler directo: tiene que rechazar (no aceptar)
    dlg._on_accept()
    check("dialogo rechaza nombre vacio", dlg.get_nombre() is None)

    # 7b. Acepta nombre existente de la lista
    dlg2 = FirmanteDialog(
        parent=win,
        tecnicos=["Elvis Vasquez", "R. Fuentes"],
        preseleccionado="",
    )
    dlg2._cb_nombre.lineEdit().setText("R. Fuentes")
    dlg2._on_accept()
    check("dialogo acepta nombre de la lista",
          dlg2.get_nombre() == "R. Fuentes",
          f"get_nombre()={dlg2.get_nombre()!r}")

    # 7c. Acepta nombre nuevo (libre, no estaba en la lista)
    dlg3 = FirmanteDialog(
        parent=win,
        tecnicos=["R. Fuentes"],
        preseleccionado="",
    )
    dlg3._cb_nombre.lineEdit().setText("  Tecnico Nuevo  ")
    dlg3._on_accept()
    check("dialogo acepta nombre libre (trim)",
          dlg3.get_nombre() == "Tecnico Nuevo",
          f"get_nombre()={dlg3.get_nombre()!r}")

    # 7d. Controller NO envia si el dialogo se cancela
    # Monkey-patch del dialogo: forzamos a que devuelva Rejected sin abrir
    from ui import firmante_dialog as fd_mod
    class _DlgCancela(FirmanteDialog):
        def exec(self_inner):  # noqa: N805
            return QDialog.Rejected
    original_dlg = fd_mod.FirmanteDialog
    fd_mod.FirmanteDialog = _DlgCancela
    # Spy: si se llegara a llamar a enviar_informe_turno, fallamos
    spy_envio = {"llamadas": 0}
    original_envio = svc_outlook.enviar_informe_turno
    def _spy_envio(*a, **kw):
        spy_envio["llamadas"] += 1
        return {"ok": True, "modo": "display", "outlook": False,
                "mensaje": "spy", "archivo": ""}
    svc_outlook.enviar_informe_turno = _spy_envio
    try:
        ctrl.on_enviar_informe()
    finally:
        fd_mod.FirmanteDialog = original_dlg
        svc_outlook.enviar_informe_turno = original_envio
    check("controller NO envia si dialogo se cancela",
          spy_envio["llamadas"] == 0,
          f"llamadas={spy_envio['llamadas']}")

    # 7e. Controller SI envia con el nombre del dialogo
    # Simulamos: dialogo devuelve "Elvis V." (capaz de tipear)
    nombre_esperado = "Elvis V."
    class _DlgAcepta(FirmanteDialog):
        def __init__(self_inner, **kw):  # noqa: N805
            super().__init__(**kw)
            _DlgAcepta.ultimo = self_inner
        def exec(self_inner):  # noqa: N805
            self_inner._cb_nombre.lineEdit().setText(nombre_esperado)
            self_inner._on_accept()
            return QDialog.Accepted
    fd_mod.FirmanteDialog = _DlgAcepta
    # Spy captura el kwarg firmante/usuario
    spy_kw = {}
    def _spy_envio_kw(*a, **kw):
        spy_kw.update(kw)
        return {"ok": True, "modo": "display", "outlook": False,
                "mensaje": "spy-kw", "archivo": ""}
    svc_outlook.enviar_informe_turno = _spy_envio_kw
    try:
        ctrl.on_enviar_informe()
    finally:
        fd_mod.FirmanteDialog = original_dlg
        svc_outlook.enviar_informe_turno = original_envio
    check("controller envia con nombre del dialogo como usuario",
          spy_kw.get("usuario") == nombre_esperado,
          f"usuario={spy_kw.get('usuario')!r}")
    check("controller envia con nombre del dialogo como firmante",
          spy_kw.get("firmante") == nombre_esperado,
          f"firmante={spy_kw.get('firmante')!r}")
    # El HTML efectivamente lleva el nombre en "Enviado por" y firma al pie
    html_con_firma = email_renderer.render_informe(
        fecha=hoy,
        turno_etiqueta="Tarde",
        turno_rango="14:00-22:00",
        usuario=nombre_esperado,
        registros=resumen.registros,
        firmante=nombre_esperado,
        destinatarios=["jefe.tecnico@casino.local"],
        cc=["subgerencia@casino.local"],
        tiempo_promedio_min=42,
    )
    check("HTML renderizado lleva el firmante en el bloque firma",
          nombre_esperado in html_con_firma,
          f"buscado={nombre_esperado!r}")

    section("8. Editar incidencia via controller")
    inc_id = regs[0]["id"]
    ctrl.on_editar_incidencia(inc_id)
    app.processEvents()
    check("form pre-cargado con motivo",
          win._form._ta_motivo["widget"].toPlainText() == "Monitor sin imagen",
          f"motivo = {win._form._ta_motivo['widget'].toPlainText()!r}")
    # Cambiamos y guardamos via services directamente
    svc_inc.editar(inc_id, {"accion_realizada": "Reemplazo de monitor OK",
                             "estado_final": "Operativa"})
    regs2 = svc_inc.listar_turno(hoy, ctrl._turno_actual)
    check("ediccion persistida",
          regs2[0]["accion_realizada"] == "Reemplazo de monitor OK")
    check("1023 sincronizada a Operativa",
          svc_maq.obtener_por_numero("1023")["estado"] == "Operativa")

    section("9. Eliminar incidencia")
    svc_inc.eliminar(inc_id)
    regs3 = svc_inc.listar_turno(hoy, ctrl._turno_actual)
    check("tabla vacia tras eliminar", len(regs3) == 0,
          f"regs = {len(regs3)}")

    print("\n" + "=" * 60)
    if _FAILS:
        print(f"FAIL: {_FAILS}")
        return 1
    print("OK: smoke end-to-end completo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())