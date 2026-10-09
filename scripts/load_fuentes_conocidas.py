"""Descarga de OpenStreetMap aserraderos y plantas industriales de Ucayali (RN-04). Tarda ~1 min.
Uso: python scripts/load_fuentes_conocidas.py
"""
from geofire.fuentes_conocidas import cargar_osm, descargar_osm

elementos = descargar_osm()
print(f"Descargados de OpenStreetMap: {len(elementos)}")
print(f"En Ucayali (+5 km) y guardados: {cargar_osm(elementos)}")
