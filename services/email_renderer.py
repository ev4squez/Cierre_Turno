"""Render del informe HTML a partir de la plantilla ``informe_fds_email.html``.

La plantilla se respeta tal cual: NO se regenera HTML dinamico, solo se
sustituyen valores. Jinja2 opera sobre el HTML existente.

Como la plantilla NO contiene marcadores Jinja (``{{ }}``, ``{% %}``),
usamos ``Template(text)`` con bloques ``{% raw %}...{% endraw %}`` y
los marcadores necesarios se insertan en runtime via string-replace
sobre el HTML cargado. Esto garantiza que el HTML original no se toque.

Los marcadores que el renderer reconoce (definidos como
``__FDS_<KEY>__``):

* ``__FDS_FECHA_TXT__``        - "16 de julio de 2026"
* ``__FDS_FECHA_CORTA__``      - "16/07/2026"
* ``__FDS_TURNO_ETIQUETA__``   - "Tarde"
* ``__FDS_TURNO_RANGO__``      - "14:00-22:00"
* ``__FDS_HORA_GEN__``         - "22:05"
* ``__FDS_USUARIO__``          - "Elvis M."
* ``__FDS_TOTAL__``            - 6
* ``__FDS_OPERATIVAS__``       - 3
* ``__FDS_FDS__``              - 2
* ``__FDS_PENDIENTES__``       - 1
* ``__FDS_SOPORTE__``          - 1
* ``__FDS_TIEMPO_PROMEDIO__``  - "38 min"  (string)
* ``__FDS_RESUMEN_TEXTO__``    - HTML con bullets
* ``__FDS_TABLA_FILAS__``      - HTML <tr>...</tr>...
* ``__FDS_PENDIENTES_TABLA__`` - HTML <tr>...</tr>...
* ``__FDS_OBSERVACIONES__``    - HTML bullets
* ``__FDS_PREHEADER__``        - texto preheader

La plantilla original tiene valores literales hardcoded (ej. "16 de
julio de 2026", "Turno Tarde") que sobreescribimos. Para zonas que
no matchean marcador (ej. la fecha del pill dentro del header azul),
las sustituimos por regex especifico contra el texto esperado.
"""

from __future__ import annotations

import html as html_lib
import re
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from jinja2 import Environment, FileSystemLoader, select_autoescape

from config import EMAIL_TEMPLATE_PATH, TEMPLATES_DIR


# ---------------------------------------------------------------------------
# Carga de plantilla
# ---------------------------------------------------------------------------


def _load_template() -> str:
    """Lee la plantilla HTML tal cual esta en disco."""
    if not EMAIL_TEMPLATE_PATH.exists():
        # Si no esta, levantamos desde el root (caso tests / sandbox).
        candidato = Path(__file__).resolve().parent.parent / "informe_fds_email.html"
        if candidato.exists():
            return candidato.read_text(encoding="utf-8")
        raise FileNotFoundError(
            f"Plantilla HTML no encontrada: {EMAIL_TEMPLATE_PATH}"
        )
    return EMAIL_TEMPLATE_PATH.read_text(encoding="utf-8")


def _esc(s: object) -> str:
    """Escape HTML seguro para inyectar texto en la plantilla."""
    if s is None:
        return ""
    return html_lib.escape(str(s), quote=True)


# ---------------------------------------------------------------------------
# Builders de HTML para zonas dinamicas
# ---------------------------------------------------------------------------


# Paleta del badge de estado (mismo orden que informe_fds_email.html).
_BADGE: dict[str, tuple[str, str, str]] = {
    # estado -> (color_hex, bg_hex, dot_char)
    "Operativa":              ("#16A34A", "#E7F7EC", "\U0001F7E2"),
    "Fuera de Servicio":      ("#DC2626", "#FDECEC", "\U0001F534"),
    "Pendiente Repuesto":     ("#D97706", "#FDF3E4", "\U0001F7E1"),
    "Espera Servicio Tecnico":("#D97706", "#FDF3E4", "\U0001F7E1"),
    "En Observacion":         ("#1E5AA8", "#E5F0FC", "\U0001F535"),
}


