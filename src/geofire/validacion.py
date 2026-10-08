"""Validacion humana del incidente en campo (HU-07, RN-03, AC-07.1).

Solo guardaparques y autoridad regional pueden confirmar una alerta o marcarla como falsa alarma.
Toda revision exige una justificacion; confirmar un incendio exige ademas evidencia (foto o referencia).
El nivel de riesgo no cambia: se guarda aparte el estado de validacion.
"""
import io
from datetime import datetime
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from geofire import auditoria
from geofire.db import get_connection
from geofire.repositorio import _query

ROLES_VALIDADORES = ("guardaparque", "autoridad_regional")
ESTADOS = ("CONFIRMADA", "FALSA_ALARMA")
DIR_FOTOS = Path(__file__).resolve().parents[2] / "data" / "fotos"
MAX_FOTO_BYTES = 5 * 1024 * 1024
MAX_LADO_PX = 2000
MIN_JUSTIFICACION = 10
FORMATOS = {"JPEG": "jpg", "PNG": "png"}


def procesar_foto(datos: bytes):
    """Valida que sea una imagen real JPG/PNG y la vuelve a guardar con Pillow (quita metadatos y contenido
    oculto, limita el tamano). Devuelve (bytes_limpios, extension)."""
    if len(datos) > MAX_FOTO_BYTES:
        raise ValueError("La foto supera 5 MB.")
    try:
        img = Image.open(io.BytesIO(datos))
        formato = img.format
        img.verify()
        img = Image.open(io.BytesIO(datos))  # verify() deja la imagen inutilizable: se reabre
        img.load()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        raise ValueError("La foto debe ser una imagen JPG o PNG válida.") from None
    if formato not in FORMATOS:
        raise ValueError("La foto debe ser JPG o PNG.")
    img.thumbnail((MAX_LADO_PX, MAX_LADO_PX))
    if formato == "JPEG" and img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    salida = io.BytesIO()
    img.save(salida, format=formato)  # sin EXIF ni otros metadatos
    return salida.getvalue(), FORMATOS[formato]


def pendientes(horas=72):
    """Alertas Alto/Critico que aun no tienen validacion humana."""
    return _query(
        "SELECT a.id, a.nivel, a.puntaje, a.estado, a.ndvi, a.en_anp, f.fecha_hora, f.frp, "
        "ST_Y(f.geom) AS lat, ST_X(f.geom) AS lon "
        "FROM alertas a JOIN focos_calor f ON f.id = a.foco_id "
        "WHERE a.nivel IN ('ALTO', 'CRITICO') AND a.estado IN ('ACTIVA', 'REVISION_HISTORICA') "
        "AND f.fecha_hora >= now() - make_interval(hours => %s) "
        "ORDER BY CASE a.nivel WHEN 'CRITICO' THEN 0 ELSE 1 END, f.fecha_hora DESC",
        (horas,),
    )


def validaciones_recientes(usuario_id=None, limite=10):
    return _query(
        "SELECT i.id, i.alerta_id, i.estado, i.comentario, i.foto_url, i.referencia_evidencia, i.validado_en, "
        "u.nombre AS validador, a.nivel, ST_Y(f.geom) AS lat, ST_X(f.geom) AS lon "
        "FROM incidentes i JOIN alertas a ON a.id = i.alerta_id JOIN focos_calor f ON f.id = a.foco_id "
        "LEFT JOIN usuarios u ON u.id = i.usuario_id "
        "WHERE (%s::int IS NULL OR i.usuario_id = %s) ORDER BY i.validado_en DESC LIMIT %s",
        (usuario_id, usuario_id, limite),
    )


def validar(alerta_id, usuario, estado, comentario="", foto=None, referencia_evidencia=""):
    """Registra la validacion. `usuario` es el dict de sesion (id, rol, email). `foto` son bytes o None."""
    if usuario["rol"] not in ROLES_VALIDADORES:
        auditoria.registrar(auditoria.ACCESO_DENEGADO, usuario.get("id"), usuario.get("email"),
                            {"accion": "validar alerta", "alerta_id": alerta_id})
        raise PermissionError("Solo guardaparques o autoridad regional pueden validar alertas (RN-03).")
    if estado not in ESTADOS:
        raise ValueError("Estado no válido.")
    comentario = (comentario or "").strip()[:1000]
    referencia = (referencia_evidencia or "").strip()[:300]
    if len(comentario) < MIN_JUSTIFICACION:
        raise ValueError(f"Escribe una justificación de al menos {MIN_JUSTIFICACION} caracteres.")
    if estado == "CONFIRMADA" and not foto and not referencia:
        raise ValueError("Para confirmar un incendio adjunta una foto o una referencia de evidencia.")

    foto_limpia = ext = None
    if foto:
        foto_limpia, ext = procesar_foto(foto)

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT estado FROM alertas WHERE id = %s FOR UPDATE", (alerta_id,))
        fila = cur.fetchone()
        if fila is None:
            raise ValueError("La alerta no existe.")
        if fila[0] in ESTADOS:
            raise ValueError("Esta alerta ya fue validada por otra persona.")
        ruta_foto = None
        if foto_limpia:
            DIR_FOTOS.mkdir(parents=True, exist_ok=True)
            nombre = f"alerta-{alerta_id}-{datetime.now():%Y%m%d%H%M%S}.{ext}"
            (DIR_FOTOS / nombre).write_bytes(foto_limpia)
            ruta_foto = f"data/fotos/{nombre}"
        cur.execute(
            "INSERT INTO incidentes (alerta_id, estado, comentario, foto_url, referencia_evidencia, usuario_id, validado_en) "
            "VALUES (%s, %s, %s, %s, %s, %s, now())",
            (alerta_id, estado, comentario, ruta_foto, referencia or None, usuario["id"]),
        )
        cur.execute("UPDATE alertas SET estado = %s WHERE id = %s", (estado, alerta_id))
    auditoria.registrar(
        auditoria.ALERTA_VALIDADA, usuario["id"], usuario.get("email"),
        {"alerta_id": alerta_id, "estado": estado, "con_foto": bool(foto_limpia), "con_referencia": bool(referencia)},
    )
