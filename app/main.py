import sys
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
    "incidentes": st.Page("views/incidentes.py", title="Incidentes", url_path="incidentes"),
    "usuarios": st.Page("views/usuarios.py", title="Usuarios", url_path="usuarios"),
}
permitidas = [TODAS[k] for k in seguridad.PERMISOS[usuario["rol"]]]
if usuario["rol"] == "guardaparque":
    permitidas[0] = st.Page("views/mapa.py", title="Mapa visor", url_path="mapa", default=True)

ROL_TXT = {"administrador": "Administrador", "autoridad_regional": "Autoridad regional", "guardaparque": "Guardaparque"}
with st.sidebar:
    st.markdown(
        f"<div style='font-size:.85rem'><b>{usuario['nombre']}</b><br>"
        f"<span style='color:#6b7a72'>{ROL_TXT[usuario['rol']]}</span></div>",
        unsafe_allow_html=True,
    )
    if st.button("Cerrar sesión", use_container_width=True):
        del st.session_state["usuario"]
        st.rerun()

st.navigation(permitidas).run()
