"""Prueba de conexion a Google Earth Engine (AC-01.1)."""
import os

import ee
from dotenv import load_dotenv

load_dotenv()
project = os.getenv("GEE_PROJECT")
if not project:
    raise SystemExit("Falta GEE_PROJECT en .env")

ee.Initialize(project=project)
img = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").first().select("B8")
print("Earth Engine OK, proyecto:", project, "| banda:", img.bandNames().getInfo())
