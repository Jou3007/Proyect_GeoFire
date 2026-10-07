"""Pipeline foco -> indices (Earth Engine) -> motor de riesgo -> alerta (HU-06)."""
from geofire import gee_indices as gi
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
                    Contexto(ndvi=ndvi, en_anp=d.get("en_anp", False)),
                )
                cur.execute(
                    "INSERT INTO alertas (foco_id, nivel, ndvi, ndwi, nbr, puntaje, reglas, estado, en_anp) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (foco_id) DO NOTHING",
                    (fid, r["nivel"], ndvi, ndwi, d.get("NBR"), r["puntaje"], r["reglas"], r["estado"], d.get("en_anp")),
                )
                resumen[r["nivel"]] += 1
    return len(focos), resumen
