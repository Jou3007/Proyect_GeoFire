"""Reportes PDF y CSV (HU-08). El CSV y el PDF salen del mismo objeto Reporte, asi los totales coinciden."""
import csv
import io
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from geofire.repositorio import ESTADO_ETIQUETA, NIVELES, _query

TITULO = "Reporte del prototipo académico GeoFire-Perú"
FUENTES = [
    "Focos de calor: NASA FIRMS (VIIRS S-NPP, VIIRS NOAA-20 y MODIS).",
    "Índices NDVI, NDWI y NBR: Sentinel-2 SR (Copernicus), procesados en Google Earth Engine.",
    "Áreas Naturales Protegidas: WDPA (UNEP-WCMC).",
    "Asentamientos y comunidades: © colaboradores de OpenStreetMap (licencia ODbL).",
    "Límite territorial: FAO GAUL 2015 (Ucayali) más una franja de 5 km.",
]
LIMITACIONES = [
    "Prototipo académico: no sustituye los reportes oficiales del SERFOR, GOREU ni INDECI.",
    "Los focos de calor son anomalías térmicas satelitales; no todos son incendios forestales (RN-03: requieren validación humana).",
    "El área afectada es una estimación del sistema con dNBR (umbral 0.27) en un radio de 500 m alrededor de cada foco; "
    "no es una medición oficial y puede subestimarse si hubo nubes o pocas imágenes Sentinel-2 en el periodo.",
    "No se incorporaron superficies reportadas por fuentes externas; el área de este documento es solo la estimada por el sistema.",
    "Las horas se expresan en UTC. Los umbrales del motor de riesgo son provisionales y se ajustan con backtesting.",
    "Los asentamientos provienen de OpenStreetMap, no del registro oficial de comunidades nativas (BDPI); pueden faltar comunidades. "
    "La mayoría de focos está a menos de 10 km de algún asentamiento (RN-02.1), por lo que la cercanía sola es poco discriminante.",
]


@dataclass
class Reporte:
    inicio: date
    fin: date
    niveles: list
    estados: list
    generado: datetime
    df: object
    total: int
    por_nivel: dict
    por_estado: dict
    area: Optional[dict] = None
    nota_area: str = ""
    no_evaluables: int = 0
    filas_omitidas_pdf: int = 0
    fuentes: list = field(default_factory=lambda: list(FUENTES))
    limitaciones: list = field(default_factory=lambda: list(LIMITACIONES))


def _codigo(fecha_hora, id_):
    return f"GF-{fecha_hora:%y%m%d}-{id_:04d}"


def construir(inicio: date, fin: date, niveles=None, estados=None, estimar_area=False) -> Reporte:
    niveles = list(niveles or NIVELES)
    estados = list(estados or ESTADO_ETIQUETA)
    df = _query(
        "SELECT a.id, a.nivel, a.puntaje, a.estado, a.ndvi, a.ndwi, a.nbr, a.en_anp, "
        "f.fecha_hora, f.frp, f.fuente, ST_Y(f.geom) AS lat, ST_X(f.geom) AS lon "
        "FROM alertas a JOIN focos_calor f ON f.id = a.foco_id "
        "WHERE f.fecha_hora >= %s AND f.fecha_hora < %s AND a.nivel = ANY(%s) AND a.estado = ANY(%s) "
        "ORDER BY f.fecha_hora DESC, a.id DESC",
        (inicio, fin + timedelta(days=1), niveles, estados),
    )
    if not df.empty:
        df["codigo"] = [_codigo(r.fecha_hora, r.id) for r in df.itertuples()]
        df["estado_txt"] = df["estado"].map(ESTADO_ETIQUETA)
    por_nivel = {n: int((df["nivel"] == n).sum()) for n in NIVELES} if not df.empty else {n: 0 for n in NIVELES}
    por_estado = (
        {ESTADO_ETIQUETA[e]: int((df["estado"] == e).sum()) for e in ESTADO_ETIQUETA} if not df.empty
        else {ESTADO_ETIQUETA[e]: 0 for e in ESTADO_ETIQUETA}
    )
    sin_eval = _query(
        "SELECT count(*) AS n FROM alertas a JOIN focos_calor f ON f.id = a.foco_id "
        "WHERE NOT a.evaluable AND f.fecha_hora >= %s AND f.fecha_hora < %s",
        (inicio, fin + timedelta(days=1)),
    )
    rep = Reporte(
        inicio=inicio, fin=fin, niveles=niveles, estados=estados, generado=datetime.now(timezone.utc),
        df=df, total=len(df), por_nivel=por_nivel, por_estado=por_estado, no_evaluables=int(sin_eval["n"].iloc[0]),
    )
    if estimar_area:
        rep.area, rep.nota_area = _estimar_area(df, inicio, fin)
    return rep


