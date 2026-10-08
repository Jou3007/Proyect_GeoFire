"""Validacion de la mascara de agua (HU-04, AC-04.1, AC-04.2).

La mascara del sistema es NDWI > umbral sobre un compuesto Sentinel-2 sin nubes. Se compara pixel a pixel con una
referencia independiente: JRC Global Surface Water (occurrence >= 50 % = agua permanente; occurrence = 0 = tierra
que nunca tuvo agua). Se mide:
  - excluidos_correctamente (AC-04.1): % de pixeles de agua de referencia que la mascara excluye. Meta: >= 95 %.
  - tierra_excluida_incorrectamente (AC-04.2): % de pixeles de tierra de referencia que la mascara marca como agua.
"""
import json
from datetime import date, timedelta

import ee

from geofire import gee_indices as gi
from geofire.db import get_connection

REFERENCIA = "JRC/GSW1_4/GlobalSurfaceWater"
RADAR_AGUA_DB = -18   # VV por debajo = agua en calma
RADAR_TIERRA_DB = -12  # VV por encima = tierra firme / vegetacion (la franja intermedia no se evalua)
OCURRENCIA_AGUA = 50  # % de meses con agua para considerar "agua permanente"
ESCALA_M = 30         # resolucion nativa del JRC

# Areas de evaluacion con rios y lagos grandes de Ucayali (oeste, sur, este, norte)
AREAS = {
    "Río Ucayali (Pucallpa)": (-74.62, -8.52, -74.40, -8.30),
    "Lago Yarinacocha": (-74.66, -8.40, -74.56, -8.30),
    "Río Urubamba (Atalaya)": (-73.85, -10.82, -73.62, -10.64),
    "Río Tambo (Atalaya)": (-73.80, -10.78, -73.60, -10.60),
    "Río Urubamba (Sepahua)": (-73.10, -11.25, -72.90, -11.05),
    "Río Aguaytía": (-75.50, -9.10, -75.30, -8.90),
}


MENSUAL = "JRC/GSW1_4/MonthlyHistory"
ANIOS_ESTACIONAL = (2019, 2021)  # ultimos anios publicados por JRC


def _referencia(corte, ventana_dias, modo):
    """(ref_agua, ref_tierra) como imagenes binarias.
    modo 'anual': ocurrencia >= 50 % (agua permanente) vs nunca hubo agua.
    modo 'estacional': mismos meses de los anios 2019-2021: agua si estuvo cubierta en >= 50 % de las observaciones
    (con al menos 2), tierra si nunca lo estuvo. Respeta la bajante de rios y lagos en la epoca seca."""
    if modo == "radar":
        # Referencia contemporanea e independiente del optico: retrodispersion VV de Sentinel-1 en los mismos 30 dias.
        # El agua en calma refleja muy poco hacia el satelite (VV muy bajo); la vegetacion y el suelo, mucho mas.
        radar = (ee.ImageCollection("COPERNICUS/S1_GRD")
                 .filterDate((corte - timedelta(days=ventana_dias)).isoformat(), (corte + timedelta(days=1)).isoformat())
                 .filter(ee.Filter.eq("instrumentMode", "IW"))
                 .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
                 .select("VV").median().focalMedian(1.5, "circle", "pixels"))  # quita el ruido de speckle
        return radar.lt(RADAR_AGUA_DB), radar.gt(RADAR_TIERRA_DB)
    if modo == "anual":
        gsw = ee.Image(REFERENCIA).select("occurrence").unmask(0)
        return gsw.gte(OCURRENCIA_AGUA), gsw.eq(0)
    meses = sorted({(corte - timedelta(days=d)).month for d in range(0, ventana_dias + 1, 5)})
    col = ee.ImageCollection(MENSUAL).filterDate(f"{ANIOS_ESTACIONAL[0]}-01-01", f"{ANIOS_ESTACIONAL[1] + 1}-01-01")         .filter(ee.Filter.calendarRange(meses[0], meses[-1], "month"))
    obs = col.map(lambda i: i.gt(0)).sum()      # meses con observacion
    agua = col.map(lambda i: i.eq(2)).sum()     # meses con agua
    ref_agua = obs.gte(2).And(agua.divide(obs).gte(0.5))
    ref_tierra = obs.gte(2).And(agua.eq(0))
    return ref_agua, ref_tierra


