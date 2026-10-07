import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

st.set_page_config(page_title="GeoFire Peru", page_icon="🔥", layout="wide")

st.logo(str(Path(__file__).resolve().parent / "logo.svg"), size="large")

paginas = [
    st.Page("views/centro.py", title="Centro de operaciones", default=True),
    st.Page("views/mapa.py", title="Mapa visor"),
    st.Page("views/incidentes.py", title="Incidentes"),
]
st.navigation(paginas).run()