def _estimar_area(df, inicio, fin):
    if df.empty:
        return {"area_ha": 0.0, "region_ha": 0.0, "imagenes_previas": 0, "imagenes_posteriores": 0}, ""
    from geofire import gee_indices as gi

    try:
        gi.init()
        puntos = list(zip(df["lon"], df["lat"]))
        res = gi.area_quemada_ha(puntos, inicio, fin)
        nota = ""
        if len(puntos) > gi.MAX_PUNTOS_AREA:
            nota = f"Se analizaron los primeros {gi.MAX_PUNTOS_AREA} de {len(puntos)} focos."
        if res["imagenes_posteriores"] == 0:
            nota += " No hay imágenes Sentinel-2 posteriores al periodo todavía: el área no es confiable."
        elif res["imagenes_posteriores"] < 6:
            nota += (f" Solo hay {res['imagenes_posteriores']} imágenes Sentinel-2 posteriores al periodo "
                     "(poca cobertura por nubes o por ser reciente): el área es una estimación poco confiable.")
        return res, nota.strip()
    except Exception as e:  # sin red, sin credenciales de Earth Engine, etc.
        return None, f"No se pudo estimar el área con Earth Engine ({type(e).__name__})."


COLUMNAS_CSV = [
    ("codigo", "codigo"), ("nivel", "nivel_riesgo"), ("estado_txt", "estado"), ("fecha_hora", "detectado_utc"),
    ("lat", "latitud"), ("lon", "longitud"), ("frp", "frp_mw"), ("ndvi", "ndvi"), ("ndwi", "ndwi"),
    ("nbr", "nbr"), ("en_anp", "en_area_protegida"), ("puntaje", "puntaje"), ("fuente", "fuente_foco"),
]


def _resumen_texto(rep: Reporte):
    lineas = [
        TITULO,
        f"Generado (UTC): {rep.generado:%Y-%m-%d %H:%M}",
        f"Periodo consultado: {rep.inicio:%Y-%m-%d} a {rep.fin:%Y-%m-%d}",
        "Niveles: " + ", ".join(rep.niveles),
        "Estados: " + ", ".join(ESTADO_ETIQUETA[e] for e in rep.estados),
        f"Total de incidentes: {rep.total}",
        "Por nivel: " + ", ".join(f"{n}={rep.por_nivel[n]}" for n in NIVELES),
        "Por estado: " + ", ".join(f"{k}={v}" for k, v in rep.por_estado.items()),
        f"Focos no evaluables en el periodo (sobre agua o sin imágenes válidas; no son un nivel de riesgo): {rep.no_evaluables}",
    ]
    if rep.area is not None:
        lineas.append(
            f"Area afectada estimada por el sistema (dNBR): {rep.area['area_ha']} ha "
            f"de {rep.area['region_ha']} ha analizadas"
        )
    else:
        lineas.append("Area afectada: no estimada en este reporte")
    lineas.append("Fuentes: " + " | ".join(rep.fuentes))
    lineas.append("Limitaciones: " + " | ".join(rep.limitaciones))
    return lineas


def a_csv(rep: Reporte) -> bytes:
    """CSV con encabezado de metadatos (lineas que empiezan con #) y una fila por incidente."""
    buf = io.StringIO()
    for linea in _resumen_texto(rep):
        buf.write(f"# {linea}\n")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow([nombre for _, nombre in COLUMNAS_CSV])
    for r in rep.df.itertuples(index=False) if not rep.df.empty else []:
        d = r._asdict()
        w.writerow([
            f"{d[c]:%Y-%m-%d %H:%M}" if c == "fecha_hora" else
            (round(d[c], 5) if c in ("lat", "lon") else (round(d[c], 3) if isinstance(d[c], float) else d[c]))
            for c, _ in COLUMNAS_CSV
        ])
    return ("﻿" + buf.getvalue()).encode("utf-8")  # BOM: Excel abre bien las tildes


MAX_FILAS_PDF = 400


