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
