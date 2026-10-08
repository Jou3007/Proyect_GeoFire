from html import escape

import streamlit as st

import ui
from geofire import repositorio as repo

ui.inicializar()
ui.encabezado("Registro operativo", "Incidentes", "Consulta y seguimiento de las alertas generadas por el motor de riesgo.")

c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
texto = c1.text_input("Buscar por ID o coordenadas", placeholder="GF-251007-0012 o -8.68")
nivel = c2.selectbox("Nivel", ["Alto y Crítico", "Todos"] + [ui.ETIQUETA[n] for n in repo.NIVELES])
estado = c3.selectbox("Estado", ["Todos"] + sorted(set(repo.ESTADO_ETIQUETA.values())))
dias = c4.selectbox("Periodo", [3, 7, 30], format_func=lambda d: f"Últimos {d} días")
p1, p2, _ = st.columns([1, 1, 2])
provincia = p1.selectbox("Provincia", ["Todas"] + repo.provincias())
prov = None if provincia == "Todas" else provincia
distrito = p2.selectbox("Distrito", ["Todos"] + repo.distritos(prov))
dist = None if distrito == "Todos" else distrito

niveles = {"Alto y Crítico": ["ALTO", "CRITICO"], "Todos": repo.NIVELES}.get(
    nivel, [k for k, v in ui.ETIQUETA.items() if v == nivel]
)
df = repo.alertas(dias * 24, niveles, prov, dist)
if not df.empty:
    df["codigo"] = df.apply(lambda r: f"GF-{r.fecha_hora:%y%m%d}-{r.id:04d}", axis=1)
    df["estado_txt"] = df["estado"].map(repo.ESTADO_ETIQUETA)
    df["provincia"] = df["provincia"].fillna("Franja de 5 km")
    df["distrito"] = df["distrito"].fillna("")
    if estado != "Todos":
        df = df[df["estado_txt"] == estado]
    if texto:
        t = texto.strip().lower()
        df = df[
            df["codigo"].str.lower().str.contains(t, regex=False)
            | df.apply(lambda r: t in f"{r.lat:.4f},{r.lon:.4f}", axis=1)
        ]

a, b = st.columns([4, 1])
a.caption(f"{len(df):,} incidentes encontrados")
if not df.empty:
    csv = df[["codigo", "nivel", "estado_txt", "fecha_hora", "provincia", "distrito", "lat", "lon", "frp", "ndvi", "en_anp"]].to_csv(index=False)
    b.download_button("Exportar CSV", csv.encode("utf-8"), "incidentes_geofire.csv", "text/csv", use_container_width=True)

POR_PAGINA = 15
paginas = max(1, -(-len(df) // POR_PAGINA))
pag = st.number_input("Página", 1, paginas, 1) if paginas > 1 else 1
vista = df.iloc[(pag - 1) * POR_PAGINA: pag * POR_PAGINA]
filas = "".join(
    f"<tr><td><b>{r.codigo}</b></td><td>{r.lat:.4f}, {r.lon:.4f}{' · ANP' if r.en_anp else ''}"
    f"<br><span style='color:#6b7a72;font-size:.75rem'>{escape(r.distrito)} {escape(r.provincia)}</span></td>"
    f"<td>{r.fecha_hora:%d %b %Y %H:%M} UTC</td><td>{ui.badge(r.nivel)}</td><td>{r.estado_txt}</td></tr>"
    for r in vista.itertuples()
)
st.markdown(
    "<table class='gf-tabla'><tr><th>ID incidente</th><th>Ubicación</th><th>Detectado</th>"
    f"<th>Nivel de riesgo</th><th>Estado</th></tr>{filas}</table>",
    unsafe_allow_html=True,
)
st.caption(f"Mostrando {len(vista)} de {len(df):,}")
