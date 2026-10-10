import json
from datetime import date, datetime, time, timedelta, timezone

import folium
import streamlit as st
from streamlit_folium import st_folium

import cache
import ui
from geofire import gee_indices as gi
from geofire import repositorio as repo
from geofire import seguridad, zonas

ui.inicializar()
ui.encabezado("Visor cartográfico", "Mapa visor", "Focos de calor, zonas evaluadas y capas satelitales de Ucayali.")

COLOR_ZONA = {"BAJO": "#3f9d5b", "MEDIO": "#e8b923", "ALTO": "#f08a24", "CRITICO": "#d93025",
              "NO_EVALUABLE": "#8a8f98", "SIN_EVALUAR": "#c9ced6"}
GIBS = {  # capa -> (identificador GIBS, nivel de teselas, formato, descripcion)
    "HUMO": ("MODIS_Combined_Value_Added_AOD", 6, "png", "Humo y aerosoles (NASA Worldview, AOD)"),
    "VIIRS": ("VIIRS_SNPP_CorrectedReflectance_TrueColor", 9, "jpg", "Imagen real VIIRS (NASA Worldview)"),
}
MIN_FECHA_S2 = date(2017, 4, 1)


@st.cache_resource
def _iniciar_gee():
    gi.init()
    return True


@st.cache_data(ttl=3000, show_spinner=False)
def _url_gee(capa, region_json, corte_iso):
    _iniciar_gee()
    return gi.url_capa(capa, json.loads(region_json), date.fromisoformat(corte_iso))


@st.cache_data(ttl=600, show_spinner=False)
def _geojson_zonas():
    return zonas.geojson_con_niveles("distrito")


restringido, zona_id = seguridad.alcance(st.session_state["usuario"])
if restringido and not zona_id:
    st.warning("Aún no tienes una zona asignada. Pídele al administrador que te asigne un distrito o una provincia.")
    st.stop()
if restringido:
    st.info(f"Estás viendo solo tu zona asignada: {st.session_state['usuario']['zona']}.")

# ---------- filtros ----------
f1, f2, f3 = st.columns([1, 1, 1.4])
provincia = f1.selectbox("Provincia", ["Todas"] + cache.provincias())
prov = None if provincia == "Todas" else provincia
distrito = f2.selectbox("Distrito", ["Todos"] + cache.distritos(prov))
dist = None if distrito == "Todos" else distrito
niveles = f3.multiselect(
    "Nivel de riesgo", repo.NIVELES + ["SIN_EVALUAR"], default=["CRITICO", "ALTO"],
    format_func=lambda n: "Sin evaluar" if n == "SIN_EVALUAR" else ui.ETIQUETA[n],
)

m1, m2 = st.columns([1, 2])
modo = m1.radio("Modo", ["Tiempo real", "Evolución histórica"], horizontal=True)
hoy = date.today()
if modo == "Tiempo real":
    horas = m2.select_slider("Ventana de tiempo", [6, 24, 48, 72], value=72, format_func=lambda h: f"{h} h")
    df = cache.alertas(horas, [n for n in niveles if n != "SIN_EVALUAR"], prov, dist, zona_id) if niveles else cache.alertas(0, [])
    fecha_ref = hoy
    leyenda = f"{len(df)} focos en las últimas {horas} h"
else:
    primera, ultima = cache.rango_de_focos()
    c1, c2 = m2.columns([2, 1])
    fecha_hasta = c1.slider("Línea de tiempo (fecha)", primera, ultima, ultima, format="DD/MM/YYYY")
    ventana_dias = c2.selectbox("Mostrar", [1, 3, 7, 15, 30], index=2, format_func=lambda d: f"{d} día(s) hasta esa fecha")
    desde = datetime.combine(fecha_hasta - timedelta(days=ventana_dias - 1), time.min, tzinfo=timezone.utc)
    hasta = datetime.combine(fecha_hasta + timedelta(days=1), time.min, tzinfo=timezone.utc)
    df = cache.focos_en_periodo(desde, hasta, prov, dist, zona_id=zona_id)
    df["nivel"] = df["nivel"].fillna("SIN_EVALUAR")
    df = df[df["nivel"].isin(niveles)] if niveles else df.iloc[0:0]
    fecha_ref = fecha_hasta
    leyenda = f"{len(df)} focos del {desde:%d/%m/%Y} al {fecha_hasta:%d/%m/%Y}"
    st.caption(f"Línea de tiempo disponible: {primera:%d/%m/%Y} a {ultima:%d/%m/%Y}")

