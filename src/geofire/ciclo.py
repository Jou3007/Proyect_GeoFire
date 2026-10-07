"""Ciclo automatico: ingesta FIRMS -> evaluacion de riesgo -> correo (cada 3 horas).

Si un paso falla se reintenta dos veces con espera creciente (cap. 11.6) y, si sigue fallando,
se registra el error y se continua con el siguiente paso en lugar de detener todo el ciclo.
"""
import json
import os
import time
import traceback
from datetime import datetime, timezone

from geofire.db import get_connection

ESPERAS = (5, 20)  # segundos antes del 2.o y del 3.er intento


def reintentar(fn, esperas=ESPERAS):
    """Ejecuta fn hasta 1 + len(esperas) veces. Devuelve (resultado, intentos). Propaga el ultimo error."""
    for intento in range(len(esperas) + 1):
        try:
            return fn(), intento + 1
        except Exception:
            if intento == len(esperas):
                raise
            time.sleep(esperas[intento])


def _pasos_por_defecto(horas_eval):
    from geofire.alertas import procesar
    from geofire.correo import enviar_alertas
    from geofire.firms import ingest

    def correo():
        if not os.getenv("SMTP_USER") or not os.getenv("ALERTA_DESTINATARIOS"):
            return "omitido (correo no configurado)"
        return enviar_alertas()

    return [
        ("ingesta", lambda: ingest(days=1)),
        ("evaluacion", lambda: procesar(horas_eval)),
        ("correo", correo),
    ]


def _registrar(inicio, fin, estado, detalle):
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ejecuciones (inicio, fin, estado, duracion_s, detalle) VALUES (%s, %s, %s, %s, %s)",
                (inicio, fin, estado, (fin - inicio).total_seconds(), json.dumps(detalle, default=str)),
            )
    except Exception as e:  # no se puede ni registrar: al menos queda en el log del job
        print(f"[ciclo] no se pudo registrar la ejecucion: {e}")


def ejecutar(pasos=None, esperas=ESPERAS, horas_eval=12):
    """Corre el ciclo completo. Devuelve el dict de detalle (estado = OK / PARCIAL / ERROR)."""
    pasos = pasos or _pasos_por_defecto(horas_eval)
    inicio = datetime.now(timezone.utc)
    detalle, fallos = {}, 0
    for nombre, fn in pasos:
        t0 = time.time()
        try:
            resultado, intentos = reintentar(fn, esperas)
            detalle[nombre] = {"ok": True, "resultado": resultado, "intentos": intentos, "segundos": round(time.time() - t0, 1)}
        except Exception as e:
            fallos += 1
            detalle[nombre] = {"ok": False, "error": f"{type(e).__name__}: {e}", "segundos": round(time.time() - t0, 1)}
            print(f"[ciclo] paso '{nombre}' fallo: {traceback.format_exc(limit=2)}")
    fin = datetime.now(timezone.utc)
    estado = "OK" if fallos == 0 else ("ERROR" if fallos == len(pasos) else "PARCIAL")
    detalle["estado"] = estado
    _registrar(inicio, fin, estado, detalle)
    return detalle


def ultima_ejecucion():
    """(fin, estado) del ultimo ciclo registrado, o None."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT fin, estado FROM ejecuciones ORDER BY inicio DESC LIMIT 1")
        return cur.fetchone()
