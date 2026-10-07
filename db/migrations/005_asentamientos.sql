-- Asentamientos humanos y comunidades (fuente: OpenStreetMap) para RN-02.1 (foco a menos de 10 km).
CREATE TABLE IF NOT EXISTS asentamientos (
    id        BIGINT PRIMARY KEY,                  -- id del nodo en OpenStreetMap
    nombre    TEXT,
    tipo      TEXT NOT NULL,                       -- city, town, village, hamlet
    fuente    TEXT NOT NULL DEFAULT 'OpenStreetMap',
    geom      GEOMETRY(Point, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_asentamientos_geom ON asentamientos USING GIST (geom);
