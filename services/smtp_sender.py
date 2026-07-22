"""Envio de correo via SMTP directo (sin Outlook clasico).

Por que existe
--------------
El casino tiene Microsoft 365 con el 'Nuevo Outlook' (app Mail
nativa de Win11) que NO expone la API COM Automation. win32com
cae al fallback de HTML persistido. Para que el operador pueda
mandar el informe sin instalar nada, este modulo envia via
SMTP directo - la mayoria de los proveedores lo soporta, incluido
Microsoft 365 con App Password.

Que se necesita del operador
----------------------------
1. En Settings -> Correo: tildar 'Enviar via SMTP en lugar de
   Outlook clasico' y completar host/puerto/usuario/password.
2. Si la cuenta es M365, el password NO es la password normal:
   es un 'App Password' que se genera en
   https://account.microsoft.com -> Security -> App passwords.

Como se usa
-----------
    from services import smtp_sender

    # Probar conexion (boton en Settings):
    r = smtp_sender.probar_conexion(host, port, user, pwd, use_tls=True)
    if r['ok']: ...

    # Enviar el informe renderizado:
    r = smtp_sender.enviar(
        host=..., port=..., user=..., password=...,
        use_tls=True,
        from_addr=user,
        to_addrs=['dest@casino.local'],
        cc_addrs=['cc@casino.local'],
        subject='Informe Diario FDS - 20/07/2026 - Noche',
        html_body='<html>...',
    )
    # r == {'ok': bool, 'modo': 'smtp', 'mensaje': str, 'archivo': str}

Notas de diseno
---------------
* Todo es best-effort: si SMTP falla, devuelve ok=False con
  mensaje de error human-readable. El caller decide si pedir
  fallback a Outlook o mostrar el dialog.
* Soporta STARTTLS (puerto 587) y SSL directo (puerto 465).
  STARTTLS es el default y el recomendado.
* Manda HTML multiparte (text/html + text/plain fallback) via
  MIMEMultipart. Outlook y todos los clientes modernos
  renderizan el HTML; clientes viejos / lectores de texto
  muestran el fallback.
"""

from __future__ import annotations

import smtplib
import socket
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from typing import Iterable


def _smtp_login_and_send(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    use_tls: bool,
    from_addr: str,
    to_addrs: list[str],
    cc_addrs: list[str],
    subject: str,
    html_body: str,
) -> None:
    """Hace login + send. Lanza excepciones smtplib / socket."""

    # Timeout razonable para no colgar si el servidor no responde
    socket.setdefaulttimeout(15)

    if use_tls and port == 465:
        # SSL directo (puerto 465 - antiguo pero soportado)
        ctx = ssl.create_default_context()
        smtp = smtplib.SMTP_SSL(host, port, context=ctx, timeout=15)
    else:
        # STARTTLS (puerto 587) o sin encriptacion (puerto 25 LAN)
        smtp = smtplib.SMTP(host, port, timeout=15)
        if use_tls:
            # Si el server anuncia STARTTLS y TLS esta habilitado.
            # Si announce falla o no esta disponible, dejo que la
            # excepcion suba para que el caller la muestre.
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()

    try:
        smtp.login(user, password)
        # El remitente que aparece en el correo es el login (from_addr);
        # Outlook y M365 rechazan From distinto del login, asi que
        # usamos siempre user como From.
        msg = _build_message(
            from_addr=from_addr,
            to_addrs=to_addrs,
            cc_addrs=cc_addrs,
            subject=subject,
            html_body=html_body,
        )
        smtp.send_message(msg)
    finally:
        try:
            smtp.quit()
        except Exception:
            pass


