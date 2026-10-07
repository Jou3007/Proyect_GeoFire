# Revisión del informe contra lo construido

Fecha de la revisión: 2026-10-07 · Fuente: `GeoFire_Peru_Informe_Avance2.docx` (cap. VII, VIII, XI y XII) · Código: rama `develop`.

Leyenda: ✅ cumple · 🟡 cumple en parte · ❌ falta · ➖ el propio informe lo marca como trabajo futuro.

## 1. Resumen

| Bloque | ✅ | 🟡 | ❌ |
|---|---|---|---|
| Requisitos funcionales (17) | 12 | 2 | 3 |
| Criterios de aceptación (19) | 7 | 9 | 3 |
| Requisitos no funcionales (9) | 2 | 1 | 5 (+1 ➖) |

Lo construido cubre bien la cadena **detectar → evaluar → alertar → validar → reportar**. Lo que falta se concentra en tres zonas:
1. **La parte preventiva** (evaluar zonas *antes* de que haya fuego), que es el objetivo central del proyecto.
2. **Trazabilidad y auditoría** (qué se evaluó, con qué datos, quién hizo qué).
3. **Despliegue y pruebas de calidad** exigidas por el cap. XII.

## 2. Mediciones hechas en esta revisión

| Qué | Resultado | Meta del informe |
|---|---|---|
| Secretos en archivos versionados e historial de git (AC-01.2) | 0 hallazgos (clave NASA, contraseña SMTP y firmas comunes) | ninguno |
| Cobertura de pruebas del paquete `geofire` | **61 %** (52 pruebas pasan) | ≥ 70 % |
| Ciclo completo ingesta → evaluación (CP-19, 177 focos) | **17 s** | ≤ 60 s |
| Carga del mapa, 20 ejecuciones, solo servidor (AC-05.2 / RNF-09) | promedio **0.9 s**, máximo 4.5 s (1.ª carga) | < 5 s |

Límites de estas mediciones: el tiempo del mapa excluye el dibujado de teselas en el navegador y no separa caché de no caché;
la cobertura baja por `correo.py` (0 %), `firms.py` (0 %) y `gee_indices.py` (26 %), que se probaron a mano pero no tienen pruebas automáticas.

## 3. Historias de usuario y criterios de aceptación

| AC | Estado | Evidencia / qué falta |
|---|---|---|
| AC-01.1 entorno reproducible | ✅ | README, Docker, `test_db.py`, `test_gee.py` |
| AC-01.2 credenciales fuera del repo | ✅ | `.env` ignorado; 0 hallazgos en el historial |
| AC-02.1 solo puntos dentro de Ucayali, con fuente y fecha | ✅ | geocerca de 5 km; se descartó el 60 % de los focos del rectángulo. Falta prueba automática |
| AC-02.2 reimportar no duplica | ✅ | 2.ª corrida = 0 nuevos; cada ciclo queda en `ejecuciones`. Histórico: 19,864 focos |
| AC-03.1 NDVI/NBR con referencia de imágenes | 🟡 | NDVI/NBR correctos y en [-1, 1]; **no se guarda qué imágenes se usaron** |
| AC-03.2 control de nubes; sin dato no se inventa ni se asigna Bajo | 🟡 | máscara SCL; sin cobertura el foco se omite y se reintenta, pero **no queda registrado como "No evaluable"** |
| AC-04.1 máscara de agua ≥ 95 % vs referencia | ❌ | existe la máscara NDWI > 0; **nunca se evaluó contra una referencia** (p. ej. JRC Global Surface Water) |
| AC-04.2 registrar píxeles de tierra excluidos por error | ❌ | igual: falta la evaluación y su documentación |
| AC-05.1 filtros coherentes en mapa y dashboard | 🟡 | filtros de 6/24/48/72 h y por nivel; **faltan capas NDVI/NBR, línea de tiempo y filtro por provincia/distrito** |
| AC-05.2 carga < 5 s en 20 ejecuciones | 🟡 | medido solo en servidor (0.9 s); falta navegador y separar caché |
| AC-06.1 evaluar zonas sin focos; estado "No evaluable" | ❌ | solo se evalúan **focos**; no hay evaluación por zona ni estado "No evaluable" |
| AC-06.2 variables, fecha de corte y versión de configuración | 🟡 | se guardan NDVI, NDWI, NBR, reglas y puntaje; **faltan fecha de corte y versión de `riesgo.json`** |
| AC-06.3 alerta + envío, con fecha y resultado, sin duplicados | 🟡 | alerta única por foco y correo funcionando; **no se guarda fecha ni resultado del envío** (solo `notificada`) |
| AC-07.1 solo roles validadores; responsable, fecha, justificación; confirmar exige evidencia | 🟡 | rol, responsable y fecha ✅ (RN-03, probado); **la justificación y la evidencia son opcionales** |
| AC-07.2 estados Pendiente/Confirmado/Descartado, con historial | ✅ | estado separado del riesgo; historial por usuario. (El informe alterna "Descartado" y "Falsa alarma": unificar el término) |
| AC-08.1 PDF y CSV coinciden con filtros y totales | ✅ | 7 pruebas automáticas |
| AC-08.2 fecha, periodo, fuentes, limitaciones, área externa vs estimada | ✅ | en PDF y CSV |
| AC-09.1 credenciales válidas/incorrectas; hash; auditoría de accesos | 🟡 | login y hash ✅; **los accesos no se registran en auditoría** |
| AC-09.2 permisos por rol; guardaparque solo de su zona | 🟡 | roles y acceso directo bloqueados ✅; **no existe "zona asignada"** |

