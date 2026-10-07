-- Esquema inicial GeoFire-Peru (Sprint 1). Se ejecuta solo la primera vez que se crea el volumen.
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS zonas (
    id          SERIAL PRIMARY KEY,
    nombre      TEXT NOT NULL,
    tipo        TEXT NOT NULL DEFAULT 'distrito',   -- region, provincia, distrito, ANP
    geom        GEOMETRY(MultiPolygon, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_zonas_geom ON zonas USING GIST (geom);

CREATE TABLE IF NOT EXISTS focos_calor (
    id          BIGSERIAL PRIMARY KEY,
    fuente      TEXT NOT NULL,                      -- VIIRS_SNPP_NRT, MODIS_NRT, ...
    fecha_hora  TIMESTAMPTZ NOT NULL,
    frp         DOUBLE PRECISION,
    confianza   TEXT,
    geom        GEOMETRY(Point, 4326) NOT NULL,
    creado_en   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (fuente, fecha_hora, geom)               -- evita duplicados (HU-02)
);
CREATE INDEX IF NOT EXISTS idx_focos_geom ON focos_calor USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_focos_fecha ON focos_calor (fecha_hora);

CREATE TABLE IF NOT EXISTS usuarios (
    id             SERIAL PRIMARY KEY,
    email          TEXT NOT NULL UNIQUE,
    password_hash  TEXT NOT NULL,
    rol            TEXT NOT NULL CHECK (rol IN ('administrador', 'autoridad_regional', 'guardaparque')),
    intentos_fallidos INT NOT NULL DEFAULT 0,
    bloqueado      BOOLEAN NOT NULL DEFAULT FALSE,
    nombre         TEXT,
    activo         BOOLEAN NOT NULL DEFAULT TRUE,
    ultimo_acceso  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS alertas (
    id          BIGSERIAL PRIMARY KEY,
    foco_id     BIGINT REFERENCES focos_calor(id),
    nivel       TEXT NOT NULL CHECK (nivel IN ('BAJO', 'MEDIO', 'ALTO', 'CRITICO')),
    ndvi        DOUBLE PRECISION,
    ndwi        DOUBLE PRECISION,
    nbr         DOUBLE PRECISION,
    creada_en   TIMESTAMPTZ NOT NULL DEFAULT now(),
    notificada  BOOLEAN NOT NULL DEFAULT FALSE,
    puntaje     INT,
    reglas      TEXT[],
    estado      TEXT NOT NULL DEFAULT 'ACTIVA',
    en_anp      BOOLEAN
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_alertas_foco ON alertas (foco_id);

CREATE TABLE IF NOT EXISTS asentamientos (
    id        BIGINT PRIMARY KEY,
    nombre    TEXT,
    tipo      TEXT NOT NULL,
    fuente    TEXT NOT NULL DEFAULT 'OpenStreetMap',
    geom      GEOMETRY(Point, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_asentamientos_geom ON asentamientos USING GIST (geom);

CREATE TABLE IF NOT EXISTS ejecuciones (
    id          BIGSERIAL PRIMARY KEY,
    inicio      TIMESTAMPTZ NOT NULL,
    fin         TIMESTAMPTZ NOT NULL,
    estado      TEXT NOT NULL CHECK (estado IN ('OK', 'PARCIAL', 'ERROR')),
    duracion_s  DOUBLE PRECISION,
    detalle     JSONB
);
CREATE INDEX IF NOT EXISTS idx_ejecuciones_inicio ON ejecuciones (inicio DESC);

CREATE TABLE IF NOT EXISTS incidentes (
    id           BIGSERIAL PRIMARY KEY,
    alerta_id    BIGINT NOT NULL REFERENCES alertas(id),
    estado       TEXT NOT NULL CHECK (estado IN ('PENDIENTE', 'CONFIRMADA', 'FALSA_ALARMA')) DEFAULT 'PENDIENTE',
    comentario   TEXT,
    foto_url     TEXT,
    usuario_id   INT REFERENCES usuarios(id),
    validado_en  TIMESTAMPTZ
);
