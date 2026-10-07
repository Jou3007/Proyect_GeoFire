import folium
import streamlit as st
from streamlit_folium import st_folium

import ui
from geofire import repositorio as repo

ui.inicializar()
ui.encabezado("Visor cartografico", "Mapa visor", "Focos de calor clasificados por nivel de riesgo.")

f1, f2 = st.columns([1, 2])
horas = f1.select_slider("Ventana de tiempo", [6, 24, 48, 72], value=72, format_func=lambda h: f"{h} h")
niveles = f2.multiselect(
    "Nivel de riesgo", repo.NIVELES, default=["CRITICO", "ALTO"], format_func=lambda n: ui.ETIQUETA[n]
)

df = repo.alertas(horas, niveles) if niveles else repo.alertas(0, [])

mapa_col, panel_col = st.columns([3, 1.25])
with mapa_col:
    m = folium.Map(location=[-9.6, -73.2], zoom_start=7, tiles="OpenStreetMap", control_scale=True)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery", name="Satelite", show=False,
    ).add_to(m)
    for r in df.head(3000).itertuples():
        folium.CircleMarker(
            [r.lat, r.lon], radius=6, color=ui.COLOR[r.nivel], fill=True, fill_opacity=0.85, weight=1,
            popup=folium.Popup(
                f"<b>{ui.ETIQUETA[r.nivel]}</b> (puntaje {r.puntaje})<br>"
                f"{r.fecha_hora:%d/%m/%Y %H:%M} UTC<br>FRP {r.frp} MW · NDVI {r.ndvi:.2f}<br>"
                f"{'En Area Natural Protegida<br>' if r.en_anp else ''}{r.lat:.4f}, {r.lon:.4f}",
                max_width=240,
            ),
        ).add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)
    st_folium(m, height=560, use_container_width=True, returned_objects=[])
with panel_col:
    st.markdown(
        "<div class='gf-kicker'>En tiempo real</div><b style='font-family:Space Grotesk;font-size:1.3rem'>"
        f"Alertas activas</b> <span class='gf-badge' style='background:#e6f2ea;color:#0f6b4f'>{len(df)}</span>",
        unsafe_allow_html=True,
    )
    with st.container(height=500, border=False):
        for r in df.head(60).itertuples():
            st.markdown(
                f"<div class='gf-alerta' style='border-color:{ui.COLOR[r.nivel]}'>"
                f"<b>{ui.ETIQUETA[r.nivel]} · puntaje {r.puntaje}</b>"
                f"<span>{r.lat:.3f}, {r.lon:.3f} · {r.fecha_hora:%d/%m %H:%M} UTC<br>"
                f"FRP {r.frp} MW · NDVI {r.ndvi:.2f}{' · ANP' if r.en_anp else ''}</span></div>",
                unsafe_allow_html=True,
            )
        if df.empty:
            st.caption("Sin alertas con estos filtros.")
st.caption(f"{len(df)} focos en las ultimas {horas} h" + (" (se dibujan los primeros 3,000)" if len(df) > 3000 else ""))
