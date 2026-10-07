-- Registro de cada ciclo automatico (ingesta -> evaluacion -> correo) para trazabilidad.
CREATE TABLE IF NOT EXISTS ejecuciones (
    id          BIGSERIAL PRIMARY KEY,
    inicio      TIMESTAMPTZ NOT NULL,
    fin         TIMESTAMPTZ NOT NULL,
    estado      TEXT NOT NULL CHECK (estado IN ('OK', 'PARCIAL', 'ERROR')),
    duracion_s  DOUBLE PRECISION,
    detalle     JSONB
);
CREATE INDEX IF NOT EXISTS idx_ejecuciones_inicio ON ejecuciones (inicio DESC);
