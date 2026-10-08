# Proyect_GeoFire (GeoFire-Peru)

Plataforma de alerta temprana de incendios forestales en Ucayali. Proyecto Integrador 2 - UTP.

Stack: Python, Google Earth Engine, NASA FIRMS, PostgreSQL + PostGIS, Docker, Streamlit/Folium.

## Puesta en marcha (HU-01)

Requisito: Docker Desktop.

```bash
cp .env.example .env          # y completa NASA_FIRMS_MAP_KEY y GEE_PROJECT
docker compose up -d db       # levanta PostgreSQL + PostGIS
docker compose run --rm app   # prueba de conexion a la base de datos
```

Earth Engine (primera vez):

```bash
docker compose run --rm app earthengine authenticate --auth_mode=notebook
docker compose run --rm app python scripts/test_gee.py
```

## Ramas
- `main`: version estable
- `develop`: integracion

## Ingesta de focos de calor (HU-02)

```bash
docker compose run --rm app python scripts/ingest_firms.py 5   # ultimos 5 dias
```
Descarga VIIRS y MODIS de NASA FIRMS para Ucayali y los guarda en `focos_calor` sin duplicados.

## Indices espectrales (HU-03)

```bash
docker compose run --rm app python scripts/ndvi_zona.py sepahua 30   # zona y dias
```
Calcula NDVI, NDWI y NBR sobre Sentinel-2 en Earth Engine (con mascara de nubes).

Carga historica (la API limita a 5 dias por consulta; SP hasta 2026-06-30, NRT desde 2026-07-01):
```bash
docker compose run --rm app python scripts/ingest_historico.py VIIRS_SNPP_SP 2025-01-01 2026-06-30
docker compose run --rm app python scripts/ingest_historico.py VIIRS_SNPP_NRT 2026-07-01 2026-10-07
```

## Alertas (HU-04, HU-06)

```bash
docker compose exec -T db psql -U geofire -d geofire < db/migrations/002_alertas.sql   # una vez, si la BD ya existia
docker compose run --rm app python scripts/procesar_alertas.py 72   # focos de las ultimas 72 h
```
Calcula NDVI/NDWI por foco en Earth Engine, excluye agua, detecta Areas Naturales Protegidas (WDPA) y guarda la alerta con su nivel de riesgo.

## Correo de alertas (HU-06)

```bash
docker compose run --rm app python scripts/enviar_alertas.py --dry-run   # simulacro, no envia
docker compose run --rm app python scripts/enviar_alertas.py             # envia y marca como notificadas
```
Requiere SMTP_USER, SMTP_PASSWORD (contrasena de aplicacion de Gmail) y ALERTA_DESTINATARIOS en `.env`.

## Interfaz web (HU-05)

```bash
docker compose up -d web      # abre http://localhost:8501
```
Pantallas: Centro de operaciones (KPIs), Mapa visor (focos por nivel de riesgo) e Incidentes (tabla con filtros y exportar CSV).

## Login y roles (HU-09)

```bash
docker compose exec -T db psql -U geofire -d geofire < db/migrations/003_usuarios.sql   # una vez, si la BD ya existia
docker compose run --rm app python scripts/crear_usuario.py   # crea el primer administrador (pide la clave por teclado)
```
Roles: `administrador` (todo + gestion de usuarios), `autoridad_regional` y `guardaparque`. La cuenta se bloquea tras 5 intentos fallidos.

## Validacion en campo (HU-07, RN-03)

Pantalla "Mis alertas" (pensada para celular): guardaparques y autoridad regional marcan cada alerta Alto/Critico
como confirmada o falsa alarma, con comentario y foto opcional. El administrador no puede validar (RN-03).
Las fotos se guardan en `data/fotos/` (fuera de git). El nivel de riesgo no cambia: se guarda aparte el estado.

## Reportes PDF/CSV (HU-08)

Pantalla "Reportes" (autoridad regional y administrador): filtra por periodo, nivel y estado y descarga PDF y CSV
con los mismos totales. Incluye fecha de generacion, periodo, fuentes, limitaciones y el area afectada estimada
con dNBR (opcional, usa Earth Engine). El area externa (oficial) no se incorpora; el documento lo indica.

