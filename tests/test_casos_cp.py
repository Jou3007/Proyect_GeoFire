"""Casos de prueba CP-01 a CP-19 del cap. 12.8 del informe, uno por caso, con el conjunto tests/datos/.

Los casos que necesitan Earth Engine o la geocerca real se omiten (skip) si no estan disponibles (p. ej. en el CI de GitHub).
`python scripts/evidencia_casos.py` ejecuta este archivo y escribe docs/casos_de_prueba.md con el resultado y la fecha.
"""
import csv
import io
import json
import os
import secrets
import sys
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
DATOS = Path(__file__).resolve().parent / "datos"
sys.path[:0] = [str(RAIZ / "app"), str(RAIZ / "src")]

from geofire import alertas, correo, firms, reportes, seguridad, validacion as val  # noqa: E402
from geofire import gee_indices as gi  # noqa: E402
from geofire import repositorio as repo  # noqa: E402
from geofire.db import get_connection  # noqa: E402
from geofire.riesgo import Contexto, Foco, evaluar  # noqa: E402
from util_pruebas import borrar_auditoria_de_prueba, imagen_bytes  # noqa: E402

CSV_FIRMS = (DATOS / "focos_firms_ejemplo.csv").read_text(encoding="utf-8")
ESCENARIOS = {e["id"]: e for e in json.loads((DATOS / "escenarios_riesgo.json").read_text(encoding="utf-8"))["escenarios"]}
JUSTIF = "Se observa humo desde el camino"


def anotar(clave, valor):
    """Guarda una medicion para que scripts/evidencia_casos.py la incluya en docs/casos_de_prueba.md."""
    archivo = Path(tempfile.gettempdir()) / "geofire_mediciones.json"
    datos = json.loads(archivo.read_text()) if archivo.exists() else {}
    datos[clave] = valor
    archivo.write_text(json.dumps(datos))


def hay_region():
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM zonas WHERE tipo = 'region'")
        return cur.fetchone()[0] > 0


def gee_disponible():
    try:
        gi.init()
        import ee
        ee.Number(1).getInfo()
        return True
    except Exception:
        return False


GEE = gee_disponible()
REGION = hay_region()


def evaluar_escenario(clave):
    e = ESCENARIOS[clave]
    return e, evaluar(Foco(**e["foco"]), Contexto(**e["contexto"]))


class Respuesta:
    status_code, text = 200, CSV_FIRMS


def lista_de_focos():
    return pd.read_csv(io.StringIO(CSV_FIRMS), dtype={"acq_time": str, "confidence": str})


