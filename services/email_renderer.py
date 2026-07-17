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


def _enriquecer_registros(registros: list[dict]) -> list[dict]:
    """Si los registros no tienen sector/marca/modelo, los cruza con la DB.

    Asi el renderer no depende de que el controller haya enriquecido
    previamente. Si la DB no tiene la maquina, deja los campos vacios.
    """
    campos_a_enriquecer = ("sector", "isla", "marca", "modelo", "denominacion")
    for r in registros:
        if any(r.get(c) for c in campos_a_enriquecer):
            continue
        numero = r.get("numero_maquina")
        if not numero:
            continue
        try:
            from services import maquinas as svc_maq
            m = svc_maq.obtener_por_numero(str(numero))
            if m:
                for c in campos_a_enriquecer:
                    r[c] = m.get(c, "")
        except Exception:
            pass
    return registros


def _build_fila_tabla(r: dict, idx: int) -> str:
    """Renderiza una fila de la tabla principal del informe.

    Cada fila muestra: hora, numero, denominacion del juego (debajo
    del codigo), sector/isla, marca/modelo, problema+accion, estado,
    tecnico.
    """
    bg = "#FFFFFF" if idx % 2 == 0 else "#F8FAFC"
    problema = _esc(r.get("problema") or "")
    accion = _esc(r.get("accion_realizada") or "")
    numero = _esc(r.get("numero_maquina") or "")
    denom = _esc(r.get("denominacion") or "")
    # Si hay denominacion, la mostramos en letra pequena debajo del numero
    numero_cell = f"{numero}"
    if denom:
        numero_cell = (
            f"{numero}<br>"
            f"<span style='color:#94A3B8; font-weight:400; font-size:11px;'>{denom}</span>"
        )
    return f'''<tr style="background-color:{bg};">
                <td style="padding:10px; font-family:'Segoe UI',Arial,sans-serif; font-size:12.5px; color:#1B2430; border-top:1px solid #EBEEF3;">{_esc(r.get("hora") or "")}</td>
                <td style="padding:10px; font-family:'Segoe UI',Arial,sans-serif; font-size:12.5px; font-weight:700; color:#1B2430; border-top:1px solid #EBEEF3;">{numero_cell}</td>
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
    empresa: dict | None = None,
    destinatarios: list[str] | None = None,
    cc: list[str] | None = None,
    firmante: str | None = None,
    total_maquinas_catalogo: int | None = None,
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
    empresa:
        Dict con ``nombre``, ``departamento`` y opcional ``color_corporativo``.
        Si es None, usa defaults del config.
    destinatarios / cc:
        Listas de emails a mostrar al pie del informe (seccion "Enviado a").
    firmante:
        Texto de la firma. Si es None, usa el default del config.
    """
    # Empresa: defaults si no se pasa
    if empresa is None:
        try:
            from services import configuracion as svc_cfg
            cfg = svc_cfg.obtener()
            empresa = cfg.get("empresa", {})
        except Exception:
            empresa = {}
    nombre_empresa = empresa.get("nombre", "Casino Ovalle")
    departamento = empresa.get("departamento", "Departamento Tecnico y Sistemas")
    color_corp = empresa.get("color_corporativo", "#1E5AA8") or "#1E5AA8"

    # Destinatarios
    if destinatarios is None or cc is None:
        try:
            from services import configuracion as svc_cfg
            cfg = svc_cfg.obtener()
            correo_cfg = cfg.get("correo", {})
            if destinatarios is None:
                destinatarios = correo_cfg.get("destinatarios", []) or []
            if cc is None:
                cc = correo_cfg.get("cc", []) or []
        except Exception:
            destinatarios = destinatarios or []
            cc = cc or []

    if firmante is None:
        try:
            from services import configuracion as svc_cfg
            firmante = svc_cfg.obtener().get("correo", {}).get("firma", "")
        except Exception:
            firmante = ""

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
        # Si el caller no pasa un valor, lo calculamos en tiempo real
        # desde la DB (updated_at - created_at de las Operativas del turno).
        # Devuelve None si no hay Operativas -> mostramos "N/D" en el reporte.
        from services.incidencias import tiempo_promedio_resolucion_min
        tiempo_promedio_min = tiempo_promedio_resolucion_min(registros)
    tiempo_txt = f"{tiempo_promedio_min} min" if tiempo_promedio_min is not None else "N/D"

    # Enriquecer registros con datos del catalogo si faltan
    # (sector, isla, marca, modelo, denominacion). Asi el renderer
    # funciona aunque el caller no haya enriquecido.
    registros_enriquecidos = _enriquecer_registros(registros)

    # Filas tablas
    filas_tabla = "\n".join(_build_fila_tabla(r, i) for i, r in enumerate(registros_enriquecidos))
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

    # Bloque "Enviado a" (lista de destinatarios)
    if destinatarios or cc:
        dest_html = "<br>".join(f"&#8226;&nbsp; {_esc(d)}" for d in destinatarios) or "Sin destinatarios"
        cc_html = "<br>".join(f"&#8226;&nbsp; {_esc(c)}" for c in cc) if cc else ""
        enviado_a_html = (
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="background-color:#F8FAFC; border:1px solid #EBEEF3; border-radius:10px; margin-top:8px;">'
            f'<tr><td style="padding:12px 16px; font-family:\'Segoe UI\',Arial,sans-serif; font-size:12.5px; color:#475569;">'
            f'<b style="color:#1B2430;">Para:</b><br>{dest_html}'
        )
        if cc_html:
            enviado_a_html += (
                f'<br><br><b style="color:#1B2430;">CC:</b><br>{cc_html}'
            )
        enviado_a_html += '</td></tr></table>'
    else:
        enviado_a_html = ""

    # Firma del firmante
    firma_html = ""
    if firmante:
        firma_html = (
            f'<tr><td style="padding:16px 32px 8px 32px;" class="p-mobile">'
            f'<span style="font-family:\'Segoe UI\',Arial,sans-serif; font-size:13px; color:#475569; white-space:pre-line;">'
            f'{_esc(firmante)}</span></td></tr>'
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
        '<div class="preheader">\n  Resumen del turno Tarde · 16 de julio de 2026 · 6 incidencias registradas, 3 resueltas, 2 fuera de servicio, 1 pendiente de repuesto.\n</div>',
        f'<div class="preheader">\n  {_esc(preheader)}\n</div>',
    )

    # 2. Pill de fecha dentro del header azul
    # Calcular total de maquinas del catalogo (antes del replace del pill)
    if total_maquinas_catalogo is None:
        from services.incidencias import total_maquinas_catalogo as _tmc
        try:
            total_maquinas_catalogo = _tmc(solo_activas=True)
        except Exception:
            total_maquinas_catalogo = None
    pill_extra = ""
    if total_maquinas_catalogo is not None:
        pill_extra = (
            f'                  <span style="display:inline-block; background-color:rgba(255,255,255,0.10); color:#FFFFFF; font-size:12.5px; font-weight:700; padding:6px 12px; border-radius:999px; margin-left:8px;">'
            f'Catalogo: <span style="font-weight:800;">{total_maquinas_catalogo}</span> maquinas</span>'
        )

    html_out = html_out.replace(
        '<span style="display:inline-block; background-color:rgba(255,255,255,0.16); color:#FFFFFF; font-size:12.5px; font-weight:700; padding:6px 12px; border-radius:999px;">\n                    16 de julio de 2026 &nbsp;·&nbsp; Turno Tarde\n                  </span>',
        f'<span style="display:inline-block; background-color:rgba(255,255,255,0.16); color:#FFFFFF; font-size:12.5px; font-weight:700; padding:6px 12px; border-radius:999px;">\n                    {_esc(_format_fecha_larga(fecha))} &nbsp;·&nbsp; Turno {_esc(turno_etiqueta)}\n                  </span>\n{pill_extra}\n                  ',
    )

    # 2b. Encabezado azul: casino + titulo del sistema (ahora con nombre real)
    html_out = _replace_header_branding(html_out, nombre_empresa, departamento, color_corp)

    # 3. Meta info (4 columnas): Fecha del informe, Turno, Hora generacion, Enviado por
    html_out = _replace_meta(html_out, fecha, turno_etiqueta, turno_rango, usuario)

    # 4. Tarjetas de resumen (6 numeros grandes)
    # Total del catalogo y operativas (si no se pasan, los calculamos aca)
    if total_maquinas_catalogo is None:
        try:
            from services.incidencias import total_maquinas_catalogo as _tmc
            total_maquinas_catalogo = _tmc(solo_activas=True)
        except Exception:
            total_maquinas_catalogo = 0
    if total_operativas_catalogo is None:
        try:
            from services.incidencias import total_operativas_catalogo as _toc
            total_operativas_catalogo = _toc(solo_activas=True)
        except Exception:
            total_operativas_catalogo = 0

    html_out = _replace_summary_cards(
        html_out,
        total=total,
        operativas_turno=operativas,
        fds=fds,
        pendientes=pendientes_rep,
        soporte=soporte,
        tiempo_txt=tiempo_txt,
        total_maquinas_catalogo=total_maquinas_catalogo or 0,
        total_operativas_catalogo=total_operativas_catalogo,
    )

    # 5. Tabla principal
    html_out = _replace_tabla_principal(html_out, filas_tabla)

    # 6. Resultado de la jornada
    html_out = _replace_resultado(html_out, total, resumen_html)

    # 7. Tabla pendientes
    html_out = _replace_pendientes(html_out, filas_pendientes)

    # 8. Observaciones
    html_out = _replace_observaciones(html_out, obs_html)

    # 9. Bloque "Enviado a" (insertado antes del pie del correo)
    if enviado_a_html:
        html_out = _inject_enviado_a(html_out, enviado_a_html)

    # 10. Firma del firmante (antes del pie)
    if firma_html:
        html_out = _inject_firma(html_out, firma_html)

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


def _replace_summary_cards(html: str, *, total: int, operativas_turno: int,
                           fds: int, pendientes: int, soporte: int,
                           tiempo_txt: str, total_maquinas_catalogo: int,
                           total_operativas_catalogo: int) -> str:
    """Reemplaza los 8 marcadores __FDS_XXX__ de las tarjetas.

    Layout: 2 filas x 4 tarjetas.
      Fila 1: Total maquinas, Operativas catalogo, Incidencias, Reparadas
      Fila 2: FDS, Pendientes, Soporte, Tiempo prom
    """
    reemplazos = {
        "__FDS_TOTAL_MAQUINAS__": str(total_maquinas_catalogo),
        "__FDS_TOTAL_OPERATIVAS__": str(total_operativas_catalogo),
        "__FDS_TOTAL__": str(total),
        "__FDS_OPERATIVAS__": str(operativas_turno),
        "__FDS_FDS__": str(fds),
        "__FDS_PENDIENTES__": str(pendientes),
        "__FDS_SOPORTE__": str(soporte),
        "__FDS_TIEMPO_PROMEDIO__": tiempo_txt,
    }
    for marcador, valor in reemplazos.items():
        html = html.replace(marcador, valor, 1)
    return html


def _replace_tabla_principal(html: str, filas_html: str) -> str:
    """Inyecta las filas reales en la tabla principal.

    El template tiene un marcador <!-- Filas inyectadas en runtime -->
    dentro de <tbody>. Reemplaza ese comentario por las filas generadas.
    """
    patron = re.compile(
        r'<!--\s*Filas inyectadas en runtime por services/email_renderer\.py\s*-->',
    )
    return patron.sub(filas_html, html, count=1)


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
    """Inyecta las filas reales en la tabla de pendientes."""
    patron = re.compile(
        r"<!--\s*Filas de pendientes inyectadas en runtime\s*-->",
    )
    return patron.sub(filas_html, html, count=1)


def _replace_observaciones(html: str, obs_html: str) -> str:
    """Inyecta las observaciones reales."""
    patron = re.compile(
        r"<!--\s*Observaciones inyectadas en runtime\s*-->",
    )
    return patron.sub(obs_html, html, count=1)


def _replace_header_branding(
    html: str, nombre_empresa: str, departamento: str, color_corporativo: str
) -> str:
    """Reemplaza el badge y el texto del casino en el header azul.

    El template tiene hardcoded:
      <span ...>OC</span>  (badge)
      Casino Ovalle · Depto. Tecnico y Sistemas  (subtitulo)
      Informe Diario de Maquinas Fuera de Servicio  (titulo)

    Cambiamos el badge a las iniciales del casino y actualizamos el
    subtitulo con el nombre real del config. El titulo se mantiene
    porque describe el contenido del correo.
    """
    # Iniciales para el badge (max 2 letras)
    iniciales = "".join(p[0].upper() for p in nombre_empresa.split()[:2] if p) or "CO"

    # Reemplazar el badge "OC"
    html = re.sub(
        r'(<span style="font-family:\'Segoe UI\',Arial,sans-serif; font-size:13px; font-weight:700; color:#1E5AA8;">)OC(</span>)',
        rf'\g<1>{_esc(iniciales)}\g<2>',
        html,
        count=1,
    )

    # Reemplazar el subtitulo del header. El template usa "·" (punto medio
    # Unicode directo) y "Técnico" con tilde directa, NO entidades HTML.
    patron_subtitulo = re.compile(
        r'<span style="font-family:\'Segoe UI\',Arial,sans-serif; font-size:11px; font-weight:600; color:#C7DBF5; letter-spacing:0.5px; text-transform:uppercase;">'
        r'Casino Ovalle\s*[·\.·]\s*Depto\.?\s*T[eé]cnico y Sistemas'
        r'</span>',
        re.DOTALL,
    )
    subtitulo_nuevo = (
        f'<span style="font-family:\'Segoe UI\',Arial,sans-serif; font-size:11px; '
        f'font-weight:600; color:#C7DBF5; letter-spacing:0.5px; text-transform:uppercase;">'
        f'{_esc(nombre_empresa)} · {_esc(departamento)}</span>'
    )
    html = patron_subtitulo.sub(subtitulo_nuevo, html, count=1)
    return html


def _inject_enviado_a(html: str, enviado_a_html: str) -> str:
    """Inyecta el bloque 'Enviado a' justo antes del pie del correo."""
    patron = re.compile(
        r'(\s*<!--\s*============\s*PIE DEL CORREO\s*============\s*-->)',
    )
    bloque = (
        f"\n        <!-- ============ ENVIADO A ============ -->\n"
        f"        <tr><td style=\"background-color:#FFFFFF; padding:0 32px 8px 32px;\" class=\"p-mobile\">\n"
        f"          <span style=\"font-family:'Segoe UI',Arial,sans-serif; font-size:11px; font-weight:700; color:#64748B; text-transform:uppercase; letter-spacing:0.5px;\">\n"
        f"            Distribucion de este informe\n"
        f"          </span>\n"
        f"          {enviado_a_html}\n"
        f"        </td></tr>"
        r"\1"
    )
    return patron.sub(bloque, html, count=1)


def _inject_firma(html: str, firma_html: str) -> str:
    """Inyecta el bloque de firma antes del pie del correo."""
    patron = re.compile(
        r'(\s*<!--\s*============\s*PIE DEL CORREO\s*============\s*-->)',
    )
    bloque = (
        f"\n        <!-- ============ FIRMA ============ -->"
        f"        <tr><td style=\"background-color:#FFFFFF; padding:8px 32px 16px 32px;\" class=\"p-mobile\">"
        f"          {firma_html}"
        f"        </td></tr>"
        r"\1"
    )
    return patron.sub(bloque, html, count=1)


__all__ = ("render_informe",)