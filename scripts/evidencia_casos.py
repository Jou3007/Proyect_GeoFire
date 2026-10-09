"""Ejecuta los casos CP-01..CP-19 (tests/test_casos_cp.py) y escribe docs/casos_de_prueba.md con el resultado y la fecha.
Uso (dentro del contenedor): pip install -r requirements-dev.txt && python scripts/evidencia_casos.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "docs" / "casos_de_prueba.md"
XML = Path(tempfile.gettempdir()) / "geofire_cp.xml"
MEDICIONES = Path(tempfile.gettempdir()) / "geofire_mediciones.json"

CASOS = [  # (id, requisito, caso, resultado esperado, sprint) - tabla 12.5 del informe
    ("CP-01", "RF-01", "Descargar focos de FIRMS de 1 día", "Se obtiene un CSV con columnas latitude, longitude, acq_date, frp", "S2"),
    ("CP-02", "RF-02", "Foco en Pucallpa y foco en Huánuco", "Se guarda el de Pucallpa; el de Huánuco se descarta", "S2"),
    ("CP-03", "RF-01", "Repetir la descarga del mismo día", "No se duplican registros (ON CONFLICT)", "S2"),
    ("CP-04", "RF-04/05", "NDVI de una zona con nubosidad < 30 %", "Valor entre -1 y 1", "S3"),
    ("CP-05", "RF-06", "NBR de un área quemada conocida", "NBR menor que el de la vegetación sana vecina", "S3"),
    ("CP-06", "HU-04", "Píxeles del río Ucayali", "Al menos 95 % de píxeles de agua excluidos", "S4"),
    ("CP-07", "RF-07", "Foco en ANP y con NDVI de estrés", "Nivel CRÍTICO (dos condiciones de RN-02)", "S4"),
    ("CP-08", "RF-07", "Foco junto a un aserradero registrado", "Nivel BAJO con regla RN-04", "S4"),
    ("CP-09", "RF-12", "Evaluación ALTA", "Se crea una alerta en estado ACTIVA", "S4"),
    ("CP-10", "RF-13", "Alerta crítica en zona con guardaparque", "Correo enviado y registrado en notificaciones", "S4"),
    ("CP-11", "RF-08/09", "Abrir el visor y activar capas", "Mapa centrado en Ucayali con capas superpuestas", "S5"),
    ("CP-12", "RF-10/11", "Clic en un foco y cambio de ventana a 48 h", "Se ven sus atributos; el mapa se actualiza", "S5"),
    ("CP-13", "RF-16", "Login con clave errónea 5 veces", "Cuenta bloqueada y evento en auditoría", "S5"),
    ("CP-14", "RF-17", "Guardaparque entra a Administración por URL", "Mensaje de acceso denegado", "S5"),
    ("CP-15", "RF-14", "Guardaparque marca una alerta como confirmada", "Estado CONFIRMADA y validación guardada", "S6"),
    ("CP-16", "RF-15", "Exportar reporte", "PDF y CSV con los mismos totales", "S6"),
    ("CP-17", "RN-05", "Alerta sin validar por más de 6 h", "Pasa a REVISION_HISTORICA", "S6"),
    ("CP-18", "RNF-09", "Cargar el mapa regional 20 veces", "Promedio menor a 5 s", "S5/S6"),
    ("CP-19", "RNF-01", "Ciclo completo del job con 200 focos", "De la descarga a la alerta en menos de 60 s", "S6"),
]

MEDICIONES.unlink(missing_ok=True)
sub = subprocess.run(
    [sys.executable, "-m", "pytest", str(RAIZ / "tests" / "test_casos_cp.py"), "-q", f"--junitxml={XML}", "-p", "no:cacheprovider"],
    cwd=RAIZ, env={**os.environ, "PYTHONPATH": "src"}, capture_output=True, text=True,
)
resultados = {}
for caso in ET.parse(XML).getroot().iter("testcase"):
    m = re.match(r"test_cp_(\d+)", caso.get("name"))
    if not m:
        continue
    cp = f"CP-{int(m.group(1)):02d}"
    if caso.find("failure") is not None or caso.find("error") is not None:
        resultados[cp] = ("FALLÓ", caso.get("name"))
    elif caso.find("skipped") is not None:
        resultados[cp] = ("OMITIDO", (caso.find("skipped").get("message") or "")[:60])
    else:
        resultados.setdefault(cp, ("PASÓ", caso.get("name")))

med = json.loads(MEDICIONES.read_text()) if MEDICIONES.exists() else {}
notas = {
    "CP-18": (f"promedio {med['cp18_promedio_s']} s, máximo {med['cp18_maximo_s']} s en 20 cargas (solo servidor)"
              if "cp18_promedio_s" in med else ""),
    "CP-19": (f"{med['cp19_segundos']} s con 200 focos (Earth Engine simulado); con Earth Engine real: 17 s para 177 focos"
              if "cp19_segundos" in med else ""),
}
hoy = datetime.now().strftime("%Y-%m-%d")
filas = []
for cp, req, caso, esperado, sprint in CASOS:
    estado, detalle = resultados.get(cp, ("SIN PRUEBA", ""))
    ev = f"`{detalle}`" if estado in ("PASÓ", "FALLÓ") else detalle
    if notas.get(cp):
        ev += f" · {notas[cp]}"
    filas.append(f"| {cp} | {req} | {caso} | {esperado} | {sprint} | **{estado}** ({hoy}) | {ev} |")
paso = sum(1 for r in resultados.values() if r[0] == "PASÓ")
omitidos = sum(1 for r in resultados.values() if r[0] == "OMITIDO")
fallan = sum(1 for r in resultados.values() if r[0] == "FALLÓ")

SALIDA.write_text(
    f"""# Casos de prueba CP-01 a CP-19 (tabla 12.5 del informe)

