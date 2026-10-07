import plotly.graph_objects as go
import streamlit as st

import ui
from geofire import repositorio as repo

ui.inicializar()
ui.encabezado("Centro de operaciones", "Centro de operaciones", "Pulso del territorio de Ucayali en tiempo casi real.")

horas = st.radio(
    "Ventana", [6, 24, 48, 72], index=3, horizontal=True,
    format_func=lambda h: f"{h} h", label_visibility="collapsed",
)
res = repo.resumen(horas)
tot = repo.totales()
activas = res["ALTO"] + res["CRITICO"]

c1, c2, c3, c4 = st.columns(4)
with c1:
    ui.tarjeta("Alertas activas (Alto + Critico)", activas, f"ultimas {horas} h", verde=True)
with c2:
    ui.tarjeta("Alertas criticas", res["CRITICO"], "cumplen 2 o mas condiciones RN-02")
with c3:
    ui.tarjeta("Focos evaluados", f"{sum(res.values()):,}", f"ultimas {horas} h")
with c4:
    ui.tarjeta("Focos en base historica", f"{int(tot['focos']):,}", f"desde {tot['desde']:%d/%m/%Y}")

st.write("")
izq, der = st.columns([3, 2])
with izq:
    st.markdown(
        "<div class='gf-kicker'>Ultimos 30 dias</div>"
        "<b style='font-family:Space Grotesk;font-size:1.25rem'>Focos de calor detectados</b>",
        unsafe_allow_html=True,
    )
    serie = repo.focos_por_dia(30)
    fig = go.Figure(go.Bar(x=serie["dia"], y=serie["focos"], marker_color="#2f7d63"))
    fig.update_layout(
        height=300, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", yaxis=dict(gridcolor="#e8eee8"), xaxis=dict(showgrid=False),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
with der:
    total = max(sum(res.values()), 1)
    filas = "".join(
        f"<div class='gf-fila'><div><span class='gf-punto' style='background:{ui.COLOR[n]}'></span>"
        f"<b>{ui.ETIQUETA[n]}</b></div><div><b>{res[n]:,}</b> "
        f"<span style='color:var(--suave)'>· {res[n] * 100 // total}%</span></div></div>"
        for n in repo.NIVELES
    )
    st.markdown(
        "<div class='gf-card'><div class='gf-kicker'>Monitoreo en vivo</div>"
        f"<b style='font-family:Space Grotesk;font-size:1.25rem'>Focos por nivel de riesgo</b>{filas}</div>",
        unsafe_allow_html=True,
    )
