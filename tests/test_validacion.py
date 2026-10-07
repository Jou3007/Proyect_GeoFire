import secrets
import unittest
from pathlib import Path

from geofire import validacion as val
from geofire.db import get_connection

JPG = b"\xff\xd8\xff\xe0" + b"0" * 100
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


class TestValidacion(unittest.TestCase):
    """Crea un foco, una alerta y usuarios temporales; todo se borra al final."""

    def setUp(self):
        sufijo = secrets.token_hex(4)
        self.fotos = []
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO focos_calor (fuente, fecha_hora, frp, confianza, geom) "
                "VALUES ('TEST', now(), 5, 'h', ST_SetSRID(ST_MakePoint(-70.0, -5.0), 4326)) RETURNING id"
            )
            self.foco = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO alertas (foco_id, nivel, ndvi, puntaje, estado) "
                "VALUES (%s, 'ALTO', 0.3, 30, 'ACTIVA') RETURNING id", (self.foco,)
            )
            self.alerta = cur.fetchone()[0]
            self.usuarios = {}
            for rol in ("guardaparque", "autoridad_regional", "administrador"):
                cur.execute(
                    "INSERT INTO usuarios (email, rol, password_hash, nombre) VALUES (%s, %s, 'x', %s) RETURNING id",
                    (f"t-{rol}-{sufijo}@geofire.test", rol, rol),
                )
                self.usuarios[rol] = {"id": cur.fetchone()[0], "rol": rol}

    def tearDown(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT foto_url FROM incidentes WHERE alerta_id = %s", (self.alerta,))
            for (ruta,) in cur.fetchall():
                if ruta:
                    Path(val.DIR_FOTOS.parents[1], ruta).unlink(missing_ok=True)
            cur.execute("DELETE FROM incidentes WHERE alerta_id = %s", (self.alerta,))
            cur.execute("DELETE FROM alertas WHERE id = %s", (self.alerta,))
            cur.execute("DELETE FROM focos_calor WHERE id = %s", (self.foco,))
            cur.execute("DELETE FROM usuarios WHERE email LIKE 't-%%@geofire.test'")

    def _estado(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT estado FROM alertas WHERE id = %s", (self.alerta,))
            return cur.fetchone()[0]

    def test_guardaparque_confirma(self):
        val.validar(self.alerta, self.usuarios["guardaparque"], "CONFIRMADA", "Humo visible")
        self.assertEqual(self._estado(), "CONFIRMADA")

    def test_autoridad_marca_falsa_alarma(self):
        val.validar(self.alerta, self.usuarios["autoridad_regional"], "FALSA_ALARMA")
        self.assertEqual(self._estado(), "FALSA_ALARMA")

    def test_administrador_no_puede_validar_rn03(self):
        with self.assertRaises(PermissionError):
            val.validar(self.alerta, self.usuarios["administrador"], "CONFIRMADA")
        self.assertEqual(self._estado(), "ACTIVA")

    def test_no_se_valida_dos_veces(self):
        val.validar(self.alerta, self.usuarios["guardaparque"], "CONFIRMADA")
        with self.assertRaises(ValueError):
            val.validar(self.alerta, self.usuarios["autoridad_regional"], "FALSA_ALARMA")

    def test_estado_invalido(self):
        with self.assertRaises(ValueError):
            val.validar(self.alerta, self.usuarios["guardaparque"], "INCENDIO_CONFIRMADO")

    def test_foto_valida_se_guarda(self):
        val.validar(self.alerta, self.usuarios["guardaparque"], "CONFIRMADA", foto=JPG)
        df = val.validaciones_recientes(self.usuarios["guardaparque"]["id"])
        ruta = Path(val.DIR_FOTOS.parents[1], df.iloc[0]["foto_url"])
        self.assertTrue(ruta.exists())

    def test_foto_png_valida(self):
        val.validar(self.alerta, self.usuarios["guardaparque"], "CONFIRMADA", foto=PNG)

    def test_archivo_que_no_es_imagen_se_rechaza(self):
        with self.assertRaises(ValueError):
            val.validar(self.alerta, self.usuarios["guardaparque"], "CONFIRMADA", foto=b"MZ ejecutable")
        self.assertEqual(self._estado(), "ACTIVA")

    def test_foto_muy_grande(self):
        with self.assertRaises(ValueError):
            val.validar(self.alerta, self.usuarios["guardaparque"], "CONFIRMADA", foto=JPG + b"0" * val.MAX_FOTO_BYTES)

    def test_validada_sale_de_pendientes(self):
        ids = lambda: set(val.pendientes(24)["id"])
        self.assertIn(self.alerta, ids())
        val.validar(self.alerta, self.usuarios["guardaparque"], "CONFIRMADA")
        self.assertNotIn(self.alerta, ids())


if __name__ == "__main__":
    unittest.main()
