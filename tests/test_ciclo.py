import unittest

from geofire import auditoria, ciclo
from geofire.db import get_connection
from util_pruebas import MARCA_CICLO, borrar_auditoria_de_prueba

SIN_ESPERA = (0, 0)
P_ING, P_EVAL, P_CORREO = (MARCA_CICLO + n for n in ("ingesta", "evaluacion", "correo"))


def roto():
    raise RuntimeError("NASA no responde")


class TestCiclo(unittest.TestCase):
    def setUp(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT coalesce(max(id), 0) FROM ejecuciones")
            self.id_base = cur.fetchone()[0]

    def tearDown(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM ejecuciones WHERE id > %s AND detalle::text LIKE %s", (self.id_base, f"%{MARCA_CICLO}%"))
        borrar_auditoria_de_prueba()

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
        detalle = ciclo.ejecutar([(P_ING, roto), (P_EVAL, lambda: 5), (P_CORREO, lambda: 0)], SIN_ESPERA)
        self.assertEqual(detalle["estado"], "PARCIAL")
        self.assertFalse(detalle[P_ING]["ok"])
        self.assertIn("NASA no responde", detalle[P_ING]["error"])
        self.assertTrue(detalle[P_EVAL]["ok"])
        self.assertTrue(detalle[P_CORREO]["ok"])

    def test_todo_bien(self):
        self.assertEqual(ciclo.ejecutar([(P_ING, lambda: 1), (P_EVAL, lambda: 2)], SIN_ESPERA)["estado"], "OK")

    def test_todo_mal_es_error(self):
        self.assertEqual(ciclo.ejecutar([(P_ING, roto), (P_EVAL, roto)], SIN_ESPERA)["estado"], "ERROR")

    def test_queda_registrado(self):
        ciclo.ejecutar([(P_ING, lambda: 1)], SIN_ESPERA)
        fin, estado = ciclo.ultima_ejecucion()
        self.assertEqual(estado, "OK")

    def test_errores_y_resumen_quedan_en_auditoria_rnf_08(self):
        ciclo.ejecutar([(P_ING, roto), (P_EVAL, lambda: 5)], SIN_ESPERA)
        errores = auditoria.consultar(["ERROR_API"], 100)
        self.assertTrue(any(MARCA_CICLO in str(d) and "NASA no responde" in str(d) for d in errores["detalle"]))
        ciclos = auditoria.consultar(["CICLO"], 100)
        self.assertTrue(any(MARCA_CICLO in str(d) for d in ciclos["detalle"]))


if __name__ == "__main__":
    unittest.main()
