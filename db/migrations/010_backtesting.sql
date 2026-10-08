-- Resultados reproducibles del backtesting (cap. XII, Sprint 6)
CREATE TABLE IF NOT EXISTS backtesting (
    id         BIGSERIAL PRIMARY KEY,
    creado_en  TIMESTAMPTZ NOT NULL DEFAULT now(),
    resultado  JSONB NOT NULL
);
