"""Evaluacion de riesgo por zona (provincias y distritos), con o sin focos de calor (HU-03, AC-06.1, AC-06.2).

Cada evaluacion conserva sus variables, la fecha de corte, la version de la configuracion y las imagenes usadas.
Si la cobertura de imagenes validas es insuficiente la zona queda "No evaluable" (no es un quinto nivel de riesgo).
"""
import json
from datetime import date, datetime, time, timezone

from geofire import gee_indices as gi
from geofire.db import get_connection
from geofire.repositorio import _query
from geofire.riesgo import CONFIG, CONFIG_VERSION

NIVELES = ["BAJO", "MEDIO", "ALTO", "CRITICO"]
MOTIVO_COBERTURA = "COBERTURA_INSUFICIENTE"


def clasificar(ndvi_medio, ndvi_historico, pct_estres, focos_por_100km2, cfg=None):
    """Nivel de la zona segun puntos acumulados. Devuelve (nivel, reglas).
    +1 estres alto, +1 estres muy alto, +1 vegetacion mas seca de lo normal, +1 quemas ya activas en la zona."""
    c = (cfg or CONFIG)["zonas"]
    reglas, puntos = [], 0
    if pct_estres is not None and pct_estres >= c["estres_alto_pct"]:
        puntos += 1
        reglas.append("ZONA-ESTRES")
    if pct_estres is not None and pct_estres >= c["estres_critico_pct"]:
        puntos += 1
        reglas.append("ZONA-ESTRES-SEVERO")
    if ndvi_medio is not None and ndvi_historico is not None and ndvi_medio - ndvi_historico <= -c["anomalia_ndvi"]:
        puntos += 1
        reglas.append("ZONA-ANOMALIA-NDVI")
    if focos_por_100km2 is not None and focos_por_100km2 >= c["focos_por_100km2"]:
        puntos += 1
        reglas.append("ZONA-FOCOS-ACTIVOS")
    nivel = NIVELES[min(puntos, 3)]
    return nivel, reglas


def _zonas_a_evaluar(cur):
    cur.execute(
        "SELECT z.id, ST_AsGeoJSON(ST_SimplifyPreserveTopology(z.geom, 0.002)), "
        "ST_Area(z.geom::geography) / 1e6, "
        "(SELECT count(*) FROM focos_calor f WHERE f.fecha_hora >= now() - interval '30 days' AND ST_Intersects(z.geom, f.geom)) "
        "FROM zonas z WHERE z.tipo IN ('distrito', 'provincia') ORDER BY z.tipo DESC, z.id"
    )
    return cur.fetchall()


def evaluar_todas(corte: date = None, ventana_dias=None):
    """Evalua todos los distritos y provincias y guarda el resultado. Devuelve un resumen."""
    cfg = CONFIG["zonas"]
    ventana_dias = ventana_dias or cfg["ventana_dias"]
    corte = corte or date.today()
    gi.init()
    with get_connection() as conn, conn.cursor() as cur:
        zonas = _zonas_a_evaluar(cur)
        stats, meta = gi.compuesto_zonas(
            [(z[0], json.loads(z[1])) for z in zonas], corte, ventana_dias, cfg["anios_base"], CONFIG["umbral_ndvi_estres"],
        )
        cur.execute(
            "INSERT INTO lotes_imagenes (coleccion, desde, hasta, imagenes) VALUES (%s, %s, %s, %s) RETURNING id",
            (meta["coleccion"], meta["desde"], meta["hasta"], meta["imagenes"]),
        )
        lote = cur.fetchone()[0]
        fecha_corte = datetime.combine(corte, time(23, 59, 59), tzinfo=timezone.utc)
        resumen = {n: 0 for n in NIVELES}
        resumen["no_evaluables"] = 0
        for zid, _, area, focos in zonas:
            s = stats.get(zid, {})
            cobertura = (s.get("valida") or 0) * 100
            f100 = focos / area * 100 if area else None
            if cobertura < cfg["cobertura_minima_pct"] or s.get("ndvi") is None:
                nivel, reglas, evaluable, motivo = None, [], False, MOTIVO_COBERTURA
                resumen["no_evaluables"] += 1
            else:
                nivel, reglas = clasificar(s["ndvi"], s.get("ndvi_historico"), (s.get("estres") or 0) * 100, f100)
                evaluable, motivo = True, None
                resumen[nivel] += 1
            cur.execute(
                "INSERT INTO evaluaciones_zona (zona_id, fecha_corte, config_version, ventana_dias, evaluable, motivo, nivel, "
                "ndvi_medio, ndvi_historico, pct_estres, pct_cobertura, focos_30d, focos_por_100km2, area_km2, reglas, "
                "lote_imagenes_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (zid, fecha_corte, CONFIG_VERSION, ventana_dias, evaluable, motivo, nivel, s.get("ndvi"),
                 s.get("ndvi_historico"), (s.get("estres") or 0) * 100 if evaluable else None, cobertura, focos, f100,
                 area, reglas, lote),
            )
    resumen["zonas"] = len(zonas)
    resumen["imagenes"] = len(meta["imagenes"])
    return resumen


