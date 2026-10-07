"""Envio de alertas por correo (HU-06). Un resumen por corrida con los focos Alto/Critico nuevos."""
import os
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv

from geofire.db import get_connection

load_dotenv()

MAX_EN_CORREO = 25
ORDEN = {"CRITICO": 0, "ALTO": 1}


def alertas_por_notificar(cur, incluir_historicas=False):
    estados = "('ACTIVA', 'REVISION_HISTORICA')" if incluir_historicas else "('ACTIVA')"
    cur.execute(
        "SELECT a.id, a.nivel, a.puntaje, a.ndvi, a.en_anp, a.estado, f.fecha_hora, f.frp, "
        "ST_Y(f.geom), ST_X(f.geom) "
        "FROM alertas a JOIN focos_calor f ON f.id = a.foco_id "
        f"WHERE a.nivel IN ('ALTO', 'CRITICO') AND NOT a.notificada AND a.estado IN {estados} "
        "ORDER BY a.puntaje DESC NULLS LAST, f.fecha_hora DESC"
    )
    return cur.fetchall()


def armar_mensaje(alertas, remitente, destinatarios):
    criticas = sum(1 for a in alertas if a[1] == "CRITICO")
    asunto = f"[GeoFire-Peru] {len(alertas)} alerta(s) de incendio en Ucayali"
    if criticas:
        asunto = f"[CRITICA] {asunto}"
    lineas = [f"Se detectaron {len(alertas)} foco(s) de riesgo Alto o Critico ({criticas} critico(s)).", ""]
    for _id, nivel, puntaje, ndvi, en_anp, estado, fecha, frp, lat, lon in alertas[:MAX_EN_CORREO]:
        lineas += [
            f"{nivel} (puntaje {puntaje}) - {fecha:%Y-%m-%d %H:%M} UTC",
            f"  Ubicacion: {lat:.4f}, {lon:.4f}  |  FRP {frp} MW  |  NDVI {ndvi:.2f}"
            + ("  |  dentro de Area Natural Protegida" if en_anp else ""),
            f"  Mapa: https://www.google.com/maps?q={lat:.5f},{lon:.5f}",
            "",
        ]
    if len(alertas) > MAX_EN_CORREO:
        lineas.append(f"... y {len(alertas) - MAX_EN_CORREO} mas. Ver el visor para el detalle.")
    lineas.append("Alerta automatica: requiere validacion humana en campo (RN-03).")
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = asunto, remitente, ", ".join(destinatarios)
    msg.set_content("\n".join(lineas))
    return msg


def enviar_alertas(dry_run=False, incluir_historicas=False):
    remitente = os.environ["SMTP_USER"]
    destinatarios = [d.strip() for d in os.environ["ALERTA_DESTINATARIOS"].split(",") if d.strip()]
    with get_connection() as conn, conn.cursor() as cur:
        alertas = alertas_por_notificar(cur, incluir_historicas)
        if not alertas:
            print("No hay alertas nuevas por notificar.")
            return 0
        msg = armar_mensaje(alertas, remitente, destinatarios)
        if dry_run:
            print(f"[SIMULACRO] Se enviaria a {len(destinatarios)} destinatario(s):\n")
            print(msg["Subject"], "\n")
            print(msg.get_content()[:900])
            return len(alertas)
        with smtplib.SMTP(os.getenv("SMTP_HOST", "smtp.gmail.com"), int(os.getenv("SMTP_PORT", "587")), timeout=30) as s:
            s.starttls()
            s.login(remitente, os.environ["SMTP_PASSWORD"])
            s.send_message(msg)
        cur.execute("UPDATE alertas SET notificada = TRUE WHERE id = ANY(%s)", ([a[0] for a in alertas],))
        print(f"Correo enviado a {len(destinatarios)} destinatario(s) con {len(alertas)} alerta(s).")
        return len(alertas)
