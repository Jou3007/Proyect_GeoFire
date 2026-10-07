"""Autenticacion y usuarios (HU-09). Contrasenas con PBKDF2-SHA256 (solo libreria estandar)."""
import hashlib
import hmac
import os

from geofire.db import get_connection

ITERACIONES = 200_000
MAX_INTENTOS = 5
MIN_PASSWORD = 8
ROLES = ("administrador", "autoridad_regional", "guardaparque")

# Paginas a las que accede cada rol (HU-09: "acceso denegado a paginas fuera del rol")
PERMISOS = {
    "administrador": ("centro", "mapa", "incidentes", "reportes", "usuarios"),
    "autoridad_regional": ("centro", "mapa", "incidentes", "validacion", "reportes"),
    "guardaparque": ("validacion", "mapa", "incidentes"),
}

MSG_CREDENCIALES = "Correo o contraseña incorrectos."
MSG_BLOQUEADA = "Cuenta bloqueada o inactiva. Contacta al administrador."


def hash_password(password: str) -> str:
    sal = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), sal, ITERACIONES)
    return f"pbkdf2_sha256${ITERACIONES}${sal.hex()}${h.hex()}"


def verificar_password(password: str, almacenado: str) -> bool:
    try:
        _, it, sal, h = almacenado.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(sal), int(it))
        return hmac.compare_digest(calc.hex(), h)
    except (ValueError, AttributeError):
        return False


_HASH_FALSO = hash_password("no-existe")  # iguala el tiempo de respuesta si el correo no existe


def autenticar(email: str, password: str):
    """Devuelve (usuario | None, mensaje). Bloquea la cuenta tras MAX_INTENTOS fallos."""
    email = (email or "").strip().lower()
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, email, nombre, password_hash, rol, intentos_fallidos, bloqueado, activo "
            "FROM usuarios WHERE lower(email) = %s",
            (email,),
        )
        fila = cur.fetchone()
        if fila is None:
            verificar_password(password or "", _HASH_FALSO)
            return None, MSG_CREDENCIALES
        uid, mail, nombre, ph, rol, intentos, bloqueado, activo = fila
        if bloqueado or not activo:
            return None, MSG_BLOQUEADA
        if verificar_password(password or "", ph):
            cur.execute(
                "UPDATE usuarios SET intentos_fallidos = 0, ultimo_acceso = now() WHERE id = %s", (uid,)
            )
            return {"id": uid, "email": mail, "nombre": nombre or mail, "rol": rol}, ""
        intentos += 1
        cur.execute(
            "UPDATE usuarios SET intentos_fallidos = %s, bloqueado = %s WHERE id = %s",
            (intentos, intentos >= MAX_INTENTOS, uid),
        )
        if intentos >= MAX_INTENTOS:
            return None, "Demasiados intentos. Cuenta bloqueada: contacta al administrador."
        return None, f"{MSG_CREDENCIALES} Intentos restantes: {MAX_INTENTOS - intentos}."


def crear_usuario(email: str, nombre: str, rol: str, password: str) -> None:
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
            "INSERT INTO usuarios (email, nombre, rol, password_hash) VALUES (%s, %s, %s, %s)",
            (email, nombre.strip() or email, rol, hash_password(password)),
        )


def listar_usuarios():
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, email, nombre, rol, activo, bloqueado, intentos_fallidos, ultimo_acceso "
            "FROM usuarios ORDER BY id"
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, f)) for f in cur.fetchall()]


def desbloquear(uid: int) -> None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE usuarios SET bloqueado = FALSE, intentos_fallidos = 0 WHERE id = %s", (uid,))


def set_activo(uid: int, activo: bool) -> None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE usuarios SET activo = %s WHERE id = %s", (activo, uid))


def cambiar_password(uid: int, password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise ValueError(f"La contraseña debe tener al menos {MIN_PASSWORD} caracteres.")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE usuarios SET password_hash = %s, bloqueado = FALSE, intentos_fallidos = 0 WHERE id = %s",
            (hash_password(password), uid),
        )
