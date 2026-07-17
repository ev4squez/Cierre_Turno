"""CRUD de Tecnicos en la DB.

Los tecnicos viven en una tabla SQLite (no en config.json como antes).
Esto permite:
  - Cambiar el nombre del usuario actual y que el topbar refleje el
    cambio en vivo (sin reiniciar la app)
  - Auditoria: timestamps de creacion/modificacion
  - Soft-delete con papelera
  - CRUD desde la UI de Settings

Tambien expone un helper de migracion para que la primera vez que el
sistema arranca, copie los tecnicos que ya existian en config.json
(si los hay) a la nueva tabla.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from database.db import get_session
from database.models import Tecnico


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------


def listar(incluir_inactivos: bool = False) -> list[dict]:
    """Lista todos los tecnicos activos (o todos si ``incluir_inactivos``)."""
    with get_session() as s:
        stmt = select(Tecnico).order_by(Tecnico.nombre.asc())
        if not incluir_inactivos:
            stmt = stmt.where(Tecnico.activo.is_(True))
        return [t.to_dict() for t in s.scalars(stmt)]


def obtener(nombre: str) -> Optional[dict]:
    """Devuelve el tecnico activo con ese nombre, o ``None``.

    Match case-insensitive y exacto. Si hay varios con el mismo nombre
    (por soft-delete + restore) devuelve el activo.
    """
    if not nombre:
        return None
    nombre_norm = nombre.strip().lower()
    with get_session() as s:
        for t in s.scalars(select(Tecnico)).all():
            if t.nombre.lower() == nombre_norm and t.activo:
                return t.to_dict()
    return None


def obtener_por_id(tecnico_id: int) -> Optional[dict]:
    with get_session() as s:
        t = s.get(Tecnico, tecnico_id)
        return t.to_dict() if t else None


def obtener_usuario_actual() -> Optional[dict]:
    """Devuelve el tecnico marcado como usuario actual, o ``None``."""
    with get_session() as s:
        t = s.scalars(
            select(Tecnico)
            .where(Tecnico.es_usuario_actual.is_(True))
            .where(Tecnico.activo.is_(True))
            .limit(1)
        ).first()
        return t.to_dict() if t else None


# ---------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------


def agregar(nombre: str, email: str = "", es_usuario_actual: bool = False) -> dict:
    """Agrega un tecnico nuevo. Lanza ``ValueError`` si el nombre esta vacio
    o si ya existe (case-insensitive)."""
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValueError("El nombre no puede estar vacio")
    with get_session() as s:
        # Verificar duplicado
        existente = s.scalars(
            select(Tecnico).where(Tecnico.nombre.ilike(nombre))
        ).first()
        if existente is not None:
            raise ValueError(f"Ya existe un tecnico con el nombre '{nombre}'")
        t = Tecnico(
            nombre=nombre,
            email=(email or "").strip() or None,
            es_usuario_actual=bool(es_usuario_actual),
        )
        # Si se marca como actual, desmarcar al resto
        if t.es_usuario_actual:
            _desmarcar_usuario_actual(s)
        s.add(t)
        try:
            s.flush()
        except IntegrityError as e:
            raise ValueError(f"No se pudo agregar el tecnico: {e}") from e
        return t.to_dict()


def renombrar(nombre_viejo: str, nombre_nuevo: str) -> dict:
    """Renombra un tecnico existente."""
    nombre_viejo = (nombre_viejo or "").strip()
    nombre_nuevo = (nombre_nuevo or "").strip()
    if not nombre_viejo or not nombre_nuevo:
        raise ValueError("Nombres no pueden estar vacios")
    if nombre_viejo == nombre_nuevo:
        t = obtener(nombre_viejo)
        if t is None:
            raise ValueError(f"No se encontro el tecnico '{nombre_viejo}'")
        return t
    with get_session() as s:
        t = s.scalars(
            select(Tecnico).where(Tecnico.nombre.ilike(nombre_viejo))
        ).first()
        if t is None:
            raise ValueError(f"No se encontro el tecnico '{nombre_viejo}'")
        # Verificar que el nuevo nombre no exista
        conflict = s.scalars(
            select(Tecnico).where(Tecnico.nombre.ilike(nombre_nuevo))
        ).first()
        if conflict is not None and conflict.id != t.id:
            raise ValueError(f"Ya existe otro tecnico con el nombre '{nombre_nuevo}'")
        t.nombre = nombre_nuevo
        s.flush()
        return t.to_dict()


def eliminar(nombre: str) -> dict:
    """Soft-delete: marca ``activo=False``. No elimina la fila."""
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValueError("El nombre no puede estar vacio")
    with get_session() as s:
        t = s.scalars(
            select(Tecnico).where(Tecnico.nombre.ilike(nombre))
        ).first()
        if t is None:
            raise ValueError(f"No se encontro el tecnico '{nombre}'")
        t.activo = False
        if t.es_usuario_actual:
            t.es_usuario_actual = False
        s.flush()
        return t.to_dict()


def reactivar(tecnico_id: int) -> dict:
    with get_session() as s:
        t = s.get(Tecnico, tecnico_id)
        if t is None:
            raise ValueError(f"Tecnico id={tecnico_id} no existe")
        t.activo = True
        s.flush()
        return t.to_dict()


def marcar_como_usuario_actual(nombre: str) -> dict:
    """Marca un tecnico como el usuario actual de la maquina.

    Solo un tecnico puede tener ``es_usuario_actual=True`` a la vez.
    El resto se desmarca automaticamente.
    """
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValueError("El nombre no puede estar vacio")
    with get_session() as s:
        t = s.scalars(
            select(Tecnico).where(Tecnico.nombre.ilike(nombre))
        ).first()
        if t is None:
            raise ValueError(f"No se encontro el tecnico '{nombre}'")
        if not t.activo:
            raise ValueError(f"El tecnico '{nombre}' esta inactivo")
        _desmarcar_usuario_actual(s)
        t.es_usuario_actual = True
        s.flush()
        return t.to_dict()


def _desmarcar_usuario_actual(s) -> None:
    """Pone ``es_usuario_actual=False`` en todos los tecnicos activos."""
    for t in s.scalars(
        select(Tecnico).where(Tecnico.es_usuario_actual.is_(True))
    ).all():
        t.es_usuario_actual = False


# ---------------------------------------------------------------------------
# Migracion desde config.json
# ---------------------------------------------------------------------------


def migrar_desde_config(forzar: bool = False) -> dict:
    """Migra los tecnicos que viven en config.json a la tabla Tecnico.

    Comportamiento idempotente con dos niveles:

    1. Si ``config.tecnicos_migrados == True``, no hace nada (la
       migracion ya se hizo). Se re-migra solo si ``forzar=True``.

    2. Si no esta marcado pero ya hay tecnicos activos en la DB con
       los mismos nombres que en el config, se marca como migrado
       sin duplicar (caso de DB que se compartio entre maquinas).

    Retorna un resumen con insertadas/ya_existian/marcadas_actual.
    """
    from services import configuracion as svc_cfg

    cfg = svc_cfg.obtener()
    nombres_cfg = cfg.get("tecnicos", []) or []
    usuario_actual_cfg = (cfg.get("usuario_actual") or "").strip()

    insertadas = 0
    ya_existian = 0
    marcadas_actual = 0

    # 1. Si ya esta marcado como migrado y no se pide forzar, salir
    if not forzar and cfg.get("tecnicos_migrados", False):
        return {"insertadas": 0, "ya_existian": 0, "marcadas_actual": 0, "skip_razon": "ya_migrado"}

    with get_session() as s:
        # Si ya hay al menos un tecnico activo, no migramos nada
        existentes = s.scalars(select(Tecnico).where(Tecnico.activo.is_(True))).all()
        nombres_en_db = {t.nombre.lower() for t in existentes}

        for nombre in nombres_cfg:
            nombre = (nombre or "").strip()
            if not nombre:
                continue
            if nombre.lower() in nombres_en_db:
                ya_existian += 1
                continue
            t = Tecnico(
                nombre=nombre,
                activo=True,
                es_usuario_actual=(nombre.lower() == usuario_actual_cfg.lower()) if usuario_actual_cfg else False,
            )
            s.add(t)
            if t.es_usuario_actual:
                marcadas_actual += 1
            insertadas += 1

        if marcadas_actual == 0 and usuario_actual_cfg:
            # Si en la DB no hay nadie marcado como actual pero el config
            # dice quien es, intentamos marcarlo.
            t = s.scalars(
                select(Tecnico).where(Tecnico.nombre.ilike(usuario_actual_cfg))
            ).first()
            if t is not None and t.activo:
                t.es_usuario_actual = True
                marcadas_actual = 1

        s.flush()

    # Marcar el config como migrado para que no se ejecute de nuevo
    cfg["tecnicos_migrados"] = True
    svc_cfg.guardar(cfg)

    return {
        "insertadas": insertadas,
        "ya_existian": ya_existian,
        "marcadas_actual": marcadas_actual,
    }


# ---------------------------------------------------------------------------
# API legacy para retrocompatibilidad
# ---------------------------------------------------------------------------
#
# Estas funciones se mantienen para que `services/admin.py` y los tests
# existentes sigan funcionando, pero delegan a la DB. La migracion se
# hace en el primer uso.


def listar_tecnicos() -> list[str]:
    """Devuelve solo los nombres de los tecnicos activos."""
    return [t["nombre"] for t in listar(incluir_inactivos=False)]


def agregar_tecnico(nombre: str) -> list[str]:
    agregar(nombre)
    return listar_tecnicos()


def eliminar_tecnico(nombre: str) -> list[str]:
    eliminar(nombre)
    return listar_tecnicos()


def renombrar_tecnico(viejo: str, nuevo: str) -> list[str]:
    renombrar(viejo, nuevo)
    return listar_tecnicos()


__all__ = (
    "listar",
    "obtener",
    "obtener_por_id",
    "obtener_usuario_actual",
    "agregar",
    "renombrar",
    "eliminar",
    "reactivar",
    "marcar_como_usuario_actual",
    "migrar_desde_config",
    # legacy
    "listar_tecnicos",
    "agregar_tecnico",
    "eliminar_tecnico",
    "renombrar_tecnico",
)