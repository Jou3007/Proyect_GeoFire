import json
from datetime import datetime, timedelta, timezone

import streamlit as st

import ui
from geofire import auditoria, seguridad

ui.inicializar()
usuario = st.session_state.get("usuario")
if not usuario or "auditoria" not in seguridad.PERMISOS.get(usuario["rol"], ()):
    seguridad.acceso_denegado("auditoria", usuario)
    st.error("Acceso denegado: el registro de auditoría es solo para administradores.")
    st.stop()

ui.encabezado("Administración", "Auditoría", "Historial inmutable de accesos, validaciones, usuarios y ciclos automáticos.")

c1, c2, c3 = st.columns([2, 1, 1])
disponibles = list(auditoria.tipos()["evento"])
eventos = c1.multiselect("Tipo de evento", disponibles, placeholder="Todos")
periodo = c2.selectbox("Periodo", ["Últimas 24 h", "Últimos 7 días", "Últimos 30 días", "Todo"])
limite = c3.selectbox("Máximo de filas", [100, 200, 500, 1000], index=1)

desde = {
    "Últimas 24 h": timedelta(hours=24), "Últimos 7 días": timedelta(days=7), "Últimos 30 días": timedelta(days=30),
}.get(periodo)
df = auditoria.consultar(eventos or None, limite, datetime.now(timezone.utc) - desde if desde else None)

st.caption(f"{len(df):,} eventos · el registro no se puede modificar ni borrar (RNF-08)")
if df.empty:
    st.info("No hay eventos con estos filtros.")
else:
    vista = df.copy()
    vista["detalle"] = vista["detalle"].map(lambda d: json.dumps(d, ensure_ascii=False) if d else "")
    vista["fecha"] = vista["fecha"].dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    # st.dataframe escapa el contenido: los textos de usuarios no se interpretan como HTML
    st.dataframe(
        vista[["fecha", "evento", "email", "detalle"]], use_container_width=True, hide_index=True, height=520,
    )
    st.download_button(
        "⬇ Descargar CSV", vista.to_csv(index=False).encode("utf-8-sig"), "auditoria_geofire.csv", "text/csv",
    )