Ejecutado el {hoy} con `python scripts/evidencia_casos.py` sobre `tests/test_casos_cp.py` y los datos de `tests/datos/`
(focos de ejemplo en Pucallpa, Atalaya, Huánuco, Brasil y Loreto, y escenarios ficticios de riesgo).

Resumen: **{paso} de {len(CASOS)}** casos pasan; {omitidos} omitidos; {fallan} fallan.
Los casos CP-04, CP-05 y CP-06 usan Earth Engine real y se omiten donde no hay credenciales (p. ej. en el CI de GitHub); CP-11, CP-12 y CP-18
requieren el límite regional cargado.

| ID | Req. | Caso | Resultado esperado | Sprint | Resultado obtenido | Evidencia |
|---|---|---|---|---|---|---|
"""
    + "\n".join(filas)
    + """

## Observaciones
- Los casos CP-09, CP-10 y CP-19 simulan la respuesta de Earth Engine (y el servidor de correo) para no tocar datos reales ni enviar correos; el resto
  de la cadena (base de datos, motor de riesgo, auditoría, notificaciones) es real. La medición con Earth Engine real quedó en la corrida del ciclo
  automático: 177 focos en 17 s.
- **CP-18 mide solo el servidor.** Con un navegador real el mapa tarda 6.5 s con 1 usuario y 37 s con 10 usuarios simultáneos (con caché):
  la meta de 5 s de RNF-09 se cumple en el servidor pero **no** de extremo a extremo. Detalle y causas en `docs/pruebas_rendimiento.md`.
- Los focos de prueba se crean con una fuente `TEST_*` y se borran al terminar cada caso; la auditoría de prueba se limpia con un permiso especial
  que solo conceden las pruebas.
""",
    encoding="utf-8",
)
print(sub.stdout[-500:])
print(f"Escrito {SALIDA}: {paso}/{len(CASOS)} pasan, {omitidos} omitidos, {fallan} fallan")
sys.exit(1 if fallan else 0)
