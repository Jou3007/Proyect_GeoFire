"""Carga comunidades nativas (RAISG / IBC-SICNA) como asentamientos de tipo 'comunidad_nativa' dentro de la geocerca de Ucayali.
No borra los de OpenStreetMap; se puede repetir. Uso: python scripts/load_comunidades.py [archivo.geojson]
Fuente: servicio ArcGIS de RAISG, capa 'Comunidades Indigenas inscritas o por inscribir (Peru)' (datos IBC/SICNA)."""
import json
import sys
from pathlib import Path

from geofire.db import get_connection

RAIZ = Path(__file__).resolve().parents[1]
ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "data" / "comunidades_raisg_peru.geojson"
BASE_ID = 9_000_000_000_000  # no choca con los ids de OpenStreetMap
datos = json.loads(ruta.read_text(encoding="utf-8"))

with get_connection() as conn, conn.cursor() as cur:
    cur.execute("DELETE FROM asentamientos WHERE tipo = 'comunidad_nativa'")
    for i, f in enumerate(datos["features"]):
        lon, lat = f["geometry"]["coordinates"][:2]
        nombre = (f["properties"].get("nombre") or "").strip() or None
        cur.execute(
            "INSERT INTO asentamientos (id, nombre, tipo, fuente, geom) "
            "SELECT %s, %s, 'comunidad_nativa', 'RAISG/IBC', ST_SetSRID(ST_MakePoint(%s, %s), 4326) "
            "WHERE EXISTS (SELECT 1 FROM zonas z WHERE z.tipo = 'geocerca' AND ST_Intersects(z.geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326)))",
            (BASE_ID + i, nombre, lon, lat, lon, lat),
        )
    cur.execute("SELECT count(*) FROM asentamientos WHERE tipo = 'comunidad_nativa'")
    print(f"{len(datos['features'])} comunidades en el archivo; {cur.fetchone()[0]} dentro de la geocerca de Ucayali.")
