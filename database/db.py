"""Capa de base de datos.

Engine + Session factory + bootstrap de schema (SQLAlchemy 2.x ORM).

Diseño:

* ``engine`` y ``SessionLocal`` son lazy: se crean la primera vez que se
  llaman, no al importar el modulo. Esto evita tocar el disco si el
  modulo solo se importa para tests.
* ``init_db()`` crea todas las tablas declaradas en ``models/`` y es
  idempotente (``checkfirst=True``).
* ``get_session()`` es el helper recomendado para los services / UI.
  Devuelve una sesion nueva por llamada y hace rollback automatico si
  el bloque ``with`` levanta una excepcion.

SQLite local, sin servidor. La ruta se toma de ``config.DATABASE_PATH``.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import DATABASE_PATH, ensure_dirs


class Base(DeclarativeBase):
    """Base declarativa unica del proyecto (SQLAlchemy 2.x)."""

    pass


# --- engine y session: lazy singletons ---------------------------------

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _build_engine() -> Engine:
    """Construye el engine SQLite con PRAGMAs razonables."""
    ensure_dirs()
    url = f"sqlite:///{DATABASE_PATH.as_posix()}"
    engine = create_engine(
        url,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
    )

    # PRAGMAs recomendadas para SQLite desktop app
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _record):  # noqa: ANN001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA synchronous = NORMAL;")
        cursor.execute("PRAGMA temp_store = MEMORY;")
        cursor.close()

    return engine


def get_engine() -> Engine:
    """Devuelve el engine SQLite (lo crea si hace falta)."""
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Devuelve la factory de sesiones."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )
    return _SessionLocal


@contextmanager
def get_session() -> Iterator[Session]:
    """Context manager que rinde una ``Session`` y maneja rollback."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Crea todas las tablas declaradas en ``database.models``.

    Importante: importa los modelos *aca*, no a nivel de modulo, para
    registrar todas las clases antes de llamar a ``create_all``.
    """
    # Import side-effect: registra las clases en Base.metadata
    from database import models  # noqa: F401

    Base.metadata.create_all(bind=get_engine(), checkfirst=True)


def reset_db() -> None:
    """Borra y recrea todas las tablas. Util solo para tests."""
    from database import models  # noqa: F401

    Base.metadata.drop_all(bind=get_engine())
    Base.metadata.create_all(bind=get_engine(), checkfirst=True)


if __name__ == "__main__":
    # Smoke: inicializa schema y reporta tablas creadas
    init_db()
    from sqlalchemy import inspect

    inspector = inspect(get_engine())
    print("DB path:", DATABASE_PATH)
    print("Tablas:", inspector.get_table_names())