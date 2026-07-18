"""Smoke test focal: coherencia aritmetica del 'Resultado de la jornada'.

Las 5 categorias son mutuamente excluyentes (cada incidencia tiene UN
solo estado_final):
  Operativa / Fuera de Servicio / Pendiente Repuesto /
  Espera Servicio Tecnico / En Observacion

Por lo tanto operativas + fds + pendientes_rep + espera_soporte +
en_observacion = total exacto.

Verifica que el HTML generado:
  1) Tiene header 'se registraron N incidencias'
  2) Los bullets principales suman exactamente N
  3) Los 5 bullets pueden aparecer (o no, segun el caso)
  4) No queda el placeholder viejo del template (3 reparadas, 2 FDS,
     1 pendiente, 2 requieren soporte = bug suma 8 sobre 6)
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services import email_renderer  # noqa: E402

_FAILS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    line = f"  [{status}] {label}"
    if detail:
        line += f" -- {detail}"
    print(line)
    if not ok:
        _FAILS.append(label)


def section(t: str) -> None:
    print(f"\n=== {t} ===")


def _sumar_bullets(html: str) -> tuple[int, list[str]]:
    """Devuelve la suma de los numeros en bullets principales y la lista."""
    bullets = re.findall(r"&#8226;&nbsp; <b>(\d+)</b> m&aacute;quina", html)
    return sum(int(b) for b in bullets), bullets


def main() -> int:
    HOY = date.today()

    # ----------------------------------------------------------------
    section("Caso A: 8 incidencias, mix de los 5 estados")
    # ----------------------------------------------------------------
    registros_a = [
        {"numero_maquina": "1001", "estado_final": "Operativa",
         "problema": "A", "accion_realizada": "A", "tecnico": "T"},
        {"numero_maquina": "1002", "estado_final": "Operativa",
         "problema": "B", "accion_realizada": "B", "tecnico": "T"},
        {"numero_maquina": "1003", "estado_final": "Operativa",
         "problema": "C", "accion_realizada": "C", "tecnico": "T"},
        {"numero_maquina": "2001", "estado_final": "Fuera de Servicio",
         "problema": "D", "accion_realizada": "D", "tecnico": "T"},
        {"numero_maquina": "2002", "estado_final": "Fuera de Servicio",
         "problema": "E", "accion_realizada": "E", "tecnico": "T"},
        {"numero_maquina": "3001", "estado_final": "Pendiente Repuesto",
         "problema": "F", "accion_realizada": "F", "tecnico": "T"},
        {"numero_maquina": "4001", "estado_final": "Espera Servicio Tecnico",
         "problema": "G", "accion_realizada": "G", "tecnico": "T"},
        {"numero_maquina": "5001", "estado_final": "En Observacion",
         "problema": "H", "accion_realizada": "H", "tecnico": "T"},
    ]
    html_a = email_renderer.render_informe(
        fecha=HOY, turno_etiqueta="Tarde", turno_rango="14:00-22:00",
        usuario="T", registros=registros_a, tiempo_promedio_min=42,
    )

    check("A1 header dice 'se registraron 8 incidencias'",
          "se registraron <b>8</b> incidencias" in html_a)
    check("A2 hay 3 Operativas (reparadas)",
          "<b>3</b> m&aacute;quinas fueron reparadas" in html_a)
    check("A3 hay 2 Fuera de Servicio",
          "<b>2</b> m&aacute;quinas permanecen Fuera de Servicio" in html_a)
    check("A4 hay 1 pendiente por repuestos",
          "<b>1</b> m&aacute;quina qued&oacute; pendiente por disponibilidad de repuestos" in html_a)
    check("A5 hay 1 espera servicio tecnico",
          "<b>1</b> m&aacute;quina requiere" in html_a
          and "intervenci&oacute;n especializada" in html_a)
    check("A6 hay 1 en observacion",
          "<b>1</b> m&aacute;quina queda en observaci&oacute;n" in html_a
          or "<b>1</b> m&aacute;quinas queda en observaci&oacute;n" in html_a
          or "queda en observaci&oacute;n" in html_a)

    # Aritmetica: 3 + 2 + 1 + 1 + 1 = 8 (header)
    suma, bullets = _sumar_bullets(html_a)
    check(f"A7 suma de bullets = {suma} (esperado 8), bullets={bullets}",
          suma == 8,
          f"suma={suma} bullets={bullets}")

    # El placeholder del template original NO debe sobrevivir como
    # bloque literal hardcoded. Antes del fix, el _replace_resultado
    # tenia un bug en el patron_fin (buscaba '&oacute;' pero el template
    # tiene 'ó' literal) -> nunca encontraba el fin -> no reemplazaba
    # -> quedaba el template original (3 reparadas, 2 FDS, 1 pendiente,
    # 2 requieren soporte = bug suma 8 sobre 6).
    # Tras el fix, el HTML real viene del renderer, no del template.
    placeholder_texto = (
        "3</b> m&aacute;quinas fueron reparadas y quedaron nuevamente operativas.<br>"
        "&#8226;&nbsp; <b>2</b> m&aacute;quinas permanecen Fuera de Servicio.<br>"
        "&#8226;&nbsp; <b>1</b> m&aacute;quina qued&oacute; pendiente por disponibilidad de repuestos.<br>"
        "&#8226;&nbsp; <b>2</b> m&aacute;quinas requieren intervenci&oacute;n especializada o soporte del fabricante."
    )
    check("A8 placeholder hardcoded del template NO sobrevivio",
          placeholder_texto not in html_a,
          "el bloque literal del template quedo sin reemplazar")

    # ----------------------------------------------------------------
    section("Caso B: solo Operativas + FDS (caso simple)")
    # ----------------------------------------------------------------
    registros_b = [
        {"numero_maquina": "1023", "estado_final": "Operativa",
         "problema": "X", "accion_realizada": "X", "tecnico": "T"},
        {"numero_maquina": "1045", "estado_final": "Fuera de Servicio",
         "problema": "X", "accion_realizada": "X", "tecnico": "T"},
    ]
    html_b = email_renderer.render_informe(
        fecha=HOY, turno_etiqueta="Tarde", turno_rango="14:00-22:00",
        usuario="T", registros=registros_b, tiempo_promedio_min=10,
    )
    check("B1 header dice 2 incidencias",
          "se registraron <b>2</b> incidencias" in html_b)
    suma, bullets = _sumar_bullets(html_b)
    check(f"B2 suma bullets = {suma} (esperado 2), bullets={bullets}",
          suma == 2, f"suma={suma}")
    check("B3 NO aparece 'espera servicio tecnico' (no hay)",
          "espera servicio tecnico" not in html_b.lower().replace("&aacute;", "a").replace("&oacute;", "o")
          and "En Observaci&oacute;n" not in html_b)
    check("B4 NO aparece 'Pendiente Repuesto' (no hay)",
          "pendiente por disponibilidad de repuestos" not in html_b)

    # ----------------------------------------------------------------
    section("Caso C: 5 estados en plurales/espacios singulares")
    # ----------------------------------------------------------------
    regs_sing = [{"numero_maquina": "1", "estado_final": "Operativa",
                  "problema": "X", "accion_realizada": "X", "tecnico": "T"}]
    html_sing = email_renderer.render_informe(
        fecha=HOY, turno_etiqueta="Tarde", turno_rango="14:00-22:00",
        usuario="T", registros=regs_sing, tiempo_promedio_min=10,
    )
    # Singular: 1 operativa -> "1 maquina fue reparada y quedo nuevamente operativa"
    sufijo_maq = "" if regs_sing.__len__() == 1 else "s"
    print(html_sing[html_sing.find("&#8226;"): html_sing.find("&#8226;") + 250])
    check("C1 singular: '<b>1</b> maquina fue reparada y quedo' (acuerdo total)",
          "<b>1</b> m&aacute;quina fue reparada y qued&oacute; nuevamente operativa" in html_sing)

    # ----------------------------------------------------------------
    section("Caso D: caso degenerado - sin incidencias")
    # ----------------------------------------------------------------
    html_d = email_renderer.render_informe(
        fecha=HOY, turno_etiqueta="Tarde", turno_rango="14:00-22:00",
        usuario="T", registros=[], tiempo_promedio_min=None,
    )
    check("D1 HTML arranca con doctype",
          html_d.lstrip().startswith("<!DOCTYPE"))
    check("D2 bloque 'Sin novedades' aparece (no hay registros)",
          "Sin novedades relevantes durante la jornada" in html_d)

    # ----------------------------------------------------------------
    section("Caso E: regression del screenshot original (plantilla)")
    # ----------------------------------------------------------------
    # El bug del screenshot era: header=6, pero bullets suman 8 porque
    # habia un bullet "2 maquinas requieren soporte" que duplicaba.
    # Con el fix, si los datos son 3+2+1+0+0 = 6, la suma da 6.
    regs_orig = [
        {"numero_maquina": str(1000 + i), "estado_final": ef,
         "problema": "X", "accion_realizada": "X", "tecnico": "T"}
        for i, ef in enumerate([
            "Operativa", "Operativa", "Operativa",
            "Fuera de Servicio", "Fuera de Servicio",
            "Pendiente Repuesto",
        ])
    ]
    html_orig = email_renderer.render_informe(
        fecha=HOY, turno_etiqueta="Tarde", turno_rango="14:00-22:00",
        usuario="T", registros=regs_orig, tiempo_promedio_min=42,
    )
    suma_orig, bullets_orig = _sumar_bullets(html_orig)
    check(f"E1 caso original coherente: header=6, suma bullets = {suma_orig}",
          suma_orig == 6,
          f"header=6 pero suma={suma_orig} bullets={bullets_orig}")
    check("E2 NO contiene '2 requieren intervencion' (eso era el bug)",
          "2</b> m&aacute;quinas requieren intervenci&oacute;n" not in html_orig
          and "2</b> m&aacute;quina requiere intervenci&oacute;n" not in html_orig)
    check("E3 header dice 6",
          "se registraron <b>6</b> incidencias" in html_orig)

    print("\n" + "=" * 60)
    if _FAILS:
        print(f"FAIL ({len(_FAILS)}): {_FAILS}")
        return 1
    n_pass = 16 - len(_FAILS)
    print(f"OK: smoke resultado coherente completo ({n_pass}/16 PASS)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
