"""Consulta NDVI/NDWI/NBR de una zona. Uso: python scripts/ndvi_zona.py [zona] [dias]"""
import sys
import time

from geofire import gee_indices as gi

zona = sys.argv[1] if len(sys.argv) > 1 else "sepahua"
dias = int(sys.argv[2]) if len(sys.argv) > 2 else 30

gi.init()
lon, lat = gi.ZONAS[zona]
t0 = time.time()
res = gi.stats_punto(lon, lat, days=dias)
print(f"Zona: {zona} ({lat}, {lon}) | ultimos {dias} dias")
print(res)
print(f"Tiempo de consulta: {time.time() - t0:.1f} s (criterio AC-03.1: < 5 s)")