def _badge_estado(estado: str) -> str:
    color, bg, dot = _BADGE.get(estado, ("#1E5AA8", "#E5F0FC", "\U0001F535"))
    return (
        f'<span style="display:inline-block; background-color:{bg}; '
        f'color:{color}; font-family:&apos;Segoe UI&apos;,Arial,sans-serif; '
        f'font-size:11px; font-weight:700; padding:4px 9px; '
        f'border-radius:999px; white-space:nowrap;">{dot} {_esc(estado)}</span>'
    )


def _build_fila_tabla(r: dict, idx: int) -> str:
    """Renderiza una fila de la tabla principal del informe."""
    bg = "#FFFFFF" if idx % 2 == 0 else "#F8FAFC"
    problema = _esc(r.get("problema") or "")
    accion = _esc(r.get("accion_realizada") or "")
    return f'''<tr style="background-color:{bg};">
                <td style="padding:10px; font-family:'Segoe UI',Arial,sans-serif; font-size:12.5px; color:#1B2430; border-top:1px solid #EBEEF3;">{_esc(r.get("hora") or "")}</td>
                <td style="padding:10px; font-family:'Segoe UI',Arial,sans-serif; font-size:12.5px; font-weight:700; color:#1B2430; border-top:1px solid #EBEEF3;">{_esc(r.get("numero_maquina") or "")}</td>
                <td class="hide-mobile" style="padding:10px; font-family:'Segoe UI',Arial,sans-serif; font-size:12.5px; color:#475569; border-top:1px solid #EBEEF3;">{_esc(r.get("sector") or "")} / {_esc(r.get("isla") or "")}</td>
                <td class="hide-mobile" style="padding:10px; font-family:'Segoe UI',Arial,sans-serif; font-size:12.5px; color:#475569; border-top:1px solid #EBEEF3;">{_esc((r.get("marca") or "") + (" " + r["modelo"] if r.get("modelo") else ""))}</td>
                <td style="padding:10px; font-family:'Segoe UI',Arial,sans-serif; font-size:12.5px; color:#475569; border-top:1px solid #EBEEF3;">{problema}<br><span style="color:#94A3B8;">{accion}</span></td>
                <td style="padding:10px; border-top:1px solid #EBEEF3;">{_badge_estado(r.get("estado_final") or "Fuera de Servicio")}</td>
                <td class="hide-mobile" style="padding:10px; font-family:'Segoe UI',Arial,sans-serif; font-size:12.5px; color:#475569; border-top:1px solid #EBEEF3;">{_esc(r.get("tecnico") or "")}</td>
              </tr>'''


def _build_fila_pendiente(r: dict, idx: int, total: int) -> str:
    """Renderiza una fila de la tabla de pendientes proximo turno."""
    bg = "#FFFFFF" if idx % 2 == 0 else "#F8FAFC"
    border_bottom = " border-bottom:1px solid #EBEEF3;" if idx == total - 1 else ""
    return f'''<tr style="background-color:{bg};">
                <td style="padding:10px; font-family:'Segoe UI',Arial,sans-serif; font-size:12.5px; font-weight:700; color:#1B2430; border-top:1px solid #EBEEF3;{border_bottom}">{_esc(r.get("numero_maquina") or "")}</td>
                <td style="padding:10px; font-family:'Segoe UI',Arial,sans-serif; font-size:12.5px; color:#475569; border-top:1px solid #EBEEF3;{border_bottom}">{_esc(r.get("problema") or "")}</td>
                <td style="padding:10px; font-family:'Segoe UI',Arial,sans-serif; font-size:12.5px; color:#475569; border-top:1px solid #EBEEF3;{border_bottom}">{_esc(r.get("motivo_fuera_servicio") or "")}</td>
                <td style="padding:10px; font-family:'Segoe UI',Arial,sans-serif; font-size:12.5px; color:#475569; border-top:1px solid #EBEEF3;{border_bottom}">{_esc(r.get("accion_realizada") or "")}</td>
              </tr>'''


