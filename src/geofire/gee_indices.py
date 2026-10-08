"""Indices espectrales sobre Sentinel-2 con Google Earth Engine (HU-03, HU-04, HU-08).

Las imagenes no se descargan: Earth Engine las procesa y solo vuelven los valores calculados.
"""
import json
import os
from datetime import date, timedelta

import ee
from dotenv import load_dotenv

from geofire.riesgo import CONFIG

load_dotenv()

S2 = "COPERNICUS/S2_SR_HARMONIZED"
# Pixeles con NDWI por encima de este valor se consideran agua y no vegetacion (HU-04). Validado en docs/validacion_mascara_agua.md
UMBRAL_AGUA = CONFIG["umbral_ndwi_agua"]

# Puntos de control (lon, lat)
ZONAS = {
    "sepahua": (-73.0, -11.14),
    "atalaya": (-73.76, -10.73),
    "pucallpa": (-74.55, -8.38),
}


def init():
    """Con GEE_SERVICE_ACCOUNT (JSON de la cuenta de servicio) funciona sin navegador, p. ej. en GitHub Actions.
    Sin esa variable usa la autenticacion de usuario (earthengine authenticate)."""
    cuenta = os.getenv("GEE_SERVICE_ACCOUNT")
    if cuenta:
        info = json.loads(cuenta)
        creds = ee.ServiceAccountCredentials(info["client_email"], key_data=cuenta)
        ee.Initialize(creds, project=os.environ["GEE_PROJECT"])
    else:
        ee.Initialize(project=os.environ["GEE_PROJECT"])


def _mask_clouds(img):
    """Quita nubes, sombras y cirros usando la banda SCL."""
    scl = img.select("SCL")
    ok = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
    return img.updateMask(ok)


def _add_indices(img):
    ndvi = img.normalizedDifference(["B8", "B4"]).rename("NDVI")
    ndwi = img.normalizedDifference(["B3", "B8"]).rename("NDWI")
    nbr = img.normalizedDifference(["B8", "B12"]).rename("NBR")
    mndwi = img.normalizedDifference(["B3", "B11"]).rename("MNDWI")  # agua con SWIR: mejor en rios turbios
    return img.addBands([ndvi, ndwi, nbr, mndwi])


def collection(region, days=30, hasta=None):
    hasta = hasta or date.today()
    return collection_entre(region, hasta - timedelta(days=days), hasta)


def collection_entre(region, desde, hasta):
    """Sentinel-2 sin nubes con NDVI/NDWI/NBR entre dos fechas (ambas incluidas)."""
    return (
        ee.ImageCollection(S2)
        .filterBounds(region)
        .filterDate(desde.isoformat(), (hasta + timedelta(days=1)).isoformat())
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 80))
        .map(_mask_clouds)
        .map(_add_indices)
    )


def stats_punto(lon, lat, radio_m=1000, days=30):
    """NDVI, NDWI y NBR medios alrededor de un punto (mediana temporal de la ventana)."""
    region = ee.Geometry.Point([lon, lat]).buffer(radio_m)
    col = collection(region, days)
    medios = (
        col.select(["NDVI", "NDWI", "NBR"])
        .median()
        .reduceRegion(ee.Reducer.mean(), region, scale=20, maxPixels=1e8)
    )
    res = ee.Dictionary(medios).set("imagenes", col.size()).getInfo()
    n = res.pop("imagenes")
    if n == 0:
        return {"imagenes": 0, "NDVI": None, "NDWI": None, "NBR": None}
    return {"imagenes": n, **{k: (round(v, 3) if v is not None else None) for k, v in res.items()}}


WDPA = "WCMC/WDPA/current/polygons"


