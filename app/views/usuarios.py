import streamlit as st

import ui
from geofire import seguridad

ui.inicializar()
usuario = st.session_state.get("usuario")
if not usuario or "usuarios" not in seguridad.PERMISOS.get(usuario["rol"], ()):
    st.error("Acceso denegado: esta página es solo para administradores.")
    st.stop()

ui.encabezado("Administración", "Usuarios", "Crea cuentas, asigna roles y desbloquea accesos.")

ROL_TXT = {"administrador": "Administrador", "autoridad_regional": "Autoridad regional", "guardaparque": "Guardaparque"}

with st.expander("➕ Nuevo usuario", expanded=False):
    with st.form("nuevo_usuario", clear_on_submit=True):
        c1, c2 = st.columns(2)
        email = c1.text_input("Correo")
        nombre = c2.text_input("Nombre completo")
        c3, c4 = st.columns(2)
        rol = c3.selectbox("Rol", seguridad.ROLES, format_func=ROL_TXT.get)
        password = c4.text_input("Contraseña inicial", type="password")
        if st.form_submit_button("Crear usuario", type="primary"):
            try:
                seguridad.crear_usuario(email, nombre, rol, password)
                st.success(f"Usuario {email} creado.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))

lista = seguridad.listar_usuarios()
st.caption(f"{len(lista)} usuarios")
for u in lista:
    estado = "Bloqueada" if u["bloqueado"] else ("Inactiva" if not u["activo"] else "Activa")
    color = "#d93025" if estado != "Activa" else "#3f9d5b"
    acceso = f"{u['ultimo_acceso']:%d/%m/%Y %H:%M}" if u["ultimo_acceso"] else "nunca"
    a, b, c, d = st.columns([3, 1.5, 1, 1.5])
    a.markdown(f"**{u['nombre'] or u['email']}**  \n<span style='color:#6b7a72;font-size:.8rem'>{u['email']} · último acceso: {acceso}</span>", unsafe_allow_html=True)
    b.markdown(ROL_TXT[u["rol"]])
    c.markdown(f"<span class='gf-badge' style='background:{color}22;color:{color}'>{estado}</span>", unsafe_allow_html=True)
    es_yo = u["id"] == usuario["id"]
    with d:
        if u["bloqueado"]:
            if st.button("Desbloquear", key=f"d{u['id']}"):
                seguridad.desbloquear(u["id"])
                st.rerun()
        elif not es_yo:
            etiqueta = "Desactivar" if u["activo"] else "Activar"
            if st.button(etiqueta, key=f"a{u['id']}"):
                seguridad.set_activo(u["id"], not u["activo"])
                st.rerun()
    st.divider()
