from datetime import date, timedelta
from html import escape

import streamlit as st

import ui
from geofire import reportes, seguridad
from geofire import repositorio as repo

ui.inicializar()
usuario = st.session_state.get("usuario")
if not usuario or "reportes" not in seguridad.PERMISOS.get(usuario["rol"], ()):
    seguridad.acceso_denegado("reportes", usuario)
    st.error("Acceso denegado: los reportes son para la autoridad regional y los administradores.")
    st.stop()

ui.encabezado("Analítica y reportes", "Reportes", "Descarga el resumen de incidentes del periodo en PDF y CSV.")

hoy = date.today()
c1, c2, c3 = st.columns([1.2, 1.4, 1.4])
rango = c1.date_input("Periodo", (hoy - timedelta(days=3), hoy), max_value=hoy)
niveles = c2.multiselect("Nivel de riesgo", repo.NIVELES, default=["CRITICO", "ALTO"], format_func=lambda n: ui.ETIQUETA[n])
estados = c3.multiselect(
    "Estado", list(repo.ESTADO_ETIQUETA), default=list(repo.ESTADO_ETIQUETA), format_func=repo.ESTADO_ETIQUETA.get
)
t1, t2, _ = st.columns([1, 1, 2])
provincia = t1.selectbox("Provincia", ["Todas"] + repo.provincias())
prov = None if provincia == "Todas" else provincia
distrito = t2.selectbox("Distrito", ["Todos"] + repo.distritos(prov))
dist = None if distrito == "Todos" else distrito
estimar = st.checkbox("Estimar el área afectada con NBR (consulta a Earth Engine, puede tardar hasta 40 s)", value=False)

if len(rango) != 2:
    st.info("Elige la fecha de inicio y la de fin.")
    st.stop()
inicio, fin = rango

if st.button("Generar reporte", type="primary"):
    if not niveles or not estados:
        st.warning("Selecciona al menos un nivel y un estado.")
    else:
        with st.spinner("Generando reporte…"):
            st.session_state["reporte"] = reportes.construir(inicio, fin, niveles, estados, estimar, prov, dist)

rep = st.session_state.get("reporte")
if rep is None:
    st.caption("Elige los filtros y pulsa «Generar reporte».")
    st.stop()

st.divider()
st.caption(
    f"Reporte generado {rep.generado:%d/%m/%Y %H:%M} UTC · periodo {rep.inicio:%d/%m/%Y} a {rep.fin:%d/%m/%Y}"
)
k1, k2, k3, k4 = st.columns(4)
with k1:
    ui.tarjeta("Incidentes", f"{rep.total:,}", "con los filtros elegidos", verde=True)
with k2:
    ui.tarjeta("Críticos", rep.por_nivel["CRITICO"], "RN-02: 2 o más condiciones")
with k3:
    ui.tarjeta("Altos", rep.por_nivel["ALTO"], "RN-02: 1 condición")
with k4:
    if rep.area is not None:
        ui.tarjeta("Área afectada (est.)", f"{rep.area['area_ha']:,} ha", "estimada con dNBR por el sistema")
    else:
        ui.tarjeta("Área afectada", "—", "no estimada en este reporte")
if rep.nota_area:
    st.warning(rep.nota_area)

st.write("")
d1, d2, d3, _ = st.columns([1, 1, 1, 1])
nombre = f"geofire_reporte_{rep.inicio:%Y%m%d}_{rep.fin:%Y%m%d}"
d1.download_button("⬇ Descargar PDF", reportes.a_pdf(rep), f"{nombre}.pdf", "application/pdf", use_container_width=True)
d2.download_button("⬇ Descargar CSV", reportes.a_csv(rep), f"{nombre}.csv", "text/csv", use_container_width=True)
d3.download_button("⬇ Descargar GeoJSON", reportes.a_geojson(rep), f"{nombre}.geojson", "application/geo+json", use_container_width=True)

if not rep.df.empty:
    filas = "".join(
        f"<tr><td><b>{r.codigo}</b></td><td>{r.lat:.4f}, {r.lon:.4f}{' · ANP' if r.en_anp else ''}"
        f"<br><span style='color:#55645c;font-size:.75rem'>{escape(r.distrito)} {escape(r.provincia)}</span></td>"
        f"<td>{r.fecha_hora:%d %b %Y %H:%M} UTC</td><td>{ui.badge(r.nivel)}</td><td>{r.estado_txt}</td></tr>"
        for r in rep.df.head(15).itertuples()
    )
    st.markdown(
        "<table class='gf-tabla'><tr><th>ID incidente</th><th>Ubicación</th><th>Detectado</th>"
        f"<th>Nivel de riesgo</th><th>Estado</th></tr>{filas}</table>",
        unsafe_allow_html=True,
    )
    st.caption(f"Vista previa: 15 de {rep.total:,}. El CSV incluye todos los registros.")
else:
    st.info("No hay incidentes con estos filtros.")
