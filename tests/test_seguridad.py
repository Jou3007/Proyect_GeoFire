import hashlib
import secrets
import unittest

from geofire import auditoria
from geofire import seguridad as seg
from geofire.db import get_connection
from util_pruebas import borrar_auditoria_de_prueba


def hash_legado(password):
    """Hash PBKDF2 como el que guardaba la version anterior."""
    sal = b"0123456789abcdef"
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), sal, 200_000)
    return f"pbkdf2_sha256$200000${sal.hex()}${h.hex()}"


class TestHash(unittest.TestCase):
    def test_hash_y_verificacion(self):
        h = seg.hash_password("clave-de-prueba")
        self.assertTrue(seg.verificar_password("clave-de-prueba", h))
        self.assertFalse(seg.verificar_password("otra", h))

    def test_hash_distinto_por_sal(self):
        self.assertNotEqual(seg.hash_password("x"), seg.hash_password("x"))

    def test_hash_corrupto_no_rompe(self):
        self.assertFalse(seg.verificar_password("x", "basura"))

    def test_es_bcrypt_rnf_06(self):
        self.assertTrue(seg.hash_password("clave-de-prueba").startswith("$2"))

    def test_clave_muy_larga_no_se_trunca(self):
        larga = "a" * 100
        h = seg.hash_password(larga)
        self.assertTrue(seg.verificar_password(larga, h))
        self.assertFalse(seg.verificar_password("a" * 99 + "b", h))  # bcrypt a secas ignoraria desde el byte 72

    def test_hash_legado_pbkdf2_sigue_verificando(self):
        h = hash_legado("vieja-clave")
        self.assertTrue(seg.es_legado(h))
        self.assertTrue(seg.verificar_password("vieja-clave", h))
        self.assertFalse(seg.verificar_password("otra", h))


class TestLogin(unittest.TestCase):
    """Usa la base real con un usuario temporal que se borra al final."""

    def setUp(self):
        self.email = f"test-{secrets.token_hex(4)}@geofire.test"
        self.password = secrets.token_urlsafe(12)
        seg.crear_usuario(self.email, "Usuario Prueba", "guardaparque", self.password)

    def tearDown(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM usuarios WHERE email = %s", (self.email,))
        borrar_auditoria_de_prueba()

    def _eventos(self, tipo):
        df = auditoria.consultar([tipo], 200)
        return df[df["email"] == self.email]

    def test_login_correcto_queda_auditado(self):
        seg.autenticar(self.email, self.password)
        self.assertEqual(len(self._eventos("LOGIN_OK")), 1)

    def test_login_fallido_y_bloqueo_quedan_auditados_ac_09_1(self):
        for _ in range(seg.MAX_INTENTOS):
            seg.autenticar(self.email, "mala")
        self.assertEqual(len(self._eventos("LOGIN_FALLIDO")), seg.MAX_INTENTOS)
        self.assertEqual(len(self._eventos("CUENTA_BLOQUEADA")), 1)

    def test_correo_inexistente_tambien_se_audita(self):
        seg.autenticar("fantasma@geofire.test", "mala")
        df = auditoria.consultar(["LOGIN_FALLIDO"], 200)
        self.assertIn("fantasma@geofire.test", set(df["email"]))

    def test_migra_de_pbkdf2_a_bcrypt_al_iniciar_sesion(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("UPDATE usuarios SET password_hash = %s WHERE email = %s", (hash_legado(self.password), self.email))
        usuario, _ = seg.autenticar(self.email, self.password)
        self.assertIsNotNone(usuario)
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT password_hash FROM usuarios WHERE email = %s", (self.email,))
            self.assertTrue(cur.fetchone()[0].startswith("$2"))
        self.assertIsNotNone(seg.autenticar(self.email, self.password)[0])  # y sigue entrando

    def test_acciones_de_administracion_se_auditan(self):
        admin = {"id": 1, "email": f"admin-{self.email}"}
        uid = next(u["id"] for u in seg.listar_usuarios() if u["email"] == self.email)
        seg.set_activo(uid, False, actor=admin)
        seg.set_activo(uid, True, actor=admin)
        seg.cambiar_password(uid, "otra-clave-larga", actor=admin)
        df = auditoria.consultar(None, 500)
        df = df[df["email"] == admin["email"]]
        self.assertEqual(set(df["evento"]), {"USUARIO_DESACTIVADO", "USUARIO_ACTIVADO", "PASSWORD_CAMBIADA"})

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

    def test_solo_el_administrador_ve_la_auditoria(self):
        self.assertIn("auditoria", seg.PERMISOS["administrador"])
        self.assertNotIn("auditoria", seg.PERMISOS["autoridad_regional"])
        self.assertNotIn("auditoria", seg.PERMISOS["guardaparque"])


if __name__ == "__main__":
    unittest.main()