def indices_para_puntos(puntos, radio_m=500, days=30, con_meta=False):
    """Indices medios y pertenencia a ANP para varios puntos en una sola consulta.

    puntos: lista de (id, lon, lat). Devuelve {id: {"NDVI", "NDWI", "NBR", "en_anp"}}.
    Con con_meta=True devuelve (resultado, meta) donde meta lista las imagenes Sentinel-2 usadas (AC-03.1):
    {"coleccion", "desde", "hasta", "imagenes": [id, ...]}.
    """
    if not puntos:
        return ({}, {"coleccion": S2, "desde": None, "hasta": None, "imagenes": []}) if con_meta else {}
    feats = [
        ee.Feature(ee.Geometry.Point([lon, lat]).buffer(radio_m), {"pid": pid})
        for pid, lon, lat in puntos
    ]
    fc = ee.FeatureCollection(feats)
    col = collection(fc.geometry().bounds(), days)
    img = col.select(["NDVI", "NDWI", "NBR"]).median()
    out = img.reduceRegions(fc, ee.Reducer.mean(), scale=20)

    anp = ee.FeatureCollection(WDPA).filter(ee.Filter.eq("ISO3", "PER")).filterBounds(fc.geometry().bounds())
    out = out.map(lambda f: f.set("en_anp", anp.filterBounds(f.geometry()).size().gt(0)))

    # Una sola consulta devuelve los valores por punto y los ids de las imagenes usadas.
    # (Una FeatureCollection dentro de un Dictionary solo devolveria sus metadatos: se pasa como lista.)
    info = ee.Dictionary({"features": out.toList(out.size()), "ids": col.aggregate_array("system:index")}).getInfo()
    res = {}
    for f in info["features"]:
        p = f["properties"]
        res[p["pid"]] = {
            "NDVI": p.get("NDVI"),
            "NDWI": p.get("NDWI"),
            "NBR": p.get("NBR"),
            "en_anp": bool(p.get("en_anp")),
        }
    if not con_meta:
        return res
    hasta = date.today()
    meta = {"coleccion": S2, "desde": hasta - timedelta(days=days), "hasta": hasta, "imagenes": sorted(info["ids"])}
    return res, meta


UMBRAL_DNBR = 0.27  # USGS: dNBR >= 0.27 = quemado de severidad moderada-baja o mayor
MAX_PUNTOS_AREA = 500


def area_quemada_ha(puntos, inicio, fin, radio_m=500):
    """Area quemada estimada con dNBR (NBR previo - NBR posterior) alrededor de los focos.

    puntos: lista de (lon, lat). inicio/fin: date del periodo del reporte.
    Previo = 30 dias antes del inicio. Posterior = desde el inicio hasta fin + 10 dias (sin pasar de hoy).
    Se usa la union de los buffers, asi que focos cercanos no se cuentan dos veces.
    """
    if not puntos:
        return {"area_ha": 0.0, "region_ha": 0.0, "imagenes_previas": 0, "imagenes_posteriores": 0}
    puntos = puntos[:MAX_PUNTOS_AREA]
    region = ee.Geometry.MultiPoint([[lon, lat] for lon, lat in puntos]).buffer(radio_m)

    hoy = date.today()
    post_fin = min(fin + timedelta(days=10), hoy)

    def compuesto(desde, hasta):
        col = collection_entre(region, desde, hasta)
        return col, col.select(["NBR", "NDWI"]).median()

    pre_col, pre = compuesto(inicio - timedelta(days=30), inicio - timedelta(days=1))
    post_col, post = compuesto(inicio, post_fin)

    quemado = (
        pre.select("NBR").subtract(post.select("NBR")).gt(UMBRAL_DNBR)
        .And(pre.select("NDWI").lt(UMBRAL_AGUA))  # no cuenta agua
        .rename("q")
    )
    r = (
        ee.Image.pixelArea().divide(10000).rename("ha")
        .addBands(quemado.multiply(ee.Image.pixelArea()).divide(10000).rename("quemado_ha"))
        .reduceRegion(ee.Reducer.sum(), region, scale=20, maxPixels=1e9)
    )
    out = ee.Dictionary({"r": r, "npre": pre_col.size(), "npost": post_col.size()}).getInfo()
    return {
        "area_ha": round(out["r"].get("quemado_ha") or 0.0, 1),
        "region_ha": round(out["r"].get("ha") or 0.0, 1),
        "imagenes_previas": out["npre"],
        "imagenes_posteriores": out["npost"],
    }


