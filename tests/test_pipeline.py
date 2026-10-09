import unittest
from datetime import date
from unittest import mock

from geofire import alertas
from geofire.db import get_connection
from geofire.riesgo import CONFIG_VERSION

# Cuatro focos de prueba lejos de Ucayali, uno por escenario
ESCENARIOS = {"critico": -60.0, "sin_imagenes": -60.1, "agua": -60.2, "bajo": -60.3}
IMAGENES = ["20260101T000000_T18LXM", "20260103T000000_T18LXM"]


def meta():
    return {"coleccion": "COPERNICUS/S2_SR_HARMONIZED", "desde": date(2026, 1, 1), "hasta": date(2026, 1, 31),
            "imagenes": IMAGENES}


class TestPipeline(unittest.TestCase):
    """Evalua focos reales de la base pero con Earth Engine simulado: ningun dato real se toca."""

    def setUp(self):
        self.focos = {}
        with get_connection() as conn, conn.cursor() as cur:
            for nombre, lon in ESCENARIOS.items():
                cur.execute(
                    "INSERT INTO focos_calor (fuente, fecha_hora, frp, confianza, geom) VALUES "
                    "('TEST_PIPELINE', now(), 12, 'h', ST_SetSRID(ST_MakePoint(%s, -3.0), 4326)) RETURNING id", (lon,))
                self.focos[nombre] = cur.fetchone()[0]
        self.indices = {
            self.focos["critico"]: {"NDVI": 0.30, "NDWI": -0.5, "NBR": 0.2, "en_anp": True},
            self.focos["sin_imagenes"]: {"NDVI": None, "NDWI": None, "NBR": None, "en_anp": False},
            self.focos["agua"]: {"NDVI": -0.1, "NDWI": 0.4, "NBR": -0.2, "en_anp": False},
            self.focos["bajo"]: {"NDVI": 0.80, "NDWI": -0.7, "NBR": 0.6, "en_anp": False},
        }

    def tearDown(self):
        ids = list(self.focos.values())
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT DISTINCT lote_imagenes_id FROM alertas WHERE foco_id = ANY(%s)", (ids,))
            lotes = [r[0] for r in cur.fetchall() if r[0]]
            cur.execute("DELETE FROM alertas WHERE foco_id = ANY(%s)", (ids,))
            cur.execute("DELETE FROM lotes_imagenes WHERE id = ANY(%s)", (lotes,))
            cur.execute("DELETE FROM focos_calor WHERE id = ANY(%s)", (ids,))

    def _procesar(self, indices=None):
        ids = set(self.focos.values())

        def solo_de_prueba(cur, horas):
            cur.execute(
                "SELECT f.id, ST_X(f.geom), ST_Y(f.geom), f.frp, COALESCE(f.confianza, ''), 0.0 "
                "FROM focos_calor f LEFT JOIN alertas a ON a.foco_id = f.id "
                "WHERE f.id = ANY(%s) AND (a.id IS NULL OR a.motivo = %s)", (list(ids), alertas.MOTIVO_SIN_IMAGENES))
            return cur.fetchall()

        datos = indices or self.indices
        with mock.patch.object(alertas.gi, "init"), \
                mock.patch.object(alertas.gi, "indices_para_puntos", return_value=(datos, meta())), \
                mock.patch.object(alertas, "_focos_pendientes", solo_de_prueba):
            return alertas.procesar(24)

    def _fila(self, nombre):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT nivel, evaluable, motivo, estado, ndvi, config_version, evaluada_en, fecha_corte, lote_imagenes_id "
                "FROM alertas WHERE foco_id = %s", (self.focos[nombre],))
            return cur.fetchone()

    def test_evaluacion_conserva_trazabilidad_ac_06_2(self):
        _, resumen = self._procesar()
        nivel, evaluable, motivo, estado, ndvi, version, evaluada, corte, lote = self._fila("critico")
        self.assertEqual((nivel, evaluable, motivo), ("CRITICO", True, None))
        self.assertAlmostEqual(ndvi, 0.30)
        self.assertEqual(version, CONFIG_VERSION)  # version de la configuracion usada
        self.assertIsNotNone(evaluada)
        self.assertIsNotNone(corte)                # fecha de corte
        self.assertEqual(resumen["CRITICO"], 1)

    def test_imagenes_usadas_quedan_registradas_ac_03_1(self):
        self._procesar()
        lote = self._fila("critico")[8]
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT coleccion, desde, hasta, imagenes FROM lotes_imagenes WHERE id = %s", (lote,))
            coleccion, desde, hasta, imagenes = cur.fetchone()
        self.assertEqual(imagenes, IMAGENES)
        self.assertEqual((desde, hasta), (date(2026, 1, 1), date(2026, 1, 31)))
        self.assertEqual(coleccion, "COPERNICUS/S2_SR_HARMONIZED")

    def test_sin_imagenes_es_no_evaluable_y_no_riesgo_bajo_ac_03_2(self):
        _, resumen = self._procesar()
        nivel, evaluable, motivo, estado, ndvi, *_ = self._fila("sin_imagenes")
        self.assertIsNone(nivel)                       # no se asigna Bajo ni ningun nivel
        self.assertIsNone(ndvi)                        # no se inventa un valor
        self.assertFalse(evaluable)
        self.assertEqual((motivo, estado), ("SIN_IMAGENES", "NO_EVALUABLE"))
        self.assertEqual(resumen["no_evaluables"], 1)
        evaluados = sum(resumen[n] for n in ("CRITICO", "ALTO", "MEDIO", "BAJO"))
        self.assertEqual(evaluados, 2)                 # solo critico y "bajo"; el que no tenia datos no cuenta

    def test_no_evaluable_se_reintenta_cuando_hay_imagenes(self):
        self._procesar()
        self.assertFalse(self._fila("sin_imagenes")[1])
        mejores = dict(self.indices)
        mejores[self.focos["sin_imagenes"]] = {"NDVI": 0.35, "NDWI": -0.6, "NBR": 0.3, "en_anp": True}
        self._procesar(mejores)
        nivel, evaluable, motivo, *_ = self._fila("sin_imagenes")
        self.assertTrue(evaluable)
        self.assertIsNone(motivo)
        self.assertEqual(nivel, "CRITICO")  # ANP + NDVI de estres

    def test_agua_se_registra_como_excluida_y_no_se_reintenta_ac_04_2(self):
        _, resumen = self._procesar()
        nivel, evaluable, motivo, *_ = self._fila("agua")
        self.assertEqual((nivel, evaluable, motivo), (None, False, "AGUA"))
        self.assertEqual(resumen["agua"], 1)
        _, resumen2 = self._procesar()  # segunda corrida: el de agua ya no esta pendiente
        self.assertEqual(resumen2["agua"], 0)

    def test_no_evaluables_no_aparecen_como_alertas_ni_en_reportes(self):
        from geofire import repositorio as repo
        from geofire import reportes
        self._procesar()
        df = repo.alertas(24)
        self.assertNotIn(None, set(df["nivel"]))
        hoy = date.today()
        rep = reportes.construir(hoy, hoy)
        self.assertGreaterEqual(rep.no_evaluables, 2)  # el sin_imagenes y el agua
        self.assertIn(b"no evaluables", reportes.a_pdf(rep).lower())

    def test_reevaluar_ignora_no_evaluables(self):
        self._procesar()
        res = alertas.reevaluar(horas=24)
        self.assertGreaterEqual(res["revisadas"], 2)  # critico y bajo; los no evaluables no se tocan
        self.assertIsNone(self._fila("sin_imagenes")[0])


if __name__ == "__main__":
    unittest.main()
