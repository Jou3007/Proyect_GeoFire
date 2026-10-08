"""Utilidades compartidas por las pruebas."""
import io

from PIL import Image

from geofire.db import get_connection

MARCA_CICLO = "zz_test_"  # prefijo de los pasos de ciclo inventados por las pruebas


def imagen_bytes(formato="JPEG", tamano=(40, 30), color=(200, 30, 30), exif=False):
    """Una imagen real y minima en memoria (para probar la validacion de fotos)."""
    img = Image.new("RGB", tamano, color)
    salida = io.BytesIO()
    if exif and formato == "JPEG":
        info = Image.Exif()
        info[0x010E] = "descripcion secreta"  # ImageDescription
        img.save(salida, format=formato, exif=info)
    else:
        img.save(salida, format=formato)
    return salida.getvalue()


def borrar_auditoria_de_prueba():
    """Borra SOLO los eventos creados por las pruebas (correos @geofire.test o pasos zz_test_).
    La tabla es inmutable; el permiso se concede unicamente dentro de esta transaccion."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL geofire.permitir_borrado = 'on'")
        cur.execute(
            "DELETE FROM log_auditoria WHERE email LIKE %s OR detalle::text LIKE %s OR detalle::text LIKE %s",
            ("%@geofire.test", f"%{MARCA_CICLO}%", "%@geofire.test%"),
        )
        # acciones sobre usuarios de prueba ya borrados (sin actor): su usuario_id ya no existe en la tabla
        cur.execute(
            "DELETE FROM log_auditoria WHERE email IS NULL AND detalle ? 'usuario_id' "
            "AND (detalle->>'usuario_id')::int NOT IN (SELECT id FROM usuarios)"
        )
