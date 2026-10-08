"""Exportacion en GeoJSON estandar (RFC 7946) para integrar con los SIG del MINAM o SERFOR (RNF-07)."""
import json
import math
from datetime import date, datetime

import pandas as pd


def _valor(v):
    if v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NaT:
        return None
    if isinstance(v, (datetime, date, pd.Timestamp)):
        return v.isoformat()
    if hasattr(v, "item"):  # numpy -> python
        return v.item()
    return v


def puntos(df, columnas, lon="lon", lat="lat"):
    """FeatureCollection de puntos. RFC 7946: las coordenadas van en orden [longitud, latitud]."""
    features = []
    for fila in df.to_dict("records"):
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(float(fila[lon]), 6), round(float(fila[lat]), 6)]},
            "properties": {c: _valor(fila.get(c)) for c in columnas},
        })
    return {"type": "FeatureCollection", "features": features}


def a_texto(fc):
    return json.dumps(fc, ensure_ascii=False)


def validar(fc):
    """Validador minimo de RFC 7946 para lo que exporta GeoFire (puntos y poligonos). Lanza ValueError si no es valido."""
    if fc.get("type") != "FeatureCollection" or not isinstance(fc.get("features"), list):
        raise ValueError("Debe ser una FeatureCollection con una lista 'features'.")
    for i, f in enumerate(fc["features"]):
        if f.get("type") != "Feature" or "geometry" not in f or "properties" not in f:
            raise ValueError(f"Feature {i}: faltan 'geometry' o 'properties'.")
        g = f["geometry"]
        if g["type"] == "Point":
            _posicion(g["coordinates"], i)
        elif g["type"] in ("Polygon", "MultiPolygon"):
            anillos = g["coordinates"] if g["type"] == "Polygon" else [a for p in g["coordinates"] for a in p]
            for anillo in anillos:
                if len(anillo) < 4 or anillo[0] != anillo[-1]:
                    raise ValueError(f"Feature {i}: anillo sin cerrar o con menos de 4 posiciones.")
                for pos in anillo:
                    _posicion(pos, i)
        else:
            raise ValueError(f"Feature {i}: tipo de geometria no soportado: {g['type']}.")
    return True


def _posicion(pos, i):
    if len(pos) < 2 or not all(isinstance(c, (int, float)) for c in pos[:2]):
        raise ValueError(f"Feature {i}: posicion no numerica.")
    lon, lat = pos[0], pos[1]
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise ValueError(f"Feature {i}: coordenadas fuera de rango (¿latitud y longitud invertidas?).")
