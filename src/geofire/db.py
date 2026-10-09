import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    # En la nube (GitHub Actions / Streamlit Cloud) se usa DATABASE_URL con SSL, como indica el informe (cap. 11.7).
    url = os.getenv("DATABASE_URL")
    if url:
        return psycopg2.connect(url, sslmode=os.getenv("POSTGRES_SSLMODE", "require"))
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "geofire"),
        user=os.getenv("POSTGRES_USER", "geofire"),
        password=os.getenv("POSTGRES_PASSWORD", "geofire_dev"),
    )
