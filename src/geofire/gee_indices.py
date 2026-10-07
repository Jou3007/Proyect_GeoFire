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
    desde = hasta - timedelta(days=days)
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
