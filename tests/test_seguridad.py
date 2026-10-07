import secrets
import unittest

from geofire import seguridad as seg
from geofire.db import get_connection


class TestHash(unittest.TestCase):
    def test_hash_y_verificacion(self):
        h = seg.hash_password("clave-de-prueba")
        self.assertTrue(seg.verificar_password("clave-de-prueba", h))
        self.assertFalse(seg.verificar_password("otra", h))

    def test_hash_distinto_por_sal(self):
        self.assertNotEqual(seg.hash_password("x"), seg.hash_password("x"))

    def test_hash_corrupto_no_rompe(self):
        self.assertFalse(seg.verificar_password("x", "basura"))


class TestLogin(unittest.TestCase):
    """Usa la base real con un usuario temporal que se borra al final."""

    def setUp(self):
        self.email = f"test-{secrets.token_hex(4)}@geofire.test"
        self.password = secrets.token_urlsafe(12)
        seg.crear_usuario(self.email, "Usuario Prueba", "guardaparque", self.password)

    def tearDown(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM usuarios WHERE email = %s", (self.email,))

    def test_login_correcto(self):
        usuario, _ = seg.autenticar(self.email, self.password)
        self.assertEqual(usuario["rol"], "guardaparque")

    def test_login_incorrecto_no_revela_si_existe(self):
        _, msg1 = seg.autenticar(self.email, "mala")
        _, msg2 = seg.autenticar("no-existe@geofire.test", "mala")
        self.assertTrue(msg1.startswith(seg.MSG_CREDENCIALES))
        self.assertEqual(msg2, seg.MSG_CREDENCIALES)

    def test_bloqueo_tras_5_intentos(self):
        for _ in range(seg.MAX_INTENTOS):
            usuario, _ = seg.autenticar(self.email, "mala")
            self.assertIsNone(usuario)
        usuario, msg = seg.autenticar(self.email, self.password)  # ya con la clave correcta
        self.assertIsNone(usuario)
        self.assertEqual(msg, seg.MSG_BLOQUEADA)

    def test_desbloquear(self):
        for _ in range(seg.MAX_INTENTOS):
            seg.autenticar(self.email, "mala")
        uid = next(u["id"] for u in seg.listar_usuarios() if u["email"] == self.email)
        seg.desbloquear(uid)
        usuario, _ = seg.autenticar(self.email, self.password)
        self.assertIsNotNone(usuario)

    def test_intentos_se_reinician_al_acertar(self):
        seg.autenticar(self.email, "mala")
        seg.autenticar(self.email, self.password)
        for _ in range(seg.MAX_INTENTOS - 1):
            seg.autenticar(self.email, "mala")
        usuario, _ = seg.autenticar(self.email, self.password)
        self.assertIsNotNone(usuario)

    def test_cuenta_inactiva(self):
        uid = next(u["id"] for u in seg.listar_usuarios() if u["email"] == self.email)
        seg.set_activo(uid, False)
        usuario, msg = seg.autenticar(self.email, self.password)
        self.assertIsNone(usuario)
        self.assertEqual(msg, seg.MSG_BLOQUEADA)

    def test_validaciones_de_creacion(self):
        with self.assertRaises(ValueError):
            seg.crear_usuario(self.email, "Dup", "guardaparque", "unaclavelarga")  # duplicado
        with self.assertRaises(ValueError):
            seg.crear_usuario("x@geofire.test", "X", "inventado", "unaclavelarga")
        with self.assertRaises(ValueError):
            seg.crear_usuario("x@geofire.test", "X", "guardaparque", "corta")


class TestPermisos(unittest.TestCase):
    def test_guardaparque_no_administra_usuarios(self):
        self.assertNotIn("usuarios", seg.PERMISOS["guardaparque"])
        self.assertNotIn("usuarios", seg.PERMISOS["autoridad_regional"])
        self.assertIn("usuarios", seg.PERMISOS["administrador"])


if __name__ == "__main__":
    unittest.main()