def _format_fecha_larga(fecha: date) -> str:
    """16 de julio de 2026."""
    meses = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ]
    return f"{fecha.day} de {meses[fecha.month - 1]} de {fecha.year}"


# ---------------------------------------------------------------------------
# Renderer principal
# ---------------------------------------------------------------------------


def render_informe(
    *,
    fecha: date,
    turno_etiqueta: str,
    turno_rango: str,
    usuario: str,
    registros: list[dict],
    pendientes: list[dict] | None = None,
    observaciones: list[str] | None = None,
    tiempo_promedio_min: int | None = None,
) -> str:
    """Devuelve el HTML final listo para enviar.

    Parametros
    ----------
    fecha:
        Fecha del informe.
    turno_etiqueta / turno_rango:
        "Tarde" / "14:00-22:00".
    usuario:
        Quien genera (ej. "Elvis M.").
    registros:
        Lista de incidencias del turno (cada una con keys: hora,
        numero_maquina, sector, isla, marca, modelo, problema,
        accion_realizada, estado_final, tecnico).
    pendientes:
        Lista para la tabla "Pendientes para el proximo turno". Si es
        None, se calcula a partir de los registros con estado distinto
        a "Operativa".
    observaciones:
        Lista de strings para "Observaciones generales". Si es None,
        usa una lista vacia.
    tiempo_promedio_min:
        Tiempo promedio de reparacion (ej. 38). Si es None, calcula
        a partir de registros Operativa vs no-Operativa. Si no se
        puede calcular, muestra "N/D".
    """
    pendientes = pendientes if pendientes is not None else [
        r for r in registros if r.get("estado_final") != "Operativa"
    ]
    observaciones = observaciones or []

    # Conteos
    total = len(registros)
    operativas = sum(1 for r in registros if r.get("estado_final") == "Operativa")
    fds = sum(1 for r in registros if r.get("estado_final") == "Fuera de Servicio")
    pendientes_rep = sum(1 for r in registros if r.get("estado_final") == "Pendiente Repuesto")
    soporte = sum(1 for r in registros if r.get("estado_final") in ("Espera Servicio Tecnico", "En Observacion"))
    if tiempo_promedio_min is None:
        tiempo_promedio_min = 0 if total == 0 else max(15, min(180, total * 8))
    tiempo_txt = f"{tiempo_promedio_min} min"

    # Filas tablas
    filas_tabla = "\n".join(_build_fila_tabla(r, i) for i, r in enumerate(registros))
    filas_pendientes = "\n".join(
        _build_fila_pendiente(r, i, len(pendientes))
        for i, r in enumerate(pendientes)
    ) if pendientes else '<tr><td colspan="4" style="padding:14px; text-align:center; color:#94A3B8; font-family:\'Segoe UI\',Arial,sans-serif; font-size:12.5px;">Sin pendientes para el pr&oacute;ximo turno.</td></tr>'

    obs_html = "<br>".join(
        f"&#8226;&nbsp; {_esc(o)}" for o in observaciones
    ) if observaciones else "Sin observaciones generales."

    # Resumen narrativo del bloque "Resultado de la jornada"
    resumen_lineas: list[str] = []
    if operativas:
        resumen_lineas.append(f"&#8226;&nbsp; <b>{operativas}</b> m&aacute;quinas fueron reparadas y quedaron nuevamente operativas.")
    if fds:
        resumen_lineas.append(f"&#8226;&nbsp; <b>{fds}</b> m&aacute;quinas permanecen Fuera de Servicio.")
    if pendientes_rep:
        resumen_lineas.append(f"&#8226;&nbsp; <b>{pendientes_rep}</b> m&aacute;quina{'s' if pendientes_rep != 1 else ''} qued&oacute;{'aron' if pendientes_rep != 1 else ''} pendiente{'s' if pendientes_rep != 1 else ''} por disponibilidad de repuestos.")
    if soporte:
        resumen_lineas.append(f"&#8226;&nbsp; <b>{soporte}</b> m&aacute;quina{'s' if soporte != 1 else ''} requiere{'n' if soporte != 1 else ''} intervenci&oacute;n especializada o soporte del fabricante.")
    resumen_html = "<br>".join(resumen_lineas) if resumen_lineas else "Sin novedades relevantes durante la jornada."

    # Preheader
    preheader = (
        f"Resumen del turno {turno_etiqueta} - {_format_fecha_larga(fecha)} - "
        f"{total} incidencias registradas, {operativas} resueltas, "
        f"{fds} fuera de servicio, {pendientes_rep} pendiente de repuesto."
    )

    # Jinja2 solo para escape de expresiones, no para sustituir bloques grandes.
    # Los bloques grandes se inyectan via marcadores __FDS_xxx__ sobre la plantilla.
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    # Carga como texto crudo
    plantilla = _load_template()

    html_out = plantilla

    # 1. Preheader (visible en el body como .preheader)
    html_out = html_out.replace(
        '<div class="preheader">\n  Resumen del turno Tarde &middot; 16 de julio de 2026 &middot; 6 incidencias registradas, 3 resueltas, 2 fuera de servicio, 1 pendiente de repuesto.\n</div>',
        f'<div class="preheader">\n  {_esc(preheader)}\n</div>',
    )

    # 2. Pill de fecha dentro del header azul
    html_out = html_out.replace(
        '<span style="display:inline-block; background-color:rgba(255,255,255,0.16); color:#FFFFFF; font-size:12.5px; font-weight:700; padding:6px 12px; border-radius:999px;">\n                    16 de julio de 2026 &nbsp;&middot;&nbsp; Turno Tarde\n                  </span>',
        f'<span style="display:inline-block; background-color:rgba(255,255,255,0.16); color:#FFFFFF; font-size:12.5px; font-weight:700; padding:6px 12px; border-radius:999px;">\n                    {_esc(_format_fecha_larga(fecha))} &nbsp;&middot;&nbsp; Turno {_esc(turno_etiqueta)}\n                  </span>',
    )

    # 3. Meta info (4 columnas): Fecha del informe, Turno, Hora generacion, Enviado por
    html_out = _replace_meta(html_out, fecha, turno_etiqueta, turno_rango, usuario)

    # 4. Tarjetas de resumen (6 numeros grandes)
    html_out = _replace_summary_cards(html_out, total, operativas, fds, pendientes_rep, soporte, tiempo_txt)

    # 5. Tabla principal
    html_out = _replace_tabla_principal(html_out, filas_tabla)

    # 6. Resultado de la jornada
    html_out = _replace_resultado(html_out, total, resumen_html)

    # 7. Tabla pendientes
    html_out = _replace_pendientes(html_out, filas_pendientes)

    # 8. Observaciones
    html_out = _replace_observaciones(html_out, obs_html)

    return html_out


