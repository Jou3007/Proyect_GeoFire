import unittest

from geofire import alertas
from geofire.asentamientos import distancias_km
from geofire.db import get_connection

ID_ASENT = -990001  # id inventado: no choca con nodos reales de OpenStreetMap


class TestAsentamientos(unittest.TestCase):
    """Foco de prueba en (-60, -3), lejos de Ucayali, con un caserio a ~5.5 km (0.05 grados)."""

    def setUp(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO asentamientos (id, nombre, tipo, geom) VALUES (%s, 'Caserio de prueba', 'hamlet', "
                "ST_SetSRID(ST_MakePoint(-60.05, -3.0), 4326))", (ID_ASENT,))
            cur.execute(
                "INSERT INTO focos_calor (fuente, fecha_hora, frp, confianza, geom) VALUES "
                "('TEST_ASENT', now(), 5, 'h', ST_SetSRID(ST_MakePoint(-60.0, -3.0), 4326)) RETURNING id")
            self.foco = cur.fetchone()[0]

    def tearDown(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM alertas WHERE foco_id = %s", (self.foco,))
            cur.execute("DELETE FROM focos_calor WHERE id = %s", (self.foco,))
            cur.execute("DELETE FROM asentamientos WHERE id = %s", (ID_ASENT,))

    def _alerta(self, ndvi, en_anp, nivel="ALTO", estado="ACTIVA", notificada=True):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO alertas (foco_id, nivel, ndvi, puntaje, estado, en_anp, notificada) "
                "VALUES (%s, %s, %s, 30, %s, %s, %s) RETURNING id", (self.foco, nivel, ndvi, estado, en_anp, notificada))
            return cur.fetchone()[0]

    def _nivel(self, aid):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT nivel, notificada FROM alertas WHERE id = %s", (aid,))
            return cur.fetchone()

    def test_distancia_en_km(self):
        with get_connection() as conn, conn.cursor() as cur:
            km = distancias_km(cur, [self.foco])[self.foco]
        self.assertAlmostEqual(km, 5.56, delta=0.2)

    def test_filtro_por_tipo(self):
        with get_connection() as conn, conn.cursor() as cur:
            solo_pueblos = distancias_km(cur, [self.foco], tipos=["village", "town", "city"])
        self.assertGreater(solo_pueblos[self.foco], 1000)  # el caserio no cuenta: el pueblo mas cercano esta en Ucayali

    def test_cercania_y_ndvi_seco_pasan_a_critico_y_se_renotifica(self):
        aid = self._alerta(ndvi=0.30, en_anp=False)  # RN-02.3 (NDVI) ya cumplida -> era ALTO
        res = alertas.reevaluar(horas=1)
        self.assertGreaterEqual(res["a_critico"], 1)
        self.assertEqual(self._nivel(aid), ("CRITICO", False))  # 02.1 + 02.3 = Critico, y se vuelve a avisar

    def test_cercania_sola_ya_no_genera_alto(self):
        aid = self._alerta(ndvi=0.80, en_anp=False, nivel="ALTO")  # alerta inflada por la regla anterior
        alertas.reevaluar(horas=1)
        self.assertEqual(self._nivel(aid)[0], "BAJO")  # FRP 5 < p50: sin condiciones agravantes

    def test_alerta_validada_no_se_toca(self):
        aid = self._alerta(ndvi=0.30, en_anp=False, estado="FALSA_ALARMA")
        alertas.reevaluar(horas=1)
        self.assertEqual(self._nivel(aid)[0], "ALTO")


if __name__ == "__main__":
    unittest.main()
