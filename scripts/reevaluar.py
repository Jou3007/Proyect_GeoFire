"""Recalcula el nivel de riesgo de las alertas sin validar (sin tocar Earth Engine).
Uso: python scripts/reevaluar.py [horas]   (sin horas = todas)
"""
import sys

from geofire.alertas import reevaluar

print(reevaluar(int(sys.argv[1]) if len(sys.argv) > 1 else None))