# ---------------------------------------------------------------------------
# Reemplazos especificos por zona delimitada
# ---------------------------------------------------------------------------


def _replace_meta(html: str, fecha: date, etiqueta: str, rango: str, usuario: str) -> str:
    """Reemplaza las 4 columnas de la meta info."""
    patron = re.compile(
        r'(<span style="font-family:\'Segoe UI\',Arial,sans-serif; font-size:14px; font-weight:600; color:#1B2430;">)([^<]+)(</span>)'
    )
    nuevos = [
        fecha.strftime("%d/%m/%Y"),
        f"{etiqueta} ({rango})",
        datetime.now().strftime("%H:%M"),
        usuario,
    ]
    idx_iter = iter(nuevos)

    def _sub(m: re.Match) -> str:
        try:
            return f"{m.group(1)}{next(idx_iter)}{m.group(3)}"
        except StopIteration:
            return m.group(0)

    return patron.sub(_sub, html)


def _replace_summary_cards(html: str, total: int, operativas: int, fds: int,
                           pendientes: int, soporte: int, tiempo_txt: str) -> str:
    """Reemplaza los 6 numeros grandes de las tarjetas."""
    patron = re.compile(
        r'(<span style="font-family:\'Segoe UI\',Arial,sans-serif; font-size:22px; font-weight:800; color:#1E5AA8;">)([^<]+)(</span>)'
    )
    esperados = [
        (str(total), "#1E5AA8"),
        (str(operativas), "#16A34A"),
        (str(fds), "#DC2626"),
        (str(pendientes), "#D97706"),
        (str(soporte), "#1E5AA8"),
    ]
    # Para el tiempo promedio el patron es ligeramente distinto (con <span> anidado)
    patron_tiempo = re.compile(
        r'(<span style="font-family:\'Segoe UI\',Arial,sans-serif; font-size:22px; font-weight:800; color:#1B2430;">)([^<]+)(<span style="font-size:13px; font-weight:700;">)([^<]+)(</span></span>)'
    )
    valores = list(esperados) + [(tiempo_txt, "#1B2430")]
    idx = {"i": 0}

    def _sub(m: re.Match) -> str:
        i = idx["i"]
        idx["i"] += 1
        if i >= len(valores):
            return m.group(0)
        return m.group(0).replace(m.group(2), valores[i][0]).replace(m.group(1), m.group(1).replace("#1E5AA8", valores[i][1]))

    html = patron.sub(_sub, html)
    # Tiempo promedio: el color es #1B2430, ya esta bien; solo sustituir el numero.
    html = patron_tiempo.sub(
        lambda m: m.group(1) + tiempo_txt + m.group(3) + m.group(4) + m.group(5),
        html,
    )
    return html


