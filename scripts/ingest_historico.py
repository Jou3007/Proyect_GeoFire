"""Carga historica de FIRMS por tramos de 5 dias (limite de la API).
Uso: python scripts/ingest_historico.py FUENTE INICIO FIN   (fechas AAAA-MM-DD)
Ej:  python scripts/ingest_historico.py VIIRS_SNPP_SP 2025-01-01 2026-06-30
"""
import sys
from datetime import date, timedelta

from geofire.firms import fetch_hotspots, save_hotspots

fuente, inicio, fin = sys.argv[1], date.fromisoformat(sys.argv[2]), date.fromisoformat(sys.argv[3])
total_desc = total_nuevos = 0
d = inicio
while d <= fin:
    dias = min(5, (fin - d).days + 1)
    df = fetch_hotspots(fuente, days=dias, fecha=d.isoformat())
    nuevos = save_hotspots(df, fuente)
    total_desc += len(df)
    total_nuevos += nuevos
    print(f"{d} +{dias}d: {len(df)} descargados, {nuevos} dentro de geocerca", flush=True)
    d += timedelta(days=dias)
print(f"TOTAL {fuente}: {total_desc} descargados, {total_nuevos} nuevos en la base")
