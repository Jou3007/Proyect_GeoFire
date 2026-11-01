# GeoFire Campo (app Android para el guardaparque)

Prototipo funcional construido con Kotlin + Jetpack Compose. Permite al guardaparque, aun sin
señal en la selva, registrar **foto, audio, video y SOS con su ubicación GPS**; todo se guarda en
el teléfono y se envía solo cuando vuelve la conexión.

## Estructura

```
app/src/main/java/com/geofire/campo/
├── data/            Room: guarda los reportes mientras no hay señal
├── network/         Retrofit; aquí está la URL del servidor (RetrofitClient.kt)
├── services/        SyncWorker (reenvía al recuperar señal); LocationTrackingService (etapa 2, aun sin activar)
└── ui/              LoginScreen, DashboardScreen (foto/audio/video/SOS), tema GeoFire
```

## Compilar el .apk

Requiere Android Studio con el SDK (API 34) y JDK 17 o 21 (NO el JDK 25 embebido en versiones
nuevas de Android Studio: Gradle 8.10 no lo soporta todavía).

```bash
cd movil-campo
set JAVA_HOME=C:\Program Files\Java\jdk-21
gradlew.bat assembleDebug
```

El `.apk` queda en `app/build/outputs/apk/debug/app-debug.apk`. Instálalo con:

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

(con el teléfono conectado por USB y la depuración USB activada), o cópialo al teléfono y ábrelo
directamente (hay que aceptar "instalar de fuentes desconocidas" la primera vez).

## Servidor que recibe los reportes

Está en `../server_campo/` (FastAPI). Usa el mismo login que la web de GeoFire
(`geofire.seguridad.autenticar`), así que el guardaparque entra con su mismo correo y clave.
Los reportes y archivos de campo se guardan aparte, en SQLite y en disco, para no tocar el
esquema de producción.

```bash
docker compose up -d db campo_api
```

Queda escuchando en el puerto 8080.

## Cómo le llega al teléfono (ngrok, mientras no hay servidor en la nube)

```bash
ngrok http 80 --url https://plank-retired-amuck.ngrok-free.dev
```

La app ya trae esa dirección por defecto (`RetrofitClient.kt`). Si el enlace cambia algún día,
basta con editar `movil-campo/servidor.json` y subirlo a GitHub: la app lo relee solo al iniciar
sesión, sin que el guardaparque tenga que actualizar nada.

## Lo que falta (a propósito, declarado)

- **Rastreo continuo de ubicación** (`LocationTrackingService`): queda como segunda etapa, porque
  necesita el servidor ya en la nube (no una laptop con ngrok) y consume batería; hay que medirlo
  en campo antes de activarlo siempre.
- **Servidor en la nube**: hoy corre en Docker en una laptop. Para una prueba piloto real hay que
  moverlo a un servicio como Render, y los archivos pesados (audio/video) a un almacenamiento
  aparte (Neon solo tiene 0.5 GB libres).
