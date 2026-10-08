from datetime import datetime, timezone
from html import escape

import plotly.graph_objects as go
import streamlit as st

import cache
import ui
from geofire import repositorio as repo

ui.inicializar()
ui.encabezado("Centro de operaciones", "Centro de operaciones", "Pulso del territorio de Ucayali en tiempo casi real.")

ultima = cache.ultima_ejecucion()
if ultima:
    hace = (datetime.now(timezone.utc) - ultima[0]).total_seconds() / 3600
    ok = ultima[1] == "OK" and hace < 4
    color = "#3f9d5b" if ok else "#d93025"
    estado = "Sistema operativo" if ok else ("Ciclo con fallos" if ultima[1] != "OK" else "Sin actualizar hace más de 4 h")
    st.markdown(
        f"<div style='font-size:.8rem;color:#55645c;margin-bottom:.6rem'><span class='gf-punto' style='background:{color}'></span>"
        f"{estado} · última actualización automática hace {hace:.1f} h</div>",
        unsafe_allow_html=True,
    )
else:
    st.caption("Sin ciclos automáticos registrados todavía.")

horas = st.radio(
    "Ventana", [6, 24, 48, 72], index=3, horizontal=True,
    format_func=lambda h: f"{h} h", label_visibility="collapsed",
)
res = cache.resumen(horas)
tot = cache.totales()
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

sin_eval = cache.no_evaluables(horas)
if sin_eval:
    detalle = ", ".join(
        f"{n} {'sobre agua (NDWI)' if m == 'AGUA' else 'sin imágenes Sentinel-2 válidas'}" for m, n in sin_eval.items()
    )
    st.caption(f"No evaluables en las últimas {horas} h (no cuentan como nivel de riesgo): {detalle}.")

st.write("")
izq, der = st.columns([3, 2])
with izq:
    st.markdown(
        "<div class='gf-kicker'>Ultimos 30 dias</div>"
        "<b style='font-family:Space Grotesk;font-size:1.25rem'>Focos de calor detectados</b>",
        unsafe_allow_html=True,
    )
    serie = cache.focos_por_dia(30)
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

st.write("")
prov_col, zona_col = st.columns(2)
with prov_col:
    pp = cache.por_provincia(horas)
    filas = "".join(
        f"<div class='gf-fila'><div><b>{escape(r.provincia)}</b></div><div>"
        f"<span class='gf-badge' style='background:#d9302522;color:#a8201a'>{r.criticas} críticas</span> "
        f"<span class='gf-badge' style='background:#f08a2422;color:#8f4300'>{r.altas} altas</span></div></div>"
        for r in pp.itertuples()
    ) or "<div class='gf-fila'>Sin alertas Alto o Crítico en este periodo.</div>"
    st.markdown(
        "<div class='gf-card'><div class='gf-kicker'>Por provincia</div>"
        f"<b style='font-family:Space Grotesk,Arial,sans-serif;font-size:1.25rem'>Alertas Alto y Crítico activas</b>{filas}</div>",
        unsafe_allow_html=True,
    )
with zona_col:
    zz = cache.zonas_ultimas("distrito")
    if zz.empty:
        cuerpo = "<div class='gf-fila'>Aún no hay evaluaciones de zona.</div>"
    else:
        zz["_o"] = zz["nivel"].map({"CRITICO": 0, "ALTO": 1, "MEDIO": 2, "BAJO": 3}).fillna(9)
        top = zz.sort_values(["_o", "pct_estres"], ascending=[True, False]).head(5)
        cuerpo = "".join(
            f"<div class='gf-fila'><div><b>{escape(r.nombre)}</b> <span style='color:var(--suave);font-size:.78rem'>"
            f"{escape(r.provincia or '')}</span></div><div>"
            f"{ui.badge(r.nivel) if r.evaluable else 'No evaluable'}</div></div>"
            for r in top.itertuples()
        ) + f"<div style='color:var(--suave);font-size:.75rem;margin-top:.5rem'>Corte de datos: {zz['fecha_corte'].max():%d/%m/%Y}</div>"
    st.markdown(
        "<div class='gf-card'><div class='gf-kicker'>Prevención</div>"
        f"<b style='font-family:Space Grotesk,Arial,sans-serif;font-size:1.25rem'>Zonas con mayor riesgo</b>{cuerpo}</div>",
        unsafe_allow_html=True,
    )
