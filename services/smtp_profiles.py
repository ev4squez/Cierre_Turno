"""Presets de proveedores SMTP comunes para el tab Correo de Settings.

El operador elige 'Gmail' / 'Office 365 con App Password' / 'Office 365
con OAuth2' / 'Otro (generico)' de un dropdown y los campos host /
puerto / TLS / instrucciones se autocompletan. Asi el operador no
tiene que saber la combinacion correcta para cada proveedor.

Cada perfil tiene:
  - host:        servidor SMTP (str)
  - puerto:      puerto SMTP (int; 587 = STARTTLS, 465 = SSL)
  - uso_tls:     True si se usa STARTTLS o SSL
  - necesita_app_password: True si requiere App Password (M365 Gmail)
  - instructions: instrucciones human-readable de como generar el
                  password (lo que aparece en el help text del tab)
  - url_app_password:  link para generar el App Password

El dropdown enumera de menor a mayor friccion:
  - 'otro' : generico, deja los campos en blanco, el operador tipea
  - 'gmail': smtp.gmail.com:587 con App Password
  - 'm365_app' : smtp.office365.com:587 con App Password de M365
  - 'm365_oauth': smtp.office365.com:587 con XOAUTH2 (OAuth2 nativo)
"""

from __future__ import annotations

from typing import TypedDict


class SMTPProfile(TypedDict, total=False):
    """Perfil SMTP completo: campos autocompletados + ayuda."""
    key: str
    label: str
    host: str
    puerto: int
    uso_tls: bool
    necesita_app_password: bool
    instructions: str
    url_app_password: str


# Orden de la dropdown UI (de lo mas simple a lo mas complejo)
_PROFILES: list[SMTPProfile] = [
    {
        "key": "gmail",
        "label": "Gmail (Google Workspace o Gmail personal)",
        "host": "smtp.gmail.com",
        "puerto": 587,
        "uso_tls": True,
        "necesita_app_password": True,
        "instructions": (
            "Para Gmail:\n"
            "  1. Habilita la verificacion en 2 pasos en "
            "https://myaccount.google.com/security\n"
            "  2. Crea un App Password en "
            "https://myaccount.google.com/apppasswords\n"
            "  3. Pega ese password de 16 caracteres en el campo de abajo"
        ),
        "url_app_password": "https://myaccount.google.com/apppasswords",
    },
    {
        "key": "m365_app",
        "label": "Microsoft 365 / Outlook (App Password)",
        "host": "smtp.office365.com",
        "puerto": 587,
        "uso_tls": True,
        "necesita_app_password": True,
        "instructions": (
            "Para M365 con App Password:\n"
            "  1. Activa MFA en "
            "https://mysignins.microsoft.com/security-info\n"
            "  2. Crea un App Password en Microsoft Account\n"
            "  3. Si tu organizacion tiene App Passwords deshabilitado, "
            "pedile al admin que lo habilite o usa otro proveedor"
        ),
        "url_app_password": "https://mysignins.microsoft.com/security-info",
    },
    {
        "key": "m365_oauth",
        "label": "Microsoft 365 (OAuth2 / XOAUTH2)",
        "host": "smtp.office365.com",
        "puerto": 587,
        "uso_tls": True,
        "necesita_app_password": False,
        "instructions": (
            "Para M365 con OAuth2:\n"
            "  Requiere App Registration en Azure + permisos Mail.Send\n"
            "  (lo configura el admin del tenant).\n"
            "  Todavia no implementado en esta version - cayes en la "
            "opcion anterior 'App Password' o usa Gmail."
        ),
        "url_app_password": "",
    },
    {
        "key": "otro",
        "label": "Otro SMTP (Relay propio / SendGrid / SES / etc.)",
        "host": "",
        "puerto": 587,
        "uso_tls": True,
        "necesita_app_password": False,
        "instructions": (
            "SMTP generico. Completa host, puerto, usuario y password.\n"
            "Si es un relay (SendGrid / Mailgun / SES), el usuario suele "
            "ser 'apikey' o similar, no la direccion de email."
        ),
        "url_app_password": "",
    },
]


def get_profiles() -> list[SMTPProfile]:
    """Devuelve la lista de perfiles disponibles (copia defensiva)."""
    return [dict(p) for p in _PROFILES]


def find_profile(key: str) -> SMTPProfile:
    """Devuelve el perfil por key, o el 'otro' si no existe."""
    for p in _PROFILES:
        if p["key"] == key:
            return dict(p)
    return _PROFILES[-1]  # 'otro'


__all__ = ("get_profiles", "find_profile", "SMTPProfile")
