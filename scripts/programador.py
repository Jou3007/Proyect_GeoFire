"""Programador local: repite el ciclo cada CICLO_MINUTOS (180 = 3 horas). Alternativa a GitHub Actions
mientras no haya base de datos en la nube. Requiere Docker Desktop encendido y el PC despierto.
"""
import os
import time
from datetime import datetime

from geofire.ciclo import ejecutar

intervalo = int(os.getenv("CICLO_MINUTOS", "180")) * 60
while True:
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] iniciando ciclo", flush=True)
    resumen = ejecutar()
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] ciclo terminado: {resumen['estado']}", flush=True)
    time.sleep(intervalo)
