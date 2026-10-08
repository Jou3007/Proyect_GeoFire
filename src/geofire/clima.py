"""Viento actual en un punto (RF-09). NASA Worldview solo publica viento sobre oceanos, asi que se usa Open-Meteo
(gratuito, sin clave), que si lo ofrece sobre tierra."""
import requests

URL = "https://api.open-meteo.com/v1/forecast"
PUNTOS = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]


def rumbo(grados):
    """Direccion de la que SOPLA el viento -> punto cardinal."""
    return PUNTOS[int((grados % 360) / 45 + 0.5) % 8]


def viento(lat, lon, timeout=15):
    """{'velocidad_kmh', 'direccion_grados', 'rumbo', 'hora'} o None si el servicio no responde."""
    try:
        r = requests.get(
            URL, params={"latitude": lat, "longitude": lon, "current": "wind_speed_10m,wind_direction_10m",
                         "wind_speed_unit": "kmh", "timezone": "UTC"}, timeout=timeout)
        r.raise_for_status()
        c = r.json()["current"]
        return {"velocidad_kmh": c["wind_speed_10m"], "direccion_grados": c["wind_direction_10m"],
                "rumbo": rumbo(c["wind_direction_10m"]), "hora": c["time"]}
    except (requests.RequestException, KeyError, ValueError):
        return None
