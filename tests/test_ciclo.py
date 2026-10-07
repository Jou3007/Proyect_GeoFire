import unittest

from geofire import ciclo
from geofire.db import get_connection

SIN_ESPERA = (0, 0)


class TestCiclo(unittest.TestCase):
    def setUp(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT coalesce(max(id), 0) FROM ejecuciones")
            self.id_base = cur.fetchone()[0]

    def tearDown(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM ejecuciones WHERE id > %s", (self.id_base,))

    def test_reintenta_y_termina_bien_al_tercer_intento(self):
        llamadas = []

        def inestable():
            llamadas.append(1)
            if len(llamadas) < 3:
                raise ConnectionError("sin red")
            return "ok"

        resultado, intentos = ciclo.reintentar(inestable, SIN_ESPERA)
        self.assertEqual((resultado, intentos), ("ok", 3))

    def test_si_siempre_falla_propaga_el_error(self):
        with self.assertRaises(ConnectionError):
            ciclo.reintentar(lambda: (_ for _ in ()).throw(ConnectionError("x")), SIN_ESPERA)

    def test_un_paso_caido_no_detiene_el_ciclo(self):
        def roto():
            raise RuntimeError("NASA no responde")

        detalle = ciclo.ejecutar([("ingesta", roto), ("evaluacion", lambda: 5), ("correo", lambda: 0)], SIN_ESPERA)
        self.assertEqual(detalle["estado"], "PARCIAL")
        self.assertFalse(detalle["ingesta"]["ok"])
        self.assertIn("NASA no responde", detalle["ingesta"]["error"])
        self.assertTrue(detalle["evaluacion"]["ok"])
        self.assertTrue(detalle["correo"]["ok"])

    def test_todo_bien(self):
        detalle = ciclo.ejecutar([("a", lambda: 1), ("b", lambda: 2)], SIN_ESPERA)
        self.assertEqual(detalle["estado"], "OK")

    def test_todo_mal_es_error(self):
        def roto():
            raise RuntimeError("x")

        self.assertEqual(ciclo.ejecutar([("a", roto), ("b", roto)], SIN_ESPERA)["estado"], "ERROR")

    def test_queda_registrado(self):
        ciclo.ejecutar([("a", lambda: 1)], SIN_ESPERA)
        fin, estado = ciclo.ultima_ejecucion()
        self.assertEqual(estado, "OK")


if __name__ == "__main__":
    unittest.main()
