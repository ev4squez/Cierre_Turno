"""Services CRUD para maquinas y tecnicos.

Funciones que la UI de Settings usa para:
  - Listar maquinas (activas, inactivas, todas)
  - Listar tecnicos
  - CRUD basico con validaciones

Las funciones son delgadas: solo validan y delegan a SQLAlchemy via
``database.db.get_session()``. Sin logica de UI ni presentation.
"""

from __future__ import annotations

from typing import Iterable

from sqlalchemy import select

from database.db import get_session
from database.models import Maquina


# ---------------------------------------------------------------------------
# Maquinas - CRUD extendido
# ---------------------------------------------------------------------------


def listar_todas(incluir_inactivas: bool = True, limit: int = 5000) -> list[dict]:
    """Lista todas las maquinas (incluyendo inactivas si ``incluir_inactivas``).

    Usado por el panel admin para mostrar la papelera.
    """
    with get_session() as s:
        stmt = select(Maquina).order_by(Maquina.numero_maquina.asc())
        if not incluir_inactivas:
            stmt = stmt.where(Maquina.activo.is_(True))
        stmt = stmt.limit(limit)
        return [m.to_dict() for m in s.scalars(stmt)]


def reactivar_maquina(maquina_id: int) -> dict:
    """Reactiva una maquina que estaba inactiva (``activo=True``).

    No cambia ningun otro campo. Util cuando eliminaste por error
    y queres volver a la papelera para sacarla.
    """
    with get_session() as s:
        m = s.get(Maquina, maquina_id)
        if m is None:
            raise ValueError(f"Maquina id={maquina_id} no existe")
        m.activo = True
        s.flush()
        return m.to_dict()


def validar_maquina(payload: dict, parcial: bool = False) -> dict:
    """Limpia y valida un payload de maquina antes de guardarlo.

    Parametros
    ----------
    payload:
        Dict con keys del modelo (numero_maquina, sector, etc).
    parcial:
        Si True, no exige numero_maquina (uso en edicion).

    Retorna un dict limpio listo para pasar al ORM. Lanza ``ValueError``
    si hay datos invalidos.
    """
    from config import ESTADOS_MAQUINA

    if not parcial:
        num = (payload.get("numero_maquina") or "").strip()
        if not num:
            raise ValueError("numero_maquina es obligatorio")
    out: dict = {
        "sector": (payload.get("sector") or "").strip() or None,
        "isla": (payload.get("isla") or "").strip() or None,
        "codigo_scj": (payload.get("codigo_scj") or "").strip() or None,
        "marca": (payload.get("marca") or "").strip() or None,
        "modelo": (payload.get("modelo") or "").strip() or None,
        "serie": (payload.get("serie") or "").strip() or None,
        "denominacion": (payload.get("denominacion") or "").strip() or None,
    }
    estado = (payload.get("estado") or "Operativa").strip()
    if estado not in ESTADOS_MAQUINA:
        estado = "Operativa"
    out["estado"] = estado
    if "activo" in payload:
        out["activo"] = bool(payload["activo"])
    elif not parcial:
        out["activo"] = True
    if "numero_maquina" in payload and payload["numero_maquina"]:
        out["numero_maquina"] = str(payload["numero_maquina"]).strip()
    return out


# ---------------------------------------------------------------------------
# Tecnicos - CRUD
# ---------------------------------------------------------------------------
#
# Los tecnicos viven en config.json, no en la DB (son pocos y los maneja
# el admin desde la pantalla de Configuracion). Esta capa es solo un
# wrapper sobre services.configuracion para darle una API uniforme.


def listar_tecnicos() -> list[str]:
    """Devuelve la lista actual de tecnicos."""
    from services import configuracion as svc_cfg
    return list(svc_cfg.obtener().get("tecnicos", []))


def agregar_tecnico(nombre: str) -> list[str]:
    """Agrega un tecnico nuevo. Devuelve la lista actualizada.

    Lanza ``ValueError`` si el nombre esta vacio o ya existe.
    """
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValueError("El nombre no puede estar vacio")
    from services import configuracion as svc_cfg
    cfg = svc_cfg.obtener()
    actual = list(cfg.get("tecnicos", []))
    if any(t.strip().lower() == nombre.lower() for t in actual):
        raise ValueError(f"Ya existe el tecnico '{nombre}'")
    actual.append(nombre)
    cfg["tecnicos"] = actual
    svc_cfg.guardar(cfg)
    return actual


def eliminar_tecnico(nombre: str) -> list[str]:
    """Elimina un tecnico de la lista. Devuelve la lista actualizada."""
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValueError("El nombre no puede estar vacio")
    from services import configuracion as svc_cfg
    cfg = svc_cfg.obtener()
    actual = list(cfg.get("tecnicos", []))
    nuevos = [t for t in actual if t.strip().lower() != nombre.lower()]
    if len(nuevos) == len(actual):
        raise ValueError(f"No se encontro el tecnico '{nombre}'")
    cfg["tecnicos"] = nuevos
    svc_cfg.guardar(cfg)
    return nuevos


def renombrar_tecnico(viejo: str, nuevo: str) -> list[str]:
    """Renombra un tecnico. Devuelve la lista actualizada."""
    viejo = (viejo or "").strip()
    nuevo = (nuevo or "").strip()
    if not viejo or not nuevo:
        raise ValueError("Nombres no pueden estar vacios")
    from services import configuracion as svc_cfg
    cfg = svc_cfg.obtener()
    actual = list(cfg.get("tecnicos", []))
    nuevos = []
    encontrado = False
    for t in actual:
        if t.strip().lower() == viejo.lower():
            nuevos.append(nuevo)
            encontrado = True
        else:
            nuevos.append(t)
    if not encontrado:
        raise ValueError(f"No se encontro el tecnico '{viejo}'")
    if any(t.strip().lower() == nuevo.lower() for t in nuevos if t != nuevo):
        raise ValueError(f"Ya existe otro tecnico con nombre '{nuevo}'")
    cfg["tecnicos"] = nuevos
    svc_cfg.guardar(cfg)
    return nuevos


__all__ = (
    "listar_todas",
    "reactivar_maquina",
    "validar_maquina",
    "listar_tecnicos",
    "agregar_tecnico",
    "eliminar_tecnico",
    "renombrar_tecnico",
)