import unittest
from datetime import date, timedelta
from unittest import mock

import pandas as pd

from geofire import clima, repositorio as repo, reportes, zonas
from geofire.db import get_connection

CAJA = (-60.5, -3.5, -59.5, -2.5)  # zona de prueba lejos de Ucayali


class TestClasificar(unittest.TestCase):
    """Reglas de la evaluacion por zona (config/riesgo.json -> zonas)."""

    def test_zona_sana_es_baja(self):
        self.assertEqual(zonas.clasificar(0.82, 0.80, 1.0, 2.0), ("BAJO", []))

    def test_estres_alto_es_medio(self):
        nivel, reglas = zonas.clasificar(0.78, 0.78, 8.0, 2.0)
        self.assertEqual((nivel, reglas), ("MEDIO", ["ZONA-ESTRES"]))

    def test_estres_severo_suma_dos_puntos(self):
        nivel, reglas = zonas.clasificar(0.70, 0.70, 15.0, 2.0)
        self.assertEqual(nivel, "ALTO")
        self.assertEqual(reglas, ["ZONA-ESTRES", "ZONA-ESTRES-SEVERO"])

    def test_anomalia_de_ndvi_frente_al_historico(self):
        nivel, reglas = zonas.clasificar(0.70, 0.78, 1.0, 2.0)  # 0.08 mas seca que lo normal
        self.assertEqual((nivel, reglas), ("MEDIO", ["ZONA-ANOMALIA-NDVI"]))

    def test_quemas_activas_suman(self):
        self.assertEqual(zonas.clasificar(0.8, 0.8, 1.0, 20.0)[1], ["ZONA-FOCOS-ACTIVOS"])

    def test_critico_con_tres_condiciones(self):
        nivel, reglas = zonas.clasificar(0.60, 0.75, 14.0, 25.0)
        self.assertEqual(nivel, "CRITICO")
        self.assertGreaterEqual(len(reglas), 3)

    def test_sin_historico_no_inventa_anomalia(self):
        self.assertNotIn("ZONA-ANOMALIA-NDVI", zonas.clasificar(0.5, None, 1.0, 1.0)[1])


