"""Evalua los focos recientes y guarda alertas. Uso: python scripts/procesar_alertas.py [horas]"""
import sys
import time

from geofire.alertas import procesar

horas = int(sys.argv[1]) if len(sys.argv) > 1 else 72
t0 = time.time()
n, resumen = procesar(horas)
print(f"Focos evaluados (ultimas {horas} h): {n}")
print(resumen)
print(f"Tiempo: {time.time() - t0:.1f} s")
