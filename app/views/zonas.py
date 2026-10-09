import json
from datetime import date
from html import escape

import folium
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

import ui
from geofire import auditoria, clima, seguridad
from geofire import gee_indices as gi
from geofire import zonas

ui.inicializar()
usuario = st.session_state.get("usuario")
if not usuario or "zonas" not in seguridad.PERMISOS.get(usuario["rol"], ()):
    seguridad.acceso_denegado("zonas", usuario)
    st.error("Acceso denegado: la evaluación por zona es para la autoridad regional y los administradores.")
    st.stop()

ui.encabezado("Prevención", "Zonas en riesgo",
              "Evaluación por distrito y provincia con imágenes Sentinel-2, aunque todavía no haya focos de calor.")

ORDEN = {"CRITICO": 0, "ALTO": 1, "MEDIO": 2, "BAJO": 3}
EXPLICA = {
    "ZONA-ESTRES": "Hay una proporción alta de vegetación con NDVI bajo el umbral de estrés.",
    "ZONA-ESTRES-SEVERO": "La proporción de vegetación en estrés es muy alta.",
    "ZONA-ANOMALIA-NDVI": "La vegetación está más seca de lo normal para esta época (frente a los 3 años anteriores).",
    "ZONA-FOCOS-ACTIVOS": "Ya hay muchas quemas activas en la zona en los últimos 30 días.",
}


@st.cache_resource
def _iniciar_gee():
    gi.init()
    return True


@st.cache_data(ttl=3000, show_spinner=False)
def _url_gee(capa, region_json, corte_iso):
    _iniciar_gee()
    return gi.url_capa(capa, json.loads(region_json), date.fromisoformat(corte_iso))


df = zonas.ultimas()
puede_evaluar = usuario["rol"] in ("administrador", "autoridad_regional")

if df.empty:
    st.info("Todavía no hay evaluaciones de zona.")
    if puede_evaluar and st.button("Evaluar zonas ahora (tarda ~1 min)", type="primary"):
        with st.spinner("Evaluando 14 distritos y 4 provincias con Sentinel-2…"):
            st.session_state["zonas_resumen"] = zonas.evaluar_todas()
        st.rerun()
    st.stop()

dist = df[df["tipo"] == "distrito"].copy()
dist["_o"] = dist["nivel"].map(ORDEN).fillna(9)
dist = dist.sort_values(["_o", "pct_estres"], ascending=[True, False])
corte = df["fecha_corte"].max()

k1, k2, k3, k4 = st.columns(4)
with k1:
    ui.tarjeta("Zonas Alto o Crítico", int(dist["nivel"].isin(["ALTO", "CRITICO"]).sum()),
               f"de {len(dist)} distritos evaluados", verde=True)
with k2:
    ui.tarjeta("Zonas No evaluables", int((~dist["evaluable"]).sum()), "sin cobertura de imágenes válida")
with k3:
    ui.tarjeta("Fecha de corte", f"{corte:%d/%m}", f"datos hasta el {corte:%d/%m/%Y}")
with k4:
    ui.tarjeta("Imágenes Sentinel-2", f"{int(df['imagenes'].max()):,}", "referenciadas en la evaluación")

if puede_evaluar:
    if st.button("Reevaluar zonas ahora (tarda ~1 min)"):
        try:
            with st.spinner("Evaluando zonas con Sentinel-2…"):
                resumen = zonas.evaluar_todas()
            auditoria.registrar("ZONAS_EVALUADAS", usuario["id"], usuario["email"], resumen)
            st.rerun()
        except Exception as ex:
            st.error(f"No se pudo reevaluar ({type(ex).__name__}): {str(ex)[:300]}")
st.write("")

filas = ""
for r in dist.itertuples():
    nivel = r.nivel if r.evaluable else None
    badge = ui.badge(nivel) if nivel else "<span class='gf-badge' style='background:#8a8f9822;color:#4b5563'>No evaluable</span>"
    filas += (
        f"<tr><td><b>{escape(r.nombre)}</b><br><span style='color:#55645c;font-size:.75rem'>{escape(r.provincia or '')}</span></td>"
        f"<td>{badge}</td><td>{'' if r.ndvi_medio != r.ndvi_medio else f'{r.ndvi_medio:.2f}'}</td>"
        f"<td>{'' if r.pct_estres != r.pct_estres else f'{r.pct_estres:.1f} %'}</td><td>{r.pct_cobertura:.0f} %</td>"
        f"<td>{r.focos_30d}</td></tr>"
    )
st.markdown(
    "<table class='gf-tabla'><tr><th>Distrito</th><th>Nivel</th><th>NDVI medio</th><th>Vegetación en estrés</th>"
    f"<th>Cobertura válida</th><th>Focos (30 d)</th></tr>{filas}</table>",
    unsafe_allow_html=True,
)
st.download_button("Exportar zonas en GeoJSON", json.dumps(zonas.geojson_con_niveles("distrito"), ensure_ascii=False).encode("utf-8"),
                   "zonas_geofire.geojson", "application/geo+json")
