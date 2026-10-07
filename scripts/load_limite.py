"""Carga el limite de Ucayali y su geocerca de 5 km (RN-01) y limpia focos fuera de ella."""
import json

from geofire.db import get_connection

with open("data/ucayali.geojson", encoding="utf-8") as f:
    feature = json.load(f)
geom = json.dumps(feature["geometry"])

with get_connection() as conn, conn.cursor() as cur:
    cur.execute("DELETE FROM zonas WHERE tipo IN ('region', 'geocerca')")
    cur.execute(
        "INSERT INTO zonas (nombre, tipo, geom) VALUES "
        "('Ucayali', 'region', ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)))",
        (geom,),
    )
    cur.execute(
        "INSERT INTO zonas (nombre, tipo, geom) "
        "SELECT 'Ucayali + 5 km', 'geocerca', ST_Multi(ST_Buffer(geom::geography, 5000)::geometry) "
        "FROM zonas WHERE tipo = 'region'"
    )
    cur.execute(
        "DELETE FROM focos_calor f WHERE NOT EXISTS ("
        "SELECT 1 FROM zonas z WHERE z.tipo = 'geocerca' AND ST_Intersects(z.geom, f.geom))"
    )
    print("Focos fuera de la geocerca eliminados:", cur.rowcount)
    cur.execute("SELECT count(*) FROM focos_calor")
    print("Focos dentro de la geocerca:", cur.fetchone()[0])