def a_pdf(rep: Reporte) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    verde, gris = colors.HexColor("#0f6b4f"), colors.HexColor("#6b7a72")
    color_nivel = {"CRITICO": "#d93025", "ALTO": "#f08a24", "MEDIO": "#e8b923", "BAJO": "#3f9d5b"}
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], textColor=verde, fontSize=19, alignment=0, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=verde, fontSize=12, spaceBefore=10, spaceAfter=4)
    txt = ParagraphStyle("t", parent=ss["BodyText"], fontSize=9, leading=12)
    chico = ParagraphStyle("c", parent=txt, fontSize=8, textColor=gris, leading=10)

    def pie(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(gris)
        canvas.drawString(1.8 * cm, 1.1 * cm, "Reporte del prototipo académico GeoFire-Perú · UTP · No es un documento oficial")
        canvas.drawRightString(A4[0] - 1.8 * cm, 1.1 * cm, f"Página {doc.page}")
        canvas.restoreState()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.6 * cm, bottomMargin=1.8 * cm,
        title=TITULO, author="GeoFire-Perú", pageCompression=0,
    )
    h = []
    h.append(Paragraph(TITULO, h1))
    h.append(Paragraph("Alerta temprana de incendios forestales · Región Ucayali", chico))
    h.append(Spacer(1, 6))
    meta = [
        ["Fecha de generación (UTC)", f"{rep.generado:%Y-%m-%d %H:%M}"],
        ["Periodo consultado", f"{rep.inicio:%Y-%m-%d} a {rep.fin:%Y-%m-%d}"],
        ["Niveles incluidos", ", ".join(rep.niveles)],
        ["Estados incluidos", ", ".join(ESTADO_ETIQUETA[e] for e in rep.estados)],
    ]
    t = Table(meta, colWidths=[5 * cm, 12.4 * cm])
    t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9), ("TEXTCOLOR", (0, 0), (0, -1), gris),
                           ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8e2"))]))
    h.append(t)

    h.append(Paragraph("Resumen", h2))
    h.append(Paragraph(f"<b>Total de incidentes: {rep.total}</b>", txt))
    filas = [["Nivel de riesgo"] + [n.capitalize() for n in NIVELES], ["Incidentes"] + [str(rep.por_nivel[n]) for n in NIVELES]]
    tn = Table(filas, colWidths=[4 * cm] + [3.3 * cm] * 4)
    estilo = [("FONTSIZE", (0, 0), (-1, -1), 9), ("ALIGN", (1, 0), (-1, -1), "CENTER"),
              ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f6f1")), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d5ddd5"))]
    for i, n in enumerate(NIVELES, start=1):
        estilo.append(("TEXTCOLOR", (i, 0), (i, 0), colors.HexColor(color_nivel[n])))
    tn.setStyle(TableStyle(estilo))
    h += [Spacer(1, 4), tn, Spacer(1, 6)]
    te = Table([list(rep.por_estado), [str(v) for v in rep.por_estado.values()]], colWidths=[4.35 * cm] * 4)
    te.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f6f1")),
                            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d5ddd5"))]))
    h.append(te)
    h.append(Paragraph(
        f"Focos no evaluables en el periodo (sobre agua o sin imágenes Sentinel-2 válidas; no son un nivel de riesgo): "
        f"{rep.no_evaluables}", chico))

    h.append(Paragraph("Área afectada", h2))
    if rep.area is not None:
        h.append(Paragraph(
            f"<b>Estimada por el sistema (dNBR con Sentinel-2): {rep.area['area_ha']:,} ha</b> "
            f"dentro de {rep.area['region_ha']:,} ha analizadas (radio de 500 m por foco). "
            f"Imágenes usadas: {rep.area['imagenes_previas']} previas y {rep.area['imagenes_posteriores']} posteriores.", txt))
        if rep.nota_area:
            h.append(Paragraph(f"Nota: {rep.nota_area}", chico))
    else:
        h.append(Paragraph("No se estimó el área en este reporte." + (f" {rep.nota_area}" if rep.nota_area else ""), txt))
    h.append(Paragraph("Reportada por fuentes externas: no incorporada en el prototipo.", chico))

    h.append(Paragraph("Fuentes de datos", h2))
    h += [Paragraph(f"• {f}", txt) for f in rep.fuentes]
    h.append(Paragraph("Limitaciones", h2))
    h += [Paragraph(f"• {texto}", txt) for texto in rep.limitaciones]

    h.append(Paragraph("Detalle de incidentes", h2))
    if rep.df.empty:
        h.append(Paragraph("No hay incidentes con los filtros seleccionados.", txt))
    else:
        vista = rep.df.head(MAX_FILAS_PDF)
        datos = [["ID", "Nivel", "Estado", "Detectado (UTC)", "Ubicación", "FRP", "NDVI"]]
        for r in vista.itertuples():
            datos.append([r.codigo, r.nivel.capitalize(), r.estado_txt, f"{r.fecha_hora:%Y-%m-%d %H:%M}",
                          f"{r.lat:.4f}, {r.lon:.4f}" + (" ANP" if r.en_anp else ""), f"{r.frp:g}", f"{r.ndvi:.2f}"])
        td = Table(datos, repeatRows=1, colWidths=[2.9 * cm, 1.7 * cm, 2.5 * cm, 3.2 * cm, 4.2 * cm, 1.4 * cm, 1.4 * cm])
        est = [("FONTSIZE", (0, 0), (-1, -1), 7.5), ("BACKGROUND", (0, 0), (-1, 0), verde),
               ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.2, colors.HexColor("#d5ddd5")),
               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7faf6")])]
        for i, r in enumerate(vista.itertuples(), start=1):
            est.append(("TEXTCOLOR", (1, i), (1, i), colors.HexColor(color_nivel[r.nivel])))
        td.setStyle(TableStyle(est))
        h.append(td)
        if len(rep.df) > MAX_FILAS_PDF:
            h.append(Paragraph(
                f"Se muestran {MAX_FILAS_PDF} de {len(rep.df)} incidentes. El CSV contiene todos los registros "
                f"y los totales de este reporte corresponden a los {len(rep.df)}.", chico))
    doc.build(h, onFirstPage=pie, onLaterPages=pie)
    return buf.getvalue()
