"""Backtesting (cap. XII, Sprint 6): ¿el NDVI de dias antes distingue donde luego hubo focos de calor?

Diseno (sin mirar hacia adelante): para cada foco historico (evento) se mide el NDVI en un compuesto Sentinel-2 de la
ventana [t - 45 d, t - 15 d], es decir, con 15 a 45 dias de anticipacion. Se compara contra dos grupos de control que NO
tuvieron focos a menos de 2 km en los 30 dias siguientes:
  - Control A (aleatorio): puntos al azar en Ucayali. Mide si el NDVI separa "terreno que arde" de "terreno que no".
    Es un criterio facil: la selva densa casi no arde y las zonas ya despejadas si.
  - Control B (vecino): puntos a 3-8 km del evento. Mismo entorno y uso de suelo: es la prueba mas exigente.
Metricas: AUC (probabilidad de que un evento tenga NDVI menor que un control), sensibilidad y tasa de falsas alarmas con el
umbral de estres del modelo (NDVI < umbral_ndvi_estres).
"""
import json
import random
from collections import defaultdict
from datetime import date, timedelta

import ee

from geofire import gee_indices as gi
from geofire.db import get_connection
from geofire.riesgo import CONFIG

ANTICIPACION_MIN, ANTICIPACION_MAX = 15, 45   # dias antes del evento
RADIO_M = 500
EXCLUSION_M = 2000    # un control no puede tener focos tan cerca...
HORIZONTE_DIAS = 30   # ...durante los 30 dias siguientes
VECINO_MIN_M, VECINO_MAX_M = 3000, 8000


def lunes(d: date) -> date:
    return d - timedelta(days=d.weekday())


