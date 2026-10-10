"""Ingesta de focos de calor de NASA FIRMS para Ucayali (HU-02)."""
import io
import os

import pandas as pd
import requests
from dotenv import load_dotenv

from geofire.db import get_connection

load_dotenv()

FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{source}/{bbox}/{days}"

# Caja aproximada de Ucayali + franja de ~5 km (RN-01). west, south, east, north.
# TODO: reemplazar por el limite oficial (GeoJSON) cuando se tenga.
UCAYALI_BBOX = (-75.95, -12.00, -70.45, -7.25)

SOURCES = ("VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "MODIS_NRT")


def fetch_hotspots(source, days=1, bbox=UCAYALI_BBOX, fecha=None):
    key = os.getenv("NASA_FIRMS_MAP_KEY")
    if not key:
        raise RuntimeError("Falta NASA_FIRMS_MAP_KEY en .env")
    url = FIRMS_URL.format(
        key=key, source=source, bbox=",".join(str(c) for c in bbox), days=days
    )
    if fecha:
        url += f"/{fecha}"  # AAAA-MM-DD: inicio del rango (historico)
    resp = requests.get(url, timeout=60)
    if resp.status_code != 200:
        # No se imprime la URL: contiene la clave.
        raise RuntimeError(f"FIRMS {source}: HTTP {resp.status_code}")
    text = resp.text.strip()
    if not text.startswith("latitude"):
        raise RuntimeError(f"FIRMS {source}: respuesta inesperada: {text[:120]}")
    return pd.read_csv(io.StringIO(text), dtype={"acq_time": str, "confidence": str})


def save_hotspots(df, source):
    """Inserta los focos en focos_calor. Devuelve cuantos eran nuevos."""
    if df.empty:
        return 0
    rows = []
    for r in df.itertuples():
        fecha_hora = f"{r.acq_date} {r.acq_time.zfill(4)[:2]}:{r.acq_time.zfill(4)[2:]}+00"
        rows.append((source, fecha_hora, float(r.frp), str(r.confidence),
                     float(r.longitude), float(r.latitude)))
    sql = (
        "INSERT INTO focos_calor (fuente, fecha_hora, frp, confianza, geom) "
        "SELECT %s, %s, %s, %s, p.geom FROM "
        "(SELECT ST_SetSRID(ST_MakePoint(%s, %s), 4326) AS geom) p "
        "WHERE EXISTS (SELECT 1 FROM zonas z WHERE z.tipo = 'geocerca' "
        "AND ST_Intersects(z.geom, p.geom)) "  # RN-01: solo dentro de Ucayali + 5 km
        "ON CONFLICT DO NOTHING"
    )
    inserted = 0
    with get_connection() as conn, conn.cursor() as cur:
        for row in rows:
            cur.execute(sql, row)
            inserted += cur.rowcount
    return inserted


def ingest(days=3):
    """Descarga las 3 fuentes. Devuelve el total de focos nuevos dentro de la geocerca."""
    total = 0
    for source in SOURCES:
        df = fetch_hotspots(source, days=days)
        nuevos = save_hotspots(df, source)
        total += nuevos
        print(f"{source}: {len(df)} descargados, {nuevos} nuevos")
    return total
