from html import escape

import streamlit as st

import ui
from geofire import seguridad
from geofire import validacion as val

ui.inicializar()
usuario = st.session_state.get("usuario")
if not usuario or usuario["rol"] not in val.ROLES_VALIDADORES:
    seguridad.acceso_denegado("validacion", usuario)
    st.error("Acceso denegado: solo guardaparques y autoridad regional validan alertas (RN-03).")
    st.stop()

# Vista pensada para celular: botones grandes y una sola columna
st.markdown(
    "<style>div.stButton > button, div[data-testid='stFormSubmitButton'] > button { min-height:3rem; font-size:1rem; }"
    " div[role='radiogroup'] label { padding:.5rem 0; }</style>",
    unsafe_allow_html=True,
)
ui.encabezado("Operaciones de campo", "Mis alertas", "Alertas Alto y Crítico pendientes de validación.")

if st.session_state.pop("validacion_ok", None):
    st.success("Validación registrada. Gracias.")

restringido, zona_id = seguridad.alcance(usuario)
if restringido and not zona_id:
    st.warning("Aún no tienes una zona asignada. Pídele al administrador que te asigne un distrito o una provincia.")
    st.stop()
df = val.pendientes(72, zona_id)
st.caption(f"{len(df)} alertas pendientes (últimas 72 h)" + (f" en tu zona: {usuario['zona']}" if restringido else ""))

if df.empty:
    st.info("No hay alertas pendientes.")
else:
    opciones = {
        int(r.id): f"{ui.ETIQUETA[r.nivel].upper()} · {r.lat:.3f}, {r.lon:.3f} · {r.fecha_hora:%d/%m %H:%M} UTC"
        for r in df.head(50).itertuples()
    }
    elegida = st.selectbox("Selecciona una alerta", list(opciones), format_func=opciones.get)
    a = df[df["id"] == elegida].iloc[0]

    color = ui.COLOR[a["nivel"]]
    st.markdown(
        f"<div class='gf-alerta' style='border-color:{color}'><b>{ui.ETIQUETA[a['nivel']]} · puntaje {a['puntaje']}</b>"
        f"<span>{a['lat']:.5f}, {a['lon']:.5f}<br>Detectado: {a['fecha_hora']:%d/%m/%Y %H:%M} UTC · FRP {a['frp']} MW"
        f"<br>NDVI {a['ndvi']:.2f}{' · dentro de Área Natural Protegida' if a['en_anp'] else ''}"
        f"{'<br>⚠ Más de 6 h sin validar (revisión histórica)' if a['estado'] == 'REVISION_HISTORICA' else ''}</span></div>",
        unsafe_allow_html=True,
    )
    st.link_button(
        "📍 Cómo llegar (abrir en Google Maps)",
        f"https://www.google.com/maps/dir/?api=1&destination={a['lat']:.5f},{a['lon']:.5f}",
        use_container_width=True,
    )

    with st.form("form_validacion", clear_on_submit=True):
        estado = st.radio(
            "¿Qué encontraste en el lugar?",
            ["CONFIRMADA", "FALSA_ALARMA"],
            format_func={"CONFIRMADA": "🔥 Incendio confirmado", "FALSA_ALARMA": "✅ Falsa alarma"}.get,
        )
        comentario = st.text_area(
            f"Justificación (obligatoria, mínimo {val.MIN_JUSTIFICACION} caracteres)", max_chars=1000,
            placeholder="Ej.: quema agrícola controlada, humo visible desde el camino…",
        )
        st.caption("Para **confirmar** un incendio adjunta una foto o una referencia de evidencia (código de parte, enlace…).")
        foto = st.file_uploader("Foto (JPG o PNG, máx. 5 MB)", type=["jpg", "jpeg", "png"])
        referencia = st.text_input("Referencia de evidencia (opcional si adjuntas foto)", max_chars=300)
        if st.form_submit_button("Enviar validación", type="primary", use_container_width=True):
            try:
                val.validar(int(elegida), usuario, estado, comentario, foto.getvalue() if foto else None, referencia)
                st.session_state["validacion_ok"] = True
                st.rerun()
            except (ValueError, PermissionError) as e:
                st.error(str(e))

st.write("")
st.markdown("<div class='gf-kicker'>Historial</div><b style='font-family:Space Grotesk,Arial,sans-serif;font-size:1.2rem'>Mis validaciones recientes</b>", unsafe_allow_html=True)
hist = val.validaciones_recientes(usuario["id"], 8)
if hist.empty:
    st.caption("Aún no has validado alertas.")
for r in hist.itertuples():
    etiqueta = "🔥 Confirmada" if r.estado == "CONFIRMADA" else "✅ Falsa alarma"
    st.markdown(
        f"**{etiqueta}** · {r.lat:.3f}, {r.lon:.3f} · {r.validado_en:%d/%m %H:%M}  \n"
        f"<span style='color:#55645c;font-size:.85rem'>{escape(r.comentario or 'Sin comentario')}"
        f"{' · evidencia: ' + escape(r.referencia_evidencia) if r.referencia_evidencia else ''}</span>",
        unsafe_allow_html=True,
    )
    if r.tiene_foto:
        st.image(val.foto(int(r.id)), width=160)
