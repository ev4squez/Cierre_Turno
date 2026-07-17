"""Servicios de maquinas: busqueda, CRUD, importacion desde Excel.

Reglas de negocio:

* ``numero_maquina`` es unico en el catalogo (constraint logico).
* Si se intenta crear una maquina con un numero existente y la
  maquina esta activa, se actualiza el resto de campos (upsert).
* La busqueda es por prefijo sobre ``numero_maquina`` y LIKE sobre
  marca/modelo para los resultados del autocomplete.
"""

from __future__ import annotations

from typing import Iterable

import pandas as pd
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from config import (
    ESTADOS_MAQUINA,
    LOGS_DIR,
)
from database.db import get_session
from database.models import Maquina


# ---------------------------------------------------------------------------
# Busqueda
# ---------------------------------------------------------------------------


def buscar_maquinas(query: str, limit: int = 25) -> list[dict]:
    """Busca maquinas por numero (prefijo), marca o modelo.

    Parametros
    ----------
    query:
        Texto libre. Si esta vacio devuelve las primeras ``limit``
        maquinas activas.
    limit:
        Cantidad maxima de resultados.

    Retorna
    -------
    list[dict]
        Cada elemento es ``Maquina.to_dict()``.
    """
    q = (query or "").strip()

    with get_session() as s:
        stmt = select(Maquina).where(Maquina.activo.is_(True))

        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                or_(
                    Maquina.numero_maquina.ilike(f"{q}%"),
                    Maquina.numero_maquina.ilike(like),
                    Maquina.marca.ilike(like),
                    Maquina.modelo.ilike(like),
                )
            )

        stmt = stmt.order_by(Maquina.numero_maquina.asc()).limit(limit)
        return [m.to_dict() for m in s.scalars(stmt)]


def obtener_por_numero(numero_maquina: str) -> dict | None:
    """Devuelve la maquina activa con ese numero, o ``None``."""
    if not numero_maquina:
        return None
    with get_session() as s:
        stmt = (
            select(Maquina)
            .where(Maquina.numero_maquina == str(numero_maquina).strip())
            .where(Maquina.activo.is_(True))
            .limit(1)
        )
        m = s.scalars(stmt).first()
        return m.to_dict() if m else None


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def crear_maquina(datos: dict) -> dict:
    """Crea una maquina. Si ya existe el numero, actualiza en su lugar.

    Retorna ``Maquina.to_dict()`` con el id asignado.
    """
    payload = _normalizar(datos)
    with get_session() as s:
        existente = s.scalars(
            select(Maquina).where(Maquina.numero_maquina == payload["numero_maquina"])
        ).first()
        if existente is not None:
            return actualizar_maquina(existente.id, datos)

        m = Maquina(**payload)
        s.add(m)
        try:
            s.flush()
        except IntegrityError as e:  # pragma: no cover - carrera rara
            raise ValueError(f"No se pudo crear la maquina: {e}") from e
        return m.to_dict()


def actualizar_maquina(maquina_id: int, datos: dict) -> dict:
    """Actualiza campos editables de una maquina existente."""
    payload = _normalizar(datos, partial=True)
    with get_session() as s:
        m = s.get(Maquina, maquina_id)
        if m is None:
            raise ValueError(f"Maquina id={maquina_id} no existe")
        for k, v in payload.items():
            setattr(m, k, v)
        s.flush()
        return m.to_dict()


def eliminar_maquina(maquina_id: int, soft: bool = True) -> None:
    """Elimina (soft por defecto: marca ``activo=False``)."""
    with get_session() as s:
        m = s.get(Maquina, maquina_id)
        if m is None:
            return
        if soft:
            m.activo = False
        else:
            s.delete(m)


# ---------------------------------------------------------------------------
# Importacion desde Excel
# ---------------------------------------------------------------------------


COLUMNAS_EXCEL = {
    # clave normalizada -> clave que el sistema entiende
    "numero": "numero_maquina",
    "numero_maquina": "numero_maquina",
    "sector": "sector",
    "isla": "isla",
    "marca": "marca",
    "modelo": "modelo",
    "serie": "serie",
    "denominacion": "denominacion",
}


