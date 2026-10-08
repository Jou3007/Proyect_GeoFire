"""Chequeo de salud: ¿funcionan la base, Earth Engine, NASA FIRMS, el correo y el ciclo automatico? No envia nada.
Uso: python scripts/salud.py      (sale con codigo 1 si algo falla)
"""
import os
import smtplib
import sys
import time

import requests

from geofire.db import get_connection

resultados = []


def revisar(nombre, fn):
    t0 = time.time()
    try:
        detalle = fn()
        resultados.append((nombre, True, f"{detalle} ({time.time() - t0:.1f} s)"))
    except Exception as e:
        resultados.append((nombre, False, f"{type(e).__name__}: {str(e)[:120]}"))


def base():
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT PostGIS_Version()")
        version = cur.fetchone()[0].split()[0]
        cur.execute("SELECT (SELECT count(*) FROM focos_calor), (SELECT count(*) FROM alertas), (SELECT count(*) FROM zonas)")
        focos, alertas, zonas = cur.fetchone()
    return f"PostGIS {version}; {focos:,} focos, {alertas:,} alertas, {zonas} zonas"


def earth_engine():
    import ee

    from geofire import gee_indices as gi
    gi.init()
    return f"conectado al proyecto {os.environ['GEE_PROJECT']} (pruebo: {ee.Number(2).add(2).getInfo()})"


def firms():
    clave = os.environ["NASA_FIRMS_MAP_KEY"]
    r = requests.get(f"https://firms.modaps.eosdis.nasa.gov/mapserver/mapkey_status/?MAP_KEY={clave}", timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    return "clave valida"


def correo():
    if not os.getenv("SMTP_USER"):
        return "no configurado (se omite)"
    with smtplib.SMTP(os.getenv("SMTP_HOST", "smtp.gmail.com"), int(os.getenv("SMTP_PORT", "587")), timeout=30) as s:
        s.starttls()
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
    return "inicio de sesion SMTP correcto (no se envio nada)"


def ciclo():
    from geofire import ciclo as c
    ultima = c.ultima_ejecucion()
    if not ultima:
        raise RuntimeError("aun no hay ciclos registrados")
    from datetime import datetime, timezone
    horas = (datetime.now(timezone.utc) - ultima[0]).total_seconds() / 3600
    if ultima[1] != "OK" or horas > 4:
        raise RuntimeError(f"ultimo ciclo: {ultima[1]} hace {horas:.1f} h")
    return f"ultimo ciclo OK hace {horas:.1f} h"


for nombre, fn in (("Base de datos", base), ("Earth Engine", earth_engine), ("NASA FIRMS", firms), ("Correo", correo), ("Ciclo automatico", ciclo)):
    revisar(nombre, fn)
for nombre, ok, detalle in resultados:
    print(f"[{'OK' if ok else 'FALLA'}] {nombre}: {detalle}")
sys.exit(0 if all(ok for _, ok, _ in resultados) else 1)
