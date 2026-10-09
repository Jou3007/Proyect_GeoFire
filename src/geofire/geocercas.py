"""Administracion de geocercas y fuentes de calor conocidas (flujo del administrador, cap. IX).

Flujo del limite regional: subir GeoJSON -> validar poligono (topologia, area razonable) -> reemplazar el limite de Ucayali
y su franja de 5 km (RN-01). Un archivo con topologia invalida se rechaza y no cambia nada.
"""
import csv
import io
import json

from geofire import auditoria
from geofire.db import get_connection
from geofire.fuentes_conocidas import TIPOS_VALIDOS, agregar

AREA_MIN_KM2, AREA_MAX_KM2 = 50_000, 200_000  # Ucayali tiene ~102,000 km2: evita subir por error otra region
MAX_BYTES = 10 * 1024 * 1024


def _geometrias(obj):
    """Lista de geometrias (dict GeoJSON) de un Feature, FeatureCollection o Geometry."""
    tipo = obj.get("type")
    if tipo == "FeatureCollection":
        return [f["geometry"] for f in obj.get("features", []) if f.get("geometry")]
    if tipo == "Feature":
        return [obj["geometry"]] if obj.get("geometry") else []
    if tipo in ("Polygon", "MultiPolygon", "Point", "MultiPoint"):
        return [obj]
    return []


def validar_geojson(texto):
    """Valida un archivo GeoJSON de poligonos. Devuelve (geometria_multipoligono_geojson, area_km2).
    Lanza ValueError con un mensaje claro si no es valido (el flujo muestra 'Topologia invalida')."""
    if isinstance(texto, bytes):
        if len(texto) > MAX_BYTES:
            raise ValueError("El archivo supera 10 MB.")
        texto = texto.decode("utf-8-sig", errors="replace")
    try:
        obj = json.loads(texto)
    except ValueError:
        raise ValueError("El archivo no es un GeoJSON válido.") from None
    geoms = [g for g in _geometrias(obj) if g.get("type") in ("Polygon", "MultiPolygon")]
    if not geoms:
        raise ValueError("El GeoJSON no contiene polígonos.")
    with get_connection() as conn, conn.cursor() as cur:
        for g in geoms:
            try:
                cur.execute("SELECT ST_IsValid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), "
                            "ST_IsValidReason(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))", (json.dumps(g), json.dumps(g)))
            except Exception:
                conn.rollback()
                raise ValueError("Topología inválida: la geometría no se puede leer.") from None
            valido, motivo = cur.fetchone()
            if not valido:
                raise ValueError(f"Topología inválida: {motivo}")
        cur.execute(
            "WITH u AS (SELECT ST_Multi(ST_CollectionExtract(ST_Union(ST_SetSRID(ST_GeomFromGeoJSON(g), 4326)), 3)) AS geom "
            "FROM unnest(%s::text[]) AS g) SELECT ST_AsGeoJSON(geom), ST_Area(geom::geography) / 1e6 FROM u",
            ([json.dumps(g) for g in geoms],),
        )
        geom, area = cur.fetchone()
    if not (AREA_MIN_KM2 <= area <= AREA_MAX_KM2):
        raise ValueError(f"El polígono cubre {area:,.0f} km²; se esperaba entre {AREA_MIN_KM2:,} y {AREA_MAX_KM2:,} km² "
                         "(Ucayali ≈ 102,000).")
    return json.loads(geom), area


def reemplazar_region(geometria, actor=None):
    """Reemplaza el limite regional y su geocerca de 5 km. Devuelve {'area_km2', 'focos_fuera'}."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM zonas WHERE tipo IN ('region', 'geocerca')")
        cur.execute("INSERT INTO zonas (nombre, tipo, geom) VALUES ('Ucayali', 'region', "
                    "ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))) RETURNING ST_Area(geom::geography) / 1e6",
                    (json.dumps(geometria),))
        area = cur.fetchone()[0]
        cur.execute("INSERT INTO zonas (nombre, tipo, geom) SELECT 'Ucayali + 5 km', 'geocerca', "
                    "ST_Multi(ST_Buffer(geom::geography, 5000)::geometry) FROM zonas WHERE tipo = 'region'")
        cur.execute("SELECT count(*) FROM focos_calor f WHERE NOT EXISTS ("
                    "SELECT 1 FROM zonas z WHERE z.tipo = 'geocerca' AND ST_Intersects(z.geom, f.geom))")
        fuera = cur.fetchone()[0]
    res = {"area_km2": round(area), "focos_fuera": fuera}
    auditoria.registrar(auditoria.GEOCERCA_ACTUALIZADA, (actor or {}).get("id"), (actor or {}).get("email"), res)
    return res


def cargar_fuentes(texto, formato, tipo_defecto="aserradero", radio_defecto=300, actor=None):
    """Carga fuentes de calor conocidas desde GeoJSON (puntos) o CSV (nombre,tipo,lat,lon,radio_m).
    Devuelve (cargadas, errores[str])."""
    if isinstance(texto, bytes):
        if len(texto) > MAX_BYTES:
            raise ValueError("El archivo supera 10 MB.")
        texto = texto.decode("utf-8-sig", errors="replace")
    filas = []
    if formato == "geojson":
        try:
            obj = json.loads(texto)
        except ValueError:
            raise ValueError("El archivo no es un GeoJSON válido.") from None
        items = obj.get("features", []) if obj.get("type") == "FeatureCollection" else [obj]
        for f in items:
            g, p = f.get("geometry") or {}, f.get("properties") or {}
            if g.get("type") == "Point":
                lon, lat = g["coordinates"][:2]
                filas.append((p.get("nombre") or p.get("name"), p.get("tipo") or tipo_defecto, lon, lat, p.get("radio_m") or radio_defecto))
    else:
        for r in csv.DictReader(io.StringIO(texto)):
            try:
                filas.append((r.get("nombre"), (r.get("tipo") or tipo_defecto).strip().lower(), float(r["lon"]), float(r["lat"]),
                              int(r.get("radio_m") or radio_defecto)))
            except (KeyError, ValueError):
                filas.append((r.get("nombre"), None, None, None, None))
    cargadas, errores = 0, []
    for i, (nombre, tipo, lon, lat, radio) in enumerate(filas, start=1):
        try:
            if tipo is None or lon is None:
                raise ValueError("fila incompleta")
            agregar(nombre, tipo, float(lon), float(lat), int(radio))
            cargadas += 1
        except (ValueError, TypeError) as e:
            errores.append(f"Fila {i}: {e}")
    auditoria.registrar(auditoria.FUENTES_CARGADAS, (actor or {}).get("id"), (actor or {}).get("email"),
                        {"cargadas": cargadas, "errores": len(errores), "formato": formato})
    return cargadas, errores


def listar_fuentes():
    from geofire.repositorio import _query
    return _query("SELECT id, nombre, tipo, fuente, radio_m, ST_Y(geom) AS lat, ST_X(geom) AS lon FROM fuentes_calor_conocidas "
                  "ORDER BY fuente, tipo, nombre NULLS LAST, id")


def eliminar_fuente(fuente_id, actor=None):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM fuentes_calor_conocidas WHERE id = %s", (fuente_id,))
    auditoria.registrar(auditoria.FUENTES_CARGADAS, (actor or {}).get("id"), (actor or {}).get("email"),
                        {"eliminada": fuente_id})


__all__ = ["validar_geojson", "reemplazar_region", "cargar_fuentes", "listar_fuentes", "eliminar_fuente", "TIPOS_VALIDOS"]
