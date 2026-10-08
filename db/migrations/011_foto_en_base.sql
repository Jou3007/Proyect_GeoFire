-- Las fotos de validacion se guardan en la base de datos: el disco de Streamlit Cloud se borra al reiniciar.
ALTER TABLE incidentes ADD COLUMN IF NOT EXISTS foto_bytes BYTEA;
ALTER TABLE incidentes ADD COLUMN IF NOT EXISTS foto_tipo TEXT;