## Ejecucion automatica cada 3 horas

Un ciclo = ingesta FIRMS -> evaluacion de riesgo -> correo (`python scripts/ciclo.py`, ~20 s). Si un paso falla se
reintenta 2 veces y el ciclo continua; cada corrida queda en la tabla `ejecuciones`.

**Opcion A: en tu PC (funciona ya).** Requiere Docker Desktop encendido y el PC despierto:
```bash
docker compose exec -T db psql -U geofire -d geofire < db/migrations/004_ejecuciones.sql   # una vez
docker compose --profile auto up -d scheduler      # arranca y repite cada 3 h
docker compose --profile auto stop scheduler       # para detenerlo
```

**Opcion B: GitHub Actions (`.github/workflows/ingesta.yml`).** Corre en la nube aunque tu PC este apagado, pero necesita:
1. Una base PostgreSQL con PostGIS en la nube (p. ej. Neon o Supabase). Cargar el esquema y el limite:
   `psql "$DATABASE_URL" -f db/init.sql` y `python scripts/load_limite.py` con `DATABASE_URL` definida.
2. Una cuenta de servicio de Google Cloud registrada en Earth Engine (su JSON va en el secreto `GEE_SERVICE_ACCOUNT`).
3. En GitHub, *Settings > Secrets and variables > Actions*: secretos `DATABASE_URL`, `NASA_FIRMS_MAP_KEY`, `GEE_PROJECT`,
   `GEE_SERVICE_ACCOUNT`, `SMTP_USER`, `SMTP_PASSWORD`, `ALERTA_DESTINATARIOS`; y la *variable* `CICLO_ACTIVO` = `true`.

Mientras `CICLO_ACTIVO` no exista, el flujo se omite y no falla.

## Integracion continua

`.github/workflows/ci.yml` corre `flake8` y `pytest` (con una base PostGIS de prueba) en cada pull request a `develop` o `main`.
Localmente: `pip install -r requirements-dev.txt && flake8 src app scripts tests && pytest`.

## Comunidades y asentamientos (RN-02.1)

```bash
docker compose exec -T db psql -U geofire -d geofire < db/migrations/005_asentamientos.sql   # una vez
docker compose run --rm app python scripts/load_asentamientos.py    # descarga de OpenStreetMap (~1 min)
docker compose run --rm app python scripts/reevaluar.py              # recalcula el nivel de las alertas sin validar
```
Fuente: OpenStreetMap (ODbL), no el registro oficial de comunidades nativas. Los tipos que cuentan para la regla se
configuran en `config/riesgo.json` (`tipos_asentamiento`); tras cambiarlos, vuelve a correr `reevaluar.py`.

## Auditoria y trazabilidad (RNF-08, AC-03.1, AC-06.2, AC-06.3, AC-09.1)

```bash
docker compose exec -T db psql -U geofire -d geofire < db/migrations/006_auditoria_trazabilidad.sql   # una vez
```
- `log_auditoria`: historial **inmutable** (un trigger impide `UPDATE` y `DELETE`) de accesos, bloqueos, validaciones,
  altas y cambios de usuarios, correos y errores de APIs. Se consulta en la pantalla **Auditoria** (solo administrador).
- Cada alerta guarda su fecha de corte, la version de `config/riesgo.json` (huella `config_version`) y el lote de
  imagenes Sentinel-2 usadas (`lotes_imagenes`). Sin imagenes validas el foco queda **No evaluable** (no es un nivel de riesgo).
- `notificaciones`: fecha, destinatarios y resultado (ENVIADO/ERROR) de cada correo; un fallo se reintenta en el ciclo siguiente.
- Contrasenas con **bcrypt** (las antiguas PBKDF2 se migran solas al iniciar sesion).
- Validar una alerta exige justificacion (>= 10 caracteres); confirmarla exige foto o referencia de evidencia. Las fotos se
  vuelven a guardar con Pillow (se quitan los metadatos EXIF).
