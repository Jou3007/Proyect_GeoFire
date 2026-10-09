import io
import secrets
import unittest

from PIL import Image

from geofire import validacion as val
from geofire.db import get_connection
from util_pruebas import borrar_auditoria_de_prueba, imagen_bytes

JUSTIF = "Se observa humo desde el camino"


class TestValidacion(unittest.TestCase):
    """Crea un foco, una alerta y usuarios temporales; todo se borra al final."""

    def setUp(self):
        sufijo = secrets.token_hex(4)
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
            cur.execute("INSERT INTO zonas (nombre, tipo, geom) VALUES ('ZZ Zona validacion', 'distrito', "
                        "ST_Multi(ST_MakeEnvelope(-70.5, -5.5, -69.5, -4.5, 4326))) RETURNING id")
            self.zona = cur.fetchone()[0]  # el guardaparque de prueba tiene asignada la zona donde esta el foco (AC-09.2)
            self.usuarios = {}
            for rol in ("guardaparque", "autoridad_regional", "administrador"):
                correo = f"t-{rol}-{sufijo}@geofire.test"
                cur.execute(
                    "INSERT INTO usuarios (email, rol, password_hash, nombre) VALUES (%s, %s, 'x', %s) RETURNING id",
                    (correo, rol, rol),
                )
                self.usuarios[rol] = {"id": cur.fetchone()[0], "rol": rol, "email": correo, "zona_id": self.zona}

    def tearDown(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM incidentes WHERE alerta_id = %s", (self.alerta,))
            cur.execute("DELETE FROM alertas WHERE id = %s", (self.alerta,))
            cur.execute("DELETE FROM focos_calor WHERE id = %s", (self.foco,))
            cur.execute("DELETE FROM usuarios WHERE email LIKE 't-%%@geofire.test'")
            cur.execute("DELETE FROM zonas WHERE id = %s", (self.zona,))
        borrar_auditoria_de_prueba()

    def _estado(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT estado FROM alertas WHERE id = %s", (self.alerta,))
            return cur.fetchone()[0]

    def test_guardaparque_confirma_con_foto(self):
        val.validar(self.alerta, self.usuarios["guardaparque"], "CONFIRMADA", JUSTIF, foto=imagen_bytes())
        self.assertEqual(self._estado(), "CONFIRMADA")

    def test_confirmar_con_referencia_de_evidencia_sin_foto(self):
        val.validar(self.alerta, self.usuarios["guardaparque"], "CONFIRMADA", JUSTIF, referencia_evidencia="Parte N.° 123")
        self.assertEqual(self._estado(), "CONFIRMADA")

    def test_confirmar_sin_evidencia_se_rechaza_ac_07_1(self):
        with self.assertRaises(ValueError):
            val.validar(self.alerta, self.usuarios["guardaparque"], "CONFIRMADA", JUSTIF)
        self.assertEqual(self._estado(), "ACTIVA")

    def test_falsa_alarma_no_exige_evidencia_pero_si_justificacion(self):
        with self.assertRaises(ValueError):
            val.validar(self.alerta, self.usuarios["autoridad_regional"], "FALSA_ALARMA", "corto")
        val.validar(self.alerta, self.usuarios["autoridad_regional"], "FALSA_ALARMA", JUSTIF)
        self.assertEqual(self._estado(), "FALSA_ALARMA")

    def test_administrador_no_puede_validar_rn03(self):
        with self.assertRaises(PermissionError):
            val.validar(self.alerta, self.usuarios["administrador"], "CONFIRMADA", JUSTIF, foto=imagen_bytes())
        self.assertEqual(self._estado(), "ACTIVA")

    def test_no_se_valida_dos_veces(self):
        val.validar(self.alerta, self.usuarios["guardaparque"], "FALSA_ALARMA", JUSTIF)
        with self.assertRaises(ValueError):
            val.validar(self.alerta, self.usuarios["autoridad_regional"], "FALSA_ALARMA", JUSTIF)

    def test_estado_invalido(self):
        with self.assertRaises(ValueError):
            val.validar(self.alerta, self.usuarios["guardaparque"], "INCENDIO_CONFIRMADO", JUSTIF)

    def test_foto_se_guarda_reprocesada(self):
        val.validar(self.alerta, self.usuarios["guardaparque"], "CONFIRMADA", JUSTIF, foto=imagen_bytes())
        df = val.validaciones_recientes(self.usuarios["guardaparque"]["id"])
        self.assertTrue(df.iloc[0]["tiene_foto"])
        guardada = val.foto(int(df.iloc[0]["id"]))  # la foto vive en la base de datos, no en el disco
        self.assertEqual(Image.open(io.BytesIO(guardada)).format, "JPEG")

    def test_foto_png_valida(self):
        val.validar(self.alerta, self.usuarios["guardaparque"], "CONFIRMADA", JUSTIF, foto=imagen_bytes("PNG"))
        df = val.validaciones_recientes(self.usuarios["guardaparque"]["id"])
        self.assertEqual(Image.open(io.BytesIO(val.foto(int(df.iloc[0]["id"])))).format, "PNG")

    def test_sin_foto_no_hay_bytes(self):
        val.validar(self.alerta, self.usuarios["guardaparque"], "FALSA_ALARMA", JUSTIF)
        df = val.validaciones_recientes(self.usuarios["guardaparque"]["id"])
        self.assertFalse(df.iloc[0]["tiene_foto"])
        self.assertIsNone(val.foto(int(df.iloc[0]["id"])))

    def test_se_quitan_los_metadatos_exif(self):
        original = imagen_bytes(exif=True)
        self.assertTrue(Image.open(io.BytesIO(original)).getexif())  # la imagen de partida si trae EXIF
        limpia, ext = val.procesar_foto(original)
        self.assertEqual(ext, "jpg")
        self.assertFalse(Image.open(io.BytesIO(limpia)).getexif())

    def test_foto_grande_se_reduce(self):
        limpia, _ = val.procesar_foto(imagen_bytes(tamano=(4000, 3000)))
        self.assertLessEqual(max(Image.open(io.BytesIO(limpia)).size), val.MAX_LADO_PX)

    def test_archivo_que_no_es_imagen_se_rechaza(self):
        with self.assertRaises(ValueError):
            val.validar(self.alerta, self.usuarios["guardaparque"], "CONFIRMADA", JUSTIF, foto=b"MZ ejecutable")
        self.assertEqual(self._estado(), "ACTIVA")

    def test_cabecera_jpg_falsa_se_rechaza(self):
        with self.assertRaises(ValueError):  # empieza como JPG pero no es una imagen decodificable
            val.procesar_foto(b"\xff\xd8\xff\xe0" + b"0" * 100)

    def test_gif_se_rechaza(self):
        gif = io.BytesIO()
        Image.new("RGB", (10, 10)).save(gif, format="GIF")
        with self.assertRaises(ValueError):
            val.procesar_foto(gif.getvalue())

    def test_foto_muy_grande(self):
        with self.assertRaises(ValueError):
            val.procesar_foto(imagen_bytes() + b"0" * val.MAX_FOTO_BYTES)

    def test_validada_sale_de_pendientes(self):
        def ids():
            return set(val.pendientes(24)["id"])

        self.assertIn(self.alerta, ids())
        val.validar(self.alerta, self.usuarios["guardaparque"], "FALSA_ALARMA", JUSTIF)
        self.assertNotIn(self.alerta, ids())

    def test_validacion_queda_en_auditoria(self):
        from geofire import auditoria
        val.validar(self.alerta, self.usuarios["guardaparque"], "FALSA_ALARMA", JUSTIF)
        eventos = auditoria.consultar(["ALERTA_VALIDADA"], 50)
        self.assertIn(self.usuarios["guardaparque"]["email"], set(eventos["email"]))


if __name__ == "__main__":
    unittest.main()
