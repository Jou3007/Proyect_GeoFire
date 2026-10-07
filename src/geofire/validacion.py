"""Validacion humana del incidente en campo (HU-07, RN-03).

Solo guardaparques y autoridad regional pueden confirmar una alerta o marcarla como falsa alarma.
El nivel de riesgo no cambia: se guarda aparte el estado de validacion.
"""
from datetime import datetime
from pathlib import Path

from geofire.db import get_connection
from geofire.repositorio import _query

ROLES_VALIDADORES = ("guardaparque", "autoridad_regional")
ESTADOS = ("CONFIRMADA", "FALSA_ALARMA")
DIR_FOTOS = Path(__file__).resolve().parents[2] / "data" / "fotos"
MAX_FOTO_BYTES = 5 * 1024 * 1024


def _extension_foto(datos: bytes):
    """Detecta el tipo real por los primeros bytes (no confia en el nombre del archivo)."""
    if datos[:3] == b"\xff\xd8\xff":
        return "jpg"
    if datos[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    return None


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
        "SELECT i.id, i.alerta_id, i.estado, i.comentario, i.foto_url, i.validado_en, u.nombre AS validador, "
        "a.nivel, ST_Y(f.geom) AS lat, ST_X(f.geom) AS lon "
        "FROM incidentes i JOIN alertas a ON a.id = i.alerta_id JOIN focos_calor f ON f.id = a.foco_id "
        "LEFT JOIN usuarios u ON u.id = i.usuario_id "
        "WHERE (%s::int IS NULL OR i.usuario_id = %s) ORDER BY i.validado_en DESC LIMIT %s",
        (usuario_id, usuario_id, limite),
    )


def validar(alerta_id, usuario, estado, comentario="", foto=None):
    """Registra la validacion. `usuario` es el dict de sesion (id, rol). `foto` son bytes o None."""
    if usuario["rol"] not in ROLES_VALIDADORES:
        raise PermissionError("Solo guardaparques o autoridad regional pueden validar alertas (RN-03).")
    if estado not in ESTADOS:
        raise ValueError("Estado no válido.")
    comentario = (comentario or "").strip()[:1000]

    ruta_foto = None
    if foto:
        if len(foto) > MAX_FOTO_BYTES:
            raise ValueError("La foto supera 5 MB.")
        ext = _extension_foto(foto)
        if ext is None:
            raise ValueError("La foto debe ser JPG o PNG.")

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT estado FROM alertas WHERE id = %s FOR UPDATE", (alerta_id,))
        fila = cur.fetchone()
        if fila is None:
            raise ValueError("La alerta no existe.")
        if fila[0] in ESTADOS:
            raise ValueError("Esta alerta ya fue validada por otra persona.")
        if foto:
            DIR_FOTOS.mkdir(parents=True, exist_ok=True)
            nombre = f"alerta-{alerta_id}-{datetime.now():%Y%m%d%H%M%S}.{ext}"
            (DIR_FOTOS / nombre).write_bytes(foto)
            ruta_foto = f"data/fotos/{nombre}"
        cur.execute(
            "INSERT INTO incidentes (alerta_id, estado, comentario, foto_url, usuario_id, validado_en) "
            "VALUES (%s, %s, %s, %s, %s, now())",
            (alerta_id, estado, comentario or None, ruta_foto, usuario["id"]),
        )
        cur.execute("UPDATE alertas SET estado = %s WHERE id = %s", (estado, alerta_id))
