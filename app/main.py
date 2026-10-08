import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

from geofire import seguridad

st.set_page_config(page_title="GeoFire Peru", page_icon="🔥", layout="wide")

usuario = st.session_state.get("usuario")

if not usuario:
    st.navigation([st.Page("views/login.py", title="Ingresar")], position="hidden").run()
    st.stop()

st.logo(str(Path(__file__).resolve().parent / "logo.svg"), size="large")

TODAS = {
    "centro": st.Page("views/centro.py", title="Centro de operaciones", url_path="centro", default=True),
    "mapa": st.Page("views/mapa.py", title="Mapa visor", url_path="mapa"),
    "zonas": st.Page("views/zonas.py", title="Zonas en riesgo", url_path="zonas"),
    "incidentes": st.Page("views/incidentes.py", title="Incidentes", url_path="incidentes"),
    "validacion": st.Page("views/validacion.py", title="Mis alertas", url_path="validacion"),
    "reportes": st.Page("views/reportes.py", title="Reportes", url_path="reportes"),
    "usuarios": st.Page("views/usuarios.py", title="Usuarios", url_path="usuarios"),
    "auditoria": st.Page("views/auditoria.py", title="Auditoría", url_path="auditoria"),
}
if usuario["rol"] == "guardaparque":  # su pantalla principal es la validacion en campo
    TODAS["validacion"] = st.Page(
        "views/validacion.py", title="Mis alertas", url_path="validacion", default=True
    )
permitidas = [TODAS[k] for k in seguridad.PERMISOS[usuario["rol"]]]

ROL_TXT = {"administrador": "Administrador", "autoridad_regional": "Autoridad regional", "guardaparque": "Guardaparque"}
with st.sidebar:
    st.markdown(
        f"<div style='font-size:.85rem'><b>{escape(usuario['nombre'])}</b><br>"
        f"<span style='color:#6b7a72'>{ROL_TXT[usuario['rol']]}</span></div>",
        unsafe_allow_html=True,
    )
    if st.button("Cerrar sesión", use_container_width=True):
        seguridad.cerrar_sesion(usuario)
        del st.session_state["usuario"]
        st.rerun()

st.navigation(permitidas).run()
