"""Configuracion global del Sistema FDS.

Define rutas absolutas basadas en la ubicacion del archivo y carga/crea
un ``config.json`` con datos de la empresa, destinatarios y firma.

Las funciones publicas son:

* :func:`BASE_DIR` - directorio raiz del proyecto.
* :func:`ensure_dirs` - crea las carpetas necesarias si no existen.
* :func:`load_config` - lee ``config.json`` (o devuelve defaults).
* :func:`save_config` - persiste cambios en ``config.json``.
* :func:`resource_path` - resuelve rutas absolutas a archivos de recursos
  (util cuando PyInstaller empaqueta en modo onefile).

El archivo ``config.json`` vive en la raiz del proyecto y puede ser
versionado; las credenciales sensibles (si las hubiera) deben ir en
``config.local.json`` que esta en ``.gitignore``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Rutas base
# ---------------------------------------------------------------------------

APP_NAME = "SistemaFDS"

# Rutas absolutas del proyecto. Se calculan una sola vez al importar.
BASE_DIR: Path = Path(__file__).resolve().parent
DATABASE_DIR: Path = BASE_DIR / "database"
DATABASE_PATH: Path = DATABASE_DIR / "database.db"
LOGS_DIR: Path = BASE_DIR / "logs"
BACKUPS_DIR: Path = BASE_DIR / "backups"
TEMPLATES_DIR: Path = BASE_DIR / "templates"
RESOURCES_DIR: Path = BASE_DIR / "resources"
ICONS_DIR: Path = RESOURCES_DIR / "icons"
STYLES_DIR: Path = RESOURCES_DIR / "styles"

CONFIG_PATH: Path = BASE_DIR / "config.json"
LOCAL_CONFIG_PATH: Path = BASE_DIR / "config.local.json"
EMAIL_TEMPLATE_PATH: Path = TEMPLATES_DIR / "informe_fds_email.html"


# ---------------------------------------------------------------------------
# Estados de maquina / incidencia (constantes canonicas)
# ---------------------------------------------------------------------------

ESTADOS_MAQUINA: tuple[str, ...] = (
    "Operativa",
    "Fuera de Servicio",
    "Pendiente Repuesto",
    "Espera Servicio Tecnico",
    "En Observacion",
)

TIPOS_PROBLEMA: tuple[str, ...] = (
    "Falla electronica",
    "Falla mecanica",
    "Software / Sistema",
    "Billetero / TITO",
    "Dano de gabinete",
    "Otro",
)

# Catalogo inicial de TAREAS del modulo 'Registro de Actividades Diarias'.
# Es la lista que el tecnico elige en el combo 'Tarea' cuando carga una
# actividad. Configurable desde Settings > Tipos de actividad (mismo
# patron que TIPOS_PROBLEMA: la primera vez se migra a la DB y despues
# el operador los maneja desde la UI).
TIPOS_ACTIVIDAD: tuple[str, ...] = (
    "Asistencia Slot",
    "Asistencia Mesa",
    "Reposicion de papel",
    "Cambio de stacker",
    "Reinicio MDC",
    "Retiro de ticket atascado",
    "Pago manual",
    "Manejo de audio de sala",
    "Manejo de ventiladores",
    "Cambio de denominacion",
    "Mantenimiento preventivo",
    "Otro",
)

# Areas del casino a las que se asocia una actividad. Combo cerrado
# (no se edita desde UI): si el casino suma un area nueva, se agrega
# aca en el siguiente release.
AREAS: tuple[str, ...] = (
    "Slots",
    "Mesas",
    "Caja",
    "Administracion",
    "Salon",
    "Otro",
)


# ---------------------------------------------------------------------------
# Defaults de configuracion
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: dict[str, Any] = {
    "empresa": {
        "nombre": "Casino Ovalle",
        "departamento": "Departamento Tecnico y Sistemas",
        "color_corporativo": "#1E5AA8",
        "logo_path": "",
    },
    "correo": {
        "destinatarios": [],
        "cc": [],
        "asunto_template": "Informe Diario FDS - {fecha} - {turno}",
        "firma": "Departamento Tecnico y Sistemas\nCasino Ovalle",
        "modo_envio": "display",  # "display" muestra el correo; "send" lo envia directo
        # --- SMTP directo (alternativa a Outlook clasico) ---
        # Si el operador no tiene Outlook clasico instalado (ej. usa el
        # 'Nuevo Outlook' / app Mail de Win11), puede configurar un SMTP
        # para enviar directamente. Soporta M365 con App Password o
        # cualquier servidor SMTP+STARTTLS.
        "smtp_enabled": False,       # si False, sigue usando Outlook (win32com)
        "smtp_host": "smtp.office365.com",
        "smtp_port": 587,            # 587 = STARTTLS (recomendado); 465 = SSL
        "smtp_user": "",             # ej. "Satovalle.OV@ovallecasinoresort.cl"
        "smtp_password": "",         # App Password de Microsoft (no la password normal)
        "smtp_use_tls": True,        # STARTTLS si port=587, SSL si port=465
    },
    "turno": {
        # Turno actual detectable por hora del sistema. Editable.
        "manana": {"etiqueta": "Manana", "rango": "08:00-14:00"},
        "tarde": {"etiqueta": "Tarde", "rango": "14:00-22:00"},
        "noche": {"etiqueta": "Noche", "rango": "22:00-06:00"},
    },
    "tecnicos": [
        # Catalogo inicial editable desde la pantalla Configuracion.
        "R. Fuentes",
        "C. Torres",
        "P. Salinas",
        "Elvis M.",
    ],
    "usuario_actual": "Elvis M.",
}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def ensure_dirs() -> None:
    """Crea las carpetas del proyecto si no existen."""
    for d in (DATABASE_DIR, LOGS_DIR, BACKUPS_DIR,
              TEMPLATES_DIR, ICONS_DIR, STYLES_DIR):
        d.mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    """Lee ``config.json`` y lo fusiona con los defaults.

    Si el archivo no existe lo crea con los defaults. Cualquier clave
    nueva agregada a ``DEFAULT_CONFIG`` se incorpora automaticamente en
    instalaciones existentes (merge shallow por seccion).
    """
    ensure_dirs()
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)

    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        # Config corrupta: respaldar y volver a defaults
        backup = CONFIG_PATH.with_suffix(".corrupt.json")
        try:
            CONFIG_PATH.replace(backup)
        except OSError:
            pass
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)

    # Merge shallow de defaults para nuevas claves
    merged = dict(DEFAULT_CONFIG)
    for section, values in data.items():
        if isinstance(values, dict) and isinstance(merged.get(section), dict):
            merged[section] = {**merged[section], **values}
        else:
            merged[section] = values
    return merged


def save_config(data: dict[str, Any]) -> None:
    """Persiste ``data`` en ``config.json`` con formato legible."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def resource_path(rel: str) -> Path:
    """Resuelve una ruta relativa a ``resources/``.

    Compatible con PyInstaller --onefile: si el archivo esta dentro del
    bundle (``sys._MEIPASS``), se devuelve esa ruta.
    """
    base = getattr(os.sys, "_MEIPASS", None)
    if base:
        candidate = Path(base) / "resources" / rel
        if candidate.exists():
            return candidate
    return RESOURCES_DIR / rel


if __name__ == "__main__":
    # Smoke: imprimir config efectiva y verificar paths clave
    ensure_dirs()
    cfg = load_config()
    print(f"BASE_DIR: {BASE_DIR}")
    print(f"DATABASE_PATH: {DATABASE_PATH}")
    print(f"EMAIL_TEMPLATE exists: {EMAIL_TEMPLATE_PATH.exists()}")
    print(f"Config keys: {list(cfg.keys())}")