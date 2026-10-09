"""Prueba de conexion a PostgreSQL/PostGIS (AC-01.1)."""
from geofire.db import get_connection

with get_connection() as conn, conn.cursor() as cur:
    cur.execute("SELECT PostGIS_Version();")
    print("PostGIS OK, version:", cur.fetchone()[0])
    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' ORDER BY 1;"
    )
    print("Tablas:", [r[0] for r in cur.fetchall()])
