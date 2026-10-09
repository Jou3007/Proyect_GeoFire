"""Arma los secretos para la nube a partir de tus archivos locales, SIN mostrarlos en pantalla.

Lee:  .env (clave de NASA, correo)  ·  .env.nube.txt (DATABASE_URL de Neon)  ·  clave-ee.json (cuenta de servicio de Google)
Escribe (ambos ignorados por git):
  .streamlit/secrets.toml          -> se copia y pega en Streamlit Cloud (Settings > Secrets)
  .streamlit/github_secretos.txt   -> un bloque por secreto, para pegarlos en GitHub (Settings > Secrets and variables > Actions)

Uso: python scripts/generar_secretos.py
"""
import json
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SALIDA_ST = RAIZ / ".streamlit" / "secrets.toml"
SALIDA_GH = RAIZ / ".streamlit" / "github_secretos.txt"


def leer_env(ruta):
    datos = {}
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8-sig").splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                k, v = linea.split("=", 1)
                datos[k.strip()] = v.strip().strip('"').strip("'")
    return datos


env = leer_env(RAIZ / ".env")
nube = leer_env(RAIZ / ".env.nube.txt") or leer_env(RAIZ / ".env.nube")
faltan = []

valores = {
    "DATABASE_URL": nube.get("DATABASE_URL"),
    "NASA_FIRMS_MAP_KEY": env.get("NASA_FIRMS_MAP_KEY"),
    "GEE_PROJECT": env.get("GEE_PROJECT"),
    "SMTP_USER": env.get("SMTP_USER"),
    "SMTP_PASSWORD": env.get("SMTP_PASSWORD"),
    "ALERTA_DESTINATARIOS": env.get("ALERTA_DESTINATARIOS"),
}
for k, v in valores.items():
    if not v:
        faltan.append(k)

cuenta = None
ruta_json = RAIZ / "clave-ee.json"
if ruta_json.exists():
    cuenta = json.loads(ruta_json.read_text(encoding="utf-8"))
    if cuenta.get("type") != "service_account" or "private_key" not in cuenta:
        raise SystemExit("clave-ee.json no parece la clave JSON de una cuenta de servicio de Google.")
else:
    faltan.append("GEE_SERVICE_ACCOUNT (falta el archivo clave-ee.json)")

# ---- Streamlit: TOML. json.dumps produce cadenas validas en TOML (escapa los saltos de linea de la clave privada)
lineas = [f"{k} = {json.dumps(v)}" for k, v in valores.items() if v]
lineas.append('SMTP_HOST = "smtp.gmail.com"')
lineas.append('SMTP_PORT = "587"')
if cuenta:
    lineas.append("")
    lineas.append("[GEE_SERVICE_ACCOUNT]")
    for campo in ("type", "project_id", "private_key_id", "private_key", "client_email", "client_id", "token_uri"):
        if campo in cuenta:
            lineas.append(f"{campo} = {json.dumps(cuenta[campo])}")
texto = "\n".join(lineas) + "\n"
tomllib.loads(texto)  # comprueba que el TOML es valido antes de guardarlo
SALIDA_ST.parent.mkdir(exist_ok=True)
SALIDA_ST.write_text(texto, encoding="utf-8")

# ---- GitHub Actions: nombre y valor de cada secreto
bloques = []
for k, v in valores.items():
    if v:
        bloques.append(f"=== {k} ===\n{v}\n")
if cuenta:
    bloques.append(f"=== GEE_SERVICE_ACCOUNT ===\n{json.dumps(cuenta)}\n")
bloques.append("=== (variable, no secreto) CICLO_ACTIVO ===\ntrue\n")
SALIDA_GH.write_text("\n".join(bloques), encoding="utf-8")

print(f"Escrito {SALIDA_ST.relative_to(RAIZ)} ({len(lineas)} lineas) y {SALIDA_GH.relative_to(RAIZ)}. Ninguno se sube a git.")
if faltan:
    print("Faltan: " + "; ".join(faltan))
