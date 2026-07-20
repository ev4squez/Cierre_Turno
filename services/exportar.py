"""Exporta la lista de incidencias del turno a CSV (auditorias externas).

Genera un CSV con todas las columnas de la tabla: hora, maquina,
sector, marca, problema, estado, tecnico. Se guarda en la ubicacion
que el operador elija, listo para abrir en Excel o enviar por mail.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable


COLS: list[str] = [
    "hora", "maquina", "sector", "marca", "problema",
    "estado", "tecnico",
]


def exportar_csv(registros: list[dict], destino: Path) -> int:
    """Escribe los registros al CSV en ``destino``.

    Retorna la cantidad de filas exportadas (sin contar el header).
    Lanza ``OSError`` si no se puede escribir.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Hora", "Maquina", "Sector", "Marca",
            "Problema", "Estado", "Tecnico",
        ])
        for r in registros:
            writer.writerow([
                str(r.get("hora") or ""),
                str(r.get("numero_maquina") or ""),
                str(r.get("sector") or ""),
                str(r.get("marca") or ""),
                str(r.get("problema") or ""),
                str(r.get("estado_final") or ""),
                str(r.get("tecnico") or ""),
            ])
    return len(registros)


__all__ = ("exportar_csv",)
