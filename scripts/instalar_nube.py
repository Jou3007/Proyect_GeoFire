"""Prepara una base PostgreSQL/PostGIS NUEVA (Neon, Supabase, ...) para GeoFire: esquema, limite de Ucayali, provincias y
distritos, asentamientos y fuentes de calor conocidas. Es idempotente: se puede repetir.

Uso:
  DATABASE_URL="postgresql://usuario:clave@host/db" python scripts/instalar_nube.py            # todo
  DATABASE_URL="..." python scripts/instalar_nube.py --sin-osm                                   # sin descargas de OpenStreetMap
Despues crea tu administrador:  DATABASE_URL="..." python scripts/crear_usuario.py
"""
import os
import subprocess
import sys
from pathlib import Path

from geofire.db import get_connection

RAIZ = Path(__file__).resolve().parents[1]

if not os.getenv("DATABASE_URL"):
    raise SystemExit("Falta DATABASE_URL (la cadena de conexion de tu base en la nube).")

print("1/5 Creando el esquema (db/init.sql)...", flush=True)
with get_connection() as conn, conn.cursor() as cur:
    cur.execute((RAIZ / "db" / "init.sql").read_text(encoding="utf-8"))
    cur.execute("SELECT PostGIS_Version()")
    print("    PostGIS", cur.fetchone()[0].split()[0])

pasos = [
    ("2/5 Cargando el limite de Ucayali y su franja de 5 km", "load_limite.py"),
    ("3/5 Cargando provincias y distritos", "load_zonas.py"),
]
if "--sin-osm" not in sys.argv:
    pasos += [
        ("4/5 Descargando asentamientos de OpenStreetMap (~1 min)", "load_asentamientos.py"),
        ("5/5 Descargando aserraderos y plantas de OpenStreetMap (~1 min)", "load_fuentes_conocidas.py"),
    ]
for titulo, script in pasos:
    print(titulo + "...", flush=True)
    r = subprocess.run([sys.executable, str(RAIZ / "scripts" / script)], cwd=RAIZ, env={**os.environ, "PYTHONPATH": str(RAIZ / "src")})
    if r.returncode:
        raise SystemExit(f"Fallo {script}. Revisa el mensaje de arriba y vuelve a ejecutar este script.")

print("\nListo. Siguientes pasos:")
print("  - Crea tu administrador:  python scripts/crear_usuario.py")
print("  - Trae focos y alertas:   python scripts/ciclo.py   (necesita NASA_FIRMS_MAP_KEY y GEE_PROJECT)")
