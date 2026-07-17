"""Smoke test de la capa DB + services.

Ejecuta un flujo realista contra SQLite:

1. Inicializa el schema.
2. Inserta catalogo de maquinas via ``services.maquinas``.
3. Simula el buscador live (prefijo '10').
4. Registra 4 incidencias en el turno actual.
5. Edita una y elimina otra.
6. Calcula el resumen del turno.
7. Marca el lote como 'correo_enviado'.
8. Reabre la DB en una sesion nueva y verifica que todo persiste.

Uso::

    python tests/smoke_db.py

Imprime PASS/FAIL por seccion y un resumen al final. Exit code != 0
si alguna verificacion falla.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

# Permitir imports del proyecto cuando se ejecuta como script suelto
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import inspect  # noqa: E402

from config import DATABASE_PATH, ensure_dirs  # noqa: E402
from database.db import get_engine, init_db, reset_db  # noqa: E402
from services import incidencias as svc_inc  # noqa: E402
from services import maquinas as svc_maq  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers de test
# ---------------------------------------------------------------------------


_FAILS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    """Reporta PASS/FAIL y acumula fallas."""
    status = "PASS" if condition else "FAIL"
    line = f"  [{status}] {label}"
    if detail:
        line += f" -- {detail}"
    print(line)
    if not condition:
        _FAILS.append(label)


def section(title: str) -> None:
    print(f"\n=== {title} ===")


# ---------------------------------------------------------------------------
# 1. Setup
# ---------------------------------------------------------------------------


def test_setup() -> None:
    section("1. Setup")
    ensure_dirs()

    # Si la DB existe de una corrida anterior, la borramos para test limpio
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()
        wal = DATABASE_PATH.with_suffix(".db-wal")
        shm = DATABASE_PATH.with_suffix(".db-shm")
        if wal.exists():
            wal.unlink()
        if shm.exists():
            shm.unlink()

    init_db()

    inspector = inspect(get_engine())
    tablas = sorted(inspector.get_table_names())
    check("tabla maquinas creada", "maquinas" in tablas)
    check("tabla incidencias creada", "incidencias" in tablas)
    check("DB existe en disco", DATABASE_PATH.exists())

    # Verificar columnas clave de maquinas
    cols_maq = {c["name"] for c in inspector.get_columns("maquinas")}
    requeridas_maq = {
        "id", "numero_maquina", "sector", "isla", "marca",
        "modelo", "serie", "denominacion", "estado", "activo",
    }
    check(
        "columnas maquinas completas",
        requeridas_maq.issubset(cols_maq),
        f"faltan: {requeridas_maq - cols_maq}" if not requeridas_maq.issubset(cols_maq) else "",
    )

    # Verificar columnas clave de incidencias
    cols_inc = {c["name"] for c in inspector.get_columns("incidencias")}
    requeridas_inc = {
        "id", "fecha", "hora", "numero_maquina", "problema",
        "motivo_fuera_servicio", "accion_realizada", "estado_final",
        "observaciones", "tecnico", "correo_enviado",
    }
    check(
        "columnas incidencias completas",
        requeridas_inc.issubset(cols_inc),
        f"faltan: {requeridas_inc - cols_inc}" if not requeridas_inc.issubset(cols_inc) else "",
    )


# ---------------------------------------------------------------------------
# 2. Catalogo de maquinas
# ---------------------------------------------------------------------------


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
    {"numero_maquina": "3311", "sector": "Sector Alto", "isla": "Isla 08",
     "marca": "Aristocrat", "modelo": "MarsX", "serie": "AR-99001-CL",
     "denominacion": "$100"},
    {"numero_maquina": "4402", "sector": "Sector Alto", "isla": "Isla 10",
     "marca": "IGT", "modelo": "PeakSlant", "serie": "IGT-77521-CL",
     "denominacion": "$500"},
]


def test_catalogo() -> None:
    section("2. Catalogo de maquinas")
    for m in CATALOGO:
        creada = svc_maq.crear_maquina(m)
        check(f"creada {creada['numero_maquina']}", creada["id"] > 0)

    # Upsert: crear de nuevo la 1023 con un campo distinto -> actualiza
    upd = svc_maq.crear_maquina({**CATALOGO[0], "modelo": "MarsX (nuevo)"})
    check(
        "upsert actualiza sin duplicar",
        upd["modelo"] == "MarsX (nuevo)",
        f"modelo final = {upd['modelo']!r}",
    )

    # Buscar por prefijo '10'
    res = svc_maq.buscar_maquinas("10")
    nums = [r["numero_maquina"] for r in res]
    check("buscar prefijo '10' devuelve 1023 y 1045",
          "1023" in nums and "1045" in nums,
          f"resultados = {nums}")

    # Obtener directa
    directa = svc_maq.obtener_por_numero("1023")
    check("obtener 1023 por numero",
          directa is not None and directa["marca"] == "Aristocrat",
          f"marca = {directa and directa['marca']!r}")


# ---------------------------------------------------------------------------
# 3. Incidencias del turno
# ---------------------------------------------------------------------------


def test_incidencias() -> None:
    section("3. Incidencias del turno")
    hoy = datetime.now().date()

    inc1 = svc_inc.registrar(
        numero_maquina="1023", problema="Falla electronica",
        motivo_fuera_servicio="Monitor sin imagen",
        accion_realizada="Diagnostico en curso",
        estado_final="Fuera de Servicio",
        tecnico="R. Fuentes", turno="Tarde", usuario="Elvis M.",
    )
    check("registrada 1023", inc1["id"] > 0)

    inc2 = svc_inc.registrar(
        numero_maquina="2056", problema="Software / Sistema",
        motivo_fuera_servicio="Error de comunicacion",
        accion_realizada="Se reinicio switch de red",
        estado_final="En Observacion",
        tecnico="C. Torres", turno="Tarde", usuario="Elvis M.",
    )
    check("registrada 2056", inc2["id"] > 0)

    inc3 = svc_inc.registrar(
        numero_maquina="1045", problema="Billetero / TITO",
        motivo_fuera_servicio="TITO atascado",
        accion_realizada="Se limpio mecanismo lector",
        estado_final="Operativa",
        tecnico="P. Salinas", turno="Tarde", usuario="Elvis M.",
    )
    check("registrada 1045", inc3["id"] > 0)

    inc4 = svc_inc.registrar(
        numero_maquina="3311", problema="Dano de gabinete",
        motivo_fuera_servicio="Falla recurrente, requiere repuesto",
        estado_final="Pendiente Repuesto",
        tecnico="R. Fuentes", turno="Tarde", usuario="Elvis M.",
    )
    check("registrada 3311", inc4["id"] > 0)

    # Validacion: campos obligatorios
    try:
        svc_inc.registrar(
            numero_maquina="", problema="x",
            motivo_fuera_servicio="y", tecnico="z",
            turno="Tarde", usuario="u",
        )
        check("rechaza numero_maquina vacio", False)
    except ValueError:
        check("rechaza numero_maquina vacio", True)

    # Edicion
    editada = svc_inc.editar(inc3["id"], {
        "accion_realizada": "Limpieza + prueba OK",
        "estado_final": "Operativa",
    })
    check("editar 1045 OK",
          editada["accion_realizada"] == "Limpieza + prueba OK",
          f"accion_realizada = {editada['accion_realizada']!r}")

    # Eliminacion
    svc_inc.eliminar(inc4["id"])
    restantes = svc_inc.listar_turno(hoy, "Tarde")
    check("eliminar 3311",
          len(restantes) == 3,
          f"restantes = {len(restantes)}")

    # Resumen
    resumen = svc_inc.resumen_turno(hoy, "Tarde")
    check("resumen.total = 3", resumen.total == 3,
          f"total = {resumen.total}")
    check("resumen.fds = 1", resumen.fds == 1,
          f"fds = {resumen.fds}")
    check("resumen.operativas = 1", resumen.operativas == 1,
          f"operativas = {resumen.operativas}")
    check("resumen.en_observacion = 1", resumen.en_observacion == 1,
          f"en_observacion = {resumen.en_observacion}")

    # Marcar correo enviado
    ids = [r["id"] for r in restantes]
    n = svc_inc.marcar_correo_enviado(ids)
    check("marcar correo_enviado (3)", n == 3, f"actualizados = {n}")

    # Verificar persistencia del flag
    rec = svc_inc.listar_turno(hoy, "Tarde")
    check("flag correo_enviado persistido",
          all(r["correo_enviado"] for r in rec),
          f"flags = {[r['correo_enviado'] for r in rec]}")


# ---------------------------------------------------------------------------
# 4. Sincronizacion estado maquina
# ---------------------------------------------------------------------------


def test_sync_estado() -> None:
    section("4. Estado de maquina sincronizado")
    hoy = datetime.now().date()

    # 1023 quedo como 'Fuera de Servicio' (inc1)
    m1023 = svc_maq.obtener_por_numero("1023")
    check("1023 estado = Fuera de Servicio",
          m1023 is not None and m1023["estado"] == "Fuera de Servicio",
          f"estado = {m1023 and m1023['estado']!r}")

    # 1045 quedo como 'Operativa' (inc3 editada)
    m1045 = svc_maq.obtener_por_numero("1045")
    check("1045 estado = Operativa",
          m1045 is not None and m1045["estado"] == "Operativa",
          f"estado = {m1045 and m1045['estado']!r}")


# ---------------------------------------------------------------------------
# 5. Busqueda final y consistencia
# ---------------------------------------------------------------------------


def test_buscar_y_listar() -> None:
    section("5. Buscar y listar")
    # Sin query -> primeras N activas ordenadas por numero
    todas = svc_maq.listar_activas()
    check("listar_activas devuelve 5", len(todas) == 5, f"cantidad = {len(todas)}")

    # Buscar por marca 'Aristo' -> 2
    res = svc_maq.buscar_maquinas("Aristo")
    check("buscar marca 'Aristo' = 2",
          len(res) == 2, f"cantidad = {len(res)}")

    # Buscar por modelo 'PeakSlant' -> 2
    res = svc_maq.buscar_maquinas("PeakSlant")
    check("buscar modelo 'PeakSlant' = 2",
          len(res) == 2, f"cantidad = {len(res)}")


# ---------------------------------------------------------------------------
# 6. Reset_db (idempotencia)
# ---------------------------------------------------------------------------


def test_reset() -> None:
    section("6. Reset_DB (solo sanity)")
    reset_db()
    todas = svc_maq.listar_activas()
    check("reset_db deja catalogo vacio", len(todas) == 0,
          f"cantidad = {len(todas)}")
    # Re-poblamos para que la DB quede lista para uso
    for m in CATALOGO:
        svc_maq.crear_maquina(m)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def main() -> int:
    print(f"DB path: {DATABASE_PATH}")
    print(f"Python:  {sys.version.split()[0]}")

    test_setup()
    test_catalogo()
    test_incidencias()
    test_sync_estado()
    test_buscar_y_listar()
    test_reset()

    print("\n" + "=" * 60)
    if _FAILS:
        print(f"FAIL: {_FAILS}")
        return 1
    print("OK: todas las verificaciones pasaron")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())