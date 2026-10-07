"""Consultas a la base de datos para la interfaz web."""
import pandas as pd

from geofire.db import get_connection

NIVELES = ["CRITICO", "ALTO", "MEDIO", "BAJO"]
ESTADO_ETIQUETA = {
    "ACTIVA": "Pendiente",
    "CONFIRMADA": "Confirmada",
    "FALSA_ALARMA": "Falsa alarma",
    "REVISION_HISTORICA": "Historica",
}


def _query(sql, params=()):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


def alertas(horas, niveles=None):
    """Alertas con su foco dentro de la ventana de tiempo (horas)."""
    return _query(
        "SELECT a.id, a.nivel, a.puntaje, a.estado, a.ndvi, a.ndwi, a.nbr, a.en_anp, "
        "f.fecha_hora, f.frp, f.confianza, f.fuente, ST_Y(f.geom) AS lat, ST_X(f.geom) AS lon "
        "FROM alertas a JOIN focos_calor f ON f.id = a.foco_id "
        "WHERE f.fecha_hora >= now() - make_interval(hours => %s) AND a.nivel = ANY(%s) "
        "ORDER BY CASE a.nivel WHEN 'CRITICO' THEN 0 WHEN 'ALTO' THEN 1 WHEN 'MEDIO' THEN 2 ELSE 3 END, "
        "f.fecha_hora DESC",
        (horas, niveles or NIVELES),
    )


def resumen(horas):
    df = _query(
        "SELECT a.nivel, count(*) AS n FROM alertas a JOIN focos_calor f ON f.id = a.foco_id "
        "WHERE f.fecha_hora >= now() - make_interval(hours => %s) GROUP BY 1",
        (horas,),
    )
    conteo = {n: 0 for n in NIVELES}
    conteo.update(dict(zip(df["nivel"], df["n"])))
    return conteo


def focos_por_dia(dias=30):
    return _query(
        "SELECT (fecha_hora AT TIME ZONE 'America/Lima')::date AS dia, count(*) AS focos "
        "FROM focos_calor WHERE fecha_hora >= now() - make_interval(days => %s) "
        "GROUP BY 1 ORDER BY 1",
        (dias,),
    )


def totales():
    df = _query(
        "SELECT count(*) AS focos, min(fecha_hora) AS desde, max(fecha_hora) AS hasta FROM focos_calor"
    )
    return df.iloc[0]
