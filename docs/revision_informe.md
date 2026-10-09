# Revisión del informe contra lo construido (estado final)

Fecha: 2026-10-08 · Fuente: `GeoFire_Peru_Informe_Avance2.docx` (cap. VII, VIII, XI y XII) · Código: rama `develop` más `feature/validacion-final`.
Sustituye a la revisión del 2026-10-07 (que listaba 12 de 17 requisitos funcionales y 7 de 19 criterios de aceptación cumplidos).

Leyenda: ✅ cumple · 🟡 cumple en parte o con una condición · ❌ falta · ➖ el propio informe lo marca como trabajo futuro.

## 1. Resumen

| Bloque | ✅ | 🟡 | ❌ | ➖ |
|---|---|---|---|---|
| Requisitos funcionales (17) | 15 | 2 | 0 | 0 |
| Criterios de aceptación (19) | 18 | 1 | 0 | 0 |
| Reglas de negocio (5) | 5 | 0 | 0 | 0 |
| Requisitos no funcionales (9) | 4 | 4 | 0 | 1 |
| Casos de prueba CP-01 a CP-19 | 19 | 0 | 0 | 0 |

**Lo que sigue pendiente depende de ti, no del código:** el despliegue en la nube (cuentas y claves), los datos oficiales de SERFOR (comunidades nativas
y focos confirmados) y la decisión sobre el umbral de NDVI. Además hay **un incumplimiento medido y documentado**: el tiempo de carga del mapa con
navegador real y varios usuarios (sección 5).

## 2. Mediciones

| Qué | Resultado | Meta del informe | Evidencia |
|---|---|---|---|
| Pruebas automáticas | **198 pasan** (192 + 6 omitidas en una base vacía, como la del CI) | todas | `pytest`, `ci.yml` |
| Cobertura del paquete `geofire` | **79 %** | ≥ 70 % | `pytest --cov` |
| Casos CP-01 a CP-19 | **19 de 19** | 100 % de prioridad alta | `docs/casos_de_prueba.md` |
| Secretos en el repositorio e historial | 0 hallazgos | ninguno | AC-01.2 |
| Ciclo de ingesta con Earth Engine real | **17 s** para 177 focos | ≤ 60 s | RNF-01 |
| Carga del mapa, solo servidor (20 ejecuciones) | **0.6–0.9 s** de promedio | < 5 s | CP-18 |
| Carga del mapa, navegador real, 1 usuario | **6.5 s** | < 5 s | `docs/pruebas_rendimiento.md` ❌ |
| 10 / 25 / 50 usuarios simultáneos | mapa en 37 s / 68 s / 94 % de errores | < 5 s | `docs/pruebas_rendimiento.md` ❌ |
| Lighthouse (pantalla de ingreso) | accesibilidad **100**, buenas prácticas 100, rendimiento 55 | accesibilidad ≥ 90 | RNF-05 |
| Contraste WCAG | modo normal ≥ 4.5:1 (AA), alto contraste ≥ 7:1 (AAA) | — | `src/geofire/contraste.py` |
| Máscara de agua vs radar Sentinel-1 | **98.6 %** del agua excluida (0.58 % de tierra excluida por error) | ≥ 95 % | `docs/validacion_mascara_agua.md` |
| Backtesting (499 eventos, 2 controles) | AUC **0.83** vs azar y **0.68** vs vecino; el umbral NDVI < 0.45 detecta solo 1.6 % | — | `docs/backtesting.md` |

## 3. Criterios de aceptación

| AC | Estado | Evidencia |
|---|---|---|
| AC-01.1 entorno reproducible | ✅ | README, Docker, `instalar_nube.py`, `salud.py` |
| AC-01.2 credenciales fuera del repo | ✅ | `.env` y `secrets.toml` ignorados; 0 hallazgos en el historial |
| AC-02.1 solo dentro de Ucayali, con fuente y fecha | ✅ | CP-02 automatizado con `tests/datos` |
| AC-02.2 reimportar no duplica | ✅ | CP-03; cada ciclo queda en `ejecuciones` |
| AC-03.1 NDVI/NBR con referencia de imágenes | ✅ | `lotes_imagenes` (hasta 482 imágenes por corrida) |
| AC-03.2 control de nubes; sin dato no se inventa ni se asigna Bajo | ✅ | estado **No evaluable** (focos y zonas), probado |
| AC-04.1 máscara de agua ≥ 95 % vs referencia | ✅ | 98.6 % vs radar; vs JRC histórico ≈ 80-90 % (explicado: JRC termina en 2021) |
| AC-04.2 píxeles de tierra excluidos por error y parámetros | ✅ | 0.58 %; corridas guardadas en `validaciones_mascara` |
| AC-05.1 filtros coherentes, estados diferenciados, fechas | ✅ | provincia/distrito, línea de tiempo, capas, comparación de fechas |
| AC-05.2 carga < 5 s en 20 ejecuciones, con y sin caché por separado | 🟡 | ✅ en servidor (0.6–0.9 s); ❌ con navegador real (6.5 s con 1 usuario). Con y sin caché reportados por separado |
| AC-06.1 evaluar zonas sin focos; "No evaluable" | ✅ | pantalla **Zonas en riesgo** (14 distritos y 4 provincias) |
| AC-06.2 variables, fecha de corte, versión de configuración | ✅ | `config_version`, `fecha_corte`, variables en cada evaluación |
| AC-06.3 alerta + envío con fecha y resultado, sin duplicados | ✅ | tabla `notificaciones`; reintento si falla |
| AC-07.1 roles, responsable, fecha, justificación; confirmar exige evidencia | ✅ | justificación obligatoria; confirmar exige foto o referencia |
| AC-07.2 estados Pendiente/Confirmado/Descartado con historial | ✅ | (el informe alterna «Descartado» y «Falsa alarma»; unificar el término al redactar) |
| AC-08.1 / AC-08.2 reportes | ✅ | PDF, CSV y GeoJSON con los mismos totales; fuentes y limitaciones |
| AC-09.1 login, hash, auditoría de accesos | ✅ | bcrypt; `log_auditoria` inmutable |
| AC-09.2 permisos y zona asignada | ✅ | el guardaparque solo ve y valida lo de su zona |

