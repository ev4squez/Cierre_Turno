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
    """Devuelve True si win32com.client esta disponible en esta maquina."""
    try:
        import win32com.client  # type: ignore[import-not-found]  # noqa: F401
        return True
    except ImportError:
        return False


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
        _log("envio_error", {"error": str(e), "asunto": asunto})
        return {
            "ok": False,
            "modo": "fallback",
            "outlook": False,
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
    """Log JSON-line simple en ``logs/correo.log``."""
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        import json
        with (LOGS_DIR / "correo.log").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": datetime.now().isoformat(), "event": evento, **data}, ensure_ascii=False) + "\n")
    except OSError:
        pass


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
) -> dict[str, Any]:
    """Helper que une render + envio. Usado por el controller."""
    html = email_renderer.render_informe(
        fecha=resumen.fecha,
        turno_etiqueta=turno_etiqueta,
        turno_rango=turno_rango,
        usuario=usuario,
        registros=resumen.registros,
        pendientes=pendientes,
        observaciones=observaciones,
        tiempo_promedio_min=tiempo_promedio_min,
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
)