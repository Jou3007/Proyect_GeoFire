"""Crea un usuario pidiendo la contrasena por teclado (no queda en el historial ni en archivos).
Uso: docker compose run --rm app python scripts/crear_usuario.py
"""
import getpass

from geofire.seguridad import ROLES, crear_usuario

email = input("Correo: ").strip()
nombre = input("Nombre: ").strip()
print("Roles:", ", ".join(ROLES))
rol = input("Rol [administrador]: ").strip() or "administrador"
password = getpass.getpass("Contraseña (mínimo 8 caracteres): ")
if password != getpass.getpass("Repite la contraseña: "):
    raise SystemExit("Las contraseñas no coinciden.")
crear_usuario(email, nombre, rol, password)
print(f"Usuario {email} creado con rol {rol}.")