def muestrear_eventos(n=500, desde="2025-03-01", hasta="2026-05-31", fuente="VIIRS_SNPP_SP", semilla=7):
    """Focos historicos dentro de Ucayali, repartidos al azar (con semilla fija: reproducible)."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT setseed(%s)", (semilla / 100,))
        cur.execute(
            "SELECT f.id, f.fecha_hora::date, ST_X(f.geom), ST_Y(f.geom) FROM focos_calor f "
            "WHERE f.fuente = %s AND f.fecha_hora >= %s AND f.fecha_hora < %s "
            "AND EXISTS (SELECT 1 FROM zonas z WHERE z.tipo = 'region' AND ST_Intersects(z.geom, f.geom)) "
            "ORDER BY random() LIMIT %s", (fuente, desde, hasta, n))
        return [{"id": i, "fecha": d, "lon": lon, "lat": lat} for i, d, lon, lat in cur.fetchall()]


def _sin_focos_cerca(cur, lon, lat, fecha):
    cur.execute(
        "SELECT NOT EXISTS (SELECT 1 FROM focos_calor f WHERE f.fecha_hora >= %s AND f.fecha_hora < %s "
        "AND ST_DWithin(f.geom::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s))",
        (fecha, fecha + timedelta(days=HORIZONTE_DIAS), lon, lat, EXCLUSION_M))
    return cur.fetchone()[0]


def controles(eventos, semilla=11):
    """Un control A (aleatorio) y un control B (vecino) por evento, con la fecha del evento."""
    rnd = random.Random(semilla)
    a, b = [], []
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT ST_XMin(geom), ST_YMin(geom), ST_XMax(geom), ST_YMax(geom) FROM zonas WHERE tipo = 'region'")
        w, s, e, n = cur.fetchone()
        for ev in eventos:
            for _ in range(60):  # control A: al azar dentro de la region
                lon, lat = rnd.uniform(w, e), rnd.uniform(s, n)
                cur.execute("SELECT ST_Intersects(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326)) FROM zonas WHERE tipo = 'region'", (lon, lat))
                if cur.fetchone()[0] and _sin_focos_cerca(cur, lon, lat, ev["fecha"]):
                    a.append({"fecha": ev["fecha"], "lon": lon, "lat": lat})
                    break
            for _ in range(60):  # control B: a 3-8 km del evento, en cualquier direccion
                cur.execute(
                    "SELECT ST_X(p), ST_Y(p) FROM (SELECT ST_Project(ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s, %s)::geometry AS p) q",
                    (ev["lon"], ev["lat"], rnd.uniform(VECINO_MIN_M, VECINO_MAX_M), rnd.uniform(0, 6.2832)))
                lon, lat = cur.fetchone()
                cur.execute("SELECT ST_Intersects(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326)) FROM zonas WHERE tipo = 'region'", (lon, lat))
                if cur.fetchone()[0] and _sin_focos_cerca(cur, lon, lat, ev["fecha"]):
                    b.append({"fecha": ev["fecha"], "lon": lon, "lat": lat})
                    break
    return a, b


def _consulta_semana(items, semana):
    """NDVI medio de varios puntos de una misma semana. {indice: valor | None}. Si Earth Engine falla (memoria,
    tiempo), divide el lote en mitades y reintenta; un punto aislado que falla queda sin dato."""
    try:
        fc = ee.FeatureCollection([ee.Feature(ee.Geometry.Point([p["lon"], p["lat"]]).buffer(RADIO_M), {"i": i}) for i, p in items])
        region = fc.geometry().bounds()
        col = gi.collection_entre(region, semana - timedelta(days=ANTICIPACION_MAX), semana - timedelta(days=ANTICIPACION_MIN))
        vacio = ee.Image.constant([0, 0]).rename(["NDVI", "NDWI"]).selfMask()  # semana sin imagenes: queda sin dato
        img = ee.Image(ee.Algorithms.If(col.size().gt(0), col.select(["NDVI", "NDWI"]).median(), vacio))
        tierra = img.select("NDWI").lt(gi.UMBRAL_AGUA)
        res = img.select("NDVI").updateMask(tierra).reduceRegions(fc, ee.Reducer.mean(), scale=20).getInfo()
        return {f["properties"]["i"]: f["properties"].get("mean") for f in res["features"]}
    except Exception:
        if len(items) == 1:
            return {items[0][0]: None}
        mitad = len(items) // 2
        return {**_consulta_semana(items[:mitad], semana), **_consulta_semana(items[mitad:], semana)}


def ndvi_previo(puntos, grupo, progreso=None):
    """NDVI medio (buffer de 500 m) con 15-45 dias de anticipacion. Devuelve lista de dicts con 'ndvi' (None si no hay dato)."""
    gi.init()
    por_semana = defaultdict(list)
    for i, p in enumerate(puntos):
        por_semana[lunes(p["fecha"])].append((i, p))
    out = [None] * len(puntos)
    for k, (semana, items) in enumerate(sorted(por_semana.items()), start=1):
        for i, v in _consulta_semana(items, semana).items():
            out[i] = v
        if progreso:
            progreso(grupo, k, len(por_semana))
    return [{**p, "ndvi": v, "grupo": grupo} for p, v in zip(puntos, out)]


def auc(eventos, controles_):
    """AUC = P(NDVI de un evento < NDVI de un control) (+ 0.5 por empates). 0.5 = azar, 1 = separa perfecto."""
    ev = [x for x in eventos if x is not None]
    co = [x for x in controles_ if x is not None]
    if not ev or not co:
        return None
    menor = sum((e < c) + 0.5 * (e == c) for e in ev for c in co)
    return menor / (len(ev) * len(co))


def metricas(eventos, controles_, umbral=None):
    umbral = CONFIG["umbral_ndvi_estres"] if umbral is None else umbral
    ev = [e["ndvi"] for e in eventos if e["ndvi"] is not None]
    co = [c["ndvi"] for c in controles_ if c["ndvi"] is not None]
    if not ev or not co:
        return None
    media = lambda xs: sum(xs) / len(xs)  # noqa: E731
    sens = sum(x < umbral for x in ev) / len(ev)
    fpr = sum(x < umbral for x in co) / len(co)
    return {
        "n_eventos": len(ev), "n_controles": len(co), "ndvi_eventos": round(media(ev), 3), "ndvi_controles": round(media(co), 3),
        "auc": round(auc(ev, co), 3), "sensibilidad_pct": round(100 * sens, 1), "falsas_alarmas_pct": round(100 * fpr, 1),
        "lift": round(sens / fpr, 2) if fpr else None, "umbral": umbral,
    }


def barrido_umbrales(eventos, controles_, umbrales=(0.5, 0.55, 0.6, 0.65, 0.7, 0.75)):
    return {u: metricas(eventos, controles_, u) for u in umbrales}


def guardar(resultado):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO backtesting (resultado) VALUES (%s) RETURNING id", (json.dumps(resultado, default=str),))
        return cur.fetchone()[0]