def _build_message(
    *,
    from_addr: str,
    to_addrs: list[str],
    cc_addrs: list[str],
    subject: str,
    html_body: str,
) -> EmailMessage:
    """Arma un EmailMessage con parte HTML + fallback text/plain."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)
    if cc_addrs:
        msg["Cc"] = ", ".join(cc_addrs)
    # Fallback de texto (clientes sin HTML / busquedas en M365).
    # Tomamos los tags visibles del HTML a la fuerza bruta: suficiente
    # para que el operador pueda leer el informe si abre el correo
    # en modo texto.
    text_fallback = _strip_html(html_body)
    msg.set_content(text_fallback)
    msg.add_alternative(html_body, subtype="html")
    return msg


def _strip_html(html: str) -> str:
    """Fallback de texto plano: saca tags y decodifica entidades basicas."""
    import re
    # Sacamos tags y entidades
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&oacute;", "o")
        .replace("&aacute;", "a")
        .replace("&eacute;", "e")
        .replace("&iacute;", "i")
        .replace("&uacute;", "u")
        .replace("&Aacute;", "A")
        .replace("&Eacute;", "E")
        .replace("&Iacute;", "I")
        .replace("&Oacute;", "O")
        .replace("&Uacute;", "U")
        .replace("&ntilde;", "n")
        .replace("&Ntilde;", "N")
    )
    return " ".join(text.split())


# ============================================================================
# API publica
# ============================================================================


def probar_conexion(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    use_tls: bool = True,
) -> dict:
    """Prueba login sin enviar nada.

    Retorna:
      - ok=True y mensaje vacio si la conexion + autenticacion
        funcionaron.
      - ok=False y 'error' con la descripcion humana si fallo.

    Pensada para el boton 'Probar conexion' del tab Correo de
    Settings. Asi el operador puede verificar sus credenciales
    sin tener que mandar un informe real.
    """
    if not host or not user or not password:
        return {"ok": False, "error": "Falta host, usuario o password."}
    try:
        socket.setdefaulttimeout(10)
        if use_tls and port == 465:
            ctx = ssl.create_default_context()
            smtp = smtplib.SMTP_SSL(host, port, context=ctx, timeout=10)
        else:
            smtp = smtplib.SMTP(host, port, timeout=10)
            if use_tls:
                smtp.ehlo()
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
        try:
            smtp.login(user, password)
            return {"ok": True, "error": ""}
        finally:
            try:
                smtp.quit()
            except Exception:
                pass
    except smtplib.SMTPAuthenticationError as e:
        return {
            "ok": False,
            "error": (
                "Autenticacion rechazada (SMTP 535). Verifica usuario y password. "
                "Si es M365, usa un App Password (no la password normal)."
            ),
            "smtp_code": e.smtp_code if hasattr(e, "smtp_code") else None,
            "smtp_error": str(e),
        }
    except smtplib.SMTPConnectError as e:
        return {
            "ok": False,
            "error": f"No se pudo conectar a {host}:{port}: {e}",
        }
    except socket.timeout:
        return {
            "ok": False,
            "error": f"Timeout conectando a {host}:{port}. "
            "El servidor SMTP no responde. Verifica host/puerto.",
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def enviar(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    use_tls: bool,
    from_addr: str,
    to_addrs: Iterable[str],
    cc_addrs: Iterable[str] = (),
    subject: str,
    html_body: str,
) -> dict:
    """Envia el informe via SMTP directo.

    Parametros:
      host, port, user, password, use_tls: configuracion SMTP.
      from_addr: direccion que aparece como 'From'. Por default
        coincide con user (asi lo requiere M365).
      to_addrs: lista de destinatarios Para.
      cc_addrs: lista de destinatarios CC (opcional).
      subject: asunto del correo.
      html_body: HTML ya renderizado por email_renderer.

    Retorna:
      dict con keys:
        ok:      bool
        modo:    'smtp'
        mensaje: str (human-readable)
        smtp_error: str (vacio si ok=True)
    """
    to_list = [t for t in (to_addrs or []) if t]
    if not to_list:
        return {"ok": False, "modo": "smtp", "mensaje": "Sin destinatarios."}
    if not host or not user or not password:
        return {
            "ok": False, "modo": "smtp",
            "mensaje": "SMTP mal configurado: falta host, usuario o password.",
        }

    cc_list = [c for c in (cc_addrs or []) if c]
    try:
        _smtp_login_and_send(
            host=host,
            port=port,
            user=user,
            password=password,
            use_tls=use_tls,
            from_addr=from_addr or user,
            to_addrs=to_list,
            cc_addrs=cc_list,
            subject=subject,
            html_body=html_body,
        )
        return {
            "ok": True,
            "modo": "smtp",
            "mensaje": f"Correo enviado via SMTP a {len(to_list)} destinatario(s).",
            "smtp_error": "",
        }
    except smtplib.SMTPAuthenticationError as e:
        return {
            "ok": False, "modo": "smtp",
            "mensaje": (
                "Autenticacion rechazada. Verifica usuario y password. "
                "Si es M365, usa un App Password."
            ),
            "smtp_error": str(e),
        }
    except smtplib.SMTPRecipientsRefused as e:
        return {
            "ok": False, "modo": "smtp",
            "mensaje": f"Algún destinatario fue rechazado: {e.recipients}",
            "smtp_error": str(e),
        }
    except smtplib.SMTPHeloError as e:
        return {
            "ok": False, "modo": "smtp",
            "mensaje": f"El servidor rechazo el HELO: {e}",
            "smtp_error": str(e),
        }
    except smtplib.SMTPSenderRefused as e:
        return {
            "ok": False, "modo": "smtp",
            "mensaje": f"Remitente rechazado: {e}",
            "smtp_error": str(e),
        }
    except socket.timeout:
        return {
            "ok": False, "modo": "smtp",
            "mensaje": f"Timeout conectando a {host}:{port}.",
            "smtp_error": "timeout",
        }
    except Exception as e:
        return {
            "ok": False, "modo": "smtp",
            "mensaje": f"Error SMTP: {type(e).__name__}: {e}",
            "smtp_error": str(e),
        }


__all__ = ("enviar", "probar_conexion")
