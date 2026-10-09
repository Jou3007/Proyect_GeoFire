# Lista de pendientes para terminar el proyecto (retómala en cualquier sesión)

Estado al 2026-10-09 (A1-A2 y B1-B7 hechos: web en Streamlit Cloud, ciclo cada 3 h en GitHub Actions, UptimeRobot 100 %). Todo el código está hecho y probado; lo que falta son **acciones tuyas** (cuentas, datos, decisiones). Cada paso trae lo que debes
decirle a Claude para continuar. Marca con una X lo que vayas terminando.

## A. Antes de nada
- [x] **A1. Fusionar el último pull request** (`feature/validacion-final` → `develop`) y revisar que el CI de GitHub (pestaña Checks) salga en verde.
  > Dile a Claude: «el CI salió en rojo, revisa» si falla.
- [x] **A2. Fusionar `develop` → `main`** (pull request). Streamlit Cloud publica desde `main`. Puede pedir la aprobación de otra persona (regla de `main`).

## B. Publicar gratis en la nube (RNF-02) — guía completa: `docs/despliegue_nube.md`
Costo: **0**. Servicios con plan gratuito: Neon (base de datos), Streamlit Community Cloud (la web), GitHub Actions (el ciclo cada 3 h), Google Earth Engine (uso no comercial).
- [x] **B1. Base de datos (Neon).** Crear cuenta, proyecto `geofire`, copiar la cadena de conexión (`postgresql://...`).
  > Dile a Claude: «ya tengo la cadena de Neon, instala la base» (la pegas **solo en tu terminal**, no en el chat).
- [x] **B2. Instalar el esquema y los datos base** en Neon (`scripts/instalar_nube.py`) y crear tu administrador (`scripts/crear_usuario.py`).
- [x] **B3. Cuenta de servicio de Google** para Earth Engine: crearla, descargar su clave JSON y registrarla en Earth Engine (paso 3 de la guía).
- [x] **B4. Streamlit Community Cloud.** New app → repositorio `Jou3007/Proyect_GeoFire`, rama `main`, archivo `app/main.py`, Python 3.12, pegar los *Secrets*.
- [x] **B5. GitHub Actions.** Cargar los secretos y la variable `CICLO_ACTIVO = true`; ejecutar el flujo `ingesta` una vez a mano.
- [x] **B6. Comprobar:** `scripts/salud.py` en `[OK]`; entrar a la dirección `.streamlit.app` y a Centro de operaciones. Apagar el programador local.
- [x] **B7. Monitor de disponibilidad:** registrar la dirección en UptimeRobot (gratis) y guardar el reporte (RNF-02, meta del MVP ≥ 95 %).

## C. Datos oficiales (RF y RN) — no hay descarga automática; hay que pedirlos o descargarlos
- [x] **C1. Comunidades nativas (parcial).** Cargadas 74 de RAISG/IBC dentro de Ucayali (scripts/load_comunidades.py); BDPI no ofrece descarga. Fuente oficial: **BDPI del Ministerio de Cultura** (bdpi.cultura.gob.pe, más de 9 mil localidades). Revisar si ofrece descarga;
  si no, pedirla por mesa de partes o correo. Alternativa referencial: capas de MapBiomas Perú (comunidades tituladas, IBC 2023).
  > Con el archivo (GeoJSON/CSV): «tengo el archivo de comunidades, cárgalo en reemplazo de OpenStreetMap».
- [x] **C2 (se usa GAUL, ver nota en el informe). Límite oficial de Ucayali** (INEI o IGN, GeoJSON). Se sube desde la pantalla **Geocercas** (valida topología y área).
- [ ] **C3. Incendios forestales confirmados.** SERFOR (visor GEOSERFOR, geo.serfor.gob.pe/visor) publica focos de calor y reportes; los confirmados
  suelen pedirse a SERFOR/INDECI (SINPAD). Pídelos por solicitud de acceso a la información pública (gratis).
  > Con la lista: «repite el backtesting con los incendios confirmados».
- [ ] **C4. Aserraderos y plantas** registrados (SERFOR/OSINFOR/OEFA): cargarlos en Geocercas → Fuentes de calor conocidas (CSV).

## D. Decisiones con SERFOR / INDECI / tu asesor
- [ ] **D1. Umbral de NDVI.** El backtesting (`docs/backtesting.md`) muestra que 0.45 detecta solo el 1.6 % de los eventos. Decidir niveles graduados (p. ej. < 0.6 y < 0.45).
  > Dile a Claude el umbral elegido: «cambia el umbral a X, reevalúa y documenta».
- [ ] **D2. Ajuste de RN-02** (la cercanía no genera Alto por sí sola): validarlo en la Sprint Review (`docs/ajuste_RN-02.md`).
- [ ] **D3. Umbrales de zona** (`config/riesgo.json`, sección `zonas`): provisionales; confirmarlos o ajustarlos.

## E. Tu informe en Word
- [ ] **E1.** Abrir `docs/Anexo_Implementacion_GeoFire.docx` (resumen de todo lo hecho) y adjuntarlo o copiarlo a tu informe.
- [ ] **E2.** Actualizar los capítulos con las desviaciones (viento por Open-Meteo, límite GAUL, caché, bcrypt, pruebas de carga con Playwright).
- [ ] **E3.** Pegar las tablas de `docs/casos_de_prueba.md` (resultado obtenido de CP-01 a CP-19) en la tabla 12.5.
- [ ] **E4.** Incluir capturas de las pantallas (login, centro, mapa, zonas, validación en celular, reportes, auditoría).

## F. Si quieres mejorar el rendimiento (opcional)
- [ ] **F1.** Servidor dedicado con varias réplicas (no es gratis); o limitar el número de puntos dibujados en el mapa. Ver `docs/pruebas_rendimiento.md`, sección 5.
- [ ] **F2.** Notificaciones *push* en la interfaz (RF-13) y viento como capa (RF-09): mejoras que quedan fuera de esta entrega.
