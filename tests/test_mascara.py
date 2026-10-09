import unittest
from datetime import date

from geofire import gee_indices as gi
from geofire import mascara_agua as m
from geofire.db import get_connection
from geofire.riesgo import CONFIG


class TestPorcentajes(unittest.TestCase):
    def test_calculo_de_las_metricas(self):
        v = {"ref_agua": 100.0, "agua_excluida": 96.0, "ref_tierra": 1000.0, "tierra_excluida": 5.0, "ref_agua_total": 100.5}
        r = m._porcentajes(v)
        self.assertEqual(r["excluidos_correctamente_pct"], 96.0)             # AC-04.1
        self.assertEqual(r["tierra_excluida_incorrectamente_pct"], 0.5)      # AC-04.2
        self.assertEqual(r["agua_sin_imagen_valida_pct"], 0.5)

    def test_sin_agua_de_referencia_no_divide_por_cero(self):
        r = m._porcentajes({"ref_agua": 0.0, "agua_excluida": 0.0, "ref_tierra": 0.0, "tierra_excluida": 0.0, "ref_agua_total": 0.0})
        self.assertIsNone(r["excluidos_correctamente_pct"])
        self.assertIsNone(r["tierra_excluida_incorrectamente_pct"])


class TestParametros(unittest.TestCase):
    def test_el_umbral_sale_de_la_configuracion(self):
        self.assertEqual(gi.UMBRAL_AGUA, CONFIG["umbral_ndwi_agua"])
        self.assertLess(gi.UMBRAL_AGUA, 0.1)

    def test_las_areas_estan_en_ucayali(self):
        for nombre, (oeste, sur, este, norte) in m.AREAS.items():
            self.assertTrue(-76 < oeste < este < -70, nombre)
            self.assertTrue(-12.1 < sur < norte < -7, nombre)

    def test_guardar_deja_la_corrida_reproducible_ac_04_2(self):
        i = m.guardar({"corrida": "prueba", "resultado": {"TOTAL": {}}}, -0.1, 30, date(2026, 1, 1))
        try:
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute("SELECT umbral_ndwi, ventana_dias, fecha_corte, referencia, escala_m, resultado "
                            "FROM validaciones_mascara WHERE id = %s", (i,))
                umbral, ventana, corte, referencia, escala, resultado = cur.fetchone()
            self.assertEqual((umbral, ventana, corte, escala), (-0.1, 30, date(2026, 1, 1), m.ESCALA_M))
            self.assertEqual(referencia, m.REFERENCIA)
            self.assertEqual(resultado["corrida"], "prueba")
        finally:
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute("DELETE FROM validaciones_mascara WHERE id = %s", (i,))


if __name__ == "__main__":
    unittest.main()
