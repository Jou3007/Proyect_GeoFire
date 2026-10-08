import os
import unittest
from unittest import mock

from geofire import correo
from geofire.db import get_connection

ENTORNO = {"SMTP_USER": "alertas@geofire.test", "SMTP_PASSWORD": "clave-de-prueba",
           "ALERTA_DESTINATARIOS": "uno@geofire.test, dos@geofire.test", "SMTP_HOST": "smtp.prueba", "SMTP_PORT": "587"}


class SmtpFalso:
    enviados = []
    fallar = False

    def __init__(self, host, port, timeout=0):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        pass

    def login(self, usuario, clave):
        if SmtpFalso.fallar:
            raise ConnectionError("servidor SMTP caido")

    def send_message(self, msg):
        SmtpFalso.enviados.append(msg)


class TestCorreo(unittest.TestCase):
    def setUp(self):
        SmtpFalso.enviados, SmtpFalso.fallar = [], False
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO focos_calor (fuente, fecha_hora, frp, geom) VALUES "
                "('TEST_CORREO', now(), 30, ST_SetSRID(ST_MakePoint(-60.5, -3.0), 4326)) RETURNING id")
            self.foco = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO alertas (foco_id, nivel, ndvi, puntaje, estado, en_anp) "
                "VALUES (%s, 'CRITICO', 0.2, 70, 'ACTIVA', true) RETURNING id", (self.foco,))
            self.alerta = cur.fetchone()[0]
        original = correo.alertas_por_notificar
        self._parches = [
            mock.patch.dict(os.environ, ENTORNO),
            mock.patch.object(correo.smtplib, "SMTP", SmtpFalso),
            # solo la alerta de prueba: nunca se marcan como avisadas alertas reales
            mock.patch.object(correo, "alertas_por_notificar",
                              lambda cur, inc=False: [r for r in original(cur, inc) if r[0] == self.alerta]),
            mock.patch.object(correo.auditoria, "registrar"),
        ]
        self.audit = [p.start() for p in self._parches][-1]

    def tearDown(self):
        for p in self._parches:
            p.stop()
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM notificaciones WHERE alerta_id = %s", (self.alerta,))
            cur.execute("DELETE FROM alertas WHERE id = %s", (self.alerta,))
            cur.execute("DELETE FROM focos_calor WHERE id = %s", (self.foco,))

    def _notificaciones(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT resultado, destinatarios, detalle, enviada_en FROM notificaciones WHERE alerta_id = %s", (self.alerta,))
            return cur.fetchall()

    def _notificada(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT notificada FROM alertas WHERE id = %s", (self.alerta,))
            return cur.fetchone()[0]

    def test_envio_correcto_registra_fecha_y_resultado_ac_06_3(self):
        self.assertEqual(correo.enviar_alertas(), 1)
        self.assertEqual(len(SmtpFalso.enviados), 1)
        resultado, destinatarios, detalle, fecha = self._notificaciones()[0]
        self.assertEqual(resultado, "ENVIADO")
        self.assertEqual(destinatarios, ["uno@geofire.test", "dos@geofire.test"])
        self.assertIsNotNone(fecha)
        self.assertTrue(self._notificada())

    def test_no_se_duplica_la_alerta(self):
        correo.enviar_alertas()
        self.assertEqual(correo.enviar_alertas(), 0)  # ya notificada: no vuelve a salir
        self.assertEqual(len(SmtpFalso.enviados), 1)
        self.assertEqual(len(self._notificaciones()), 1)

    def test_si_el_servidor_falla_se_registra_el_error_y_se_reintenta(self):
        SmtpFalso.fallar = True
        with self.assertRaises(ConnectionError):
            correo.enviar_alertas()
        resultado, _, detalle, _ = self._notificaciones()[0]
        self.assertEqual(resultado, "ERROR")
        self.assertIn("servidor SMTP caido", detalle)
        self.assertFalse(self._notificada())  # sigue pendiente
        SmtpFalso.fallar = False
        self.assertEqual(correo.enviar_alertas(), 1)  # el siguiente ciclo la envia
        self.assertEqual([n[0] for n in self._notificaciones()], ["ERROR", "ENVIADO"])
        eventos = [c.args[0] for c in self.audit.call_args_list]
        self.assertEqual(eventos, ["CORREO_ERROR", "CORREO_ENVIADO"])

    def test_simulacro_no_envia_ni_registra(self):
        self.assertEqual(correo.enviar_alertas(dry_run=True), 1)
        self.assertEqual(SmtpFalso.enviados, [])
        self.assertEqual(self._notificaciones(), [])
        self.assertFalse(self._notificada())

    def test_contenido_del_mensaje(self):
        correo.enviar_alertas()
        msg = SmtpFalso.enviados[0]
        self.assertIn("[CRITICA]", msg["Subject"])
        cuerpo = msg.get_content()
        self.assertIn("google.com/maps?q=-3.00000,-60.50000", cuerpo)
        self.assertIn("Area Natural Protegida", cuerpo)
        self.assertIn("RN-03", cuerpo)

    def test_sin_alertas_no_envia(self):
        correo.enviar_alertas()
        SmtpFalso.enviados.clear()
        correo.enviar_alertas()
        self.assertEqual(SmtpFalso.enviados, [])


if __name__ == "__main__":
    unittest.main()
