"""Carga provincias y distritos de Ucayali (GADM 4.1, edicion 2018) desde data/ucayali_distritos.geojson.
Las provincias se forman uniendo sus distritos, asi que ambos niveles coinciden exactamente.
Uso: python scripts/load_zonas.py
"""
import json
from pathlib import Path

from geofire.db import get_connection

ARCHIVO = Path(__file__).resolve().parents[1] / "data" / "ucayali_distritos.geojson"
NOMBRES = {  # GADM viene sin espacios ni tildes
    "CoronelPortillo": "Coronel Portillo", "PadreAbad": "Padre Abad", "NuevaRequena": "Nueva Requena",
    "Purus": "Purús", "Yurua": "Yurúa", "Callaria": "Callería", "Iparia": "Iparía", "Tahuania": "Tahuanía",
    "Curimana": "Curimaná",
}


def bonito(nombre):
    return NOMBRES.get(nombre, nombre)


gj = json.loads(ARCHIVO.read_text(encoding="utf-8"))
with get_connection() as conn, conn.cursor() as cur:
    cur.execute("DELETE FROM evaluaciones_zona")
    cur.execute("DELETE FROM zonas WHERE tipo IN ('distrito', 'provincia')")
    provincias = {}
    for f in gj["features"]:
        prov = bonito(f["properties"]["NAME_2"])
        if prov not in provincias:
            cur.execute(
                "INSERT INTO zonas (nombre, tipo, geom, codigo) VALUES (%s, 'provincia', "
                "ST_GeomFromText('MULTIPOLYGON EMPTY', 4326), %s) RETURNING id", (prov, prov.upper().replace(" ", "_")))
            provincias[prov] = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO zonas (nombre, tipo, geom, padre_id, codigo) VALUES (%s, 'distrito', "
            "ST_Multi(ST_MakeValid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))), %s, %s)",
            (bonito(f["properties"]["NAME_3"]), json.dumps(f["geometry"]), provincias[prov], f["properties"]["GID_3"]),
        )
    cur.execute(
        "UPDATE zonas p SET geom = (SELECT ST_Multi(ST_CollectionExtract(ST_Union(d.geom), 3)) FROM zonas d "
        "WHERE d.padre_id = p.id) WHERE p.tipo = 'provincia'"
    )
    cur.execute("SELECT p.nombre, count(d.id), round((ST_Area(p.geom::geography) / 1e6)::numeric) "
                "FROM zonas p LEFT JOIN zonas d ON d.padre_id = p.id WHERE p.tipo = 'provincia' GROUP BY p.id ORDER BY 3 DESC")
    for nombre, n, km2 in cur.fetchall():
        print(f"{nombre}: {n} distritos, {km2:,} km2")
