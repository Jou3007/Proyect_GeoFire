"""Restablece la contrasena de un usuario (y lo desbloquea). La contrasena se pide por teclado: no queda en historial ni en chats.

Uso:
  python scripts/restablecer_clave.py          -> base local (Docker)
  python scripts/restablecer_clave.py --nube   -> base de Neon (lee la cadena de .env.nube.txt)
Muestra primero los usuarios registrados, por si no recuerdas el correo.
"""
import getpass
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

if "--nube" in sys.argv:
    for nombre in (".env.nube.txt", ".env.nube"):
        ruta = RAIZ / nombre
        if ruta.exists():
            for linea in ruta.read_text(encoding="utf-8-sig").splitlines():
                if linea.strip().startswith("DATABASE_URL="):
                    os.environ["DATABASE_URL"] = linea.split("=", 1)[1].strip().strip('"').strip("'")
    if not os.getenv("DATABASE_URL"):
        raise SystemExit("No encontre DATABASE_URL en .env.nube.txt")
    print("Base: NUBE (Neon)")
else:
    print("Base: LOCAL")

from geofire import seguridad  # noqa: E402  (se importa despues de fijar DATABASE_URL)

usuarios = seguridad.listar_usuarios()
print("\nUsuarios registrados:")
for u in usuarios:
    estado = "BLOQUEADO" if u["bloqueado"] else ("inactivo" if not u["activo"] else "activo")
    print(f"  - {u['email']}  ({u['rol']}, {estado})")

por_defecto = usuarios[0]["email"] if len(usuarios) == 1 else ""
email = input(f"\nCorreo a restablecer [{por_defecto}]: ").strip() or por_defecto
clave = getpass.getpass(f"Nueva contraseña (mínimo {seguridad.MIN_PASSWORD} caracteres): ")
if clave != getpass.getpass("Repite la contraseña: "):
    raise SystemExit("Las contraseñas no coinciden. No se cambió nada.")
try:
    seguridad.restablecer_por_correo(email, clave)
except ValueError as e:
    raise SystemExit(f"No se cambió nada: {e}")
print(f"Listo: contraseña de {email} restablecida y cuenta desbloqueada.")
