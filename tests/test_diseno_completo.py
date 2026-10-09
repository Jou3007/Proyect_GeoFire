"""RN-04 (fuentes conocidas), AC-09.2 (zona asignada), geocercas del administrador, GeoJSON (RNF-07) y contraste (RNF-05)."""
import json
import secrets
import unittest
from datetime import date
from unittest import mock

from geofire import alertas, geocercas, geojson, reportes, seguridad
from geofire import fuentes_conocidas as fk
from geofire import repositorio as repo
from geofire import validacion as val
from geofire.contraste import PARES_ALTO_CONTRASTE, PARES_NORMAL, ratio
from geofire.db import get_connection
from geofire.riesgo import Contexto, Foco, evaluar
from util_pruebas import borrar_auditoria_de_prueba, imagen_bytes

CAJA = (-60.5, -3.5, -59.5, -2.5)
JUSTIF = "Se observa humo desde el camino"


class BaseConZona(unittest.TestCase):
    """Provincia 'ZZ Provincia', distrito 'ZZ Distrito', otra zona 'ZZ Otra' y un foco con alerta dentro de ZZ Distrito."""

    def setUp(self):
        sufijo = secrets.token_hex(4)
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO zonas (nombre, tipo, geom) VALUES ('ZZ Provincia', 'provincia', "
                        "ST_Multi(ST_MakeEnvelope(%s, %s, %s, %s, 4326))) RETURNING id", CAJA)
            self.prov = cur.fetchone()[0]
            cur.execute("INSERT INTO zonas (nombre, tipo, geom, padre_id) VALUES ('ZZ Distrito', 'distrito', "
                        "ST_Multi(ST_MakeEnvelope(%s, %s, %s, %s, 4326)), %s) RETURNING id", (*CAJA, self.prov))
            self.dist = cur.fetchone()[0]
            cur.execute("INSERT INTO zonas (nombre, tipo, geom) VALUES ('ZZ Otra', 'distrito', "
                        "ST_Multi(ST_MakeEnvelope(-65, -3.5, -64, -2.5, 4326))) RETURNING id")
            self.otra = cur.fetchone()[0]
            cur.execute("INSERT INTO focos_calor (fuente, fecha_hora, frp, geom) VALUES ('TEST_T3', now(), 20, "
                        "ST_SetSRID(ST_MakePoint(-60.0, -3.0), 4326)) RETURNING id")
            self.foco = cur.fetchone()[0]
            cur.execute("INSERT INTO alertas (foco_id, nivel, ndvi, puntaje, estado) VALUES (%s, 'ALTO', 0.3, 30, 'ACTIVA') RETURNING id",
                        (self.foco,))
            self.alerta = cur.fetchone()[0]
            self.correo = f"t3-{sufijo}@geofire.test"
            cur.execute("INSERT INTO usuarios (email, rol, password_hash, nombre) VALUES (%s, 'guardaparque', 'x', 'G') RETURNING id",
                        (self.correo,))
            self.uid = cur.fetchone()[0]

    def tearDown(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM incidentes WHERE alerta_id = %s", (self.alerta,))
            cur.execute("DELETE FROM alertas WHERE id = %s", (self.alerta,))
            cur.execute("DELETE FROM focos_calor WHERE id = %s", (self.foco,))
            cur.execute("DELETE FROM usuarios WHERE id = %s", (self.uid,))
            cur.execute("DELETE FROM zonas WHERE id = ANY(%s)", ([self.dist, self.otra],))
            cur.execute("DELETE FROM zonas WHERE id = %s", (self.prov,))
            cur.execute("DELETE FROM fuentes_calor_conocidas WHERE fuente = 'TEST'")
        borrar_auditoria_de_prueba()

    def guardaparque(self, zona_id):
        return {"id": self.uid, "rol": "guardaparque", "email": self.correo, "zona_id": zona_id}


class TestZonaAsignada(BaseConZona):
    def test_alcance(self):
        self.assertEqual(seguridad.alcance({"rol": "guardaparque", "zona_id": 5}), (True, 5))
        self.assertEqual(seguridad.alcance({"rol": "guardaparque"}), (True, None))
        self.assertEqual(seguridad.alcance({"rol": "autoridad_regional"}), (False, None))

    def test_asignar_zona_y_quedar_auditado(self):
        seguridad.asignar_zona(self.uid, self.dist, actor={"id": 1, "email": self.correo})
        u = next(x for x in seguridad.listar_usuarios() if x["id"] == self.uid)
        self.assertEqual((u["zona_id"], u["zona"]), (self.dist, "ZZ Distrito"))

    def test_login_trae_la_zona(self):
        seguridad.crear_usuario(f"z-{self.correo}", "Z", "guardaparque", "clave-larga-123")
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("UPDATE usuarios SET zona_id = %s WHERE email = %s", (self.dist, f"z-{self.correo}"))
        usuario, _ = seguridad.autenticar(f"z-{self.correo}", "clave-larga-123")
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM usuarios WHERE email = %s", (f"z-{self.correo}",))
        self.assertEqual((usuario["zona_id"], usuario["zona"]), (self.dist, "ZZ Distrito"))

    def test_solo_ve_las_alertas_de_su_zona(self):
        self.assertIn(self.alerta, set(repo.alertas(1, zona_id=self.dist)["id"]))
        self.assertNotIn(self.alerta, set(repo.alertas(1, zona_id=self.otra)["id"]))
        self.assertIn(self.alerta, set(val.pendientes(1, self.dist)["id"]))
        self.assertNotIn(self.alerta, set(val.pendientes(1, self.otra)["id"]))

    def test_linea_de_tiempo_limitada_a_la_zona(self):
        from datetime import datetime, timedelta, timezone
        ahora = datetime.now(timezone.utc)
        dentro = repo.focos_en_periodo(ahora - timedelta(hours=1), ahora + timedelta(hours=1), zona_id=self.dist)
        fuera = repo.focos_en_periodo(ahora - timedelta(hours=1), ahora + timedelta(hours=1), zona_id=self.otra)
        self.assertEqual((len(dentro), len(fuera)), (1, 0))

    def test_valida_dentro_de_su_zona(self):
        val.validar(self.alerta, self.guardaparque(self.dist), "FALSA_ALARMA", JUSTIF)

    def test_no_puede_validar_fuera_de_su_zona_ac_09_2(self):
        with self.assertRaises(PermissionError) as ctx:
            val.validar(self.alerta, self.guardaparque(self.otra), "CONFIRMADA", JUSTIF, foto=imagen_bytes())
        self.assertIn("fuera de tu zona", str(ctx.exception))
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT estado FROM alertas WHERE id = %s", (self.alerta,))
            self.assertEqual(cur.fetchone()[0], "ACTIVA")

    def test_sin_zona_asignada_no_puede_validar(self):
        with self.assertRaises(PermissionError) as ctx:
            val.validar(self.alerta, self.guardaparque(None), "FALSA_ALARMA", JUSTIF)
        self.assertIn("zona asignada", str(ctx.exception))

    def test_la_autoridad_regional_no_esta_limitada(self):
        autoridad = {"id": self.uid, "rol": "autoridad_regional", "email": self.correo}
        val.validar(self.alerta, autoridad, "FALSA_ALARMA", JUSTIF)


class TestFuentesConocidas(BaseConZona):
    def _fuente(self, lon, lat, radio=300):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO fuentes_calor_conocidas (nombre, tipo, fuente, radio_m, geom) VALUES "
                        "('Aserradero de prueba', 'aserradero', 'TEST', %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))",
                        (radio, lon, lat))

    def test_foco_dentro_del_radio_se_detecta(self):
        self._fuente(-60.001, -3.0)  # ~110 m
        with get_connection() as conn, conn.cursor() as cur:
            self.assertEqual(fk.cerca_de_fuente(cur, [self.foco]), {self.foco})

    def test_foco_fuera_del_radio_no(self):
        self._fuente(-60.01, -3.0)  # ~1.1 km
        with get_connection() as conn, conn.cursor() as cur:
            self.assertEqual(fk.cerca_de_fuente(cur, [self.foco]), set())

    def test_radio_propio_de_cada_fuente(self):
        self._fuente(-60.01, -3.0, radio=2000)
        with get_connection() as conn, conn.cursor() as cur:
            self.assertEqual(fk.cerca_de_fuente(cur, [self.foco]), {self.foco})

    def test_cp_08_foco_junto_a_un_aserradero_es_bajo_con_rn_04(self):
        r = evaluar(Foco(frp=10), Contexto(en_anp=True, ndvi=0.2, dist_comunidad_km=2, cerca_fuente_conocida=True))
        self.assertEqual((r["nivel"], r["estado"]), ("BAJO", "FUENTE_CONOCIDA"))
        self.assertIn("RN-04", r["reglas"])

    def test_la_intensidad_extrema_supera_la_regla_rn_04(self):
        r = evaluar(Foco(frp=90), Contexto(en_anp=True, ndvi=0.2, cerca_fuente_conocida=True))
        self.assertEqual(r["nivel"], "CRITICO")

    def test_reevaluar_aplica_rn_04_a_alertas_existentes(self):
        self._fuente(-60.001, -3.0)
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("UPDATE alertas SET en_anp = TRUE, nivel = 'CRITICO' WHERE id = %s", (self.alerta,))
        alertas.reevaluar(horas=1)
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT nivel, estado, reglas FROM alertas WHERE id = %s", (self.alerta,))
            nivel, estado, reglas = cur.fetchone()
        self.assertEqual((nivel, estado), ("BAJO", "FUENTE_CONOCIDA"))
        self.assertIn("RN-04", reglas)

    def test_agregar_valida_los_datos(self):
        i = fk.agregar("A", "aserradero", -74.5, -8.4, 300, fuente="TEST")
        self.assertIsInstance(i, int)
        for malo in (("A", "tipo-raro", -74.5, -8.4, 300), ("A", "aserradero", -50.0, -8.4, 300),
                     ("A", "aserradero", -74.5, -8.4, 10), ("A", "aserradero", -74.5, -8.4, 99999)):
            with self.assertRaises(ValueError):
                fk.agregar(*malo, fuente="TEST")

    def test_estado_fuente_conocida_tiene_etiqueta(self):
        self.assertEqual(repo.ESTADO_ETIQUETA["FUENTE_CONOCIDA"], "Fuente conocida")

    def test_tipos_de_osm(self):
        self.assertEqual(fk._tipo_osm({"industrial": "sawmill"}), "aserradero")
        self.assertEqual(fk._tipo_osm({"craft": "sawmill"}), "aserradero")
        self.assertEqual(fk._tipo_osm({"industrial": "oil"}), "hidrocarburos")
        self.assertEqual(fk._tipo_osm({"man_made": "works"}), "planta")

    def test_cargar_fuentes_desde_csv_y_geojson(self):
        csv_ok = "nombre,tipo,lat,lon,radio_m\nPlanta A,planta,-8.40,-74.50,400\nMala,planta,abc,-74.5,300\n"
        with mock.patch.object(geocercas, "agregar", wraps=lambda *a, **k: fk.agregar(*a, fuente="TEST", **k)):
            n, errores = geocercas.cargar_fuentes(csv_ok, "csv")
        self.assertEqual(n, 1)
        self.assertEqual(len(errores), 1)
        gj = json.dumps({"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"nombre": "B", "tipo": "aserradero"}, "geometry": {"type": "Point", "coordinates": [-74.6, -8.5]}}]})
        with mock.patch.object(geocercas, "agregar", wraps=lambda *a, **k: fk.agregar(*a, fuente="TEST", **k)):
            self.assertEqual(geocercas.cargar_fuentes(gj, "geojson")[0], 1)


def cuadrado(w, s, e, n):
    return {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}


class TestGeocercas(unittest.TestCase):
    def test_poligono_valido(self):
        geom, area = geocercas.validar_geojson(json.dumps(cuadrado(-75, -11, -71, -8)))  # ~ 4 x 3 grados ≈ 146,000 km2
        self.assertEqual(geom["type"], "MultiPolygon")
        self.assertTrue(geocercas.AREA_MIN_KM2 <= area <= geocercas.AREA_MAX_KM2)

    def test_acepta_feature_y_featurecollection(self):
        f = {"type": "Feature", "properties": {}, "geometry": cuadrado(-75, -11, -71, -8)}
        geocercas.validar_geojson(json.dumps(f))
        geocercas.validar_geojson(json.dumps({"type": "FeatureCollection", "features": [f]}))

    def test_topologia_invalida_se_rechaza(self):
        corbata = {"type": "Polygon", "coordinates": [[[-75, -11], [-71, -8], [-71, -11], [-75, -8], [-75, -11]]]}  # se autointerseca
        with self.assertRaises(ValueError) as ctx:
            geocercas.validar_geojson(json.dumps(corbata))
        self.assertIn("Topología inválida", str(ctx.exception))

    def test_archivos_que_no_sirven(self):
        for malo in ("esto no es json", json.dumps({"type": "FeatureCollection", "features": []}),
                     json.dumps({"type": "Point", "coordinates": [-74, -8]})):
            with self.assertRaises(ValueError):
                geocercas.validar_geojson(malo)

    def test_area_fuera_de_rango_se_rechaza(self):
        with self.assertRaises(ValueError) as ctx:
            geocercas.validar_geojson(json.dumps(cuadrado(-74.6, -8.5, -74.5, -8.4)))  # ~120 km2
        self.assertIn("km²", str(ctx.exception))
        with self.assertRaises(ValueError):
            geocercas.validar_geojson(b"{" + b"x" * (geocercas.MAX_BYTES + 1))

    def test_reemplazar_region_y_restaurar(self):
        """Reemplaza la region por otra y la restaura: verifica el flujo sin dejar cambios."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT ST_AsGeoJSON(geom) FROM zonas WHERE tipo = 'region'")
            fila = cur.fetchone()
            if not fila:
                self.skipTest("la base no tiene el limite regional cargado (scripts/load_limite.py)")
            original = json.loads(fila[0])
            cur.execute("SELECT count(*) FROM zonas WHERE tipo IN ('region', 'geocerca')")
            antes = cur.fetchone()[0]
        try:
            geom, _ = geocercas.validar_geojson(json.dumps(cuadrado(-75, -11, -71, -8)))
            res = geocercas.reemplazar_region(geom, {"id": None, "email": "t@geofire.test"})
            self.assertGreater(res["area_km2"], 100_000)
            self.assertIn("focos_fuera", res)
        finally:
            geocercas.reemplazar_region(original, {"id": None, "email": "t@geofire.test"})
            borrar_auditoria_de_prueba()
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM zonas WHERE tipo IN ('region', 'geocerca')")
            self.assertEqual(cur.fetchone()[0], antes)


class TestGeoJSON(BaseConZona):
    def test_exportacion_valida_rfc_7946(self):
        df = repo.alertas(1, zona_id=self.dist)
        fc = geojson.puntos(df, ["id", "nivel", "fecha_hora", "ndvi", "en_anp"])
        self.assertTrue(geojson.validar(fc))
        f = next(x for x in fc["features"] if x["properties"]["id"] == self.alerta)
        self.assertEqual(f["geometry"]["coordinates"], [-60.0, -3.0])  # [longitud, latitud]
        json.loads(geojson.a_texto(fc))  # serializable

    def test_el_reporte_se_exporta_como_geojson(self):
        rep = reportes.construir(date.today(), date.today(), provincia="ZZ Provincia")
        fc = json.loads(reportes.a_geojson(rep))
        geojson.validar(fc)
        self.assertEqual(len(fc["features"]), rep.total)
        self.assertEqual(fc["properties"]["total"], rep.total)

    def test_reporte_vacio_tambien_es_valido(self):
        rep = reportes.construir(date(2019, 1, 1), date(2019, 1, 2))
        self.assertTrue(geojson.validar(json.loads(reportes.a_geojson(rep))))

    def test_las_zonas_exportadas_son_validas(self):
        from geofire import zonas
        self.assertTrue(geojson.validar(zonas.geojson_con_niveles("distrito")))

    def test_el_validador_detecta_errores(self):
        malos = [
            {"type": "Feature"},
            {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [-8.4, -200]},
                                                        "properties": {}}]},  # latitud fuera de rango (lat/lon invertidas)
            {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {},
                                                        "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1]]]}}]},
            {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {},
                                                        "geometry": {"type": "Point", "coordinates": ["a", "b"]}}]},
        ]
        for m in malos:
            with self.assertRaises(ValueError):
                geojson.validar(m)


class TestContraste(unittest.TestCase):
    def test_modo_normal_cumple_wcag_aa(self):
        for nombre, (fg, bg) in PARES_NORMAL.items():
            self.assertGreaterEqual(ratio(fg, bg), 4.5, nombre)

    def test_alto_contraste_cumple_wcag_aaa(self):
        for nombre, (fg, bg) in PARES_ALTO_CONTRASTE.items():
            self.assertGreaterEqual(ratio(fg, bg), 7.0, nombre)

    def test_valores_de_referencia(self):
        self.assertAlmostEqual(ratio("#000000", "#ffffff"), 21.0, places=1)
        self.assertAlmostEqual(ratio("#ffffff", "#ffffff"), 1.0, places=1)

    def test_etiquetas_de_riesgo_legibles_en_modo_normal(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
        import ui
        for nivel, color in ui.COLOR.items():
            fondo = "#" + "".join(f"{int(int(color[i:i + 2], 16) * 0.133 + 255 * 0.867):02x}" for i in (1, 3, 5))  # color al 13 % sobre blanco
            self.assertGreaterEqual(ratio(ui.COLOR_TEXTO[nivel], fondo), 4.5, nivel)


if __name__ == "__main__":
    unittest.main()
