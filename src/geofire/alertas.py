"""Pipeline foco -> indices (Earth Engine) -> motor de riesgo -> alerta (HU-06).

Cada evaluacion conserva sus variables, la fecha de corte, la version de la configuracion y las imagenes usadas
(AC-03.1, AC-06.2). Si no hay imagenes validas el foco queda "No evaluable" (no es un quinto nivel de riesgo) y se
reintenta en el siguiente ciclo; si cae sobre agua se registra como excluido (AC-03.2, AC-04.2, AC-06.1).
"""
from geofire import gee_indices as gi
from geofire.asentamientos import distancias_km
from geofire.db import get_connection
from geofire.riesgo import CONFIG_VERSION, Contexto, Foco, evaluar

LOTE = 300
UMBRAL_AGUA_NDWI = 0.0  # HU-04: NDWI > 0 es agua (rio, cocha); no se evalua como vegetacion
MOTIVO_SIN_IMAGENES = "SIN_IMAGENES"
MOTIVO_AGUA = "AGUA"
ESTADO_NO_EVALUABLE = "NO_EVALUABLE"


def _focos_pendientes(cur, horas):
    """Focos sin evaluar, o que quedaron sin imagenes validas en un ciclo anterior (se reintentan)."""
    cur.execute(
        "SELECT f.id, ST_X(f.geom), ST_Y(f.geom), f.frp, COALESCE(f.confianza, ''), "
        "EXTRACT(EPOCH FROM (now() - f.fecha_hora)) / 3600 "
        "FROM focos_calor f LEFT JOIN alertas a ON a.foco_id = f.id "
        "WHERE (a.id IS NULL OR a.motivo = %s) AND f.fecha_hora >= now() - make_interval(hours => %s) "
        "ORDER BY f.fecha_hora DESC",
        (MOTIVO_SIN_IMAGENES, horas),
    )
    return cur.fetchall()


def _guardar_lote_imagenes(cur, meta):
    cur.execute(
        "INSERT INTO lotes_imagenes (coleccion, desde, hasta, imagenes) VALUES (%s, %s, %s, %s) RETURNING id",
        (meta["coleccion"], meta["desde"], meta["hasta"], meta["imagenes"]),
    )
    return cur.fetchone()[0]


def _guardar_no_evaluable(cur, fid, motivo, lote_id, ndwi=None):
    cur.execute(
        "INSERT INTO alertas (foco_id, nivel, ndwi, estado, evaluable, motivo, evaluada_en, fecha_corte, "
        "config_version, lote_imagenes_id) "
        "VALUES (%s, NULL, %s, %s, FALSE, %s, now(), now(), %s, %s) "
        "ON CONFLICT (foco_id) DO UPDATE SET motivo = EXCLUDED.motivo, evaluada_en = now(), fecha_corte = now(), "
        "lote_imagenes_id = EXCLUDED.lote_imagenes_id WHERE alertas.evaluable = FALSE",
        (fid, ndwi, ESTADO_NO_EVALUABLE, motivo, CONFIG_VERSION, lote_id),
    )


def procesar(horas=72):
    gi.init()
    resumen = {"BAJO": 0, "MEDIO": 0, "ALTO": 0, "CRITICO": 0, "agua": 0, "no_evaluables": 0}
    with get_connection() as conn, conn.cursor() as cur:
        focos = _focos_pendientes(cur, horas)
        for i in range(0, len(focos), LOTE):
            lote = focos[i: i + LOTE]
            idx, meta = gi.indices_para_puntos([(f[0], f[1], f[2]) for f in lote], con_meta=True)
            lote_id = _guardar_lote_imagenes(cur, meta)
            dist = distancias_km(cur, [f[0] for f in lote])
            for fid, lon, lat, frp, conf, antig in lote:
                d = idx.get(fid, {})
                ndvi, ndwi = d.get("NDVI"), d.get("NDWI")
                if ndwi is not None and ndwi > UMBRAL_AGUA_NDWI:
                    _guardar_no_evaluable(cur, fid, MOTIVO_AGUA, lote_id, ndwi)
                    resumen["agua"] += 1
                    continue
                if ndvi is None:  # nubes o sin cobertura: no se inventa un valor ni se asigna riesgo Bajo
                    _guardar_no_evaluable(cur, fid, MOTIVO_SIN_IMAGENES, lote_id)
                    resumen["no_evaluables"] += 1
                    continue
                r = evaluar(
                    Foco(frp=float(frp or 0), confianza=conf, antiguedad_h=float(antig)),
                    Contexto(ndvi=ndvi, en_anp=d.get("en_anp", False), dist_comunidad_km=dist.get(fid)),
                )
                cur.execute(
                    "INSERT INTO alertas (foco_id, nivel, ndvi, ndwi, nbr, puntaje, reglas, estado, en_anp, "
                    "evaluable, motivo, evaluada_en, fecha_corte, config_version, lote_imagenes_id) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, NULL, now(), now(), %s, %s) "
                    "ON CONFLICT (foco_id) DO UPDATE SET nivel = EXCLUDED.nivel, ndvi = EXCLUDED.ndvi, "
                    "ndwi = EXCLUDED.ndwi, nbr = EXCLUDED.nbr, puntaje = EXCLUDED.puntaje, reglas = EXCLUDED.reglas, "
                    "estado = EXCLUDED.estado, en_anp = EXCLUDED.en_anp, evaluable = TRUE, motivo = NULL, "
                    "evaluada_en = now(), fecha_corte = now(), config_version = EXCLUDED.config_version, "
                    "lote_imagenes_id = EXCLUDED.lote_imagenes_id WHERE alertas.evaluable = FALSE",
                    (fid, r["nivel"], ndvi, ndwi, d.get("NBR"), r["puntaje"], r["reglas"], r["estado"],
                     d.get("en_anp"), CONFIG_VERSION, lote_id),
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
            f"WHERE a.evaluable AND a.estado IN ('ACTIVA', 'REVISION_HISTORICA') {filtro}",
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
                "config_version = %s, reevaluada_en = now(), "
                "notificada = CASE WHEN %s THEN FALSE ELSE notificada END WHERE id = %s",
                (r["nivel"], r["puntaje"], r["reglas"], r["estado"], CONFIG_VERSION, sube, aid),
            )
    return {"revisadas": len(filas), "cambiaron": cambios, "a_critico": a_critico}
