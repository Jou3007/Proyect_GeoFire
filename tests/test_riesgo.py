import unittest

from geofire.riesgo import CONFIG, Contexto, Foco, evaluar


class TestRiesgo(unittest.TestCase):
    def test_critico_por_anp_y_ndvi(self):
        r = evaluar(Foco(frp=20, confianza="h"), Contexto(ndvi=0.3, en_anp=True))
        self.assertEqual(r["nivel"], "CRITICO")
        self.assertEqual(r["puntaje"], 70)

    def test_alto_con_una_condicion(self):
        r = evaluar(Foco(frp=5), Contexto(en_anp=True))
        self.assertEqual(r["nivel"], "ALTO")

    def test_cercania_sola_no_es_alto(self):
        r = evaluar(Foco(frp=5), Contexto(dist_comunidad_km=4, ndvi=0.8))
        self.assertEqual(r["nivel"], "BAJO")
        self.assertNotIn("RN-02.1", r["reglas"])

    def test_cercania_sola_con_frp_alto_es_medio(self):
        self.assertEqual(evaluar(Foco(frp=20), Contexto(dist_comunidad_km=4, ndvi=0.8))["nivel"], "MEDIO")

    def test_cercania_agrava_una_condicion_y_da_critico(self):
        r = evaluar(Foco(frp=5), Contexto(dist_comunidad_km=4, ndvi=0.3))  # 02.1 + 02.3
        self.assertEqual(r["nivel"], "CRITICO")
        self.assertIn("RN-02.1", r["reglas"])

    def test_una_condicion_independiente_sola_es_alto(self):
        self.assertEqual(evaluar(Foco(frp=5), Contexto(ndvi=0.3))["nivel"], "ALTO")
        self.assertEqual(evaluar(Foco(frp=5), Contexto(en_anp=True, ndvi=0.8))["nivel"], "ALTO")

    def test_regla_literal_se_puede_reactivar_por_configuracion(self):
        cfg = dict(CONFIG, cercania_sola_genera_alto=True)
        self.assertEqual(evaluar(Foco(frp=5), Contexto(dist_comunidad_km=4, ndvi=0.8), cfg)["nivel"], "ALTO")

    def test_medio_por_frp(self):
        self.assertEqual(evaluar(Foco(frp=10), Contexto(ndvi=0.8))["nivel"], "MEDIO")

    def test_bajo(self):
        self.assertEqual(evaluar(Foco(frp=2), Contexto(ndvi=0.8))["nivel"], "BAJO")

    def test_rn04_fuente_conocida(self):
        r = evaluar(Foco(frp=10), Contexto(en_anp=True, ndvi=0.2, cerca_fuente_conocida=True))
        self.assertEqual(r["nivel"], "BAJO")
        self.assertIn("RN-04", r["reglas"])

    def test_rn04_no_aplica_si_intensidad_extrema(self):
        r = evaluar(Foco(frp=80), Contexto(en_anp=True, ndvi=0.2, cerca_fuente_conocida=True))
        self.assertEqual(r["nivel"], "CRITICO")

    def test_rn05_revision_historica(self):
        r = evaluar(Foco(frp=10, antiguedad_h=7), Contexto())
        self.assertEqual(r["estado"], "REVISION_HISTORICA")
        self.assertIn("RN-05", r["reglas"])

    def test_sin_datos_no_rompe(self):
        self.assertEqual(evaluar(Foco(frp=1), Contexto())["nivel"], "BAJO")


if __name__ == "__main__":
    unittest.main()
