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

-- 6) Alertas anteriores a esta migracion: se conserva su fecha y se marca que no tienen version de configuracion
UPDATE alertas SET evaluada_en = creada_en, fecha_corte = creada_en WHERE evaluada_en IS NULL;
UPDATE alertas SET config_version = 'previa-a-trazabilidad' WHERE config_version IS NULL AND evaluable;