# ---------- capas ----------
with st.expander("Capas del mapa", expanded=False):
    st.caption("Marca la casilla para mostrar la capa y mueve la barra (0 = transparente, 100 = opaca). Las capas de Earth Engine tardan unos segundos en dibujarse.")
    capas = {}
    filas = [("ZONAS", "Zonas evaluadas (nivel de riesgo)", 35), ("NDVI", gi.CAPAS["NDVI"][0], 70),
             ("ESTRES", gi.CAPAS["ESTRES"][0], 80), ("NBR", gi.CAPAS["NBR"][0], 70),
             ("HUMO", GIBS["HUMO"][3], 60), ("VIIRS", GIBS["VIIRS"][3], 80)]
    for clave, etiqueta, op in filas:
        a, b = st.columns([2, 1])
        activa = a.checkbox(etiqueta, value=clave == "ZONAS", key=f"capa_{clave}")
        opacidad = b.slider("Opacidad (%)", 0, 100, op, key=f"op_{clave}", label_visibility="collapsed")
        capas[clave] = (activa, opacidad / 100)
    _firma = "_".join(f"{int(a)}{int(o * 100)}" for a, o in capas.values())
    sat = any(capas[c][0] for c in ("NDVI", "ESTRES", "NBR"))
    d1, d2 = st.columns(2)
    fecha_sat = d1.date_input("Fecha de las capas Sentinel-2 (promedio de los 30 días previos)", min(fecha_ref, hoy),
                              min_value=MIN_FECHA_S2, max_value=hoy)
    comparar = d2.checkbox("Comparar con otra fecha (lado a lado)", disabled=not sat)
    fecha_b = d2.date_input("Fecha de comparación", min(fecha_sat, hoy) - timedelta(days=90), min_value=MIN_FECHA_S2,
                            max_value=hoy, disabled=not comparar)


def _vista():
    """Centro y zoom segun la provincia o el distrito elegidos, y su poligono para recortar capas."""
    if dist:
        zid = cache.id_por_nombre(dist, "distrito")
    elif prov:
        zid = cache.id_por_nombre(prov, "provincia")
    else:
        zid = None
    geom, (w, s, e, n) = cache.geometria(zid) if zid else cache.geometria_region()
    span = max(e - w, n - s)
    zoom = 7 if span > 3 else 8 if span > 2 else 9 if span > 1 else 10 if span > 0.5 else 11
    caja = {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}
    return ((s + n) / 2, (w + e) / 2), zoom, caja


def construir_mapa(corte, centro, zoom, caja, avisos, datos=None):
    datos = df if datos is None else datos
    m = folium.Map(location=list(centro), zoom_start=zoom, tiles="OpenStreetMap", control_scale=True)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery", name="Satélite base", show=False,
    ).add_to(m)
    activa, op = capas["ZONAS"]
    if activa:
        folium.GeoJson(
            _geojson_zonas(), name="Zonas evaluadas", control=True,
            style_function=lambda f: {"color": "#444", "weight": 1, "fillOpacity": op,
                                      "fillColor": COLOR_ZONA.get(f["properties"]["nivel"], "#c9ced6")},
            tooltip=folium.GeoJsonTooltip(fields=["nombre", "nivel", "ndvi", "estres", "corte"],
                                          aliases=["Distrito", "Nivel", "NDVI", "% estrés", "Corte de datos"]),
        ).add_to(m)
    for capa in ("NDVI", "ESTRES", "NBR"):
        activa, op = capas[capa]
        if not activa:
            continue
        try:
            url = _url_gee(capa, json.dumps(caja), corte.isoformat())
            folium.TileLayer(tiles=url, attr="Google Earth Engine · Copernicus Sentinel-2", name=f"{gi.CAPAS[capa][0]} · {corte:%d/%m/%Y}",
                             opacity=op, overlay=True, max_zoom=14).add_to(m)
        except Exception as e:  # sin red, sin credenciales de Earth Engine, etc.
            avisos.append(f"Capa «{gi.CAPAS[capa][0]}» no disponible ({type(e).__name__}): {str(e)[:220]}")
    gibs_dia = min(fecha_ref, hoy - timedelta(days=1))
    for clave, (ident, nivel, ext, desc) in GIBS.items():
        activa, op = capas[clave]
        if activa:
            folium.TileLayer(
                tiles=f"https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/{ident}/default/{gibs_dia}/GoogleMapsCompatible_Level{nivel}/{{z}}/{{y}}/{{x}}.{ext}",
                attr="NASA GIBS / Worldview", name=f"{desc} · {gibs_dia:%d/%m/%Y}", opacity=op, overlay=True,
                max_native_zoom=nivel, max_zoom=14,
            ).add_to(m)
    for r in datos.head(3000).itertuples():
        nivel = r.nivel
        color = ui.COLOR.get(nivel, "#55645c")
        etiqueta = ui.ETIQUETA.get(nivel, "Sin evaluar")
        extra = f"<br>Puntaje {r.puntaje} · NDVI {r.ndvi:.2f}" if hasattr(r, "puntaje") and r.puntaje == r.puntaje else ""
        folium.CircleMarker(
            [r.lat, r.lon], radius=6, color=color, fill=True, fill_opacity=0.85, weight=1,
            popup=folium.Popup(
                f"<b>{etiqueta}</b>{extra}<br>{r.fecha_hora:%d/%m/%Y %H:%M} UTC<br>FRP {r.frp} MW<br>"
                f"{(r.distrito or 'Franja de 5 km')} · {(r.provincia or '')}<br>{r.lat:.4f}, {r.lon:.4f}", max_width=240),
        ).add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)
    return m


