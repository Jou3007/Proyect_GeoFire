"""Streamlit Cloud guarda las claves en st.secrets; el resto del codigo las lee de variables de entorno.
cargar() copia los secretos a os.environ (sin pisar lo que ya este definido, p. ej. por Docker o .env)."""
import json
import os

import streamlit as st

CLAVES = (
    "DATABASE_URL", "POSTGRES_SSLMODE", "NASA_FIRMS_MAP_KEY", "GEE_PROJECT", "GEE_SERVICE_ACCOUNT",
    "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "ALERTA_DESTINATARIOS",
)


def cargar():
    try:
        secretos = st.secrets
        disponibles = set(secretos.keys())
    except Exception:  # sin archivo de secretos (ejecucion local): no hay nada que copiar
        return []
    copiadas = []
    for clave in CLAVES:
        if clave in disponibles and not os.getenv(clave):
            valor = secretos[clave]
            # la cuenta de servicio de Google puede pegarse como tabla TOML: se convierte a JSON
            os.environ[clave] = valor if isinstance(valor, str) else json.dumps(dict(valor))
            copiadas.append(clave)
    return copiadas
