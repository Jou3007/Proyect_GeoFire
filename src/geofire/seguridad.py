"""Autenticacion y usuarios (HU-09, RNF-06). Contrasenas con bcrypt; las antiguas (PBKDF2) se migran al iniciar sesion."""
import base64
import hashlib
import hmac

import bcrypt

from geofire import auditoria
from geofire.db import get_connection

BCRYPT_ROUNDS = 12
ITERACIONES_LEGADO = 200_000
MAX_INTENTOS = 5
MIN_PASSWORD = 8
ROLES = ("administrador", "autoridad_regional", "guardaparque")

# Paginas a las que accede cada rol (HU-09: "acceso denegado a paginas fuera del rol")
PERMISOS = {
    "administrador": ("centro", "mapa", "zonas", "incidentes", "reportes", "geocercas", "usuarios", "auditoria"),
    "autoridad_regional": ("centro", "mapa", "zonas", "incidentes", "validacion", "reportes"),
    "guardaparque": ("validacion", "mapa", "incidentes"),
}

MSG_CREDENCIALES = "Correo o contraseña incorrectos."
MSG_BLOQUEADA = "Cuenta bloqueada o inactiva. Contacta al administrador."


def _prehash(password: str) -> bytes:
    """SHA-256 + base64 antes de bcrypt: evita el limite de 72 bytes y los bytes nulos de bcrypt."""
    return base64.b64encode(hashlib.sha256(password.encode()).digest())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode()


def es_legado(almacenado: str) -> bool:
    return (almacenado or "").startswith("pbkdf2_sha256$")


def verificar_password(password: str, almacenado: str) -> bool:
    try:
        if almacenado.startswith("$2"):
            return bcrypt.checkpw(_prehash(password), almacenado.encode())
        if es_legado(almacenado):
            _, it, sal, h = almacenado.split("$")
            calc = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(sal), int(it))
            return hmac.compare_digest(calc.hex(), h)
    except (ValueError, AttributeError):
        pass
    return False


_HASH_FALSO = hash_password("no-existe")  # iguala el tiempo de respuesta si el correo no existe


def autenticar(email: str, password: str):
    """Devuelve (usuario | None, mensaje). Bloquea la cuenta tras MAX_INTENTOS fallos. Todo intento queda auditado."""
    email = (email or "").strip().lower()
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT u.id, u.email, u.nombre, u.password_hash, u.rol, u.intentos_fallidos, u.bloqueado, u.activo, "
            "u.zona_id, z.nombre FROM usuarios u LEFT JOIN zonas z ON z.id = u.zona_id WHERE lower(u.email) = %s",
            (email,),
        )
        fila = cur.fetchone()
        if fila is None:
            verificar_password(password or "", _HASH_FALSO)
            auditoria.registrar(auditoria.LOGIN_FALLIDO, email=email, detalle={"motivo": "usuario inexistente"})
            return None, MSG_CREDENCIALES
        uid, mail, nombre, ph, rol, intentos, bloqueado, activo, zona_id, zona = fila
        if bloqueado or not activo:
            auditoria.registrar(auditoria.LOGIN_FALLIDO, uid, mail, {"motivo": "cuenta bloqueada o inactiva"})
            return None, MSG_BLOQUEADA
        if verificar_password(password or "", ph):
            cur.execute(
                "UPDATE usuarios SET intentos_fallidos = 0, ultimo_acceso = now() WHERE id = %s", (uid,)
            )
            if es_legado(ph):  # migracion transparente PBKDF2 -> bcrypt
                cur.execute("UPDATE usuarios SET password_hash = %s WHERE id = %s", (hash_password(password), uid))
            auditoria.registrar(auditoria.LOGIN_OK, uid, mail, {"rol": rol})
            return {"id": uid, "email": mail, "nombre": nombre or mail, "rol": rol, "zona_id": zona_id, "zona": zona}, ""
        intentos += 1
        cur.execute(
            "UPDATE usuarios SET intentos_fallidos = %s, bloqueado = %s WHERE id = %s",
            (intentos, intentos >= MAX_INTENTOS, uid),
        )
        auditoria.registrar(auditoria.LOGIN_FALLIDO, uid, mail, {"motivo": "clave incorrecta", "intentos": intentos})
        if intentos >= MAX_INTENTOS:
            auditoria.registrar(auditoria.CUENTA_BLOQUEADA, uid, mail, {"intentos": intentos})
            return None, "Demasiados intentos. Cuenta bloqueada: contacta al administrador."
        return None, f"{MSG_CREDENCIALES} Intentos restantes: {MAX_INTENTOS - intentos}."


