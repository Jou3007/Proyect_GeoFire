"""Indices espectrales sobre Sentinel-2 con Google Earth Engine (HU-03, HU-04, HU-08).

Las imagenes no se descargan: Earth Engine las procesa y solo vuelven los valores calculados.
"""
import os
from datetime import date, timedelta

import ee
from dotenv import load_dotenv

load_dotenv()

S2 = "COPERNICUS/S2_SR_HARMONIZED"

# Puntos de control (lon, lat)
ZONAS = {
    "sepahua": (-73.0, -11.14),
    "atalaya": (-73.76, -10.73),
    "pucallpa": (-74.55, -8.38),
}


def init():
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
    return img.addBands([ndvi, ndwi, nbr])


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


def indices_para_puntos(puntos, radio_m=500, days=30):
    """Indices medios y pertenencia a ANP para varios puntos en una sola consulta.

    puntos: lista de (id, lon, lat). Devuelve {id: {"NDVI", "NDWI", "NBR", "en_anp"}}.
    """
    if not puntos:
        return {}
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

    res = {}
    for f in out.getInfo()["features"]:
        p = f["properties"]
        res[p["pid"]] = {
            "NDVI": p.get("NDVI"),
            "NDWI": p.get("NDWI"),
            "NBR": p.get("NBR"),
            "en_anp": bool(p.get("en_anp")),
        }
    return res


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
        .And(pre.select("NDWI").lt(0))  # no cuenta agua
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
