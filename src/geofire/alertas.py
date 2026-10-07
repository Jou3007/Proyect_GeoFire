"""Pipeline foco -> indices (Earth Engine) -> motor de riesgo -> alerta (HU-06)."""
from geofire import gee_indices as gi
from geofire.asentamientos import distancias_km
from geofire.db import get_connection
from geofire.riesgo import Contexto, Foco, evaluar

LOTE = 300
UMBRAL_AGUA_NDWI = 0.0  # HU-04: NDWI > 0 es agua (rio, cocha); no se evalua como vegetacion


def _focos_pendientes(cur, horas):
    cur.execute(
        "SELECT f.id, ST_X(f.geom), ST_Y(f.geom), f.frp, COALESCE(f.confianza, ''), "
        "EXTRACT(EPOCH FROM (now() - f.fecha_hora)) / 3600 "
        "FROM focos_calor f LEFT JOIN alertas a ON a.foco_id = f.id "
        "WHERE a.id IS NULL AND f.fecha_hora >= now() - make_interval(hours => %s) "
        "ORDER BY f.fecha_hora DESC",
        (horas,),
    )
    return cur.fetchall()


def procesar(horas=72):
    gi.init()
    resumen = {"BAJO": 0, "MEDIO": 0, "ALTO": 0, "CRITICO": 0, "agua": 0, "sin_indices": 0}
    with get_connection() as conn, conn.cursor() as cur:
        focos = _focos_pendientes(cur, horas)
        for i in range(0, len(focos), LOTE):
            lote = focos[i : i + LOTE]
            idx = gi.indices_para_puntos([(f[0], f[1], f[2]) for f in lote])
            dist = distancias_km(cur, [f[0] for f in lote])
            for fid, lon, lat, frp, conf, antig in lote:
                d = idx.get(fid, {})
                ndvi, ndwi = d.get("NDVI"), d.get("NDWI")
                if ndwi is not None and ndwi > UMBRAL_AGUA_NDWI:
                    resumen["agua"] += 1
                    continue
                if ndvi is None:
                    resumen["sin_indices"] += 1  # nubes: se reintenta en la proxima corrida
                    continue
                r = evaluar(
                    Foco(frp=float(frp or 0), confianza=conf, antiguedad_h=float(antig)),
                    Contexto(ndvi=ndvi, en_anp=d.get("en_anp", False), dist_comunidad_km=dist.get(fid)),
                )
                cur.execute(
                    "INSERT INTO alertas (foco_id, nivel, ndvi, ndwi, nbr, puntaje, reglas, estado, en_anp) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (foco_id) DO NOTHING",
                    (fid, r["nivel"], ndvi, ndwi, d.get("NBR"), r["puntaje"], r["reglas"], r["estado"], d.get("en_anp")),
                )
                resumen[r["nivel"]] += 1
    return len(focos), resumen


def reevaluar(horas=None):
    """Recalcula el nivel de las alertas aun sin validar con los datos ya guardados (NDVI, ANP) mas la
    distancia a asentamientos. No consulta Earth Engine. Si una alerta sube a CRITICO se marca para notificar.
    Devuelve {"revisadas": n, "cambiaron": n, "a_critico": n}."""
    filtro = "AND f.fecha_hora >= now() - make_interval(hours => %(h)s)" if horas else ""
    cambios = a_critico = 0
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT a.id, a.foco_id, a.nivel, a.ndvi, a.en_anp, f.frp, COALESCE(f.confianza, ''), "
            "EXTRACT(EPOCH FROM (now() - f.fecha_hora)) / 3600 "
            "FROM alertas a JOIN focos_calor f ON f.id = a.foco_id "
            f"WHERE a.estado IN ('ACTIVA', 'REVISION_HISTORICA') {filtro}",
            {"h": horas},
        )
        filas = cur.fetchall()
        dist = distancias_km(cur, [f[1] for f in filas])
        for aid, fid, nivel_antes, ndvi, en_anp, frp, conf, antig in filas:
            r = evaluar(
                Foco(frp=float(frp or 0), confianza=conf, antiguedad_h=float(antig)),
                Contexto(ndvi=ndvi, en_anp=bool(en_anp), dist_comunidad_km=dist.get(fid)),
            )
            if r["nivel"] == nivel_antes:
                continue
            cambios += 1
            sube = r["nivel"] == "CRITICO"
            a_critico += sube
            cur.execute(
                "UPDATE alertas SET nivel = %s, puntaje = %s, reglas = %s, estado = %s, "
                "notificada = CASE WHEN %s THEN FALSE ELSE notificada END WHERE id = %s",
                (r["nivel"], r["puntaje"], r["reglas"], r["estado"], sube, aid),
            )
    return {"revisadas": len(filas), "cambiaron": cambios, "a_critico": a_critico}
