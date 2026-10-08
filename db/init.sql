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

-- Migracion 006 (auditoria, trazabilidad, notificaciones, No evaluable)
-- RNF-08 (auditoria inmutable), AC-03.1/AC-06.2 (trazabilidad de evaluaciones), AC-06.3 (registro de envios),
-- AC-03.2/AC-06.1 (estado "No evaluable") y AC-07.1 (referencia de evidencia).

-- 1) Log de auditoria: solo se agrega, no se modifica ni se borra.
CREATE TABLE IF NOT EXISTS log_auditoria (
    id          BIGSERIAL PRIMARY KEY,
    fecha       TIMESTAMPTZ NOT NULL DEFAULT now(),
    evento      TEXT NOT NULL,
    usuario_id  INT,
    email       TEXT,
    detalle     JSONB
);
CREATE INDEX IF NOT EXISTS idx_auditoria_fecha ON log_auditoria (fecha DESC);
CREATE INDEX IF NOT EXISTS idx_auditoria_evento ON log_auditoria (evento);

CREATE OR REPLACE FUNCTION log_auditoria_inmutable() RETURNS trigger AS $$
BEGIN
    -- Solo las pruebas automaticas activan este permiso (SET LOCAL geofire.permitir_borrado = 'on').
    IF coalesce(current_setting('geofire.permitir_borrado', true), 'off') = 'on' THEN
        RETURN CASE TG_OP WHEN 'DELETE' THEN OLD ELSE NEW END;
    END IF;
    RAISE EXCEPTION 'log_auditoria es inmutable: no se permite % (RNF-08)', TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_auditoria_inmutable ON log_auditoria;
CREATE TRIGGER trg_auditoria_inmutable BEFORE UPDATE OR DELETE ON log_auditoria
    FOR EACH ROW EXECUTE FUNCTION log_auditoria_inmutable();

-- 2) Imagenes Sentinel-2 usadas en cada lote de evaluacion (AC-03.1)
CREATE TABLE IF NOT EXISTS lotes_imagenes (
    id          BIGSERIAL PRIMARY KEY,
    creado_en   TIMESTAMPTZ NOT NULL DEFAULT now(),
    coleccion   TEXT NOT NULL,
    desde       DATE,
    hasta       DATE,
    imagenes    TEXT[] NOT NULL DEFAULT '{}'
);

-- 3) Trazabilidad de cada evaluacion (AC-06.2) y estado "No evaluable" (AC-03.2, AC-06.1)
ALTER TABLE alertas ALTER COLUMN nivel DROP NOT NULL;
ALTER TABLE alertas DROP CONSTRAINT IF EXISTS alertas_nivel_check;
ALTER TABLE alertas ADD CONSTRAINT alertas_nivel_check CHECK (nivel IS NULL OR nivel IN ('BAJO', 'MEDIO', 'ALTO', 'CRITICO'));
ALTER TABLE alertas ADD COLUMN IF NOT EXISTS evaluada_en TIMESTAMPTZ;
ALTER TABLE alertas ADD COLUMN IF NOT EXISTS fecha_corte TIMESTAMPTZ;
ALTER TABLE alertas ADD COLUMN IF NOT EXISTS config_version TEXT;
ALTER TABLE alertas ADD COLUMN IF NOT EXISTS reevaluada_en TIMESTAMPTZ;
ALTER TABLE alertas ADD COLUMN IF NOT EXISTS lote_imagenes_id BIGINT REFERENCES lotes_imagenes(id);
ALTER TABLE alertas ADD COLUMN IF NOT EXISTS evaluable BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE alertas ADD COLUMN IF NOT EXISTS motivo TEXT;

-- 4) Registro de cada envio de notificacion (AC-06.3)
CREATE TABLE IF NOT EXISTS notificaciones (
    id             BIGSERIAL PRIMARY KEY,
    alerta_id      BIGINT NOT NULL REFERENCES alertas(id),
    enviada_en     TIMESTAMPTZ NOT NULL DEFAULT now(),
    canal          TEXT NOT NULL DEFAULT 'correo',
    destinatarios  TEXT[],
    resultado      TEXT NOT NULL CHECK (resultado IN ('ENVIADO', 'ERROR')),
    detalle        TEXT
);
CREATE INDEX IF NOT EXISTS idx_notificaciones_alerta ON notificaciones (alerta_id);

-- 5) Evidencia de la validacion (AC-07.1)
ALTER TABLE incidentes ADD COLUMN IF NOT EXISTS referencia_evidencia TEXT;

UPDATE alertas SET evaluada_en = creada_en, fecha_corte = creada_en WHERE evaluada_en IS NULL;
UPDATE alertas SET config_version = 'previa-a-trazabilidad' WHERE config_version IS NULL AND evaluable;
-- Provincias y distritos de Ucayali + evaluacion de riesgo POR ZONA, aunque no haya focos (HU-03, AC-06.1).
ALTER TABLE zonas ADD COLUMN IF NOT EXISTS padre_id INT REFERENCES zonas(id);
ALTER TABLE zonas ADD COLUMN IF NOT EXISTS codigo TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS uq_zonas_tipo_nombre ON zonas (tipo, nombre, COALESCE(padre_id, 0));

CREATE TABLE IF NOT EXISTS evaluaciones_zona (
    id                BIGSERIAL PRIMARY KEY,
    zona_id           INT NOT NULL REFERENCES zonas(id),
    evaluada_en       TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_corte       TIMESTAMPTZ NOT NULL,                 -- no se usan imagenes posteriores a esta fecha (AC-06.2)
    config_version    TEXT NOT NULL,
    ventana_dias      INT NOT NULL,
    evaluable         BOOLEAN NOT NULL,
    motivo            TEXT,                                 -- p. ej. COBERTURA_INSUFICIENTE (No evaluable)
    nivel             TEXT CHECK (nivel IS NULL OR nivel IN ('BAJO', 'MEDIO', 'ALTO', 'CRITICO')),
    ndvi_medio        DOUBLE PRECISION,
    ndvi_historico    DOUBLE PRECISION,                     -- mismo periodo de anios anteriores (linea base)
    pct_estres        DOUBLE PRECISION,                     -- % de la vegetacion con NDVI bajo el umbral de estres
    pct_cobertura     DOUBLE PRECISION,                     -- % de la zona con imagen valida (sin nubes ni agua)
    focos_30d         INT,
    focos_por_100km2  DOUBLE PRECISION,
    area_km2          DOUBLE PRECISION,
    reglas            TEXT[],
    lote_imagenes_id  BIGINT REFERENCES lotes_imagenes(id)
);
CREATE INDEX IF NOT EXISTS idx_evalzona_zona_fecha ON evaluaciones_zona (zona_id, evaluada_en DESC);
-- Resultado reproducible de cada validacion de la mascara de agua (AC-04.1, AC-04.2)
CREATE TABLE IF NOT EXISTS validaciones_mascara (
    id                   BIGSERIAL PRIMARY KEY,
    creada_en            TIMESTAMPTZ NOT NULL DEFAULT now(),
    umbral_ndwi          DOUBLE PRECISION NOT NULL,
    ventana_dias         INT NOT NULL,
    fecha_corte          DATE NOT NULL,
    referencia           TEXT NOT NULL,
    ocurrencia_agua_pct  INT NOT NULL,
    escala_m             INT NOT NULL,
    resultado            JSONB NOT NULL
);