def ultimas(tipo=None):
    """Ultima evaluacion de cada zona."""
    return _query(
        "SELECT DISTINCT ON (z.id) z.id, z.nombre, z.tipo, p.nombre AS provincia, e.evaluada_en, e.fecha_corte, "
        "e.ventana_dias, e.evaluable, e.motivo, e.nivel, e.ndvi_medio, e.ndvi_historico, e.pct_estres, e.pct_cobertura, "
        "e.focos_30d, e.focos_por_100km2, e.area_km2, e.reglas, e.config_version, "
        "(SELECT array_length(l.imagenes, 1) FROM lotes_imagenes l WHERE l.id = e.lote_imagenes_id) AS imagenes "
        "FROM zonas z JOIN evaluaciones_zona e ON e.zona_id = z.id LEFT JOIN zonas p ON p.id = z.padre_id "
        "WHERE (%s::text IS NULL OR z.tipo = %s) ORDER BY z.id, e.evaluada_en DESC",
        (tipo, tipo),
    )


def historial(zona_id, limite=60):
    return _query(
        "SELECT evaluada_en, fecha_corte, nivel, evaluable, ndvi_medio, pct_estres, pct_cobertura FROM evaluaciones_zona "
        "WHERE zona_id = %s ORDER BY evaluada_en DESC LIMIT %s", (zona_id, limite),
    )


def geometria(zona_id):
    """Geometria GeoJSON de una zona (para recortar capas y centrar el mapa) y su caja [oeste, sur, este, norte]."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, 0.002)), ST_XMin(geom), ST_YMin(geom), ST_XMax(geom), "
            "ST_YMax(geom) FROM zonas WHERE id = %s", (zona_id,))
        g, w, s, e, n = cur.fetchone()
        return json.loads(g), (w, s, e, n)


def evaluar_si_toca(horas_minimas=20):
    """Para el ciclo automatico: reevalua las zonas solo si la ultima evaluacion tiene mas de `horas_minimas` horas."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT EXTRACT(EPOCH FROM (now() - max(evaluada_en))) / 3600 FROM evaluaciones_zona")
        horas = cur.fetchone()[0]
    if horas is not None and horas < horas_minimas:
        return f"vigente (hace {horas:.1f} h)"
    return evaluar_todas()


def geojson_con_niveles(tipo="distrito"):
    """FeatureCollection de las zonas con su ultimo nivel, para dibujarlas en el mapa."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT z.id, z.nombre, ST_AsGeoJSON(ST_SimplifyPreserveTopology(z.geom, 0.003)), e.nivel, e.evaluable, "
            "e.ndvi_medio, e.pct_estres, e.fecha_corte "
            "FROM zonas z LEFT JOIN LATERAL (SELECT * FROM evaluaciones_zona WHERE zona_id = z.id "
            "ORDER BY evaluada_en DESC LIMIT 1) e ON TRUE WHERE z.tipo = %s ORDER BY z.nombre", (tipo,))
        features = []
        for zid, nombre, geom, nivel, evaluable, ndvi, estres, corte in cur.fetchall():
            features.append({
                "type": "Feature", "geometry": json.loads(geom),
                "properties": {
                    "id": zid, "nombre": nombre, "nivel": nivel or ("NO_EVALUABLE" if evaluable is False else "SIN_EVALUAR"),
                    "ndvi": None if ndvi is None else round(ndvi, 2), "estres": None if estres is None else round(estres, 1),
                    "corte": None if corte is None else f"{corte:%Y-%m-%d}",
                },
            })
    return {"type": "FeatureCollection", "features": features}


def geometria_region():
    """Poligono (GeoJSON) y caja de toda la region Ucayali."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, 0.01)), ST_XMin(geom), ST_YMin(geom), ST_XMax(geom), "
            "ST_YMax(geom) FROM zonas WHERE tipo = 'region' LIMIT 1")
        g, w, s, e, n = cur.fetchone()
        return json.loads(g), (w, s, e, n)


def id_por_nombre(nombre, tipo):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM zonas WHERE nombre = %s AND tipo = %s ORDER BY id LIMIT 1", (nombre, tipo))
        fila = cur.fetchone()
        return fila[0] if fila else None
