"""Descarga los asentamientos de Ucayali desde OpenStreetMap y los carga en la base (tarda ~1 min).
Uso: python scripts/load_asentamientos.py
"""
from geofire.asentamientos import cargar, descargar

nodos = descargar()
print(f"Descargados de OpenStreetMap: {len(nodos)}")
print(f"Dentro de Ucayali (+5 km) y guardados: {cargar(nodos)}")
