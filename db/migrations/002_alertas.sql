-- Alinea alertas con el motor de riesgo (niveles en mayusculas, puntaje, reglas, estado).
ALTER TABLE alertas DROP CONSTRAINT IF EXISTS alertas_nivel_check;
ALTER TABLE alertas ADD CONSTRAINT alertas_nivel_check CHECK (nivel IN ('BAJO', 'MEDIO', 'ALTO', 'CRITICO'));
ALTER TABLE alertas ADD COLUMN IF NOT EXISTS puntaje INT;
ALTER TABLE alertas ADD COLUMN IF NOT EXISTS reglas TEXT[];
ALTER TABLE alertas ADD COLUMN IF NOT EXISTS estado TEXT NOT NULL DEFAULT 'ACTIVA';
ALTER TABLE alertas ADD COLUMN IF NOT EXISTS en_anp BOOLEAN;
CREATE UNIQUE INDEX IF NOT EXISTS uq_alertas_foco ON alertas (foco_id);