st.caption("«No evaluable» no es un nivel de riesgo: significa que no hubo imágenes válidas suficientes (AC-06.1).")

# ---------- detalle ----------
st.write("")
st.markdown("<b style='font-family:Space Grotesk,Arial,sans-serif;font-size:1.3rem'>Detalle de una zona</b>", unsafe_allow_html=True)
nombres = list(df.sort_values(["tipo", "nombre"], ascending=[False, True]).apply(lambda r: f"{r.nombre} ({r.tipo})", axis=1))
defecto = next((i for i, n in enumerate(nombres) if n.startswith("Sepahua")), 0)
elegida = st.selectbox("Zona", nombres, index=defecto)
fila = df[df.apply(lambda r: f"{r.nombre} ({r.tipo})" == elegida, axis=1)].iloc[0]
zid = int(fila["id"])
geom, (w, s, e, n) = zonas.geometria(zid)

c1, c2 = st.columns([1.1, 1.4])
with c1:
    if fila["evaluable"]:
        st.markdown(f"**Nivel: {ui.badge(fila['nivel'])}**", unsafe_allow_html=True)
        st.write(f"NDVI medio **{fila['ndvi_medio']:.2f}** (mismo periodo, años anteriores: {fila['ndvi_historico']:.2f})")
        st.write(f"Vegetación en estrés: **{fila['pct_estres']:.1f} %** · Cobertura válida: {fila['pct_cobertura']:.0f} %")
        st.write(f"Focos en 30 días: **{fila['focos_30d']}** ({fila['focos_por_100km2']:.1f} por 100 km²) · Área {fila['area_km2']:,.0f} km²")
        motivos = [EXPLICA[x] for x in (fila["reglas"] or []) if x in EXPLICA]
        st.markdown("**Por qué este nivel:**")
        for t in motivos or ["Ninguna condición de riesgo se cumple: vegetación sana y pocas quemas."]:
            st.markdown(f"- {t}")
    else:
        st.warning("Zona **No evaluable**: no hubo imágenes Sentinel-2 válidas suficientes. No se asigna ningún nivel de riesgo.")
    st.caption(f"Corte de datos: {fila['fecha_corte']:%d/%m/%Y} · ventana {fila['ventana_dias']} días · "
               f"imágenes usadas: {int(fila['imagenes'])} · configuración {fila['config_version']}")
    v = clima.viento((s + n) / 2, (w + e) / 2)
    if v:
        st.markdown(f"🌬️ **Viento ahora:** {v['velocidad_kmh']:.0f} km/h del {v['rumbo']} ({v['direccion_grados']:.0f}°) · Open-Meteo")
    else:
        st.caption("Viento no disponible en este momento.")
with c2:
    capa_ndvi = st.checkbox("Mostrar NDVI", value=True)
    capa_estres = st.checkbox("Resaltar áreas con estrés", value=True)
    op = st.slider("Opacidad", 10, 100, 75)
    m = folium.Map(location=[(s + n) / 2, (w + e) / 2], zoom_start=9 if max(e - w, n - s) > 1 else 10, tiles="OpenStreetMap")
    caja = {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}
    aviso = None
    for activa, capa in ((capa_ndvi, "NDVI"), (capa_estres, "ESTRES")):
        if activa:
            try:
                folium.TileLayer(tiles=_url_gee(capa, json.dumps(geom), fila["fecha_corte"].date().isoformat()),
                                 attr="Google Earth Engine · Copernicus Sentinel-2", name=gi.CAPAS[capa][0],
                                 opacity=op / 100, overlay=True, max_zoom=14).add_to(m)
            except Exception as ex:
                aviso = f"Capas satelitales no disponibles ({type(ex).__name__}): {str(ex)[:220]}"
    folium.GeoJson(geom, style_function=lambda f: {"color": "#0f6b4f", "weight": 3, "fillOpacity": 0}).add_to(m)
    st_folium(m, height=420, use_container_width=True, returned_objects=[], key=f"zona_{zid}")
    if aviso:
        st.warning(aviso)

hist = zonas.historial(zid)
if len(hist) > 1:
    hist = hist[hist["evaluable"]].sort_values("fecha_corte")
    fig = go.Figure(go.Scatter(x=hist["fecha_corte"], y=hist["pct_estres"], mode="lines+markers", line=dict(color="#d93025")))
    fig.update_layout(height=220, margin=dict(l=0, r=0, t=10, b=0), yaxis_title="% en estrés",
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.markdown("**Evolución de la vegetación en estrés**")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
