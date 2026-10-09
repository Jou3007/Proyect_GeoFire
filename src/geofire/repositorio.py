"""Consultas a la base de datos para la interfaz web."""
import pandas as pd

from geofire.db import get_connection

NIVELES = ["CRITICO", "ALTO", "MEDIO", "BAJO"]
ESTADO_ETIQUETA = {
    "ACTIVA": "Pendiente",
    "CONFIRMADA": "Confirmada",
    "FALSA_ALARMA": "Falsa alarma",
    "REVISION_HISTORICA": "Histórica",
    "FUENTE_CONOCIDA": "Fuente conocida",
}

# Provincia y distrito de cada foco (union espacial con las zonas). `f` es focos_calor.
ZONA_JOIN = (
    "LEFT JOIN LATERAL (SELECT d.nombre AS distrito, p.nombre AS provincia FROM zonas d "
    "JOIN zonas p ON p.id = d.padre_id WHERE d.tipo = 'distrito' AND ST_Intersects(d.geom, f.geom) LIMIT 1) zz ON TRUE "
)
ZONA_FILTRO = "AND (%s::text IS NULL OR zz.provincia = %s) AND (%s::text IS NULL OR zz.distrito = %s) "
# Limita a lo que cae dentro de una zona asignada (guardaparque, AC-09.2)
ZONA_ID_FILTRO = "AND (%s::int IS NULL OR EXISTS (SELECT 1 FROM zonas zs WHERE zs.id = %s AND ST_Intersects(zs.geom, f.geom))) "


def _zona_params(provincia, distrito):
    return (provincia, provincia, distrito, distrito)


def _query(sql, params=()):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


def alertas(horas, niveles=None, provincia=None, distrito=None, zona_id=None):
    """Alertas con su foco dentro de la ventana de tiempo (horas), opcionalmente de una provincia o distrito."""
    return _query(
        "SELECT a.id, a.nivel, a.puntaje, a.estado, a.ndvi, a.ndwi, a.nbr, a.en_anp, "
        "f.fecha_hora, f.frp, f.confianza, f.fuente, ST_Y(f.geom) AS lat, ST_X(f.geom) AS lon, zz.provincia, zz.distrito "
        "FROM alertas a JOIN focos_calor f ON f.id = a.foco_id " + ZONA_JOIN +
        "WHERE f.fecha_hora >= now() - make_interval(hours => %s) AND a.nivel = ANY(%s) " + ZONA_FILTRO + ZONA_ID_FILTRO +
        "ORDER BY CASE a.nivel WHEN 'CRITICO' THEN 0 WHEN 'ALTO' THEN 1 WHEN 'MEDIO' THEN 2 ELSE 3 END, "
        "f.fecha_hora DESC",
        (horas, niveles or NIVELES, *_zona_params(provincia, distrito), zona_id, zona_id),
    )


def resumen(horas, provincia=None, distrito=None):
    df = _query(
        "SELECT a.nivel, count(*) AS n FROM alertas a JOIN focos_calor f ON f.id = a.foco_id " + ZONA_JOIN +
        "WHERE f.fecha_hora >= now() - make_interval(hours => %s) AND a.nivel IS NOT NULL " + ZONA_FILTRO + "GROUP BY 1",
        (horas, *_zona_params(provincia, distrito)),
    )
    conteo = {n: 0 for n in NIVELES}
    conteo.update(dict(zip(df["nivel"], df["n"])))
    return conteo


def por_provincia(horas):
    """Alertas Alto/Critico por provincia. 'Fuera de Ucayali' agrupa la franja de 5 km."""
    return _query(
        "SELECT COALESCE(zz.provincia, 'Franja de 5 km') AS provincia, "
        "count(*) FILTER (WHERE a.nivel = 'CRITICO') AS criticas, count(*) FILTER (WHERE a.nivel = 'ALTO') AS altas, "
        "count(*) AS total "
        "FROM alertas a JOIN focos_calor f ON f.id = a.foco_id " + ZONA_JOIN +
        "WHERE f.fecha_hora >= now() - make_interval(hours => %s) AND a.nivel IN ('ALTO', 'CRITICO') "
        "GROUP BY 1 ORDER BY criticas DESC, altas DESC",
        (horas,),
    )


def no_evaluables(horas):
    """Focos sin evaluar: {'AGUA': n, 'SIN_IMAGENES': n}. No son un quinto nivel de riesgo (AC-06.1)."""
    df = _query(
        "SELECT a.motivo, count(*) AS n FROM alertas a JOIN focos_calor f ON f.id = a.foco_id "
        "WHERE NOT a.evaluable AND f.fecha_hora >= now() - make_interval(hours => %s) GROUP BY 1",
        (horas,),
    )
    return dict(zip(df["motivo"], df["n"]))


def focos_en_periodo(desde, hasta, provincia=None, distrito=None, limite=5000, zona_id=None):
    """Focos entre dos instantes (linea de tiempo, RF-11). `nivel` es NULL si el foco no tiene evaluacion de riesgo."""
    return _query(
        "SELECT f.id, f.fecha_hora, f.frp, f.fuente, ST_Y(f.geom) AS lat, ST_X(f.geom) AS lon, a.nivel, zz.provincia, zz.distrito "
        "FROM focos_calor f LEFT JOIN alertas a ON a.foco_id = f.id " + ZONA_JOIN +
        "WHERE f.fecha_hora >= %s AND f.fecha_hora < %s " + ZONA_FILTRO + ZONA_ID_FILTRO + "ORDER BY f.fecha_hora DESC LIMIT %s",
        (desde, hasta, *_zona_params(provincia, distrito), zona_id, zona_id, limite),
    )


def rango_de_focos():
    """(primera, ultima) fecha de focos disponibles, como date."""
    df = _query("SELECT min(fecha_hora)::date AS desde, max(fecha_hora)::date AS hasta FROM focos_calor")
    return df["desde"].iloc[0], df["hasta"].iloc[0]


def provincias():
    return list(_query("SELECT nombre FROM zonas WHERE tipo = 'provincia' ORDER BY nombre")["nombre"])


def distritos(provincia=None):
    df = _query(
        "SELECT d.nombre FROM zonas d JOIN zonas p ON p.id = d.padre_id "
        "WHERE d.tipo = 'distrito' AND (%s::text IS NULL OR p.nombre = %s) ORDER BY d.nombre",
        (provincia, provincia),
    )
    return list(df["nombre"])


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
