"""Registro de auditoria (RNF-08, AC-09.1): historial inmutable de las acciones criticas.

registrar() nunca interrumpe la accion que se esta auditando: si el log falla, lo informa por consola.
"""
import json

from geofire.db import get_connection
from geofire.repositorio import _query

# Eventos que se registran
LOGIN_OK = "LOGIN_OK"
LOGIN_FALLIDO = "LOGIN_FALLIDO"
CUENTA_BLOQUEADA = "CUENTA_BLOQUEADA"
LOGOUT = "LOGOUT"
USUARIO_CREADO = "USUARIO_CREADO"
USUARIO_DESBLOQUEADO = "USUARIO_DESBLOQUEADO"
USUARIO_ACTIVADO = "USUARIO_ACTIVADO"
USUARIO_DESACTIVADO = "USUARIO_DESACTIVADO"
PASSWORD_CAMBIADA = "PASSWORD_CAMBIADA"
ALERTA_VALIDADA = "ALERTA_VALIDADA"
CICLO = "CICLO"
ERROR_API = "ERROR_API"
CORREO_ENVIADO = "CORREO_ENVIADO"
CORREO_ERROR = "CORREO_ERROR"
ACCESO_DENEGADO = "ACCESO_DENEGADO"
ZONA_ASIGNADA = "ZONA_ASIGNADA"
GEOCERCA_ACTUALIZADA = "GEOCERCA_ACTUALIZADA"
FUENTES_CARGADAS = "FUENTES_CARGADAS"


def registrar(evento, usuario_id=None, email=None, detalle=None):
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO log_auditoria (evento, usuario_id, email, detalle) VALUES (%s, %s, %s, %s)",
                (evento, usuario_id, email, json.dumps(detalle, default=str) if detalle is not None else None),
            )
    except Exception as e:  # el log no debe romper el flujo principal
        print(f"[auditoria] no se pudo registrar {evento}: {e}")


def consultar(eventos=None, limite=200, desde=None):
    """Ultimos eventos (mas recientes primero). `eventos` filtra por tipo; `desde` es un datetime/fecha."""
    return _query(
        "SELECT id, fecha, evento, usuario_id, email, detalle FROM log_auditoria "
        "WHERE (%s::text[] IS NULL OR evento = ANY(%s)) AND (%s::timestamptz IS NULL OR fecha >= %s) "
        "ORDER BY id DESC LIMIT %s",
        (eventos, eventos, desde, desde, limite),
    )


def tipos():
    return _query("SELECT evento, count(*) AS n FROM log_auditoria GROUP BY 1 ORDER BY 2 DESC")
