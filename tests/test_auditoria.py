import secrets
import unittest

import psycopg2

from geofire import auditoria
from geofire.db import get_connection
from util_pruebas import borrar_auditoria_de_prueba


class TestAuditoria(unittest.TestCase):
    def setUp(self):
        self.email = f"aud-{secrets.token_hex(4)}@geofire.test"

    def tearDown(self):
        borrar_auditoria_de_prueba()

    def _id(self):
        auditoria.registrar("EVENTO_PRUEBA", 7, self.email, {"clave": "valor"})
        df = auditoria.consultar(["EVENTO_PRUEBA"], 50)
        return int(df[df["email"] == self.email]["id"].iloc[0])

    def test_registrar_y_consultar(self):
        auditoria.registrar("EVENTO_PRUEBA", 7, self.email, {"clave": "valor"})
        fila = auditoria.consultar(["EVENTO_PRUEBA"], 50).query("email == @self.email").iloc[0]
        self.assertEqual(fila["usuario_id"], 7)
        self.assertEqual(fila["detalle"], {"clave": "valor"})

    def test_no_se_puede_modificar_rnf_08(self):
        i = self._id()
        with self.assertRaises(psycopg2.Error):
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute("UPDATE log_auditoria SET evento = 'ALTERADO' WHERE id = %s", (i,))

    def test_no_se_puede_borrar_rnf_08(self):
        i = self._id()
        with self.assertRaises(psycopg2.Error):
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute("DELETE FROM log_auditoria WHERE id = %s", (i,))
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM log_auditoria WHERE id = %s", (i,))
            self.assertEqual(cur.fetchone()[0], 1)

    def test_un_fallo_del_log_no_rompe_la_accion(self):
        # detalle no serializable a JSON de forma normal: registrar() lo convierte con str() y no lanza
        auditoria.registrar("EVENTO_PRUEBA", None, self.email, {"objeto": object()})

    def test_filtro_por_tipo(self):
        self._id()
        otros = auditoria.consultar(["LOGIN_OK"], 50)
        self.assertNotIn(self.email, set(otros["email"]))


if __name__ == "__main__":
    unittest.main()