class BaseZonaDePrueba(unittest.TestCase):
    """Crea una provincia y un distrito de prueba con un foco dentro (todo se borra al final)."""

    def setUp(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO zonas (nombre, tipo, geom) VALUES ('ZZ Provincia', 'provincia', "
                "ST_Multi(ST_MakeEnvelope(%s, %s, %s, %s, 4326))) RETURNING id", CAJA)
            self.prov = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO zonas (nombre, tipo, geom, padre_id) VALUES ('ZZ Distrito', 'distrito', "
                "ST_Multi(ST_MakeEnvelope(%s, %s, %s, %s, 4326)), %s) RETURNING id", (*CAJA, self.prov))
            self.dist = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO focos_calor (fuente, fecha_hora, frp, geom) VALUES ('TEST_ZONA', now(), 20, "
                "ST_SetSRID(ST_MakePoint(-60.0, -3.0), 4326)) RETURNING id")
            self.foco = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO alertas (foco_id, nivel, ndvi, puntaje, estado) VALUES (%s, 'ALTO', 0.3, 30, 'ACTIVA') RETURNING id",
                (self.foco,))
            self.alerta = cur.fetchone()[0]

    def tearDown(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM evaluaciones_zona WHERE zona_id = ANY(%s)", ([self.prov, self.dist],))
            cur.execute("DELETE FROM lotes_imagenes WHERE id NOT IN (SELECT lote_imagenes_id FROM alertas "
                        "WHERE lote_imagenes_id IS NOT NULL) AND id NOT IN (SELECT lote_imagenes_id FROM evaluaciones_zona "
                        "WHERE lote_imagenes_id IS NOT NULL) AND coleccion = 'TEST'")
            cur.execute("DELETE FROM alertas WHERE id = %s", (self.alerta,))
            cur.execute("DELETE FROM focos_calor WHERE id = %s", (self.foco,))
            cur.execute("DELETE FROM zonas WHERE id = %s", (self.dist,))
            cur.execute("DELETE FROM zonas WHERE id = %s", (self.prov,))


class TestFiltrosTerritoriales(BaseZonaDePrueba):
    def test_alerta_trae_su_provincia_y_distrito(self):
        df = repo.alertas(1, provincia="ZZ Provincia")
        fila = df[df["id"] == self.alerta].iloc[0]
        self.assertEqual((fila["provincia"], fila["distrito"]), ("ZZ Provincia", "ZZ Distrito"))

    def test_filtro_por_provincia_y_distrito(self):
        self.assertIn(self.alerta, set(repo.alertas(1, distrito="ZZ Distrito")["id"]))
        self.assertNotIn(self.alerta, set(repo.alertas(1, provincia="Atalaya")["id"]))
        self.assertNotIn(self.alerta, set(repo.alertas(1, distrito="Sepahua")["id"]))

    def test_listas_para_los_selectores(self):
        self.assertIn("ZZ Provincia", repo.provincias())
        self.assertEqual(repo.distritos("ZZ Provincia"), ["ZZ Distrito"])

    def test_por_provincia(self):
        pp = repo.por_provincia(1)
        self.assertEqual(int(pp[pp["provincia"] == "ZZ Provincia"]["altas"].iloc[0]), 1)

    def test_resumen_filtrado(self):
        self.assertEqual(repo.resumen(1, provincia="ZZ Provincia")["ALTO"], 1)
        self.assertEqual(repo.resumen(1, provincia="Purús")["ALTO"], 0)

    def test_linea_de_tiempo_incluye_focos_sin_evaluar(self):
        ahora = self._ahora()
        df = repo.focos_en_periodo(ahora - timedelta(hours=1), ahora + timedelta(hours=1), provincia="ZZ Provincia")
        self.assertEqual(len(df), 1)
        self.assertEqual(df["nivel"].iloc[0], "ALTO")

    def test_reporte_filtra_y_totaliza_por_provincia(self):
        hoy = date.today()
        rep = reportes.construir(hoy, hoy, provincia="ZZ Provincia")
        self.assertEqual(rep.total, 1)
        self.assertEqual(rep.por_provincia, {"ZZ Provincia": 1})
        self.assertIn(b"ZZ Provincia", reportes.a_pdf(rep))
        csv = reportes.a_csv(rep).decode("utf-8-sig")
        self.assertIn("provincia,distrito", csv)
        self.assertIn("Territorio: ZZ Provincia", csv)
        self.assertEqual(reportes.construir(hoy, hoy, provincia="Atalaya", distrito="Sepahua").por_provincia.get("ZZ Provincia"), None)

    @staticmethod
    def _ahora():
        from datetime import datetime, timezone
        return datetime.now(timezone.utc)


class TestEvaluacionDeZonas(BaseZonaDePrueba):
    """evaluar_todas con Earth Engine simulado y solo la zona de prueba."""

    def _evaluar(self, stats):
        meta = {"coleccion": "TEST", "desde": date(2026, 9, 1), "hasta": date(2026, 9, 30), "imagenes": ["a", "b", "c"]}

        def solo_la_de_prueba(cur):
            cur.execute("SELECT z.id, ST_AsGeoJSON(z.geom), ST_Area(z.geom::geography) / 1e6, 3 FROM zonas z WHERE z.id = %s",
                        (self.dist,))
            return cur.fetchall()

        with mock.patch.object(zonas.gi, "init"), \
                mock.patch.object(zonas.gi, "compuesto_zonas", return_value=({self.dist: stats}, meta)), \
                mock.patch.object(zonas, "_zonas_a_evaluar", solo_la_de_prueba):
            return zonas.evaluar_todas(date(2026, 9, 30))

    def _ultima(self):
        df = zonas.ultimas("distrito")
        return df[df["id"] == self.dist].iloc[0]

    def test_evalua_una_zona_sin_focos_ni_alertas_ac_06_1(self):
        stats = {"ndvi": 0.74, "estres": 0.14, "valida": 0.95, "tierra_valida": 0.9, "ndvi_historico": 0.75}
        res = self._evaluar(stats)
        fila = self._ultima()
        self.assertTrue(fila["evaluable"])
        self.assertEqual(fila["nivel"], "ALTO")  # estres alto + severo
        self.assertAlmostEqual(fila["pct_estres"], 14.0)
        self.assertEqual(res["ALTO"], 1)

    def test_conserva_trazabilidad_ac_06_2(self):
        self._evaluar({"ndvi": 0.8, "estres": 0.01, "valida": 0.99, "tierra_valida": 0.9, "ndvi_historico": 0.8})
        fila = self._ultima()
        self.assertEqual(fila["fecha_corte"].date(), date(2026, 9, 30))   # fecha de corte
        self.assertEqual(fila["imagenes"], 3)                              # imagenes referenciadas
        self.assertTrue(fila["config_version"])                            # version de la configuracion
        self.assertEqual(fila["ventana_dias"], 30)

    def test_sin_cobertura_es_no_evaluable_y_no_inventa_nivel_ac_03_2(self):
        self._evaluar({"ndvi": 0.8, "estres": 0.01, "valida": 0.10, "tierra_valida": 0.1, "ndvi_historico": 0.8})
        fila = self._ultima()
        self.assertFalse(fila["evaluable"])
        self.assertTrue(pd.isna(fila["nivel"]))   # sin nivel: ni Bajo ni ningun otro
        self.assertEqual(fila["motivo"], "COBERTURA_INSUFICIENTE")

    def test_sin_datos_en_absoluto_es_no_evaluable(self):
        self._evaluar({"ndvi": None, "estres": None, "valida": 0.0, "tierra_valida": 0.0, "ndvi_historico": None})
        self.assertFalse(self._ultima()["evaluable"])

    def test_geojson_con_niveles(self):
        self._evaluar({"ndvi": 0.8, "estres": 0.01, "valida": 0.99, "tierra_valida": 0.9, "ndvi_historico": 0.8})
        props = {f["properties"]["nombre"]: f["properties"] for f in zonas.geojson_con_niveles("distrito")["features"]}
        self.assertEqual(props["ZZ Distrito"]["nivel"], "BAJO")

    def test_evaluar_si_toca_respeta_la_vigencia(self):
        self._evaluar({"ndvi": 0.8, "estres": 0.01, "valida": 0.99, "tierra_valida": 0.9, "ndvi_historico": 0.8})
        # hay evaluaciones recientes (las de este test): no vuelve a consultar Earth Engine
        with mock.patch.object(zonas, "evaluar_todas") as ev:
            self.assertIn("vigente", zonas.evaluar_si_toca(horas_minimas=20))
        ev.assert_not_called()

    def test_historial_y_geometria(self):
        self._evaluar({"ndvi": 0.8, "estres": 0.01, "valida": 0.99, "tierra_valida": 0.9, "ndvi_historico": 0.8})
        self.assertEqual(len(zonas.historial(self.dist)), 1)
        geom, caja = zonas.geometria(self.dist)
        self.assertIn(geom["type"], ("Polygon", "MultiPolygon"))
        self.assertEqual(caja, CAJA)
        self.assertEqual(zonas.id_por_nombre("ZZ Distrito", "distrito"), self.dist)


class TestViento(unittest.TestCase):
    def test_rumbo(self):
        self.assertEqual((clima.rumbo(0), clima.rumbo(90), clima.rumbo(225), clima.rumbo(350)), ("N", "E", "SO", "N"))

    def test_viento_correcto(self):
        class R:
            @staticmethod
            def raise_for_status():
                pass

            @staticmethod
            def json():
                return {"current": {"wind_speed_10m": 12.5, "wind_direction_10m": 90, "time": "2026-10-08T12:00"}}

        with mock.patch.object(clima.requests, "get", return_value=R()):
            v = clima.viento(-10, -73)
        self.assertEqual((v["velocidad_kmh"], v["rumbo"]), (12.5, "E"))

    def test_si_el_servicio_falla_devuelve_none(self):
        with mock.patch.object(clima.requests, "get", side_effect=clima.requests.ConnectionError("sin red")):
            self.assertIsNone(clima.viento(-10, -73))


if __name__ == "__main__":
    unittest.main()