## 4. Requisitos funcionales

| RF | Estado | Nota |
|---|---|---|
| RF-01 API NASA FIRMS | ✅ | VIIRS S-NPP, NOAA-20 y MODIS |
| RF-02 Filtro geográfico | ✅ | polígono FAO GAUL + 5 km (el informe pide el límite oficial; diferencia de área ≈ 3 %) |
| RF-03 NASA Worldview (humo, viento) | ❌ | prioridad Media; no iniciado |
| RF-04 Sentinel-2 | ✅ | vía Earth Engine, sin descargar imágenes (como define el cap. XI) |
| RF-05 NDVI · RF-06 NBR | ✅ | |
| RF-07 Triangulación de riesgo | ✅ | RN-02 con el ajuste documentado en `docs/ajuste_RN-02.md` |
| RF-08 Mapa base con capas de GEE | 🟡 | mapa Folium centrado en Ucayali; **sin capas temáticas de GEE** |
| RF-09 Capas con opacidad (FIRMS, NDVI, NBR, viento, humo) | ❌ | solo focos |
| RF-10 Atributos al hacer clic | ✅ | |
| RF-11 Línea de tiempo | ❌ | solo ventana 6/24/48/72 h |
| RF-12 Alertas automáticas | ✅ | |
| RF-13 Notificaciones push y correo | 🟡 | correo ✅; **sin notificación push en la interfaz** |
| RF-14 Validación de incidentes | ✅ | |
| RF-15 Reportes PDF/CSV con hectáreas por NBR | ✅ | falta desglose por provincia/distrito (el informe lo menciona) |
| RF-16 Autenticación · RF-17 Roles | ✅ | |

## 5. Reglas de negocio

| RN | Estado | Nota |
|---|---|---|
| RN-01 geocerca | ✅ | |
| RN-02 riesgo crítico | ✅ | con el ajuste de cercanía (decisión pendiente de validar con SERFOR/INDECI) |
| RN-03 validación humana | ✅ | el administrador no puede validar |
| RN-04 fuentes de calor conocidas (aserraderos) | ❌ | el motor lo soporta, pero **no hay datos ni carga de fuentes conocidas** (`cerca_fuente_conocida` siempre falso) |
| RN-05 vigencia de 6 h | ✅ | |

## 6. Requisitos no funcionales

| RNF | Estado | Nota |
|---|---|---|
| RNF-01 latencia ≤ 60 s | ✅ | 17 s |
| RNF-02 disponibilidad 99.9 % en la nube | ❌ | corre en tu PC; no hay despliegue (Streamlit Cloud + base en la nube) |
| RNF-03 trabajo sin conexión | ➖ | trabajo futuro según el propio informe |
| RNF-04 escalabilidad | ➖ | sin prueba de carga (Locust) |
| RNF-05 alto contraste móvil | ❌ | no hay modo de alto contraste |
| RNF-06 cifrado: TLS y **bcrypt** | 🟡 | se usa PBKDF2-SHA256 (sólido, pero **el informe dice bcrypt**); TLS depende del despliegue; SMTP usa STARTTLS |
| RNF-07 GeoJSON | ❌ | no hay exportación GeoJSON |
| RNF-08 auditoría inmutable | ❌ | no existe `log_auditoria`; los fallos de ciclo sí quedan en `ejecuciones` |
| RNF-09 mapa < 5 s | ✅ | 0.9 s en servidor |

