import streamlit as st

import ui
from geofire import seguridad

ui.inicializar()
st.markdown(
    """
<style>
section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], header[data-testid="stHeader"] { display:none; }
.block-container { max-width:none; padding:0 !important; }
.gf-hero { min-height:100vh; padding:3rem 3.5rem; display:flex; flex-direction:column; justify-content:flex-end;
  background: radial-gradient(circle at 30% 20%, #2a6b52 0%, #0f3d2e 55%, #0a2a20 100%); color:#fff; }
.gf-hero .k { color:#c2e46a; letter-spacing:.2em; font-size:.7rem; margin-bottom:1rem; }
.gf-hero h1 { font-family:'Space Grotesk',Arial,sans-serif; font-size:3.6rem; line-height:1.02; font-weight:600; margin:0 0 1.2rem; color:#fff; }
.gf-hero h1 em { color:#c2e46a; font-style:normal; }
.gf-hero p { color:#cfe0d6; max-width:26rem; }
.gf-login-marca { display:flex; align-items:center; gap:.6rem; margin-bottom:3rem; }
.gf-login-marca .logo { background:#c2e46a; color:#0f6b4f; font-family:'Space Grotesk',Arial,sans-serif; font-weight:700; width:34px; height:34px; border-radius:9px; display:flex; align-items:center; justify-content:center; }
.gf-login-marca b { font-family:'Space Grotesk',Arial,sans-serif; font-size:1.2rem; display:block; line-height:1; }
.gf-login-marca small { color:#6b7a72; letter-spacing:.2em; font-size:.6rem; }
div[data-testid="stForm"] { border:none; padding:0; }
</style>
""",
    unsafe_allow_html=True,
)

izq, der = st.columns([1.1, 1], gap="small")
with izq:
    st.markdown(
        "<div class='gf-hero'><div class='k'>MONITOREO TERRITORIAL</div>"
        "<h1>Una mirada<br><em>más cerca</em><br>del fuego.</h1>"
        "<p>Información satelital para proteger nuestros bosques y a quienes los custodian.</p></div>",
        unsafe_allow_html=True,
    )
with der:
    _, centro, _ = st.columns([0.12, 0.76, 0.12])
    with centro:
        st.write("")
        st.write("")
        st.markdown(
            "<div class='gf-login-marca'><div class='logo'>G</div><div><b>GeoFire</b><small>PERÚ</small></div></div>"
            "<div class='gf-kicker'>Plataforma de vigilancia</div>"
            "<div class='gf-h1' style='font-size:2rem'>Bienvenido de vuelta</div>"
            "<div class='gf-sub'>Ingresa con tus credenciales operativas para continuar.</div>",
            unsafe_allow_html=True,
        )
        with st.form("login"):
            email = st.text_input("Correo institucional", placeholder="nombre@serfor.gob.pe")
            password = st.text_input("Contraseña", type="password")
            enviar = st.form_submit_button("Ingresar", type="primary", use_container_width=True)
        if enviar:
            usuario, mensaje = seguridad.autenticar(email, password)
            if usuario:
                st.session_state["usuario"] = usuario
                st.rerun()
            st.error(mensaje)
        st.caption("Acceso exclusivo para personal autorizado.")
