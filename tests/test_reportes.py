import csv
import io
import unittest
from datetime import date

from geofire import reportes as rp
from geofire.db import get_connection

DIA = date(2020, 1, 15)  # fecha antigua: no se mezcla con datos reales


def filas_csv(contenido: bytes):
    texto = contenido.decode("utf-8-sig")
    lineas = [l for l in texto.splitlines() if not l.startswith("#")]
    return list(csv.DictReader(io.StringIO("\n".join(lineas))))


class TestReportes(unittest.TestCase):
    """Crea 3 alertas de prueba (CRITICO activa, ALTO confirmada, ALTO activa) y las borra al final."""

    def setUp(self):
        self.focos = []
        with get_connection() as conn, conn.cursor() as cur:
            for i, (nivel, estado) in enumerate([("CRITICO", "ACTIVA"), ("ALTO", "CONFIRMADA"), ("ALTO", "ACTIVA")]):
                cur.execute(
                    "INSERT INTO focos_calor (fuente, fecha_hora, frp, geom) VALUES "
                    "('TEST_REPORTE', %s, 12.5, ST_SetSRID(ST_MakePoint(%s, -5.0), 4326)) RETURNING id",
                    (f"2020-01-15 1{i}:00+00", -70.0 - i * 0.1),
                )
                fid = cur.fetchone()[0]
                self.focos.append(fid)
                cur.execute(
                    "INSERT INTO alertas (foco_id, nivel, ndvi, ndwi, nbr, puntaje, estado, en_anp) "
                    "VALUES (%s, %s, 0.31, -0.6, 0.2, 40, %s, %s)", (fid, nivel, estado, i == 0),
                )

    def tearDown(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM alertas WHERE foco_id = ANY(%s)", (self.focos,))
            cur.execute("DELETE FROM focos_calor WHERE id = ANY(%s)", (self.focos,))

    def test_totales_coinciden_entre_pantalla_csv_y_pdf(self):
        rep = rp.construir(DIA, DIA)
        self.assertEqual(rep.total, 3)
        self.assertEqual(rep.por_nivel["CRITICO"], 1)
        self.assertEqual(rep.por_nivel["ALTO"], 2)
        self.assertEqual(len(filas_csv(rp.a_csv(rep))), rep.total)
        pdf = rp.a_pdf(rep)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertIn(b"Total de incidentes: 3", pdf)

    def test_filtro_de_nivel(self):
        rep = rp.construir(DIA, DIA, niveles=["ALTO"])
        self.assertEqual(rep.total, 2)
        filas = filas_csv(rp.a_csv(rep))
        self.assertEqual({f["nivel_riesgo"] for f in filas}, {"ALTO"})
        self.assertIn(b"Total de incidentes: 2", rp.a_pdf(rep))

    def test_filtro_de_estado(self):
        rep = rp.construir(DIA, DIA, estados=["CONFIRMADA"])
        self.assertEqual(rep.total, 1)
        self.assertEqual(filas_csv(rp.a_csv(rep))[0]["estado"], "Confirmada")

    def test_filtro_de_fechas(self):
        self.assertEqual(rp.construir(date(2020, 1, 16), date(2020, 1, 20)).total, 0)
        self.assertEqual(rp.construir(date(2020, 1, 14), date(2020, 1, 16)).total, 3)

    def test_reporte_vacio_no_rompe(self):
        rep = rp.construir(date(2019, 1, 1), date(2019, 1, 2))
        self.assertEqual(rep.total, 0)
        self.assertEqual(filas_csv(rp.a_csv(rep)), [])
        self.assertIn(b"Total de incidentes: 0", rp.a_pdf(rep))

    def test_metadatos_obligatorios_ac_08_2(self):
        rep = rp.construir(DIA, DIA)
        csv_txt = rp.a_csv(rep).decode("utf-8-sig")
        for esperado in ("Generado (UTC)", "Periodo consultado: 2020-01-15 a 2020-01-15", "Fuentes:", "Limitaciones:",
                         "prototipo académico", "Area afectada"):
            self.assertIn(esperado, csv_txt)
        pdf = rp.a_pdf(rep)
        for esperado in (b"Fecha de generaci", b"Periodo consultado", b"Fuentes de datos", b"Limitaciones",
                         b"Reportada por fuentes externas"):
            self.assertIn(esperado, pdf)

    def test_area_no_estimada_se_indica(self):
        rep = rp.construir(DIA, DIA, estimar_area=False)
        self.assertIsNone(rep.area)
        self.assertIn("no estimada", rp.a_csv(rep).decode("utf-8-sig"))


if __name__ == "__main__":
    unittest.main()