def importar_desde_excel(ruta_archivo: str) -> dict:
    """Importa maquinas desde un Excel.

    Comportamiento esperado (segun el spec):

    * Si la maquina existe (por ``numero_maquina``), actualiza campos.
    * Si no existe, la inserta con ``activo=True`` y ``estado="Operativa"``.

    Solo se procesan las columnas: Numero, Sector, Isla, Marca, Modelo,
    Serie, Denominacion.

    Retorna
    -------
    dict con conteo ``insertadas``, ``actualizadas`` y ``errores``.
    """
    df = pd.read_excel(ruta_archivo, dtype=str, engine="openpyxl")
    df.columns = [_norm_col(c) for c in df.columns]

    # Filtrar a las columnas que nos interesan
    cols_presentes = {k: v for k, v in COLUMNAS_EXCEL.items() if k in df.columns}
    if "numero_maquina" not in cols_presentes:
        raise ValueError(
            "El Excel debe contener una columna 'Numero' o 'Numero Maquina'"
        )

    insertadas = 0
    actualizadas = 0
    errores: list[str] = []

    with get_session() as s:
        for idx, row in df.iterrows():
            num_raw = row.get("numero_maquina")
            if pd.isna(num_raw) or not str(num_raw).strip():
                errores.append(f"Fila {idx + 2}: numero vacio")
                continue

            numero = str(num_raw).strip()
            payload = {
                "numero_maquina": numero,
                "sector": _safe_str(row.get("sector")),
                "isla": _safe_str(row.get("isla")),
                "marca": _safe_str(row.get("marca")),
                "modelo": _safe_str(row.get("modelo")),
                "serie": _safe_str(row.get("serie")),
                "denominacion": _safe_str(row.get("denominacion")),
                "estado": "Operativa",
                "activo": True,
            }

            existente = s.scalars(
                select(Maquina).where(Maquina.numero_maquina == numero)
            ).first()
            if existente is None:
                s.add(Maquina(**payload))
                insertadas += 1
            else:
                for k, v in payload.items():
                    if k == "numero_maquina":
                        continue
                    setattr(existente, k, v)
                actualizadas += 1
        s.flush()

    # Log simple del resultado
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOGS_DIR / "importaciones.log"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(
                f"{pd.Timestamp.now().isoformat()} archivo={ruta_archivo} "
                f"insertadas={insertadas} actualizadas={actualizadas} "
                f"errores={len(errores)}\n"
            )
            for e in errores:
                f.write(f"  - {e}\n")
    except OSError:
        pass

    return {"insertadas": insertadas, "actualizadas": actualizadas, "errores": errores}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalizar(datos: dict, partial: bool = False) -> dict:
    """Limpia y valida un payload de maquina."""
    if "numero_maquina" not in datos or not str(datos["numero_maquina"]).strip():
        raise ValueError("numero_maquina es obligatorio")
    out: dict = {
        "numero_maquina": str(datos["numero_maquina"]).strip(),
        "sector": (datos.get("sector") or "").strip() or None,
        "isla": (datos.get("isla") or "").strip() or None,
        "marca": (datos.get("marca") or "").strip() or None,
        "modelo": (datos.get("modelo") or "").strip() or None,
        "serie": (datos.get("serie") or "").strip() or None,
        "denominacion": (datos.get("denominacion") or "").strip() or None,
    }
    if not partial:
        estado = (datos.get("estado") or "Operativa").strip()
        if estado not in ESTADOS_MAQUINA:
            estado = "Operativa"
        out["estado"] = estado
        out["activo"] = bool(datos.get("activo", True))
    else:
        if "estado" in datos:
            estado = (datos["estado"] or "Operativa").strip()
            if estado not in ESTADOS_MAQUINA:
                estado = "Operativa"
            out["estado"] = estado
        if "activo" in datos:
            out["activo"] = bool(datos["activo"])
    return out


def _safe_str(v) -> str:  # type: ignore[no-untyped-def]
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    return str(v).strip()


def _norm_col(name: str) -> str:
    """Normaliza nombre de columna: lower, sin tildes, sin espacios."""
    s = str(name).strip().lower()
    repl = str.maketrans("áéíóúüñ", "aeiouun")
    s = s.translate(repl)
    return " ".join(s.split())


def listar_activas(limit: int = 500) -> list[dict]:
    """Atajo para listar todas las maquinas activas."""
    return buscar_maquinas("", limit=limit)


__all__: Iterable[str] = (
    "buscar_maquinas",
    "obtener_por_numero",
    "crear_maquina",
    "actualizar_maquina",
    "eliminar_maquina",
    "importar_desde_excel",
    "listar_activas",
)