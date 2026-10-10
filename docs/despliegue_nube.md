# Despliegue en la nube (RNF-02): que el sistema funcione sin tu laptop

Arquitectura (cap. XI del informe): **Streamlit Community Cloud** (la web) + **base PostgreSQL con PostGIS en la nube** + **GitHub Actions**
(el ciclo cada 3 horas) + **Earth Engine con cuenta de servicio**. Todo tiene plan gratuito. Esta guia se puede seguir desde el celular.

> El codigo ya esta listo: la app lee sus claves de `st.secrets`, acepta `DATABASE_URL` con SSL, las fotos van a la base (no al disco, que en
> Streamlit Cloud se borra al reiniciar) y hay un instalador de la base. Lo que falta son **tus cuentas y claves**, que no puedo crear por ti.

## Paso 1. Base de datos PostGIS (Neon, gratis)
1. Entra a <https://neon.tech> y crea una cuenta (puedes usar GitHub). Crea un proyecto `geofire`, region **US East** (la mas cercana con plan gratuito).
2. En el panel copia la **cadena de conexion** (*Connection string*, empieza con `postgresql://`). Debe terminar en `?sslmode=require`. Guardala: es tu `DATABASE_URL`.
3. Neon permite `CREATE EXTENSION postgis`; el instalador lo hace solo.
   - Alternativa: Supabase (*Database > Extensions > postgis*).

## Paso 2. Instalar el esquema y los datos base (una vez, desde la laptop)
```bash
docker compose run --rm -e DATABASE_URL="postgresql://..." app python scripts/instalar_nube.py
docker compose run --rm -it -e DATABASE_URL="postgresql://..." app python scripts/crear_usuario.py
```
El primero crea las tablas, carga el limite de Ucayali, las provincias, los distritos, los asentamientos y los aserraderos (unos 3 minutos).
El segundo crea tu administrador (te pide la contrasena por teclado; no la escribas en ningun chat).
Opcional: copiar los focos historicos ya descargados (`pg_dump` de tu base local y `psql` a la nube) o volver a traerlos con `scripts/ingest_historico.py`.

## Paso 3. Cuenta de servicio de Google para Earth Engine
Hoy Earth Engine funciona con *tu* sesion personal; en la nube necesita una cuenta de servicio.
1. <https://console.cloud.google.com> -> proyecto `geofire-peru-ucayali-510812` -> *IAM y administracion* -> *Cuentas de servicio* -> **Crear**. Nombre: `geofire-ee`.
2. Roles: **Lector de recursos de Earth Engine** y **Consumidor de Service Usage**.
3. Entra a la cuenta creada -> *Claves* -> **Agregar clave > JSON**. Se descarga un archivo `.json`: es secreto.
4. Registra la cuenta de servicio en Earth Engine: <https://code.earthengine.google.com/register> -> *Register a service account* -> pega su correo (`geofire-ee@...iam.gserviceaccount.com`).
5. Verificacion (en la laptop, con el JSON a mano):
   `docker compose run --rm -e GEE_PROJECT=geofire-peru-ucayali-510812 -e GEE_SERVICE_ACCOUNT="$(cat clave.json)" app python scripts/test_gee.py`

## Paso 4. La web en Streamlit Community Cloud
1. <https://share.streamlit.io> -> inicia sesion con GitHub -> **New app**.
2. Repositorio `Jou3007/Proyect_GeoFire`, rama **main**, archivo principal **`app/main.py`**. En *Advanced settings* elige **Python 3.12**.
3. En *Secrets* pega el contenido de `.streamlit/secrets.toml.example` con tus valores (`DATABASE_URL`, `NASA_FIRMS_MAP_KEY`, `GEE_PROJECT`,
   SMTP y la tabla `[GEE_SERVICE_ACCOUNT]` con los campos del JSON del paso 3).
4. **Deploy**. En 2-3 minutos tendras una direccion `https://....streamlit.app` con HTTPS (TLS) incluido (RNF-06).
5. La app se *duerme* tras unos dias sin visitas: la primera visita la despierta (tarda ~30 s).

## Paso 5. El ciclo cada hora en GitHub Actions
En GitHub: repositorio -> *Settings* -> *Secrets and variables* -> *Actions*.
- **Secrets**: `DATABASE_URL`, `NASA_FIRMS_MAP_KEY`, `GEE_PROJECT`, `GEE_SERVICE_ACCOUNT` (el JSON completo), `SMTP_USER`, `SMTP_PASSWORD`, `ALERTA_DESTINATARIOS`.
- **Variables**: `CICLO_ACTIVO` = `true`.
Luego *Actions* -> *ingesta* -> **Run workflow** para probarlo. Despues corre solo cada hora y deja de depender de tu laptop.
Apaga entonces el programador local (`docker compose --profile auto stop scheduler`) para no duplicar correos.

## Paso 6. Comprobacion final
```bash
docker compose run --rm -e DATABASE_URL="..." -e GEE_PROJECT=... -e GEE_SERVICE_ACCOUNT="$(cat clave.json)" -e NASA_FIRMS_MAP_KEY=... app python scripts/salud.py
```
Debe mostrar `[OK]` en base, Earth Engine, NASA FIRMS, correo y ciclo. Entra a la direccion de Streamlit, inicia sesion y revisa **Centro de operaciones**.
Para medir disponibilidad (RNF-02) registra la direccion en un monitor externo gratuito (UptimeRobot) durante el Sprint 6.

## Limites del plan gratuito (para decirlo en la sustentacion)
- Neon gratuito: 0.5 GB y la base se suspende tras unos minutos de inactividad (la primera consulta tarda un poco). Alcanza para este prototipo; los 20 mil focos ocupan pocos MB.
- Streamlit Community Cloud: ~1 GB de memoria, un solo proceso; la prueba de carga (`docs/pruebas_rendimiento.md`) indica cuantos usuarios simultaneos aguanta el servidor local y sirve de referencia.
- GitHub Actions: los flujos programados pueden retrasarse varios minutos en horas de alta demanda.
- La meta de disponibilidad 99.9 % del informe requiere un servicio de pago; en el MVP se mide y se reporta (meta del MVP: >= 95 %).

## Seguridad
- Ninguna clave va al repositorio (`.env` y `.streamlit/secrets.toml` estan en `.gitignore`).
- Si una clave se expone, se revoca y se genera otra (NASA FIRMS, contrasena de aplicacion de Gmail, clave JSON de la cuenta de servicio, contrasena de Neon).
