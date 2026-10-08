"""Fuentes de calor conocidas (RN-04): aserraderos, plantas industriales, etc.

Un foco a menos de `radio_m` de una de ellas se etiqueta como "Fuente de calor conocida" y no entra al flujo de alertas
criticas, salvo que su intensidad (FRP) supere el umbral historico (p90).
"""
import time

import requests

from geofire.asentamientos import BBOX, CUADRICULA, SERVIDORES
from geofire.db import get_connection

# Etiquetas de OpenStreetMap que se consideran fuentes de calor industriales
CONSULTA = (
    'nwr["industrial"~"^(sawmill|oil|gas|wood|timber)$"]({b});'
    'nwr["craft"="sawmill"]({b});'
    'nwr["man_made"="works"]({b});'
    'nwr["power"="plant"]["plant:source"~"oil|gas|diesel|biomass|wood"]({b});'
)
TIPOS_VALIDOS = ("aserradero", "hidrocarburos", "planta", "otro")


def _tipo_osm(tags):
    if tags.get("industrial") in ("sawmill", "wood", "timber") or tags.get("craft") == "sawmill":
        return "aserradero"
    if tags.get("industrial") in ("oil", "gas"):
        return "hidrocarburos"
    return "planta"


def _tramo(caja, esperas=(6, 12, 24)):
    s, w, n, e = caja
    consulta = f"[out:json][timeout:90];({CONSULTA.format(b=f'{s},{w},{n},{e}')});out center tags;"
    for intento in range(len(esperas) + 1):
        for url in SERVIDORES:
            try:
                r = requests.post(url, data={"data": consulta}, timeout=120, headers={"User-Agent": "GeoFire-Peru-academico/1.0"})
                if r.status_code == 200:
                    return r.json()["elements"]
            except requests.RequestException:
                pass
        if intento < len(esperas):
            time.sleep(esperas[intento])
    raise RuntimeError("Overpass no respondio; reintenta en unos minutos.")


def descargar_osm():
    s0, w0, n0, e0 = BBOX
    elementos = {}
    for i in range(CUADRICULA):
        for j in range(CUADRICULA):
            caja = (round(s0 + (n0 - s0) * i / CUADRICULA, 3), round(w0 + (e0 - w0) * j / CUADRICULA, 3),
                    round(s0 + (n0 - s0) * (i + 1) / CUADRICULA, 3), round(w0 + (e0 - w0) * (j + 1) / CUADRICULA, 3))
            for el in _tramo(caja):
                elementos[(el["type"], el["id"])] = el
    return list(elementos.values())


def cargar_osm(elementos):
    """Reemplaza las fuentes de OpenStreetMap (las cargadas a mano se conservan). Devuelve cuantas quedaron en Ucayali."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM fuentes_calor_conocidas WHERE fuente = 'OpenStreetMap'")
        for el in elementos:
            lat = el.get("lat") or el.get("center", {}).get("lat")
            lon = el.get("lon") or el.get("center", {}).get("lon")
            if lat is None or lon is None:
                continue
            tags = el.get("tags", {})
            osm_id = el["id"] * 10 + {"node": 1, "way": 2, "relation": 3}[el["type"]]  # id unico entre tipos
            cur.execute(
                "INSERT INTO fuentes_calor_conocidas (nombre, tipo, fuente, osm_id, geom) "
                "VALUES (%s, %s, 'OpenStreetMap', %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326)) ON CONFLICT DO NOTHING",
                (tags.get("name"), _tipo_osm(tags), osm_id, lon, lat),
            )
        cur.execute(
            "DELETE FROM fuentes_calor_conocidas f WHERE f.fuente = 'OpenStreetMap' AND NOT EXISTS ("
            "SELECT 1 FROM zonas z WHERE z.tipo = 'geocerca' AND ST_Intersects(z.geom, f.geom))"
        )
        cur.execute("SELECT count(*) FROM fuentes_calor_conocidas WHERE fuente = 'OpenStreetMap'")
        return cur.fetchone()[0]


def agregar(nombre, tipo, lon, lat, radio_m=300, fuente="carga manual"):
    if tipo not in TIPOS_VALIDOS:
        raise ValueError("Tipo no válido.")
    if not (-76 <= lon <= -70 and -12.5 <= lat <= -7):
        raise ValueError("Las coordenadas están fuera de Ucayali.")
    if not (50 <= radio_m <= 5000):
        raise ValueError("El radio debe estar entre 50 y 5000 m.")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO fuentes_calor_conocidas (nombre, tipo, fuente, radio_m, geom) "
            "VALUES (%s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326)) RETURNING id",
            ((nombre or "").strip() or None, tipo, fuente, int(radio_m), lon, lat),
        )
        return cur.fetchone()[0]


def cerca_de_fuente(cur, foco_ids):
    """Conjunto de focos que estan a menos de radio_m de una fuente conocida (RN-04)."""
    if not foco_ids:
        return set()
    cur.execute(
        "SELECT DISTINCT f.id FROM focos_calor f JOIN fuentes_calor_conocidas k "
        "ON ST_DWithin(f.geom::geography, k.geom::geography, k.radio_m) WHERE f.id = ANY(%s)",
        (list(foco_ids),),
    )
    return {r[0] for r in cur.fetchall()}
