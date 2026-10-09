"""Un ciclo completo: ingesta -> evaluacion -> correo. Lo lanza GitHub Actions cada 3 horas o el programador local.
Uso: python scripts/ciclo.py
"""
import json
import sys

from geofire.ciclo import ejecutar

detalle = ejecutar()
print(json.dumps(detalle, indent=2, ensure_ascii=False, default=str))
sys.exit(0 if detalle["estado"] != "ERROR" else 1)
