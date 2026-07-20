# -*- mode: python ; coding: utf-8 -*-
"""Spec de PyInstaller para Sistema FDS (Casino Ovalle).

Genera un directorio portable en ``dist/SistemaFDS/`` con el .exe y
todas las DLLs/assets. Listo para correr desde un pendrive sin
instalar nada en la maquina destino.

Build (en Windows):

    venv\\Scripts\\activate
    pip install -r requirements.txt
    pyinstaller app.spec --noconfirm

Resultado:

    dist/SistemaFDS/
        SistemaFDS.exe         # entry point
        _internal/             # dependencias (DLLs, .pyd, etc)
        resources/             # logos, QSS
        templates/             # informe_fds_email.html
        database.db            # se crea al primer arranque

Tamanio tipico: 300-500 MB.

Notas tecnicas:
    - collect_all para PySide6 evita que falten DLLs de Qt (qsvg, etc)
    - collect_data_files para resources/ y templates/ que el codigo
      lee en runtime via Path relativa al __file__
    - hiddenimports explicitos para modulos que PyInstaller no detecta
"""

from pathlib import Path

import sys

# ---------------------------------------------------------------------------
# Paths base
# ---------------------------------------------------------------------------
# PyInstaller define spec_dir automaticamente. Es el directorio donde vive
# este .spec (la raiz del repo).
# Cuando PyInstaller ejecuta el spec, expone SPECPATH en el namespace.
SPEC_DIR = Path(SPECPATH).resolve()
ROOT = SPEC_DIR

block_cipher = None

# Datos que se copian junto al .exe
# Solo se incluyen directorios que existen y tienen contenido, asi
# PyInstaller no falla si una carpeta esta vacia.
def _dir_con_contenido(path: Path) -> tuple | None:
    """Devuelve (str(path), basename) si el dir existe y tiene archivos."""
    if not path.exists() or not path.is_dir():
        return None
    if not any(path.iterdir()):
        return None
    return (str(path), path.name)

DATAS = []
for sub in ("resources", "templates"):
    entry = _dir_con_contenido(ROOT / sub)
    if entry is not None:
        DATAS.append(entry)
    else:
        print(f"[app.spec] AVISO: {sub}/ no existe o esta vacio, se omite del build")

# Icono del .exe (si existe)
ICON_PATH = ROOT / "resources" / "icons" / "app.ico"
ICON_PATH_STR = str(ICON_PATH) if ICON_PATH.exists() else None

# Imports ocultos que PyInstaller no detecta automaticamente.
# Solo los modulos que se importan dinamicamente (ej. via importlib).
# Los dialectos de SQLAlchemy se registran solos, no hay que listarlos.
HIDDENIMPORTS = []
# Agregar modulos de Windows solo si el sistema es Windows
if sys.platform == "win32":
    HIDDENIMPORTS += [
        "win32com",
        "win32com.client",
        "win32com.client.makepy",
        "pythoncom",
        "pywintypes",
    ]

# collect_all = empaqueta DLLs nativas que no estan en hiddenimports
COLLECT_ALL = [
    "PySide6",
    "sqlalchemy",
    "openpyxl",
    "jinja2",
]


a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=DATAS,
    hiddenimports=HIDDENIMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Excluir modulos innecesarios para reducir tamano
        "tkinter",
        "matplotlib",
        "scipy",
        "PyQt5",
        "PyQt6",
        "test",
        "unittest",
        "pytest",
        "setuptools",
        "pip",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    # Version del sistema. La lee desde app.py asi no hay que
    # hardcodearla en 2 lugares. Si actualizas __version__ en
    # app.py, el .exe generado tendra ese nombre.
    name=f"SistemaFDS_v{__import__('app').__version__}",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                # UPX desactivado (puede romper antivirus)
    console=False,            # GUI, sin consola
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_PATH_STR,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SistemaFDS",
)