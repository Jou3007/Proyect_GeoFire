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