class GeocercaDePrueba(unittest.TestCase):
    """Si la base no tiene la geocerca real (CI), crea una caja que cubre Ucayali y la retira al final."""

    temporal = None

    def setUp(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM zonas WHERE tipo = 'geocerca'")
            if cur.fetchone()[0] == 0:
                cur.execute("INSERT INTO zonas (nombre, tipo, geom) VALUES ('Geocerca CP', 'geocerca', "
                            "ST_Multi(ST_MakeEnvelope(-75.95, -12.0, -70.45, -7.25, 4326))) RETURNING id")
                self.temporal = cur.fetchone()[0]

    def tearDown(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM focos_calor WHERE fuente = 'TEST_CP'")
            if self.temporal:
                cur.execute("DELETE FROM zonas WHERE id = %s", (self.temporal,))


class TestIngesta(GeocercaDePrueba):
    def test_cp_01_descarga_de_focos_de_1_dia_trae_las_columnas(self):
        with mock.patch.dict(os.environ, {"NASA_FIRMS_MAP_KEY": "k"}), mock.patch.object(firms.requests, "get", return_value=Respuesta()):
            df = firms.fetch_hotspots("VIIRS_SNPP_NRT", days=1)
        self.assertTrue({"latitude", "longitude", "acq_date", "frp"} <= set(df.columns))
        self.assertEqual(len(df), 5)

    def test_cp_02_foco_en_pucallpa_se_guarda_y_el_de_huanuco_se_descarta(self):
        self.assertEqual(firms.save_hotspots(lista_de_focos(), "TEST_CP"), 2)  # Pucallpa y Atalaya, dentro de Ucayali
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT ST_X(geom) FROM focos_calor WHERE fuente = 'TEST_CP' ORDER BY 1")
            lons = [r[0] for r in cur.fetchall()]
        self.assertEqual([round(x, 2) for x in lons], [-74.55, -73.76])  # ni -76.40 (Huanuco), ni -69.00 (Brasil), ni -74.00 (Loreto)

    def test_cp_03_repetir_la_descarga_del_mismo_dia_no_duplica(self):
        firms.save_hotspots(lista_de_focos(), "TEST_CP")
        self.assertEqual(firms.save_hotspots(lista_de_focos(), "TEST_CP"), 0)


@unittest.skipUnless(GEE, "requiere Earth Engine")
class TestIndicesEnVivo(unittest.TestCase):
    def test_cp_04_ndvi_de_una_zona_esta_entre_menos_1_y_1(self):
        r = gi.stats_punto(*gi.ZONAS["sepahua"], days=30)
        self.assertGreater(r["imagenes"], 0)
        for k in ("NDVI", "NDWI", "NBR"):
            self.assertTrue(-1 <= r[k] <= 1, k)

    def test_cp_05_el_nbr_de_un_area_quemada_es_menor_que_el_de_la_vegetacion_sana(self):
        import ee
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT ST_X(geom), ST_Y(geom) FROM focos_calor WHERE fecha_hora BETWEEN '2026-08-15' AND '2026-08-26' "
                        "AND frp > 15 ORDER BY frp DESC LIMIT 60")
            pts = cur.fetchall()
        if len(pts) < 5:
            self.skipTest("no hay focos intensos de agosto de 2026 en la base")
        region = ee.Geometry.MultiPoint([list(p) for p in pts]).buffer(1000)
        pre = gi.collection_entre(region, date(2026, 7, 16), date(2026, 8, 14)).select(["NBR", "NDWI"]).median()
        post = gi.collection_entre(region, date(2026, 8, 15), date(2026, 9, 5)).select(["NBR", "NDWI"]).median()
        quemado = pre.select("NBR").subtract(post.select("NBR")).gt(gi.UMBRAL_DNBR).And(pre.select("NDWI").lt(gi.UMBRAL_AGUA))
        nbr = post.select("NBR")
        r = ee.Dictionary({
            "quemado": nbr.updateMask(quemado).reduceRegion(ee.Reducer.mean(), region, 20, maxPixels=1e9).get("NBR"),
            "sano": nbr.updateMask(quemado.Not()).updateMask(post.select("NDWI").lt(gi.UMBRAL_AGUA))
                       .reduceRegion(ee.Reducer.mean(), region, 20, maxPixels=1e9).get("NBR"),
        }).getInfo()
        self.assertLess(r["quemado"], r["sano"])

    def test_cp_06_la_mascara_de_agua_excluye_al_menos_95_por_ciento(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT resultado FROM validaciones_mascara WHERE resultado->>'corrida' = 'radar_completo' "
                        "ORDER BY id DESC LIMIT 1")
            fila = cur.fetchone()
        if not fila:
            self.skipTest("aun no se corrio scripts/validar_mascara_agua.py")
        self.assertGreaterEqual(fila[0]["resultado"]["TOTAL"]["excluidos_correctamente_pct"], 95)


class TestMotorDeRiesgo(unittest.TestCase):
    def test_cp_07_foco_en_anp_con_ndvi_de_estres_es_critico(self):
        e, r = evaluar_escenario("CP-07")
        self.assertEqual(r["nivel"], e["esperado"]["nivel"])
        self.assertTrue(set(e["esperado"]["reglas"]) <= set(r["reglas"]))

    def test_cp_08_foco_junto_a_un_aserradero_es_bajo_con_rn_04(self):
        e, r = evaluar_escenario("CP-08")
        self.assertEqual(r["nivel"], "BAJO")
        self.assertIn("RN-04", r["reglas"])
        self.assertEqual(evaluar_escenario("CP-08b")[1]["nivel"], "CRITICO")

    def test_cp_17_alerta_con_mas_de_6_h_pasa_a_revision_historica(self):
        e, r = evaluar_escenario("CP-17")
        self.assertEqual(r["estado"], "REVISION_HISTORICA")
        self.assertIn("RN-05", r["reglas"])

    def test_los_escenarios_del_archivo_se_cumplen_todos(self):
        for clave, e in ESCENARIOS.items():
            _, r = evaluar_escenario(clave)
            self.assertEqual(r["nivel"], e["esperado"]["nivel"], clave)
            if "estado" in e["esperado"]:
                self.assertEqual(r["estado"], e["esperado"]["estado"], clave)


class TestAlertasYCorreo(unittest.TestCase):
    def setUp(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO focos_calor (fuente, fecha_hora, frp, confianza, geom) VALUES ('TEST_CP', now(), 5, 'n', "
                        "ST_SetSRID(ST_MakePoint(-60.0, -3.0), 4326)) RETURNING id")
            self.foco = cur.fetchone()[0]

    def tearDown(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT lote_imagenes_id FROM alertas WHERE foco_id = %s", (self.foco,))
            lotes = [r[0] for r in cur.fetchall() if r[0]]
            cur.execute("DELETE FROM notificaciones WHERE alerta_id IN (SELECT id FROM alertas WHERE foco_id = %s)", (self.foco,))
            cur.execute("DELETE FROM alertas WHERE foco_id = %s", (self.foco,))
            cur.execute("DELETE FROM lotes_imagenes WHERE id = ANY(%s)", (lotes,))
            cur.execute("DELETE FROM focos_calor WHERE id = %s", (self.foco,))

    def _procesar(self, indices):
        def solo_este(cur, horas):
            cur.execute("SELECT f.id, ST_X(f.geom), ST_Y(f.geom), f.frp, 'n', 0.0 FROM focos_calor f WHERE f.id = %s AND NOT EXISTS "
                        "(SELECT 1 FROM alertas a WHERE a.foco_id = f.id)", (self.foco,))
            return cur.fetchall()
        meta = {"coleccion": "TEST", "desde": date(2026, 1, 1), "hasta": date(2026, 1, 31), "imagenes": ["x"]}
        with mock.patch.object(alertas.gi, "init"), \
                mock.patch.object(alertas.gi, "indices_para_puntos", return_value=({self.foco: indices}, meta)), \
                mock.patch.object(alertas, "_focos_pendientes", solo_este):
            return alertas.procesar(24)

    def _alerta(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, nivel, estado FROM alertas WHERE foco_id = %s", (self.foco,))
            return cur.fetchone()

    def test_cp_09_una_evaluacion_alta_crea_una_alerta_activa(self):
        self._procesar({"NDVI": 0.30, "NDWI": -0.5, "NBR": 0.2, "en_anp": False})
        _, nivel, estado = self._alerta()
        self.assertEqual((nivel, estado), ("ALTO", "ACTIVA"))

    def test_cp_10_una_alerta_critica_envia_el_correo_y_queda_registrada(self):
        self._procesar({"NDVI": 0.30, "NDWI": -0.5, "NBR": 0.2, "en_anp": True})  # ANP + NDVI = CRITICO
        aid, nivel, _ = self._alerta()
        self.assertEqual(nivel, "CRITICO")
        enviados = []

        class Smtp:
            def __init__(self, *a, **k):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def starttls(self):
                pass

            def login(self, *a):
                pass

            def send_message(self, m):
                enviados.append(m)

        original = correo.alertas_por_notificar
        entorno = {"SMTP_USER": "a@geofire.test", "SMTP_PASSWORD": "x", "ALERTA_DESTINATARIOS": "d@geofire.test"}
        with mock.patch.dict(os.environ, entorno), mock.patch.object(correo.smtplib, "SMTP", Smtp), \
                mock.patch.object(correo, "alertas_por_notificar", lambda cur, inc=False: [r for r in original(cur, inc) if r[0] == aid]), \
                mock.patch.object(correo.auditoria, "registrar"):
            self.assertEqual(correo.enviar_alertas(), 1)
        self.assertEqual(len(enviados), 1)
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT resultado FROM notificaciones WHERE alerta_id = %s", (aid,))
            self.assertEqual(cur.fetchone()[0], "ENVIADO")  # registrado en notificaciones

    def test_cp_19_el_ciclo_con_200_focos_tarda_menos_de_60_s(self):
        with get_connection() as conn, conn.cursor() as cur:
            for i in range(200):
                cur.execute("INSERT INTO focos_calor (fuente, fecha_hora, frp, confianza, geom) VALUES ('TEST_CP19', now(), 8, 'n', "
                            "ST_SetSRID(ST_MakePoint(%s, -3.0), 4326))", (-61 - i * 0.001,))
            cur.execute("SELECT id FROM focos_calor WHERE fuente = 'TEST_CP19'")
            ids = [r[0] for r in cur.fetchall()]
        try:
            indices = {i: {"NDVI": 0.7, "NDWI": -0.6, "NBR": 0.4, "en_anp": False} for i in ids}
            meta = {"coleccion": "TEST", "desde": date(2026, 1, 1), "hasta": date(2026, 1, 31), "imagenes": ["x"]}

            def solo_prueba(cur, horas):
                cur.execute("SELECT f.id, ST_X(f.geom), ST_Y(f.geom), f.frp, 'n', 0.0 FROM focos_calor f WHERE f.fuente = 'TEST_CP19'")
                return cur.fetchall()
            t0 = time.time()
            with mock.patch.object(alertas.gi, "init"), mock.patch.object(alertas.gi, "indices_para_puntos", return_value=(indices, meta)), \
                    mock.patch.object(alertas, "_focos_pendientes", solo_prueba):
                n, _ = alertas.procesar(24)
            segundos = time.time() - t0
            self.assertEqual(n, 200)
            anotar("cp19_segundos", round(segundos, 2))
            self.assertLess(segundos, 60)  # con Earth Engine real se midieron 17 s para 177 focos (ver docs/casos_de_prueba.md)
        finally:
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute("DELETE FROM alertas WHERE foco_id = ANY(%s)", (ids,))
                cur.execute("DELETE FROM lotes_imagenes WHERE coleccion = 'TEST'")
                cur.execute("DELETE FROM focos_calor WHERE fuente = 'TEST_CP19'")


class TestUsuarios(unittest.TestCase):
    def setUp(self):
        self.sufijo = secrets.token_hex(4)
        self.correo = f"cp-{self.sufijo}@geofire.test"
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO zonas (nombre, tipo, geom) VALUES ('ZZ CP Prov', 'provincia', "
                        "ST_Multi(ST_MakeEnvelope(-60.5, -3.5, -59.5, -2.5, 4326))) RETURNING id")
            self.prov = cur.fetchone()[0]
            cur.execute("INSERT INTO zonas (nombre, tipo, geom, padre_id) VALUES ('ZZ CP', 'distrito', "
                        "ST_Multi(ST_MakeEnvelope(-60.5, -3.5, -59.5, -2.5, 4326)), %s) RETURNING id", (self.prov,))
            self.zona = cur.fetchone()[0]
            cur.execute("INSERT INTO focos_calor (fuente, fecha_hora, frp, geom) VALUES ('TEST_CP', now(), 20, "
                        "ST_SetSRID(ST_MakePoint(-60.0, -3.0), 4326)) RETURNING id")
            self.foco = cur.fetchone()[0]
            cur.execute("INSERT INTO alertas (foco_id, nivel, ndvi, puntaje, estado) VALUES (%s, 'ALTO', 0.3, 30, 'ACTIVA') RETURNING id",
                        (self.foco,))
            self.alerta = cur.fetchone()[0]

    def tearDown(self):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM incidentes WHERE alerta_id = %s", (self.alerta,))
            cur.execute("DELETE FROM alertas WHERE id = %s", (self.alerta,))
            cur.execute("DELETE FROM focos_calor WHERE id = %s", (self.foco,))
            cur.execute("DELETE FROM usuarios WHERE email LIKE %s", ("cp-%@geofire.test",))
            cur.execute("DELETE FROM zonas WHERE id = %s", (self.zona,))
            cur.execute("DELETE FROM zonas WHERE id = %s", (self.prov,))
        borrar_auditoria_de_prueba()

    def test_cp_13_cinco_claves_erroneas_bloquean_la_cuenta_y_quedan_en_auditoria(self):
        seguridad.crear_usuario(self.correo, "CP", "guardaparque", "clave-larga-123")
        for _ in range(5):
            seguridad.autenticar(self.correo, "mala")
        usuario, msg = seguridad.autenticar(self.correo, "clave-larga-123")
        self.assertIsNone(usuario)
        self.assertEqual(msg, seguridad.MSG_BLOQUEADA)
        from geofire import auditoria
        eventos = auditoria.consultar(["CUENTA_BLOQUEADA"], 100)
        self.assertIn(self.correo, set(eventos["email"]))

    def test_cp_14_un_guardaparque_que_abre_administracion_por_url_recibe_acceso_denegado(self):
        from streamlit.testing.v1 import AppTest
        for pagina in ("usuarios", "auditoria", "geocercas"):
            at = AppTest.from_file(str(RAIZ / "app" / "views" / f"{pagina}.py"), default_timeout=60)
            at.session_state["usuario"] = {"id": 1, "rol": "guardaparque", "nombre": "x", "email": self.correo, "zona_id": None}
            at.run()
            self.assertTrue(any("Acceso denegado" in e.value for e in at.error), pagina)

    def test_cp_15_el_guardaparque_marca_una_alerta_como_confirmada(self):
        g = {"id": 1, "rol": "guardaparque", "email": self.correo, "zona_id": self.zona}
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO usuarios (email, rol, password_hash, nombre) VALUES (%s, 'guardaparque', 'x', 'CP') RETURNING id",
                        (self.correo,))
            g["id"] = cur.fetchone()[0]
        val.validar(self.alerta, g, "CONFIRMADA", JUSTIF, foto=imagen_bytes())
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT a.estado, i.estado, i.usuario_id FROM alertas a JOIN incidentes i ON i.alerta_id = a.id WHERE a.id = %s",
                        (self.alerta,))
            self.assertEqual(cur.fetchone(), ("CONFIRMADA", "CONFIRMADA", g["id"]))

    def test_cp_16_el_reporte_pdf_y_csv_traen_los_mismos_totales(self):
        rep = reportes.construir(date.today(), date.today(), distrito="ZZ CP")
        self.assertEqual(rep.total, 1)
        filas = [ln for ln in rep_csv_lineas(rep) if not ln.startswith("#")]
        self.assertEqual(len(list(csv.DictReader(io.StringIO("\n".join(filas))))), rep.total)
        self.assertIn(f"Total de incidentes: {rep.total}".encode(), reportes.a_pdf(rep))


def rep_csv_lineas(rep):
    return reportes.a_csv(rep).decode("utf-8-sig").splitlines()


@unittest.skipUnless(REGION, "requiere el limite regional cargado (scripts/load_limite.py)")
class TestVisor(unittest.TestCase):
    def _mapa(self, ajustar=None):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(RAIZ / "app" / "views" / "mapa.py"), default_timeout=120)
        at.session_state["usuario"] = {"id": 1, "rol": "administrador", "nombre": "x", "email": "x@geofire.test"}
        at.run()
        if ajustar:
            ajustar(at)
            at.run()
        return at

    def test_cp_11_el_visor_abre_centrado_en_ucayali_con_capas_para_superponer(self):
        at = self._mapa()
        self.assertEqual(len(at.exception), 0)
        capas = " | ".join(c.label for c in at.checkbox)
        for esperado in ("Zonas evaluadas", "NDVI", "Estrés", "NBR", "Humo", "VIIRS"):
            self.assertIn(esperado, capas)

    def test_cp_12_cambiar_la_ventana_a_48_h_actualiza_el_mapa_y_los_focos_traen_sus_atributos(self):
        at = self._mapa(lambda a: a.select_slider[0].set_value(48))
        self.assertEqual(len(at.exception), 0)
        self.assertTrue(any("48 h" in c.value for c in at.caption))
        df = repo.alertas(48)
        for columna in ("lat", "lon", "frp", "fecha_hora", "nivel"):  # lo que muestra la tarjeta al hacer clic en un foco
            self.assertIn(columna, df.columns)

    def test_cp_18_cargar_el_mapa_regional_20_veces_tarda_menos_de_5_s_en_promedio(self):
        from streamlit.testing.v1 import AppTest
        tiempos = []
        for _ in range(20):
            at = AppTest.from_file(str(RAIZ / "app" / "views" / "mapa.py"), default_timeout=120)
            at.session_state["usuario"] = {"id": 1, "rol": "administrador", "nombre": "x", "email": "x@geofire.test"}
            t0 = time.time()
            at.run()
            tiempos.append(time.time() - t0)
        anotar("cp18_promedio_s", round(sum(tiempos) / len(tiempos), 2))
        anotar("cp18_maximo_s", round(max(tiempos), 2))
        self.assertLess(sum(tiempos) / len(tiempos), 5)


if __name__ == "__main__":
    unittest.main()
