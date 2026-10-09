-- RN-04: fuentes de calor conocidas (aserraderos, plantas) y AC-09.2: zona asignada a cada usuario.
CREATE TABLE IF NOT EXISTS fuentes_calor_conocidas (
    id        BIGSERIAL PRIMARY KEY,
    nombre    TEXT,
    tipo      TEXT NOT NULL DEFAULT 'aserradero',   -- aserradero, hidrocarburos, planta, otro
    fuente    TEXT NOT NULL,                        -- OpenStreetMap, carga manual, ...
    osm_id    BIGINT,
    radio_m   INT NOT NULL DEFAULT 300,             -- un foco a menos de esta distancia se considera de la instalacion
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    geom      GEOMETRY(Point, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fuentes_conocidas_geom ON fuentes_calor_conocidas USING GIST (geom);
CREATE UNIQUE INDEX IF NOT EXISTS uq_fuentes_conocidas_osm ON fuentes_calor_conocidas (osm_id) WHERE osm_id IS NOT NULL;

-- Zona (distrito o provincia) a la que se limita el guardaparque
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS zona_id INT REFERENCES zonas(id);
