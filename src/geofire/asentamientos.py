"""Asentamientos humanos de Ucayali desde OpenStreetMap (Overpass API) para la regla RN-02.1.

Datos (c) colaboradores de OpenStreetMap, licencia ODbL. No es el registro oficial de comunidades nativas
(BDPI del Ministerio de Cultura): puede estar incompleto.
"""
import time

import requests

from geofire.db import get_connection
from geofire.riesgo import CONFIG

BBOX = (-12.0, -75.95, -7.25, -70.45)  # sur, oeste, norte, este (igual que la geocerca de FIRMS)
SERVIDORES = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
TIPOS = "city|town|village|hamlet"
CUADRICULA = 3  # el area se pide en 3x3 tramos: una sola consulta grande suele dar 504


def _tramo(s, w, n, e, esperas=(6, 12, 24)):
    consulta = f'[out:json][timeout:90];node["place"~"^({TIPOS})$"]({s},{w},{n},{e});out body;'
    for intento in range(len(esperas) + 1):
        for url in SERVIDORES:
            try:
                r = requests.post(url, data={"data": consulta}, timeout=120,
                                  headers={"User-Agent": "GeoFire-Peru-academico/1.0"})
                if r.status_code == 200:
                    return r.json()["elements"]
            except requests.RequestException:
                pass
        if intento < len(esperas):
            time.sleep(esperas[intento])
    raise RuntimeError("Overpass no respondio; reintenta en unos minutos.")


def descargar():
    s0, w0, n0, e0 = BBOX
    nodos = {}
    for i in range(CUADRICULA):
        for j in range(CUADRICULA):
            s = s0 + (n0 - s0) * i / CUADRICULA
            n = s0 + (n0 - s0) * (i + 1) / CUADRICULA
            w = w0 + (e0 - w0) * j / CUADRICULA
            e = w0 + (e0 - w0) * (j + 1) / CUADRICULA
            for el in _tramo(round(s, 3), round(w, 3), round(n, 3), round(e, 3)):
                nodos[el["id"]] = el
    return list(nodos.values())


def cargar(nodos):
    """Reemplaza el contenido de la tabla. Devuelve cuantos quedaron dentro de la geocerca de Ucayali."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM asentamientos")
        for el in nodos:
            cur.execute(
                "INSERT INTO asentamientos (id, nombre, tipo, geom) "
                "VALUES (%s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326)) ON CONFLICT (id) DO NOTHING",
                (el["id"], el.get("tags", {}).get("name"), el["tags"]["place"], el["lon"], el["lat"]),
            )
        cur.execute(
            "DELETE FROM asentamientos a WHERE NOT EXISTS ("
            "SELECT 1 FROM zonas z WHERE z.tipo = 'geocerca' AND ST_Intersects(z.geom, a.geom))"
        )
        cur.execute("SELECT count(*) FROM asentamientos")
        return cur.fetchone()[0]


def distancias_km(cur, foco_ids, tipos=None):
    """Distancia (km) de cada foco al asentamiento mas cercano. {foco_id: km}. Vacio si no hay asentamientos.
    `tipos` limita los tipos considerados (por defecto los de config/riesgo.json)."""
    if not foco_ids:
        return {}
    tipos = list(tipos or CONFIG["tipos_asentamiento"])
    cur.execute(
        "SELECT f.id, d.km FROM focos_calor f CROSS JOIN LATERAL ("
        "  SELECT ST_Distance(f.geom::geography, a.geom::geography) / 1000 AS km "
        "  FROM asentamientos a WHERE a.tipo = ANY(%s) ORDER BY a.geom <-> f.geom LIMIT 1) d "
        "WHERE f.id = ANY(%s)",
        (tipos, list(foco_ids)),
    )
    return {fid: float(km) for fid, km in cur.fetchall()}