centro, zoom, caja = _vista()
avisos = []
mapa_col, panel_col = st.columns([3, 1.25])
with mapa_col:
    if sat and comparar:
        ca, cb = st.columns(2)
        with ca:
            st.caption(f"Capas del {fecha_sat:%d/%m/%Y}")
            st_folium(construir_mapa(fecha_sat, centro, zoom, caja, avisos), height=520, use_container_width=True,
                      returned_objects=[], key=f"mapa_a_{_firma}")
        with cb:
            st.caption(f"Capas y focos del {fecha_b:%d/%m/%Y} (comparación)")
            dias = ventana_dias if modo != "Tiempo real" else max(1, -(-horas // 24))
            df_b = cache.focos_en_periodo(
                datetime.combine(fecha_b - timedelta(days=dias - 1), time.min, tzinfo=timezone.utc),
                datetime.combine(fecha_b + timedelta(days=1), time.min, tzinfo=timezone.utc), prov, dist, zona_id=zona_id)
            df_b["nivel"] = df_b["nivel"].fillna("SIN_EVALUAR")
            df_b = df_b[df_b["nivel"].isin(niveles)] if niveles else df_b.iloc[0:0]
            st_folium(construir_mapa(fecha_b, centro, zoom, caja, avisos, df_b), height=520, use_container_width=True,
                      returned_objects=[], key=f"mapa_b_{_firma}")
    else:
        st_folium(construir_mapa(fecha_sat, centro, zoom, caja, avisos), height=560, use_container_width=True,
                  returned_objects=[], key=f"mapa_{_firma}")
    for a in dict.fromkeys(avisos):
        st.warning(a)
with panel_col:
    st.markdown(
        "<div class='gf-kicker'>En tiempo real</div><b style='font-family:Space Grotesk,Arial,sans-serif;font-size:1.3rem'>"
        f"Alertas activas</b> <span class='gf-badge' style='background:#e6f2ea;color:#0f6b4f'>{len(df)}</span>",
        unsafe_allow_html=True,
    )
    with st.container(height=500, border=False):
        for r in df.head(60).itertuples():
            nivel = r.nivel
            st.markdown(
                f"<div class='gf-alerta' style='border-color:{ui.COLOR.get(nivel, '#55645c')}'>"
                f"<b>{ui.ETIQUETA.get(nivel, 'Sin evaluar')}</b>"
                f"<span>{r.lat:.3f}, {r.lon:.3f} · {r.fecha_hora:%d/%m %H:%M} UTC<br>"
                f"{r.distrito or 'Franja de 5 km'} · FRP {r.frp} MW</span></div>",
                unsafe_allow_html=True,
            )
        if df.empty:
            st.caption("Sin focos con estos filtros.")
st.caption(leyenda + (" (se dibujan los primeros 3,000)" if len(df) > 3000 else ""))