def cerrar_sesion(usuario: dict) -> None:
    auditoria.registrar(auditoria.LOGOUT, usuario["id"], usuario["email"])


def acceso_denegado(pagina: str, usuario: dict | None) -> None:
    auditoria.registrar(
        auditoria.ACCESO_DENEGADO, (usuario or {}).get("id"), (usuario or {}).get("email"), {"pagina": pagina}
    )


def crear_usuario(email: str, nombre: str, rol: str, password: str, actor: dict | None = None) -> None:
    email = email.strip().lower()
    if "@" not in email:
        raise ValueError("Correo no válido.")
    if rol not in ROLES:
        raise ValueError("Rol no válido.")
    if len(password) < MIN_PASSWORD:
        raise ValueError(f"La contraseña debe tener al menos {MIN_PASSWORD} caracteres.")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM usuarios WHERE lower(email) = %s", (email,))
        if cur.fetchone():
            raise ValueError("Ya existe un usuario con ese correo.")
        cur.execute(
            "INSERT INTO usuarios (email, nombre, rol, password_hash) VALUES (%s, %s, %s, %s) RETURNING id",
            (email, nombre.strip() or email, rol, hash_password(password)),
        )
        nuevo = cur.fetchone()[0]
    auditoria.registrar(
        auditoria.USUARIO_CREADO, (actor or {}).get("id"), (actor or {}).get("email"),
        {"usuario_id": nuevo, "email": email, "rol": rol},
    )


def listar_usuarios():
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT u.id, u.email, u.nombre, u.rol, u.activo, u.bloqueado, u.intentos_fallidos, u.ultimo_acceso, "
            "u.zona_id, z.nombre AS zona FROM usuarios u LEFT JOIN zonas z ON z.id = u.zona_id ORDER BY u.id"
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, f)) for f in cur.fetchall()]


def alcance(usuario: dict):
    """(restringido, zona_id): el guardaparque solo ve y valida lo de su zona asignada (AC-09.2)."""
    if usuario["rol"] == "guardaparque":
        return True, usuario.get("zona_id")
    return False, None


def asignar_zona(uid: int, zona_id, actor: dict | None = None) -> None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE usuarios SET zona_id = %s WHERE id = %s", (zona_id, uid))
    auditoria.registrar(auditoria.ZONA_ASIGNADA, (actor or {}).get("id"), (actor or {}).get("email"),
                        {"usuario_id": uid, "zona_id": zona_id})


def desbloquear(uid: int, actor: dict | None = None) -> None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE usuarios SET bloqueado = FALSE, intentos_fallidos = 0 WHERE id = %s", (uid,))
    auditoria.registrar(auditoria.USUARIO_DESBLOQUEADO, (actor or {}).get("id"), (actor or {}).get("email"), {"usuario_id": uid})


def set_activo(uid: int, activo: bool, actor: dict | None = None) -> None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE usuarios SET activo = %s WHERE id = %s", (activo, uid))
    evento = auditoria.USUARIO_ACTIVADO if activo else auditoria.USUARIO_DESACTIVADO
    auditoria.registrar(evento, (actor or {}).get("id"), (actor or {}).get("email"), {"usuario_id": uid})


def cambiar_password(uid: int, password: str, actor: dict | None = None) -> None:
    if len(password) < MIN_PASSWORD:
        raise ValueError(f"La contraseña debe tener al menos {MIN_PASSWORD} caracteres.")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE usuarios SET password_hash = %s, bloqueado = FALSE, intentos_fallidos = 0 WHERE id = %s",
            (hash_password(password), uid),
        )
    auditoria.registrar(auditoria.PASSWORD_CAMBIADA, (actor or {}).get("id"), (actor or {}).get("email"), {"usuario_id": uid})
