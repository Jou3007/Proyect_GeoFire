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
