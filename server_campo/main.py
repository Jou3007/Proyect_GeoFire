"""API pequena para la app movil GeoFire Campo (foto, audio, video, GPS, SOS).

No toca la base de datos principal de GeoFire mas que para leer (login): usa
`geofire.seguridad.autenticar`, la misma funcion que usa la web, para que el
guardaparque entre con su mismo correo y clave. Los reportes de campo y los
archivos se guardan aparte, en server_campo/datos/, en SQLite y en disco, para
no arriesgar nada del esquema de producción mientras esto es un prototipo.

Uso:  uvicorn server_campo.main:app --host 0.0.0.0 --port 8080
"""
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Form, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

CARPETA_DATOS = Path(__file__).resolve().parent / "datos"
CARPETA_EVIDENCIAS = CARPETA_DATOS / "evidencias"
CARPETA_EVIDENCIAS.mkdir(parents=True, exist_ok=True)
BASE_SQLITE = CARPETA_DATOS / "campo.db"

app = FastAPI(title="GeoFire Campo API")


def _conexion():
    conn = sqlite3.connect(BASE_SQLITE)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS reportes_campo ("
        " id TEXT PRIMARY KEY, correo TEXT NOT NULL, tipo TEXT NOT NULL,"
        " latitud REAL, longitud REAL, nota TEXT, marca_tiempo INTEGER NOT NULL,"
        " archivo TEXT, recibido_en TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS ubicaciones_campo ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT, correo TEXT NOT NULL,"
        " latitud REAL NOT NULL, longitud REAL NOT NULL, marca_tiempo INTEGER NOT NULL,"
        " recibido_en TEXT NOT NULL)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ubicaciones_correo ON ubicaciones_campo (correo, marca_tiempo DESC)")
    return conn


class LoginEntrada(BaseModel):
    correo: str
    clave: str


@app.post("/api/campo/login")
def login(datos: LoginEntrada):
    from geofire import seguridad  # import tardio: solo si se usa esta ruta

    usuario, mensaje = seguridad.autenticar(datos.correo, datos.clave)
    if usuario is None:
        return JSONResponse({"ok": False, "mensaje": mensaje}, status_code=401)
    return {"ok": True, "nombre": usuario.get("nombre") or usuario.get("email"), "rol": usuario.get("rol")}


@app.post("/api/campo/reportes")
async def recibir_reporte(
    correo: str = Form(...),
    tipo: str = Form(...),
    latitud: float = Form(...),
    longitud: float = Form(...),
    nota: str = Form(""),
    marca_tiempo: int = Form(...),
    archivo: UploadFile | None = None,
):
    nombre_guardado = None
    if archivo is not None and archivo.filename:
        extension = Path(archivo.filename).suffix or ""
        nombre_guardado = f"{uuid.uuid4().hex}{extension}"
        destino = CARPETA_EVIDENCIAS / nombre_guardado
        contenido = await archivo.read()
        destino.write_bytes(contenido)

    id_reporte = uuid.uuid4().hex
    with _conexion() as conn:
        conn.execute(
            "INSERT INTO reportes_campo (id, correo, tipo, latitud, longitud, nota, marca_tiempo, archivo, recibido_en)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (id_reporte, correo, tipo, latitud, longitud, nota, marca_tiempo, nombre_guardado,
             datetime.now(timezone.utc).isoformat()),
        )
    return {"ok": True, "id": id_reporte}


@app.get("/api/campo/reportes")
def listar_reportes(limite: int = 100):
    """Solo para revisar en la demo; en producción esto se vería desde la web de GeoFire."""
    with _conexion() as conn:
        filas = conn.execute(
            "SELECT id, correo, tipo, latitud, longitud, nota, marca_tiempo, archivo, recibido_en"
            " FROM reportes_campo ORDER BY marca_tiempo DESC LIMIT ?",
            (limite,),
        ).fetchall()
    columnas = ["id", "correo", "tipo", "latitud", "longitud", "nota", "marca_tiempo", "archivo", "recibido_en"]
    return [dict(zip(columnas, fila)) for fila in filas]


class UbicacionEntrada(BaseModel):
    correo: str
    latitud: float
    longitud: float
    marca_tiempo: int


@app.post("/api/campo/ubicacion")
def recibir_ubicacion(datos: UbicacionEntrada):
    with _conexion() as conn:
        conn.execute(
            "INSERT INTO ubicaciones_campo (correo, latitud, longitud, marca_tiempo, recibido_en)"
            " VALUES (?,?,?,?,?)",
            (datos.correo, datos.latitud, datos.longitud, datos.marca_tiempo, datetime.now(timezone.utc).isoformat()),
        )
    return {"ok": True}


@app.get("/api/campo/ubicaciones/ultimas")
def ultimas_ubicaciones():
    """Última posición conocida de cada guardaparque. Usado por el panel de la web (campo_vivo.py)."""
    with _conexion() as conn:
        filas = conn.execute(
            "SELECT correo, latitud, longitud, marca_tiempo, recibido_en FROM ubicaciones_campo u"
            " WHERE marca_tiempo = (SELECT max(marca_tiempo) FROM ubicaciones_campo WHERE correo = u.correo)"
            " ORDER BY marca_tiempo DESC"
        ).fetchall()
    columnas = ["correo", "latitud", "longitud", "marca_tiempo", "recibido_en"]
    return [dict(zip(columnas, fila)) for fila in filas]


@app.get("/api/campo/salud")
def salud():
    return {"ok": True}
