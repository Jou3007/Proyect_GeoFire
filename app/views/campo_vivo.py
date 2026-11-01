"""Ultima ubicacion conocida de cada guardaparque, enviada por la app movil GeoFire Campo.

Lee server_campo/datos/campo.db (SQLite) directamente del disco compartido entre
contenedores; no es la base principal de GeoFire (Postgres), es la cola de la
app movil. Por eso esta pantalla es de solo lectura y aparte del resto.
"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import folium
import streamlit as st
from streamlit_folium import st_folium

import ui

ui.inicializar()
ui.encabezado("Guardaparques en vivo", "Guardaparques en vivo", "Última posición enviada por cada guardaparque desde la app de campo.")

RUTA_BD = Path(__file__).resolve().parents[2] / "server_campo" / "datos" / "campo.db"


def _consultar(sql, parametros=()):
    if not RUTA_BD.exists():
        return []
    with sqlite3.connect(RUTA_BD) as conn:
        return conn.execute(sql, parametros).fetchall()


ubicaciones = _consultar(
    "SELECT correo, latitud, longitud, marca_tiempo, recibido_en FROM ubicaciones_campo u"
    " WHERE marca_tiempo = (SELECT max(marca_tiempo) FROM ubicaciones_campo WHERE correo = u.correo)"
    " ORDER BY marca_tiempo DESC"
)

if not RUTA_BD.exists():
    st.info("Todavía no se conectó ningún guardaparque desde la app de campo.")
    st.stop()

st.caption(
    "**No es rastreo en tiempo real de verdad**: es la última posición que el teléfono logró "
    "enviar. Si el guardaparque está sin señal, la posición mostrada puede tener minutos u "
    "horas de antigüedad; la pantalla lo indica en cada fila."
)

if not ubicaciones:
    st.info("Ningún guardaparque ha iniciado su jornada de campo todavía.")
    st.stop()

ahora = datetime.now(timezone.utc)
centro = [ubicaciones[0][1], ubicaciones[0][2]]
mapa = folium.Map(location=centro, zoom_start=9, tiles="OpenStreetMap")

filas = []
for correo, lat, lon, marca_tiempo, recibido_en in ubicaciones:
    hace_min = (ahora.timestamp() - marca_tiempo / 1000) / 60
    reciente = hace_min < 10
    color = "green" if reciente else ("orange" if hace_min < 60 else "red")
    folium.Marker(
        [lat, lon],
        tooltip=correo,
        popup=f"{correo}<br>hace {hace_min:.0f} min",
        icon=folium.Icon(color=color, icon="user"),
    ).add_to(mapa)
    filas.append({"Guardaparque": correo, "Hace": f"{hace_min:.0f} min", "Lat": round(lat, 5), "Lon": round(lon, 5)})

st_folium(mapa, height=460, use_container_width=True, returned_objects=[], key="mapa_campo_vivo")
st.write("")
st.dataframe(filas, use_container_width=True, hide_index=True)

reportes = _consultar(
    "SELECT tipo, correo, nota, marca_tiempo FROM reportes_campo ORDER BY marca_tiempo DESC LIMIT 20"
)
if reportes:
    st.subheader("Últimos reportes de campo (foto, audio, video, SOS)")
    for tipo, correo, nota, marca_tiempo in reportes:
        fecha = datetime.fromtimestamp(marca_tiempo / 1000, tz=timezone.utc)
        st.markdown(f"**{tipo}** · {correo} · {fecha:%d/%m/%Y %H:%M} UTC — {nota}")
