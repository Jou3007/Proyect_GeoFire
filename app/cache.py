"""Consultas con cache para el visor y el centro de operaciones (RNF-09, AC-05.2).

Cada sesion de Streamlit vuelve a ejecutar la pagina en cada interaccion; sin cache, 25 usuarios repiten las mismas consultas espaciales
25 veces. Los datos cambian como maximo en cada ciclo (3 h), asi que 60 s de cache no afectan el "tiempo casi real".
Los resultados con y sin cache se miden por separado en docs/pruebas_rendimiento.md.
"""
import streamlit as st

from geofire import ciclo, zonas
from geofire import repositorio as repo

CORTO = 60      # segundos: alertas, resumenes, series
LARGO = 3600    # segundos: catalogos que casi no cambian (provincias, distritos, geometrias)


def _c(fn, ttl):
    return st.cache_data(ttl=ttl, show_spinner=False)(fn)


# catalogos y geometrias
provincias = _c(repo.provincias, LARGO)
distritos = _c(repo.distritos, LARGO)
rango_de_focos = _c(repo.rango_de_focos, CORTO)
id_por_nombre = _c(zonas.id_por_nombre, LARGO)
geometria = _c(zonas.geometria, LARGO)
geometria_region = _c(zonas.geometria_region, LARGO)

# datos del tablero
alertas = _c(repo.alertas, CORTO)
focos_en_periodo = _c(repo.focos_en_periodo, CORTO)
resumen = _c(repo.resumen, CORTO)
por_provincia = _c(repo.por_provincia, CORTO)
no_evaluables = _c(repo.no_evaluables, CORTO)
focos_por_dia = _c(repo.focos_por_dia, CORTO)
totales = _c(repo.totales, CORTO)
zonas_ultimas = _c(zonas.ultimas, CORTO)
ultima_ejecucion = _c(ciclo.ultima_ejecucion, CORTO)