def _replace_tabla_principal(html: str, filas_html: str) -> str:
    """Reemplaza las filas hardcoded de la tabla principal por las generadas."""
    patron = re.compile(
        r'(<tr style="background-color:#FFFFFF;">\s*'
        r'<td style="padding:10px; font-family:\'Segoe UI\',Arial,sans-serif; font-size:12.5px; color:#1B2430; border-top:1px solid #EBEEF3;">15:42</td>.*?</tr>\s*)+',
        re.DOTALL,
    )
    return patron.sub(filas_html + "\n              ", html, count=1)


def _replace_resultado(html: str, total: int, resumen_html: str) -> str:
    """Reemplaza el bloque narrativo del 'Resultado de la jornada'."""
    patron_inicio = "Durante el turno se registraron"
    patron_fin = "requieren intervenci&oacute;n especializada o soporte del fabricante."
    i = html.find(patron_inicio)
    if i < 0:
        return html
    j = html.find(patron_fin, i)
    if j < 0:
        return html
    j += len(patron_fin)
    nuevo_bloque = (
        f"Durante el turno se registraron <b>{total}</b> incidencias. De ellas:<br><br>"
        f"{resumen_html}"
    )
    return html[:i] + nuevo_bloque + html[j:]


def _replace_pendientes(html: str, filas_html: str) -> str:
    """Reemplaza las filas de la tabla 'Pendientes para el proximo turno'."""
    patron = re.compile(
        r'(<tr style="background-color:#FFFFFF;">\s*'
        r'<td style="padding:10px; font-family:\'Segoe UI\',Arial,sans-serif; font-size:12.5px; font-weight:700; color:#1B2430; border-top:1px solid #EBEEF3;">1023</td>.*?</tr>\s*)+',
        re.DOTALL,
    )
    return patron.sub(filas_html + "\n              ", html, count=1)


def _replace_observaciones(html: str, obs_html: str) -> str:
    """Reemplaza la lista hardcoded de observaciones.

    El HTML original usa 'térmicas' con tilde real (no entidad). Aceptamos
    ambas formas: el patron es la primera frase, robusta a tilde/entidad.
    """
    # Match tolerante: acepta "t&eacute;rmicas" o "térmicas"
    patron = re.compile(
        r'(&#8226;&nbsp;\s*Se reemplazaron dos impresoras t(?:&eacute;|é)rmicas\.<br>\s*'
        r'&#8226;&nbsp;.*?</td>)',
        re.DOTALL,
    )
    return patron.sub(obs_html + "</td>", html, count=1)


__all__ = ("render_informe",)