# Pruebas de rendimiento (cap. 12.10 y 12.12 del informe)

Realizadas el 2026-10-08 en la laptop de desarrollo (Docker Desktop: 4 CPU, 8 GB), con 20 mil focos y 2.2 mil alertas en la base.
Scripts: `scripts/prueba_carga.py` (navegador real), `tests/test_casos_cp.py` (CP-18, CP-19) y Lighthouse.

## 1. Resumen contra las metas del informe

| Prueba | Meta | Resultado | Estado |
|---|---|---|---|
| RNF-09 / CP-18: cargar el mapa regional 20 veces (solo servidor, `AppTest`) | < 5 s en promedio | 0.9 s promedio, 4.5 s la primera carga | **Cumple** |
| RNF-09 con navegador real, 1 usuario | < 5 s | mapa en **6.5 s** (con caché) | **No cumple** (por poco) |
| 10 usuarios simultáneos, visor | < 5 s, 0 % de errores | mapa en **37 s**, 0 % de errores | **No cumple el tiempo** |
| 25 usuarios simultáneos, visor | < 5 s, < 1 % de errores | mapa en **68 s**, 0 % de errores | **No cumple el tiempo** |
| 50 usuarios simultáneos, visor | medir el punto de degradación | **94 % de errores** (tiempo agotado a los 120 s) | Degradación medida |
| RNF-01 / CP-19: ciclo de ingesta con 200 focos | < 60 s | 17 s con Earth Engine real (177 focos); < 1 s con Earth Engine simulado | **Cumple** |
| RNF-05: Lighthouse accesibilidad (pantalla de ingreso) | ≥ 90 | **100** | **Cumple** |
| Lighthouse buenas prácticas / rendimiento | — | 100 / 55 | Informativo |

## 2. Prueba de carga con navegador real (Playwright + Chromium)
Cada usuario abre la aplicación, inicia sesión y abre el **Mapa visor** hasta que el mapa está dibujado. Todos arrancan a la vez.
Se corrió dos veces con el mismo método: **antes** y **después** de agregar caché de 60 s a las consultas del visor y del centro de operaciones
(`app/cache.py`). Los resultados con y sin caché se reportan por separado, como pide AC-05.2.

| Usuarios | Sin caché: sesión / mapa / errores | Con caché: sesión / mapa / errores |
|---|---|---|
| 1 | 8.8 s / 10.3 s / 0 % | 7.6 s / 6.5 s / 0 % |
| 3 | 16.4 s / 32.6 s / 0 % | — |
| 5 | 21.3 s / 22.2 s / 0 % | — |
| 10 | 67.6 s / 47.9 s / 0 % | 46.4 s / 37.3 s / 0 % |
| 25 | 128.7 s / 83.8 s / 4 % | 108.3 s / 67.5 s / 0 % |
| 50 | — / — / 100 % | 137 s / 35 s / 94 % |

(«sesión» = desde que se abre la página hasta ver el menú tras iniciar sesión; «mapa» = desde que se pulsa *Mapa visor* hasta que el mapa aparece.)

### Cómo leerlo (y sus límites)
- Es una **medición pesimista**: los navegadores de prueba corren en la misma laptop y en el mismo Docker que el servidor, así que compiten por CPU.
  Un servidor en la nube con los usuarios en sus propios equipos rendiría mejor; esta prueba sirve para comparar versiones, no como cifra absoluta.
- Aun así hay un límite real: Streamlit ejecuta cada sesión como un script de Python dentro de **un solo proceso**; las sesiones se pelean por el mismo núcleo.
  Con 1 usuario el mapa tarda 6.5 s en un navegador real, aunque el servidor tarda 0.9 s en producir la página: el resto es la descarga de la aplicación,
  el dibujado de Folium y de las teselas.
- El caché ayudó (mapa 37 % más rápido con 1 usuario; 25 usuarios sin errores en vez de 4 %), pero no cambia el orden de magnitud.
- El «inicio de sesión» incluye la primera carga del paquete de JavaScript de Streamlit (varios MB) y la pantalla de Centro de operaciones con sus gráficos.
- La meta del informe (< 5 s con 10 usuarios) **no se cumple** con esta arquitectura en una máquina local.

## 3. Lighthouse (pantalla de ingreso, http://localhost:8501)
Versión 13.5.0, modo móvil simulado (red lenta y CPU 4× más lenta): accesibilidad **100**, buenas prácticas **100**, rendimiento **55**
(primer contenido visible 13.7 s *simulados*, 0 ms de bloqueo). El rendimiento bajo se debe al peso del paquete de Streamlit y a la simulación de red 4G lenta;
la accesibilidad, que es lo que exige RNF-05, no tiene fallas. El contraste de color se midió además con la relación WCAG (`src/geofire/contraste.py`):
modo normal ≥ 4.5:1 (AA) y modo de alto contraste ≥ 7:1 (AAA).

## 4. Ciclo de ingesta (RNF-01 / CP-19)
- Con Earth Engine real: 177 focos nuevos se descargaron y evaluaron en **17 s** (4 s de ingesta + 13 s de evaluación).
- Con 200 focos y Earth Engine simulado: el procesamiento propio (consultas espaciales, motor de riesgo, guardado) toma menos de 1 s: el tiempo lo domina Earth Engine.
- Meta del informe para 500 focos (< 5 min): se extrapola ~45 s (la evaluación se hace por lotes de 300).

## 5. Qué hacer para cumplir la meta de 5 s con muchos usuarios
1. **Desplegar en un servidor dedicado** (no en la laptop con los navegadores): quita la competencia de CPU de esta prueba.
2. **Varias réplicas de la aplicación** detrás de un balanceador (Streamlit Community Cloud no lo permite; sí un servidor propio con Docker): reparte las sesiones entre procesos.
3. **Menos trabajo por sesión**: la pantalla de Mapa visor reconstruye Folium en cada interacción; separar el mapa en un componente que no se rehaga, o reducir los
   puntos dibujados (agrupar con clústeres), baja el tiempo de dibujado.
4. **Repetir la prueba en la nube**: `scripts/prueba_carga.py` apunta a cualquier dirección (`GEOFIRE_URL`).
