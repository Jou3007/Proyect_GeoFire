import unittest
from datetime import date

from geofire import backtesting as b


class TestAuc(unittest.TestCase):
    def test_separacion_perfecta(self):
        self.assertEqual(b.auc([0.2, 0.3], [0.7, 0.8]), 1.0)  # eventos con NDVI menor que todos los controles

    def test_azar(self):
        self.assertEqual(b.auc([0.5, 0.5], [0.5, 0.5]), 0.5)

    def test_al_reves(self):
        self.assertEqual(b.auc([0.8, 0.9], [0.1, 0.2]), 0.0)

    def test_valor_intermedio(self):
        self.assertAlmostEqual(b.auc([0.4, 0.8], [0.6, 0.7]), 0.5)

    def test_sin_datos(self):
        self.assertIsNone(b.auc([], [0.5]))
        self.assertIsNone(b.auc([None], [0.5]))

    def test_ignora_los_sin_dato(self):
        self.assertEqual(b.auc([0.2, None], [0.9, None]), 1.0)


class TestMetricas(unittest.TestCase):
    def test_sensibilidad_y_falsas_alarmas(self):
        ev = [{"ndvi": 0.3}, {"ndvi": 0.4}, {"ndvi": 0.8}, {"ndvi": None}]
        co = [{"ndvi": 0.3}, {"ndvi": 0.8}, {"ndvi": 0.9}, {"ndvi": 0.85}]
        m = b.metricas(ev, co, umbral=0.45)
        self.assertEqual((m["n_eventos"], m["n_controles"]), (3, 4))
        self.assertAlmostEqual(m["sensibilidad_pct"], 66.7)
        self.assertEqual(m["falsas_alarmas_pct"], 25.0)
        self.assertAlmostEqual(m["lift"], 2.67, places=2)
        self.assertGreater(m["auc"], 0.5)

    def test_sin_datos(self):
        self.assertIsNone(b.metricas([], [{"ndvi": 0.5}]))

    def test_barrido_devuelve_un_resultado_por_umbral(self):
        ev, co = [{"ndvi": 0.3}], [{"ndvi": 0.9}]
        self.assertEqual(set(b.barrido_umbrales(ev, co, (0.4, 0.5))), {0.4, 0.5})

    def test_lunes_de_la_semana(self):
        self.assertEqual(b.lunes(date(2026, 10, 8)), date(2026, 10, 5))  # jueves -> lunes
        self.assertEqual(b.lunes(date(2026, 10, 5)), date(2026, 10, 5))


class TestMuestreo(unittest.TestCase):
    def test_eventos_son_reproducibles_y_estan_dentro_de_la_fecha(self):
        a = b.muestrear_eventos(n=15, semilla=3)
        c = b.muestrear_eventos(n=15, semilla=3)
        self.assertEqual([e["id"] for e in a], [e["id"] for e in c])
        for e in a:
            self.assertTrue(date(2025, 3, 1) <= e["fecha"] < date(2026, 6, 1))


if __name__ == "__main__":
    unittest.main()