def compuesto_zonas(zonas, corte, ventana_dias=30, anios_base=3, umbral_estres=0.45, escala=100):
    """Estadisticas por zona SIN necesidad de focos (HU-03, AC-06.1): NDVI medio, % de vegetacion con estres,
    cobertura de imagen valida y NDVI historico (mismo periodo de los `anios_base` anios anteriores).

    zonas: lista de (id, geojson_geometry). Solo usa imagenes hasta la fecha de corte (AC-06.2).
    Devuelve ({zona_id: {...}}, meta) con meta = imagenes Sentinel-2 usadas (AC-03.1).
    """
    feats = [ee.Feature(ee.Geometry(g), {"zid": zid}) for zid, g in zonas]
    fc = ee.FeatureCollection(feats)
    region = fc.geometry().bounds()
    desde = corte - timedelta(days=ventana_dias)

    def compuesto(d, h):
        col = collection_entre(region, d, h)
        return col, col.select(["NDVI", "NDWI"]).median()

    col_actual, actual = compuesto(desde, corte)
    ndvi = actual.select("NDVI")
    tierra = actual.select("NDWI").lt(UMBRAL_AGUA)  # el agua no cuenta como vegetacion (HU-04)
    ndvi_tierra = ndvi.updateMask(tierra)
    bandas = [
        ndvi_tierra.rename("ndvi"),
        ndvi_tierra.lt(umbral_estres).rename("estres"),
        ndvi.mask().unmask(0).rename("valida"),  # fraccion de la zona con imagen valida
        tierra.unmask(0).rename("tierra_valida"),
    ]
    hist = []
    for k in range(1, anios_base + 1):
        d, h = desde - timedelta(days=365 * k), corte - timedelta(days=365 * k)
        _, c = compuesto(d, h)
        hist.append(c.select("NDVI").updateMask(c.select("NDWI").lt(UMBRAL_AGUA)))
    bandas.append(ee.ImageCollection(hist).mean().rename("ndvi_historico"))

    img = ee.Image.cat(bandas)
    out = img.reduceRegions(fc, ee.Reducer.mean(), scale=escala, tileScale=8)
    info = ee.Dictionary({"features": out.toList(out.size()), "ids": col_actual.aggregate_array("system:index")}).getInfo()
    res = {}
    for f in info["features"]:
        p = f["properties"]
        res[p["zid"]] = {k: p.get(k) for k in ("ndvi", "estres", "valida", "tierra_valida", "ndvi_historico")}
    meta = {"coleccion": S2, "desde": desde, "hasta": corte, "imagenes": sorted(info["ids"])}
    return res, meta


CAPAS = {  # nombre -> (descripcion, parametros de visualizacion)
    "NDVI": ("Vigor de la vegetación (NDVI)",
             {"min": 0.0, "max": 0.9, "palette": ["#a52a2a", "#e6c95c", "#9acd32", "#1a7a2e", "#0b4d1a"]}),
    "ESTRES": ("Estrés de la vegetación (NDVI bajo el umbral)", {"min": 0, "max": 1, "palette": ["#d93025"]}),
    "NBR": ("Severidad de quema (NBR)",
            {"min": -0.5, "max": 0.8, "palette": ["#7a0403", "#f08a24", "#f5e663", "#76b852", "#1a6b3a"]}),
}


def url_capa(capa, region_geojson, corte, ventana_dias=30, umbral_estres=0.45):
    """URL de teselas de Earth Engine para dibujar una capa tematica en el mapa (RF-08, RF-09).
    capa: 'NDVI', 'ESTRES' o 'NBR'. Se recorta a la region dada."""
    region = ee.Geometry(region_geojson)
    col = collection_entre(region, corte - timedelta(days=ventana_dias), corte)
    comp = col.select(["NDVI", "NDWI", "NBR"]).median().clip(region)
    tierra = comp.select("NDWI").lt(UMBRAL_AGUA)
    if capa == "NDVI":
        img = comp.select("NDVI").updateMask(tierra)
    elif capa == "ESTRES":
        img = comp.select("NDVI").updateMask(tierra).lt(umbral_estres).selfMask()
    elif capa == "NBR":
        img = comp.select("NBR").updateMask(tierra)
    else:
        raise ValueError(f"Capa desconocida: {capa}")
    return img.getMapId(CAPAS[capa][1])["tile_fetcher"].url_format