## 7. Pruebas y calidad (cap. XII)

| Elemento | Estado |
|---|---|
| Pruebas unitarias en cada PR (CI con flake8 + pytest) | ✅ configurado (`ci.yml`) |
| Cobertura ≥ 70 % | 🟡 61 % |
| Casos CP-01 a CP-19 con evidencia | 🟡 comportamientos verificados a mano, **sin registrar la evidencia** (fecha y captura/salida) en la tabla 12.5 |
| Conjunto de datos de prueba `tests/datos/` (foco en ANP, junto a aserradero, en el río, fuera de la región) | ❌ |
| Pruebas de rendimiento con Locust (10/25/50 usuarios) y Lighthouse ≥ 90 | ❌ |
| Backtesting con focos históricos confirmados (Sprint 6) | ❌ requiere datos de SERFOR; ver opción en el plan |
| Disponibilidad con monitor externo (UptimeRobot) | ❌ depende del despliegue |

## 8. Despliegue

| Elemento | Estado |
|---|---|
| Ciclo cada 3 h | ✅ local (programador Docker); 🟡 en la nube (flujo listo, faltan base en la nube y cuenta de servicio) |
| Publicación en Streamlit Community Cloud al pasar `develop` a `main` | ❌ |
| Base PostGIS en la nube con SSL | ❌ (el código ya acepta `DATABASE_URL`) |

## 9. Plan sugerido (por valor para la entrega)

**Prioridad 1 — cierra criterios con poco esfuerzo**
1. **Auditoría** (`log_auditoria`): inicios de sesión, bloqueos, validaciones, altas de usuario y errores de APIs. Cierra RNF-08 y AC-09.1.
2. **Trazabilidad de evaluaciones y envíos**: guardar fecha de corte, versión de configuración, imágenes usadas y fecha/resultado del envío. Cierra AC-03.1, AC-06.2 y AC-06.3.
3. **Validación más estricta**: justificación y evidencia obligatorias al confirmar; re-guardar la foto con Pillow. Cierra AC-07.1.
4. **bcrypt** en lugar de PBKDF2 (RNF-06), con migración transparente al iniciar sesión.
5. **Subir la cobertura a ≥ 70 %** con pruebas (simuladas) de `firms.py`, `correo.py` y `gee_indices.py`.

**Prioridad 2 — el núcleo preventivo del proyecto**
6. **Evaluación por zona sin focos** (HU-03, AC-06.1): mapa de NDVI de una zona (Sepahua/Atalaya) con las áreas de estrés resaltadas y estado "No evaluable" cuando no hay imágenes válidas.
7. **Provincias y distritos** (límites FAO GAUL nivel 2) para filtros, dashboard y reportes.
8. **Capas del mapa** (NDVI, NBR) con opacidad y línea de tiempo (RF-08, RF-09, RF-11).
9. **Validación de la máscara de agua** contra JRC Global Surface Water (AC-04.1/04.2).

**Prioridad 3 — completar el diseño**
10. RN-04: tabla y carga de fuentes de calor conocidas (aserraderos) y pantalla de Geocercas del administrador.
11. Zona asignada por guardaparque (AC-09.2). Exportación GeoJSON (RNF-07). Modo de alto contraste (RNF-05).
12. Pruebas de rendimiento (Locust, Lighthouse) y conjunto `tests/datos/`.

**Prioridad 4 — requiere acciones o datos tuyos**
13. Despliegue en la nube (base PostGIS con SSL, cuenta de servicio de Google, Streamlit Cloud) → RNF-02, RF de disponibilidad.
14. Registro oficial de comunidades nativas (BDPI) y focos históricos **confirmados** por SERFOR para el backtesting.
15. Sustentar el ajuste de RN-02 y los umbrales provisionales en la Sprint Review.

**Opción de backtesting sin datos de SERFOR:** con los 19,864 focos históricos se puede medir si el NDVI de 15 días antes
distingue los lugares donde luego hubo focos de lugares donde no. No sustituye los incendios confirmados, pero da una
primera evidencia cuantitativa de la hipótesis.
