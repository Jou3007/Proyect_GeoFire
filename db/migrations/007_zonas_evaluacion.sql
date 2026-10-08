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
