import json
import os
import unittest
from datetime import date
from unittest import mock

from geofire import asentamientos, gee_indices as gi


class TestInicializacion(unittest.TestCase):
    def test_con_usuario(self):
        with mock.patch.dict(os.environ, {"GEE_PROJECT": "proyecto-x", "GEE_SERVICE_ACCOUNT": ""}), \
                mock.patch.object(gi.ee, "Initialize") as init:
            gi.init()
        init.assert_called_once_with(project="proyecto-x")

    def test_con_cuenta_de_servicio_sin_navegador(self):
        cuenta = json.dumps({"client_email": "bot@proyecto.iam.gserviceaccount.com", "private_key": "x"})
        with mock.patch.dict(os.environ, {"GEE_PROJECT": "proyecto-x", "GEE_SERVICE_ACCOUNT": cuenta}), \
                mock.patch.object(gi.ee, "ServiceAccountCredentials", return_value="CREDS") as cred, \
                mock.patch.object(gi.ee, "Initialize") as init:
            gi.init()
        cred.assert_called_once_with("bot@proyecto.iam.gserviceaccount.com", key_data=cuenta)
        init.assert_called_once_with("CREDS", project="proyecto-x")


class TestSinPuntos(unittest.TestCase):
    def test_indices_sin_puntos(self):
        self.assertEqual(gi.indices_para_puntos([]), {})
        res, meta = gi.indices_para_puntos([], con_meta=True)
        self.assertEqual((res, meta["imagenes"]), ({}, []))

    def test_area_sin_puntos(self):
        res = gi.area_quemada_ha([], date(2026, 1, 1), date(2026, 1, 5))
        self.assertEqual(res["area_ha"], 0.0)


class TestOpenStreetMap(unittest.TestCase):
    def test_descarga_por_cuadrantes_y_sin_duplicados(self):
        class R:
            status_code = 200

            @staticmethod
            def json():
                return {"elements": [{"id": 1, "lat": -9.0, "lon": -74.0, "tags": {"place": "village", "name": "A"}}]}

        with mock.patch.object(asentamientos.requests, "post", return_value=R()) as post:
            nodos = asentamientos.descargar()
        self.assertEqual(post.call_count, asentamientos.CUADRICULA ** 2)  # 3 x 3 consultas
        self.assertEqual(len(nodos), 1)  # el mismo nodo en todos los cuadrantes se cuenta una vez

    def test_reintenta_si_el_servidor_esta_saturado(self):
        class Malo:
            status_code = 504

        class Bueno:
            status_code = 200

            @staticmethod
            def json():
                return {"elements": []}

        with mock.patch.object(asentamientos.requests, "post", side_effect=[Malo(), Malo(), Bueno()]), \
                mock.patch.object(asentamientos.time, "sleep"):
            self.assertEqual(asentamientos._tramo(-12, -76, -7, -70), [])

    def test_si_nunca_responde_falla_con_mensaje_claro(self):
        class Malo:
            status_code = 504

        with mock.patch.object(asentamientos.requests, "post", return_value=Malo()), \
                mock.patch.object(asentamientos.time, "sleep"):
            with self.assertRaises(RuntimeError):
                asentamientos._tramo(-12, -76, -7, -70)


if __name__ == "__main__":
    unittest.main()