def metricas(umbral=None, ventana_dias=30, corte=None, areas=None, escala=ESCALA_M, indice="NDWI", referencia="estacional",
             regla=None, borde_px=0):
    """Compara la mascara <indice> > umbral con JRC GSW en cada area. Devuelve {area: {...}, 'TOTAL': {...}}."""
    areas = areas or AREAS
    corte = corte or date.today()
    umbral = gi.UMBRAL_AGUA if umbral is None else umbral
    gi.init()
    fc = ee.FeatureCollection([
        ee.Feature(ee.Geometry.Rectangle(list(c)), {"area": nombre}) for nombre, c in areas.items()
    ])
    region = fc.geometry().bounds()
    col = gi.collection_entre(region, corte - timedelta(days=ventana_dias), corte)
    comp = col.select(["NDVI", "NDWI", "MNDWI"]).median()
    nuestro_agua = regla(comp) if regla else comp.select(indice).gt(umbral)
    valido = comp.select("NDWI").mask()  # solo se evaluan pixeles con imagen valida (sin nubes)

    ref_agua, ref_tierra = _referencia(corte, ventana_dias, referencia)
    if borde_px:
        # Solo agua "interior": se descartan los pixeles a menos de borde_px de la orilla, donde se mezclan agua y
        # tierra y donde un cambio de cauce posterior a la referencia pesa mas. Lo mismo para la tierra.
        # (focalMin sobre un binario = erosion; el relleno con 0 evita el borde del dominio)
        k = ee.Kernel.square(borde_px, "pixels")
        ref_agua = ref_agua.unmask(0).focalMin(kernel=k)
        ref_tierra = ref_tierra.unmask(0).focalMin(kernel=k)

    unos = ee.Image.pixelArea().divide(1e6).rename("km2")  # area real de cada pixel
    bandas = ee.Image.cat([
        unos.updateMask(valido).updateMask(ref_agua).rename("ref_agua"),
        unos.updateMask(valido).updateMask(ref_agua).updateMask(nuestro_agua).rename("agua_excluida"),
        unos.updateMask(valido).updateMask(ref_tierra).rename("ref_tierra"),
        unos.updateMask(valido).updateMask(ref_tierra).updateMask(nuestro_agua).rename("tierra_excluida"),
        unos.updateMask(ref_agua).rename("ref_agua_total"),
    ])
    out = bandas.reduceRegions(fc, ee.Reducer.sum(), scale=escala, tileScale=4).getInfo()

    res, tot = {}, {k: 0.0 for k in ("ref_agua", "agua_excluida", "ref_tierra", "tierra_excluida", "ref_agua_total")}
    for f in out["features"]:
        p = f["properties"]
        fila = {k: float(p.get(k) or 0.0) for k in tot}
        for k in tot:
            tot[k] += fila[k]
        res[p["area"]] = _porcentajes(fila)
    res["TOTAL"] = _porcentajes(tot)
    return res


def _porcentajes(v):
    ref_agua, ref_tierra = v["ref_agua"], v["ref_tierra"]
    return {
        "agua_referencia_km2": round(ref_agua, 2),
        "agua_excluida_km2": round(v["agua_excluida"], 2),
        "excluidos_correctamente_pct": round(100 * v["agua_excluida"] / ref_agua, 1) if ref_agua else None,
        "tierra_referencia_km2": round(ref_tierra, 2),
        "tierra_excluida_km2": round(v["tierra_excluida"], 2),
        "tierra_excluida_incorrectamente_pct": round(100 * v["tierra_excluida"] / ref_tierra, 2) if ref_tierra else None,
        "agua_sin_imagen_valida_pct": round(100 * (1 - ref_agua / v["ref_agua_total"]), 1) if v["ref_agua_total"] else None,
    }


def barrido(indice="NDWI", umbrales=(-0.2, -0.1, 0.0), **kw):  # kw: referencia='anual'|'estacional'
    """Repite la comparacion con varios umbrales para elegir el mejor con criterio documentado."""
    return {u: metricas(umbral=u, indice=indice, **kw)["TOTAL"] for u in umbrales}


def guardar(resultado, umbral, ventana_dias, corte):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO validaciones_mascara (umbral_ndwi, ventana_dias, fecha_corte, referencia, ocurrencia_agua_pct, "
            "escala_m, resultado) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (umbral, ventana_dias, corte, REFERENCIA, OCURRENCIA_AGUA, ESCALA_M, json.dumps(resultado)),
        )
        return cur.fetchone()[0]