## 4. Requisitos funcionales, reglas de negocio y no funcionales

| Requisito | Estado | Nota |
|---|---|---|
| RF-01, RF-02, RF-04 a RF-08, RF-10, RF-11, RF-12, RF-14 a RF-17 | ✅ | RF-02 con límite GAUL (≈ 3 % de diferencia con el oficial); se reemplaza desde la pantalla **Geocercas** |
| RF-03 NASA Worldview | ✅ | humo/aerosoles (AOD) e imagen VIIRS por WMTS. **Desviación:** Worldview no publica viento sobre tierra |
| RF-09 capas con opacidad | 🟡 | FIRMS, NDVI, NBR, estrés, humo e imagen con opacidad; el **viento** se muestra como dato (Open-Meteo), no como capa |
| RF-13 notificaciones push y correo | 🟡 | correo ✅; sin notificación *push* en la interfaz |
| RN-01 a RN-05 | ✅ | RN-02 con el ajuste documentado en `docs/ajuste_RN-02.md`; RN-04 con 24 fuentes de OpenStreetMap |
| RNF-01 latencia ≤ 60 s | ✅ | 17 s |
| RNF-02 disponibilidad 99.9 % en la nube | 🟡 | **código y guía listos** (`docs/despliegue_nube.md`); falta que crees las cuentas y despliegues |
| RNF-03 trabajo sin conexión | ➖ | trabajo futuro según el informe |
| RNF-04 escalabilidad | 🟡 | degradación medida (50 usuarios); sin escalado horizontal implementado |
| RNF-05 alto contraste móvil | ✅ | interruptor de alto contraste; Lighthouse 100; contraste WCAG medido |
| RNF-06 cifrado | 🟡 | bcrypt ✅, SMTP con STARTTLS ✅, `sslmode=require` ✅; el TLS de la web llega con el despliegue |
| RNF-07 GeoJSON | ✅ | incidentes, reportes y zonas en RFC 7946 (con validador) |
| RNF-08 auditoría inmutable | ✅ | trigger que impide `UPDATE` y `DELETE` |
| RNF-09 mapa < 5 s | 🟡 | ✅ servidor; ❌ navegador real con varios usuarios |

## 5. Lo que no se cumple, dicho con claridad
1. **Tiempo de carga del mapa de extremo a extremo (RNF-09, AC-05.2).** 6.5 s con 1 usuario y 37 s con 10 usuarios simultáneos, contra una meta de 5 s.
   Es una medición pesimista (los navegadores de prueba comparten CPU con el servidor) pero el límite es real: Streamlit corre en un solo proceso.
   Mejoras aplicadas: caché de consultas (−37 % con 1 usuario). Pendiente: servidor dedicado y varias réplicas (`docs/pruebas_rendimiento.md`, sección 5).
2. **Umbral de NDVI del modelo.** El backtesting muestra que NDVI < 0.45 detecta solo el 1.6 % de los eventos; el NDVI sí distingue dónde habrá focos
   (AUC 0.83 / 0.68). Se recomienda niveles graduados (p. ej. < 0.6 y < 0.45) y decidirlo con SERFOR; no se cambió el modelo sin esa decisión.
3. **Disponibilidad en la nube (RNF-02):** no desplegado todavía (requiere tus cuentas).

## 6. Lo que solo puedes hacer tú
1. **Desplegar:** base PostGIS en la nube, cuenta de servicio de Google, Streamlit Cloud y secretos de GitHub (`docs/despliegue_nube.md`, 6 pasos).
2. **Datos oficiales:** registro de comunidades nativas (BDPI), límite oficial de Ucayali (INEI) y, sobre todo, la lista de **incendios confirmados** de SERFOR para repetir el backtesting.
3. **Decidir con SERFOR/INDECI:** el ajuste de RN-02, el umbral de NDVI y los umbrales de zona (provisionales).
4. **Pruebas con usuarios reales** (Sprint Review) y la medición de disponibilidad con un monitor externo.
5. **Actualizar el informe (Word)** con estas desviaciones: viento por Open-Meteo, límite GAUL, bcrypt, caché, y los resultados de las secciones 2 y 5.
