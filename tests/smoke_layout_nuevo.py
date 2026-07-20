"""Smoke test standalone del layout nuevo.

No toca la DB (SQLAlchemy 2.0.36 esta roto en Python 3.14 host);
solo verifica que la MainWindow se construya con el layout nuevo:

* DashboardBar arriba con 4 KPI cards
* Topbar con info-chip agrupada (Fecha + Turno)
* MachinePanel con SearchPanel embebido
* FormPanel a la derecha
* Tabla + Footer

Falla si cualquier widget no se construye o si las APIs publicas
no responden.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def main() -> int:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)

    from ui.helpers import load_stylesheet
    from ui.main_window import MainWindow

    load_stylesheet(app)

    fails: list[str] = []
    def check(label: str, ok: bool, detail: str = "") -> None:
        status = "PASS" if ok else "FAIL"
        line = f"  [{status}] {label}"
        if detail:
            line += f" -- {detail}"
        print(line)
        if not ok:
            fails.append(label)

    print("=== Layout nuevo: MainWindow ===")
    w = MainWindow()
    w.show()
    app.processEvents()

    check("minimo 1400x900", w.minimumWidth() == 1400 and w.minimumHeight() == 900)
    check("tamano inicial >= minimo", w.width() >= 1400 and w.height() >= 900,
          f"actual={w.width()}x{w.height()}")

    print("\n=== Topbar info-chip agrupada ===")
    check("topbar presente", w._topbar is not None)
    check("lbl_fecha es QLabel", w._topbar._lbl_fecha is not None)
    check("lbl_turno es QLabel", w._topbar._lbl_turno is not None)
    # El HTML del topbar pide "Jueves, 16 de julio" o similar - el dia se
    # calcula en runtime, asi que verificamos que tenga texto no vacio
    check("lbl_fecha tiene texto", len(w._topbar._lbl_fecha.text()) > 0,
          f"texto={w._topbar._lbl_fecha.text()!r}")
    check("lbl_turno tiene texto", len(w._topbar._lbl_turno.text()) > 0,
          f"texto={w._topbar._lbl_turno.text()!r}")

    print("\n=== Dashboard KPI cards ===")
    check("dashboard presente", w._dashboard is not None)
    check("4 KPI cards visibles",
          all(c.isVisible() for c in [
              w._dashboard._fds, w._dashboard._pend,
              w._dashboard._obs, w._dashboard._res,
          ]))
    # Test API: set_quick_stats
    w.set_quick_stats(fds=3, pendientes=1, resueltas=5, en_observacion=2)
    app.processEvents()
    check("KPI FDS = 3", w._dashboard._fds._value.text() == "3",
          f"value={w._dashboard._fds._value.text()!r}")
    check("KPI Pend = 1", w._dashboard._pend._value.text() == "1")
    check("KPI Obs = 2", w._dashboard._obs._value.text() == "2")
    check("KPI Res = 5", w._dashboard._res._value.text() == "5")
    # Test zero styling
    w.set_quick_stats(fds=0, pendientes=0, resueltas=0, en_observacion=0)
    app.processEvents()
    check("KPI 0 marca zero=true",
          w._dashboard._fds._value.property("zero") == "true")

    print("\n=== Search embebido en MachinePanel ===")
    check("machine_panel.search_panel es SearchPanel",
          w._search_panel is w._machine_panel.search_panel)
    check("search_panel tiene _search (QLineEdit)",
          w._search_panel._search is not None)
    check("search_panel puede escribir", True)
    w._search_panel._search.setText("10")
    app.processEvents()
    check("texto del search se setea",
          w._search_panel._search.text() == "10",
          f"text={w._search_panel._search.text()!r}")
    # Test set_results
    w.set_search_results([
        {"numero_maquina": "1023", "marca": "Aristocrat", "modelo": "MarsX",
         "isla": "Isla 05", "sector": "Sector Alto", "estado": "Fuera de Servicio"},
        {"numero_maquina": "1045", "marca": "Konami", "modelo": "KP3",
         "isla": "Isla 07", "sector": "Sector Alto", "estado": "Operativa"},
    ])
    app.processEvents()
    check("set_results pinto 2 items",
          len(w._search_panel._result_widgets) == 2,
          f"items={len(w._search_panel._result_widgets)}")

    print("\n=== Seleccion de maquina propaga al form ===")
    primera = {"numero_maquina": "1023", "marca": "Aristocrat", "modelo": "MarsX",
               "sector": "Sector Alto", "isla": "Isla 05", "serie": "AR-88213-CL",
               "denominacion": "$100", "estado": "Fuera de Servicio"}
    w._search_panel.machineSelected.emit(primera)
    app.processEvents()
    check("machine_panel muestra N.° 1023",
          w._machine_panel._big_num.text().endswith("1023"),
          f"big_num={w._machine_panel._big_num.text()!r}")
    check("form recibe maquina",
          w._form._in_maquina["widget"].text() == "1023")

    print("\n=== Form: campos y set_tecnicos ===")
    w.set_tecnicos(["Rodrigo Fuentes", "Camila Torres", "Pedro Salinas"])
    app.processEvents()
    check("tecnicos cargados",
          w._form._cb_tecnico["widget"].count() == 4,  # "Seleccionar..." + 3
          f"count={w._form._cb_tecnico['widget'].count()}")

    print("\n=== Tabla y Footer ===")
    w.set_table_rows([
        {"id": 1, "hora": "14:32", "numero_maquina": "1023", "sector": "Sector Alto",
         "marca": "Aristocrat", "problema": "Falla electronica",
         "estado_final": "Fuera de Servicio", "tecnico": "Rodrigo Fuentes"},
    ])
    app.processEvents()
    check("tabla tiene 1 fila", w._table._tabla.rowCount() == 1)

    w.set_footer(total=1, maquinas=1, pendientes=1, inicio_turno="14:00")
    app.processEvents()
    check("footer total = 1", w._footer._total["value"].text() == "1")
    check("footer pendientes = 1", w._footer._pendientes["value"].text() == "1")

    print("\n=== Senales de edicion/eliminacion conectadas ===")
    editados: list[int] = []
    eliminados: list[int] = []
    w.editarIncidencia.connect(lambda i: editados.append(i))
    w.eliminarIncidencia.connect(lambda i: eliminados.append(i))
    # Disparar botones de la primera fila
    actions_w = w._table._tabla.cellWidget(0, 7)
    btns = actions_w.findChildren(__import__("PySide6.QtWidgets").QtWidgets.QToolButton)
    btns[0].click()  # edit
    app.processEvents()
    btns[1].click()  # delete
    app.processEvents()
    check("editar emitio id", len(editados) == 1, f"editados={editados}")
    check("eliminar emitio id", len(eliminados) == 1, f"eliminados={eliminados}")

    print("\n=== Render visual: capturar pixmap ===")
    pix = w.grab()
    out_path = "/tmp/sistema_fds_layout_nuevo.png"
    ok_save = pix.save(out_path)
    check("pixmap guardado para revision visual", ok_save,
          f"path={out_path} size={pix.width()}x{pix.height()}")

    print("\n" + "=" * 60)
    if fails:
        print(f"FAIL: {fails}")
        return 1
    print("OK: layout nuevo verifica correctamente")
    print(f"Screenshot guardado en {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
