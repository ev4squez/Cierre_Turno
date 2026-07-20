"""Backup automatico de la DB SQLite.

Copia ``database/sistema_fds.db`` a la carpeta ``backups/`` con
un timestamp en el nombre. Mantiene los ultimos N backups (los
mas viejos se borran automaticamente).

Pensado para correr periodicamente (ej: cada 30 minutos) desde
el controller, asi si la DB se corrompe o se borra el archivo,
hay un backup reciente para restaurar.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from config import BACKUPS_DIR, DATABASE_PATH


MAX_BACKUPS: int = 20  # cuantos backups mantener


def hacer_backup(origen: Optional[Path] = None,
                destino_dir: Optional[Path] = None,
                max_backups: int = MAX_BACKUPS) -> Optional[Path]:
    """Copia la DB al directorio de backups.

    Retorna el path del backup creado, o None si falla.
    Mantiene solo los ``max_backups`` mas recientes.
    """
    src = origen or DATABASE_PATH
    dst_dir = destino_dir or BACKUPS_DIR
    if not src.exists():
        return None
    try:
        dst_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        destino = dst_dir / f"sistema_fds_{timestamp}.db"
        shutil.copy2(src, destino)
        # Limpiar backups viejos
        _limpiar_viejos(dst_dir, max_backups)
        return destino
    except Exception:
        return None


def _limpiar_viejos(destino_dir: Path, max_backups: int) -> None:
    """Borra los backups mas viejos dejando solo los ``max_backups`` recientes."""
    backups = sorted(
        destino_dir.glob("sistema_fds_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for viejo in backups[max_backups:]:
        try:
            viejo.unlink()
        except Exception:
            pass


def listar_backups(destino_dir: Optional[Path] = None) -> list[dict]:
    """Lista los backups disponibles ordenados por fecha descendente.

    Retorna lista de dicts con keys: path, size_mb, timestamp.
    """
    dst_dir = destino_dir or BACKUPS_DIR
    if not dst_dir.exists():
        return []
    backups = sorted(
        dst_dir.glob("sistema_fds_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    resultado = []
    for p in backups:
        try:
            stat = p.stat()
            resultado.append({
                "path": str(p),
                "name": p.name,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "timestamp": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
        except Exception:
            continue
    return resultado


def restaurar(backup_path: Path,
              destino: Optional[Path] = None) -> bool:
    """Restaura la DB desde un backup. Retorna True si se restauro.

    IMPORTANTE: el caller debe cerrar la sesion de SQLAlchemy antes
    de llamar a esta funcion (sino el archivo queda locked en Windows).
    """
    dst = destino or DATABASE_PATH
    if not backup_path.exists():
        return False
    try:
        # Hacer un backup de seguridad antes de pisar
        hacer_backup(origen=dst, destino_dir=dst.parent / "backups_pre_restore")
        shutil.copy2(backup_path, dst)
        return True
    except Exception:
        return False


__all__ = ("hacer_backup", "listar_backups", "restaurar")
