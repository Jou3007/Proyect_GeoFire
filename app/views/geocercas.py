import streamlit as st

import ui
from geofire import geocercas, repositorio as repo, seguridad

ui.inicializar()
usuario = st.session_state.get("usuario")
if not usuario or "geocercas" not in seguridad.PERMISOS.get(usuario["rol"], ()):
    seguridad.acceso_denegado("geocercas", usuario)
    st.error("Acceso denegado: las geocercas son solo para administradores.")
    st.stop()

ui.encabezado("Administración", "Geocercas y fuentes conocidas",
              "Actualiza el límite de Ucayali y las fuentes de calor conocidas (aserraderos, plantas).")

# ---------- Limite regional ----------
st.markdown("<b style='font-family:Space Grotesk,Arial,sans-serif;font-size:1.3rem'>Límite regional (RN-01)</b>", unsafe_allow_html=True)
actual = repo._query("SELECT round((ST_Area(geom::geography) / 1e6)::numeric) AS km2 FROM zonas WHERE tipo = 'region' LIMIT 1")
if not actual.empty:
    st.caption(f"Límite vigente: Ucayali, {int(actual['km2'].iloc[0]):,} km² (más una franja de 5 km para filtrar los focos).")
archivo = st.file_uploader("Subir polígono de Ucayali (GeoJSON)", type=["geojson", "json"], key="limite")
if archivo is not None:
    try:
        geometria, area = geocercas.validar_geojson(archivo.getvalue())
        st.success(f"Polígono válido: {area:,.0f} km².")
        confirmar = st.checkbox("Entiendo que esto reemplaza el límite y la franja de 5 km usados para filtrar los focos")
        if st.button("Actualizar límite de Ucayali", type="primary", disabled=not confirmar):
            res = geocercas.reemplazar_region(geometria, usuario)
            st.success(f"Límite actualizado ({res['area_km2']:,} km²). Focos ya guardados fuera de la nueva geocerca: {res['focos_fuera']}.")
    except ValueError as e:
        st.error(str(e))  # "Topología inválida": no se cambia nada

# ---------- Fuentes de calor conocidas ----------
st.write("")
st.markdown("<b style='font-family:Space Grotesk,Arial,sans-serif;font-size:1.3rem'>Fuentes de calor conocidas (RN-04)</b>", unsafe_allow_html=True)
st.caption("Un foco a menos del radio de una de estas instalaciones se etiqueta «Fuente conocida» y no genera alerta crítica, "
           "salvo que su intensidad supere el umbral histórico.")
c1, c2 = st.columns(2)
with c1:
    with st.form("nueva_fuente", clear_on_submit=True):
        nombre = st.text_input("Nombre")
        tipo = st.selectbox("Tipo", list(geocercas.TIPOS_VALIDOS))
        a, b = st.columns(2)
        lat = a.number_input("Latitud", value=-8.38, format="%.5f")
        lon = b.number_input("Longitud", value=-74.55, format="%.5f")
        radio = st.number_input("Radio (m)", 50, 5000, 300, step=50)
        if st.form_submit_button("Agregar fuente", type="primary"):
            try:
                geocercas.agregar(nombre, tipo, lon, lat, radio)
                st.success("Fuente agregada.")
            except ValueError as e:
                st.error(str(e))
with c2:
    carga = st.file_uploader("O cargar un archivo (GeoJSON de puntos o CSV con nombre,tipo,lat,lon,radio_m)",
                             type=["geojson", "json", "csv"], key="fuentes")
    if carga is not None and st.button("Cargar archivo"):
        try:
            formato = "csv" if carga.name.lower().endswith(".csv") else "geojson"
            n, errores = geocercas.cargar_fuentes(carga.getvalue(), formato, actor=usuario)
            st.success(f"{n} fuentes cargadas.")
            for e in errores[:10]:
                st.warning(e)
        except ValueError as e:
            st.error(str(e))

fuentes = geocercas.listar_fuentes()
st.caption(f"{len(fuentes)} fuentes registradas")
st.dataframe(fuentes.drop(columns=["id"]), use_container_width=True, hide_index=True, height=300)
if not fuentes.empty:
    manuales = fuentes[fuentes["fuente"] != "OpenStreetMap"]
    if not manuales.empty:
        opcion = st.selectbox("Eliminar una fuente cargada a mano", manuales["id"],
                              format_func=lambda i: f"{manuales[manuales['id'] == i]['nombre'].iloc[0] or 'sin nombre'} (#{i})")
        if st.button("Eliminar"):
            geocercas.eliminar_fuente(int(opcion), usuario)
            st.rerun()
