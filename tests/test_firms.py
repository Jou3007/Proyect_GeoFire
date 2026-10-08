import os
import unittest
from unittest import mock

import pandas as pd

from geofire import firms
from geofire.db import get_connection

CSV = (
    "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight\n"
    "-3.0,-60.0,330.1,0.4,0.4,2026-10-01,1830,N,VIIRS,n,2.0NRT,290.0,12.5,D\n"
    "-3.0,-50.0,331.0,0.4,0.4,2026-10-01,1830,N,VIIRS,h,2.0NRT,291.0,9.1,D\n"
)
FUENTE = "TEST_FIRMS"


class Respuesta:
    def __init__(self, status=200, text=CSV):
        self.status_code, self.text = status, text


class TestDescarga(unittest.TestCase):
    def test_parsea_el_csv(self):
        with mock.patch.dict(os.environ, {"NASA_FIRMS_MAP_KEY": "CLAVE-SECRETA"}), \
                mock.patch.object(firms.requests, "get", return_value=Respuesta()) as get:
            df = firms.fetch_hotspots("VIIRS_SNPP_NRT", days=1)
        self.assertEqual(len(df), 2)
        self.assertEqual(df["acq_time"].iloc[0], "1830")  # la hora se conserva como texto (no 1830.0)
        self.assertIn("/VIIRS_SNPP_NRT/", get.call_args.args[0])

    def test_historico_agrega_la_fecha(self):
        with mock.patch.dict(os.environ, {"NASA_FIRMS_MAP_KEY": "k"}), \
                mock.patch.object(firms.requests, "get", return_value=Respuesta()) as get:
            firms.fetch_hotspots("VIIRS_SNPP_SP", days=5, fecha="2025-03-01")
        self.assertTrue(get.call_args.args[0].endswith("/5/2025-03-01"))

    def test_error_http_no_filtra_la_clave(self):
        with mock.patch.dict(os.environ, {"NASA_FIRMS_MAP_KEY": "CLAVE-SECRETA"}), \
                mock.patch.object(firms.requests, "get", return_value=Respuesta(400, "Invalid MAP_KEY.")):
            with self.assertRaises(RuntimeError) as ctx:
                firms.fetch_hotspots("MODIS_NRT")
        self.assertNotIn("CLAVE-SECRETA", str(ctx.exception))
        self.assertIn("400", str(ctx.exception))

    def test_respuesta_inesperada(self):
        with mock.patch.dict(os.environ, {"NASA_FIRMS_MAP_KEY": "k"}), \
                mock.patch.object(firms.requests, "get", return_value=Respuesta(200, "Invalid MAP_KEY.")):
            with self.assertRaises(RuntimeError):
                firms.fetch_hotspots("MODIS_NRT")

    def test_sin_clave(self):
        with mock.patch.dict(os.environ, {"NASA_FIRMS_MAP_KEY": ""}):
            with self.assertRaises(RuntimeError):
                firms.fetch_hotspots("MODIS_NRT")


class TestGuardado(unittest.TestCase):
    """Usa una geocerca temporal alrededor de (-60, -3): un punto cae dentro y el otro (-50, -3) fuera (RN-01)."""

    def setUp(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO zonas (nombre, tipo, geom) VALUES ('Geocerca de prueba', 'geocerca', "
                "ST_Multi(ST_MakeEnvelope(-60.5, -3.5, -59.5, -2.5, 4326))) RETURNING id")
            self.zona = cur.fetchone()[0]
        self.df = pd.read_csv(__import__("io").StringIO(CSV), dtype={"acq_time": str, "confidence": str})

    def tearDown(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM focos_calor WHERE fuente = %s", (FUENTE,))
            cur.execute("DELETE FROM zonas WHERE id = %s", (self.zona,))

    def _cuantos(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*), min(fecha_hora)::text FROM focos_calor WHERE fuente = %s", (FUENTE,))
            return cur.fetchone()

    def test_solo_se_guardan_los_puntos_dentro_de_la_geocerca_ac_02_1(self):
        self.assertEqual(firms.save_hotspots(self.df, FUENTE), 1)
        n, fecha = self._cuantos()
        self.assertEqual(n, 1)
        self.assertTrue(fecha.startswith("2026-10-01 18:30"))  # conserva fecha y hora de adquisicion

    def test_reimportar_no_duplica_ac_02_2(self):
        firms.save_hotspots(self.df, FUENTE)
        self.assertEqual(firms.save_hotspots(self.df, FUENTE), 0)
        self.assertEqual(self._cuantos()[0], 1)

    def test_dataframe_vacio(self):
        self.assertEqual(firms.save_hotspots(self.df.iloc[0:0], FUENTE), 0)

    def test_ingest_suma_las_fuentes(self):
        with mock.patch.object(firms, "SOURCES", (FUENTE,)), \
                mock.patch.object(firms, "fetch_hotspots", return_value=self.df):
            self.assertEqual(firms.ingest(days=1), 1)
            self.assertEqual(firms.ingest(days=1), 0)


if __name__ == "__main__":
    unittest.main()
