"""Descarga e inserta focos de calor de NASA FIRMS. Uso: python scripts/ingest_firms.py [dias]"""
import sys

from geofire.firms import ingest

ingest(days=int(sys.argv[1]) if len(sys.argv) > 1 else 1)
