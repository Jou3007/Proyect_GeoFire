"""Estilo y componentes compartidos (basados en los mockups del cap. IX)."""
import streamlit as st

COLOR = {"CRITICO": "#d93025", "ALTO": "#f08a24", "MEDIO": "#e8b923", "BAJO": "#3f9d5b"}
# Texto de las etiquetas: mas oscuro que el color del punto del mapa para cumplir contraste AA (>= 4.5:1) sobre su fondo claro
COLOR_TEXTO = {"CRITICO": "#a8201a", "ALTO": "#8f4300", "MEDIO": "#6e5200", "BAJO": "#1b6636"}
ETIQUETA = {"CRITICO": "Crítico", "ALTO": "Alto", "MEDIO": "Medio", "BAJO": "Bajo"}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
:root { --verde:#0f6b4f; --lima:#c2e46a; --fondo:#f3f6f1; --texto:#1b2a22; --suave:#55645c; --borde:#e2e8e2; }
html, body, [class*="css"], .stApp { font-family:'DM Sans',sans-serif; color:var(--texto); }
.stApp { background:var(--fondo); }
header[data-testid="stHeader"] { background:transparent; }
.block-container { padding-top:2rem; max-width:1280px; }
h1, h2, h3 { font-family:'Space Grotesk',Arial,sans-serif,sans-serif !important; letter-spacing:-0.02em; }
section[data-testid="stSidebar"] { background:#fff; border-right:1px solid var(--borde); }
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a { border-radius:10px; padding:.45rem .7rem; }
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"] { background:#e6f2ea; color:var(--verde); font-weight:600; }
.gf-marca { display:flex; align-items:center; gap:.6rem; padding:.2rem 0 1rem; }
.gf-marca .logo { background:var(--lima); color:var(--verde); font-family:'Space Grotesk',Arial,sans-serif; font-weight:700; width:34px; height:34px; border-radius:9px; display:flex; align-items:center; justify-content:center; }
.gf-marca b { font-family:'Space Grotesk',Arial,sans-serif; font-size:1.1rem; display:block; line-height:1; }
.gf-marca small { color:var(--suave); letter-spacing:.2em; font-size:.6rem; }
.gf-kicker { color:var(--suave); letter-spacing:.14em; font-size:.72rem; text-transform:uppercase; }
.gf-h1 { font-family:'Space Grotesk',Arial,sans-serif; font-size:2.4rem; font-weight:600; margin:.1rem 0 .2rem; letter-spacing:-0.03em; }
.gf-sub { color:var(--suave); margin-bottom:1.2rem; }
.gf-card { background:#fff; border:1px solid var(--borde); border-radius:16px; padding:1.1rem 1.3rem; }
.gf-card .nota { min-height:1.2rem; }
.gf-card:has(.num) { min-height:9.2rem; box-sizing:border-box; }
.gf-card.verde { background:var(--verde); color:#fff; border-color:var(--verde); }
.gf-card .et { font-size:.78rem; color:var(--suave); }
.gf-card.verde .et { color:#cfe8da; }
.gf-card .num { font-family:'Space Grotesk',Arial,sans-serif; font-size:2.6rem; font-weight:600; line-height:1.1; }
.gf-card .nota { font-size:.74rem; color:var(--suave); }
.gf-card.verde .nota { color:#cfe8da; }
.gf-badge { display:inline-block; padding:.12rem .55rem; border-radius:6px; font-size:.72rem; font-weight:600; }
.gf-fila { display:flex; justify-content:space-between; align-items:center; padding:.65rem 0; border-bottom:1px solid var(--borde); }
.gf-fila:last-child { border-bottom:none; }
.gf-punto { width:9px; height:9px; border-radius:50%; display:inline-block; margin-right:.5rem; }
.gf-alerta { border-left:3px solid; padding:.55rem .7rem; margin-bottom:.45rem; background:#fff; border-radius:0 10px 10px 0; font-size:.82rem; }
.gf-alerta b { display:block; font-size:.88rem; }
.gf-alerta span { color:var(--suave); }
table.gf-tabla { width:100%; border-collapse:collapse; font-size:.85rem; background:#fff; border-radius:12px; }
table.gf-tabla th { text-align:left; color:var(--suave); font-size:.68rem; letter-spacing:.1em; text-transform:uppercase; padding:.6rem .5rem; border-bottom:1px solid var(--borde); }
table.gf-tabla td { padding:.7rem .5rem; border-bottom:1px solid #f0f3ef; }
div.stButton > button, div.stDownloadButton > button { border-radius:10px; }
</style>
"""

# Modo de alto contraste (RNF-05): negro sobre blanco, bordes gruesos, etiquetas solidas y texto mas grande
CSS_ALTO_CONTRASTE = """
<style>
:root { --verde:#003d24; --fondo:#ffffff; --texto:#000000; --suave:#1a1a1a; --borde:#000000; }
.stApp, html, body { background:#ffffff !important; color:#000000 !important; font-size:1.08rem; }
section[data-testid="stSidebar"] { background:#ffffff !important; border-right:3px solid #000 !important; }
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"] { background:#000 !important; color:#fff !important; }
.gf-card { border:2px solid #000 !important; }
.gf-card.verde { background:#003d24 !important; color:#fff !important; }
.gf-card.verde .et, .gf-card.verde .nota { color:#fff !important; }
.gf-card .et, .gf-card .nota, .gf-sub, .gf-kicker { color:#1a1a1a !important; }
.gf-badge { font-weight:800 !important; border:2px solid #000 !important; }
.gf-badge.n-CRITICO { background:#8b0000 !important; color:#fff !important; }
.gf-badge.n-ALTO { background:#8a3300 !important; color:#fff !important; }
.gf-badge.n-MEDIO { background:#ffd400 !important; color:#000 !important; }
.gf-badge.n-BAJO { background:#005a26 !important; color:#fff !important; }
.gf-alerta { border-left-width:8px !important; border:2px solid #000; }
table.gf-tabla td, table.gf-tabla th { border-bottom:2px solid #000 !important; color:#000 !important; }
div.stButton > button, div.stDownloadButton > button { border:3px solid #000 !important; font-weight:700 !important; min-height:3rem; }
*:focus-visible { outline:4px solid #ff6a00 !important; outline-offset:2px; }
</style>
"""


def inicializar():
    st.markdown(CSS, unsafe_allow_html=True)
    if st.session_state.get("alto_contraste"):
        st.markdown(CSS_ALTO_CONTRASTE, unsafe_allow_html=True)


def badge(nivel):
    c = COLOR[nivel]
    return f"<span class='gf-badge n-{nivel}' style='background:{c}22;color:{COLOR_TEXTO[nivel]}'>{ETIQUETA[nivel]}</span>"


def tarjeta(etiqueta, numero, nota="", verde=False):
    st.markdown(
        f"<div class='gf-card {'verde' if verde else ''}'><div class='et'>{etiqueta}</div>"
        f"<div class='num'>{numero}</div><div class='nota'>{nota}</div></div>",
        unsafe_allow_html=True,
    )


def encabezado(kicker, titulo, sub=""):
    st.markdown(
        f"<div class='gf-kicker'>{kicker}</div><div class='gf-h1'>{titulo}</div><div class='gf-sub'>{sub}</div>",
        unsafe_allow_html=True,
    )
