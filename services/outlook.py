"""Envio de correo via Microsoft Outlook instalado (win32com).

NO usa SMTP, NO usa Office365, NO usa OAuth. Solo interactua con el
Outlook de Windows ya instalado via COM (Automation API).

Comportamiento:

* Si el modulo ``win32com`` esta disponible y ``Outlook.Application``
  arranca -> crea el MailItem, setea HTMLBody, destinatarios y muestra
  o envia el correo segun configuracion.
* Si NO esta disponible (sandbox / Linux / Outlook no instalado),
  ``enviar_informe()`` no rompe: devuelve ``False`` y un mensaje,
  dejando el HTML persistido en disco para depuracion o envio manual.

El modo de envio (``display`` vs ``send``) se configura en
``config.json > correo.modo_envio``.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from config import BACKUPS_DIR, LOGS_DIR
from services import email_renderer


# ---------------------------------------------------------------------------
# Deteccion de win32com
# ---------------------------------------------------------------------------


def outlook_disponible() -> bool:
    """Devuelve True si Outlook esta REALMENTE usable para enviar.

    Antes solo chequeaba si la libreria ``win32com`` estaba instalada
    (es decir si pip la habia bajado). Eso daba falso positivo en
    equipos con pywin32 instalado pero sin Outlook configurado / sin
    cuenta / con Outlook cerrado.

    Ahora hace 3 chequeos:
      1. win32com.client se puede importar
      2. Outlook.Application se puede instanciar (sin que tire error)
      3. Hay al menos una cuenta configurada

    Si cualquier falla, devuelve False. El caller deberia mostrarle
    al operador que el informe se va a guardar como archivo .eml en
    vez de mandarse por Outlook.
    """
    # 1. win32com instalado?
    try:
        import win32com.client  # type: ignore[import-not-found]  # noqa: F401
    except ImportError:
        return False

    # 2. Outlook.Application instanciable?
    try:
        import win32com.client  # type: ignore[import-not-found]
        app = win32com.client.Dispatch("Outlook.Application")
    except Exception:
        return False

    # 3. Hay al menos una cuenta configurada?
    try:
        # Namespace es lo que da acceso a cuentas / carpetas. Si
        # Outlook no esta logueado, esto puede tirar.
        namespace = app.GetNamespace("MAPI")
        if namespace is None:
            return False
        # Session.Accounts: lista de cuentas activas. Si Count == 0,
        # no hay cuenta para enviar desde.
        try:
            session = namespace.Session
            if session is None or session.Accounts.Count == 0:
                return False
        except Exception:
            return False
    except Exception:
        return False

    return True


# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------


def enviar_informe(
    *,
    html: str,
    asunto: str,
    destinatarios: list[str],
    cc: list[str] | None = None,
    modo: str = "display",
    logo_path: str | None = None,
) -> dict[str, Any]:
    """Crea y envia (o muestra) el correo en Outlook.

    Parametros
    ----------
    html:
        HTML final ya renderizado por ``email_renderer.render_informe``.
    asunto:
        Asunto del correo.
    destinatarios:
        Lista de emails 'Para:'.
    cc:
        Lista de emails en CC (opcional).
    modo:
        'display' para que el operador revise antes de enviar.
        'send' para enviar directo.
    logo_path:
        Ruta absoluta a un logo local para incrustar (opcional). Outlook
        suele bloquear imagenes externas, asi que se adjunta como
        attachment y se referencia con cid:.

    Retorna
    -------
    dict con keys:
        ok:       bool
        modo:     str ('display' / 'send' / 'fallback')
        mensaje:  str  (descripcion humana del resultado)
        outlook:  bool (True si uso Outlook real)
        archivo:  str  (ruta del HTML persistido si no se uso Outlook)
    """
    cc = cc or []

    # Logueamos el intento siempre (util para soporte).
    _log("intento_envio", {
        "asunto": asunto,
        "dest": destinatarios,
        "cc": cc,
        "modo": modo,
    })

    if not destinatarios:
        # Sin destinatarios: no se puede enviar; persistimos HTML para envio manual.
        path = _persistir_html(html, asunto)
        return {
            "ok": False,
            "modo": "fallback",
            "outlook": False,
            "mensaje": "No hay destinatarios configurados. HTML guardado en disco.",
            "archivo": str(path),
        }

    if not outlook_disponible():
        path = _persistir_html(html, asunto)
        return {
            "ok": False,
            "modo": "fallback",
            "outlook": False,
            "mensaje": (
                "Outlook no disponible en esta maquina (win32com no encontrado). "
                "HTML guardado en disco para envio manual."
            ),
            "archivo": str(path),
        }

    try:
        import win32com.client  # type: ignore[import-not-found]

        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")

        # MailItem. Para evitar el popup de seguridad de Outlook cuando se
        # usa Application.CreateItem en algunos perfiles, usamos el atajo
        # namespace.OpenSharedItem o el CreateItem estandar.
        mail = outlook.CreateItem(0)  # 0 = olMailItem
        mail.Subject = asunto
        mail.HTMLBody = html
        mail.To = "; ".join(destinatarios)
        if cc:
            mail.CC = "; ".join(cc)

        if logo_path and Path(logo_path).exists():
            try:
                attachment = mail.Attachments.Add(str(Path(logo_path).resolve()))
                # cid embebido en el HTML si lo referenciamos como <img src="cid:logo">
                attachment.PropertyAccessor.SetProperty(
                    "http://schemas.microsoft.com/mapi/proptag/0x3712001E", "logo"
                )
            except Exception as e:  # pragma: no cover - entorno dependiente
                _log("logo_error", {"error": str(e)})

        modo_ejecucion = (modo or "display").lower().strip()
        if modo_ejecucion == "send":
            mail.Send()
            accion = "enviado"
        else:
            mail.Display()
            accion = "mostrado"

        _log("envio_ok", {"asunto": asunto, "accion": accion})
        return {
            "ok": True,
            "modo": modo_ejecucion,
            "outlook": True,
            "mensaje": f"Correo {accion} correctamente en Outlook.",
            "archivo": "",
        }

    except Exception as e:
        path = _persistir_html(html, asunto)
        # Clasificar el error para que el caller muestre el dialog
        # accionable correcto. Outlook tira variantes del mismo problema
        # de "perfil / archivo de datos no encontrado" con codigos
        # COM especificos:
        #   -2147352567  (0x80004005 E_FAIL generico)
        #   -2147221219  (0x8004010F que es MAPI_E_NOT_FOUND)
        # Mas el texto "no se encuentra un archivo de datos" / "data file"
        # / "no hay perfiles" / "default profile".
        categoria = _clasificar_error_outlook(e)
        _log("envio_error", {
            "error": str(e),
            "asunto": asunto,
            "categoria": categoria,
        })
        return {
            "ok": False,
            "modo": "fallback",
            "outlook": False,
            "categoria": categoria,
            "mensaje": f"Error al usar Outlook: {e}. HTML guardado en disco.",
            "archivo": str(path),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _persistir_html(html: str, asunto: str) -> Path:
    """Guarda el HTML renderizado en ``backups/`` para envio manual / auditoria."""
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    nombre = _safe_filename(asunto) + ".html"
    path = BACKUPS_DIR / nombre
    path.write_text(html, encoding="utf-8")
    return path


def _safe_filename(s: str) -> str:
    """Convierte un texto a nombre de archivo seguro."""
    keep = "-_."
    return "".join(c if (c.isalnum() or c in keep) else "_" for c in (s or ""))[:80].strip("_") or "informe"


def _log(evento: str, data: dict) -> None:
    """Log JSON-line simple en ``logs/correo.log`` con rotacion automatica.

    Cuando el archivo supera ``_LOG_MAX_BYTES`` (5 MB por defecto),
    se renombra a ``correo.log.1`` y se empieza uno nuevo. Si ya
    existe ``correo.log.1``, se borra primero (rotacion de 1 nivel:
    suficiente para auditoria de errores sin acumular gigas).
    """
    try:
        import json
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOGS_DIR / "correo.log"
        # Rotar si supera el tamano maximo
        if log_path.exists():
            try:
                if log_path.stat().st_size >= _LOG_MAX_BYTES:
                    backup = LOGS_DIR / "correo.log.1"
                    if backup.exists():
                        backup.unlink()
                    log_path.rename(backup)
            except OSError:
                pass  # si no podemos rotar, seguimos con el log grande
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(
                {"ts": datetime.now().isoformat(), "event": evento, **data},
                ensure_ascii=False,
            ) + "\n")
    except OSError:
        pass


_LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB


# ---------------------------------------------------------------------------
# Conveniencia: arma asunto + render + envio en una sola llamada
# ---------------------------------------------------------------------------


def armar_asunto(template: str, *, fecha, turno: str) -> str:
    """Aplica el template de asunto de ``config.json``.

    Si el template falla por falta de claves, devuelve el template crudo.
    """
    try:
        return template.format(fecha=fecha.strftime("%d/%m/%Y"), turno=turno)
    except (KeyError, IndexError, AttributeError):
        return template


# ---------------------------------------------------------------------------
# Clasificacion de errores + helper para abrir Panel de control
# ---------------------------------------------------------------------------


# Codigos COM mas comunes que vemos cuando Outlook no puede enviar:
#   -2147352567  -> 0x80004005 (E_FAIL generico, "no se encuentra un
#                   archivo de datos" suele caer aca)
#   -2147221219  -> 0x8004010F (MAPI_E_NOT_FOUND)
#   -2147164126  -> 0x80030305 (error de archivo .ost/.pst)
# Estos los emite Outlook cuando CreateItem() no tiene perfil/default
# store. El operador lo ve como "no hay archivo de datos para enviar y
# recibir mensajes".
_OUTLOOK_COM_CODES_FALLA_PERFIL = (
    -2147352567,  # 0x80004005
    -2147221219,  # 0x8004010F
    -2147164126,  # 0x80030305
)

# Frases que Outlook mete en el mensaje cuando es problema de perfil.
_OUTLOOK_FRASES_FALLA_PERFIL = (
    "no se encuentra un archivo de datos",
    "archivo de datos",
    "data file",
    "no hay ningun perfil",
    "no se puede crear el mensaje",
    "default profile",
    "perfil predeterminado",
    "no profile",
)


def _clasificar_error_outlook(exc: BaseException) -> str:
    """Categoriza la excepcion que devolvio Outlook.

    Categorias posibles:
      * ``perfil_no_configurado`` -> no hay perfil / cuenta default.
        El operador tiene que configurar uno. Le mostramos el camino
        al Panel de control -> Correo.
      * ``otro`` -> cualquier otro error (red, permisos, antivirus).
        Mensaje generico.
    """
    # El __cause__ o args suelen traer la tupla COM (code, source, msg, ...)
    candidatos: list[str] = []
    code_val: int | None = None
    s = str(exc) or ""
    candidatos.append(s)
    if exc.__cause__ is not None:
        candidatos.append(str(exc.__cause__))
    if exc.__context__ is not None:
        candidatos.append(str(exc.__context__))
    if hasattr(exc, "args"):
        for a in (exc.args or ()):
            if isinstance(a, (int, float)):
                code_val = int(a)
            else:
                candidatos.append(str(a))

    blob = " | ".join(c.lower() for c in candidatos)
    # Match por codigo COM
    for code in _OUTLOOK_COM_CODES_FALLA_PERFIL:
        if code_val == code or str(code) in blob:
            # Refinamos con texto si esta, si no asumimos perfil por
            # estar en el set conocido de errores COM de MAPI.
            if any(frase in blob for frase in _OUTLOOK_FRASES_FALLA_PERFIL):
                return "perfil_no_configurado"
            if code in (-2147352567, -2147221219):
                return "perfil_no_configurado"
    # Match solo por texto (cubrimos mensajes localizados)
    for frase in _OUTLOOK_FRASES_FALLA_PERFIL:
        if frase in blob:
            return "perfil_no_configurado"
    return "otro"


def abrir_panel_control_correo() -> bool:
    """Abre el dialogo 'Panel de control -> Correo' (Mail applet) de Windows.

    Sirve para que el operador pueda configurar / seleccionar el perfil
    de Outlook que el sistema va a usar. Pensado para llamarlo desde el
    boton del dialog de error.

    Comandos intentados en orden (Win11 a veces cambia el canonico):
      1. ``control.exe /name Microsoft.Mail``   (canonico moderno)
      2. ``control.exe mlcfg32.cpl``            (canonico legacy)
      3. ``control.exe /name Microsoft.Mail32`` (algunas builds)

    Devuelve True si pudo disparar alguno sin error OS.
    """
    import subprocess
    candidatos = [
        ["control.exe", "/name", "Microsoft.Mail"],
        ["control.exe", "mlcfg32.cpl"],
        ["control.exe", "/name", "Microsoft.Mail32"],
    ]
    for cmd in candidatos:
        try:
            r = subprocess.run(cmd, timeout=4, capture_output=True)
            # control.exe devuelve 0 si abrio el applet. Aun si no,
            # el proceso arranco; dejamos que Windows muestre el error
            # nativo. Solo abortamos si el ejecutable no existe.
            return True
        except FileNotFoundError:
            continue
        except Exception:
            continue
    return False


def enviar_informe_turno(
    *,
    resumen,  # services.incidencias.ResumenTurno
    usuario: str,
    turno_etiqueta: str,
    turno_rango: str,
    destinatarios: list[str],
    cc: list[str] | None = None,
    modo: str = "display",
    asunto_template: str = "Informe Diario FDS - {fecha} - {turno}",
    pendientes: list[dict] | None = None,
    observaciones: list[str] | None = None,
    tiempo_promedio_min: int | None = None,
    logo_path: str | None = None,
    empresa: dict | None = None,
    firmante: str | None = None,
    total_maquinas_catalogo: int | None = None,
    actividades: list[dict] | None = None,
) -> dict[str, Any]:
    """Helper que une render + envio. Usado por el controller.

    Por defecto trae ``empresa``, ``destinatarios``, ``cc`` y ``firmante``
    del ``config.json`` si no se pasan explicitamente. Asi el controller
    no tiene que recordar de pasarlos en cada llamada.
    """
    # Defaults desde config si no se pasaron
    if empresa is None or destinatarios is None or cc is None or firmante is None:
        try:
            from services import configuracion as svc_cfg
            cfg = svc_cfg.obtener()
            if empresa is None:
                empresa = cfg.get("empresa", {})
            correo_cfg = cfg.get("correo", {})
            if destinatarios is None:
                destinatarios = correo_cfg.get("destinatarios", []) or []
            if cc is None:
                cc = correo_cfg.get("cc", []) or []
            if firmante is None:
                firmante = correo_cfg.get("firma", "")
        except Exception:
            empresa = empresa or {}
            destinatarios = destinatarios or []
            cc = cc or []
            firmante = firmante or ""

    html = email_renderer.render_informe(
        fecha=resumen.fecha,
        turno_etiqueta=turno_etiqueta,
        turno_rango=turno_rango,
        usuario=usuario,
        registros=resumen.registros,
        pendientes=pendientes,
        observaciones=observaciones,
        tiempo_promedio_min=tiempo_promedio_min,
        total_maquinas_catalogo=total_maquinas_catalogo,
        empresa=empresa,
        destinatarios=destinatarios,
        cc=cc,
        firmante=firmante,
        actividades=actividades,
    )
    asunto = armar_asunto(asunto_template, fecha=resumen.fecha, turno=turno_etiqueta)
    return enviar_informe(
        html=html,
        asunto=asunto,
        destinatarios=destinatarios,
        cc=cc,
        modo=modo,
        logo_path=logo_path,
    )


__all__ = (
    "outlook_disponible",
    "enviar_informe",
    "enviar_informe_turno",
    "armar_asunto",
    "abrir_panel_control_correo",
)