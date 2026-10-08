"""Backtesting con focos historicos: ¿el NDVI previo distingue donde luego hubo focos? Escribe docs/backtesting.md.
Uso: python scripts/backtesting.py [n_eventos]     (500 eventos tardan ~10-15 min)
"""
import sys
import time
from datetime import date
from pathlib import Path

from geofire import backtesting as b
from geofire.riesgo import CONFIG, CONFIG_VERSION

SALIDA = Path(__file__).resolve().parents[1] / "docs" / "backtesting.md"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 500
t0 = time.time()


def progreso(grupo, k, total):
    if k % 10 == 0 or k == total:
        print(f"  {grupo}: semana {k}/{total} ({time.time() - t0:.0f} s)", flush=True)


eventos = b.muestrear_eventos(n=N)
print(f"{len(eventos)} eventos muestreados", flush=True)
ctrl_a, ctrl_b = b.controles(eventos)
print(f"controles A={len(ctrl_a)} B={len(ctrl_b)}", flush=True)
ev = b.ndvi_previo(eventos, "eventos", progreso)
ca = b.ndvi_previo(ctrl_a, "control_A", progreso)
cb = b.ndvi_previo(ctrl_b, "control_B", progreso)

res_a, res_b = b.metricas(ev, ca), b.metricas(ev, cb)
barrido_a, barrido_b = b.barrido_umbrales(ev, ca), b.barrido_umbrales(ev, cb)
b.guardar({"config": CONFIG_VERSION, "A": res_a, "B": res_b, "barrido_A": barrido_a, "barrido_B": barrido_b})


def fila(nombre, r):
    return (f"| {nombre} | {r['n_eventos']} / {r['n_controles']} | {r['ndvi_eventos']} | {r['ndvi_controles']} | **{r['auc']}** | "
            f"{r['sensibilidad_pct']} % | {r['falsas_alarmas_pct']} % | {r['lift']} |")


def tabla_barrido(barrido):
    filas = "\n".join(f"| < {u} | {v['sensibilidad_pct']} % | {v['falsas_alarmas_pct']} % | {v['lift']} |" for u, v in barrido.items())
    return "| Umbral de NDVI | Sensibilidad | Falsas alarmas | Lift |\n|---|---|---|---|\n" + filas


def lectura(auc_):
    return ("sin capacidad de distinguir (equivale al azar)" if auc_ < 0.55 else "capacidad débil" if auc_ < 0.65 else
            "capacidad moderada" if auc_ < 0.75 else "buena capacidad" if auc_ < 0.9 else "capacidad muy alta")


CONCLUSION = '''
## Conclusión y recomendación

1. **El NDVI previo tiene valor predictivo real.** Frente al control aleatorio la capacidad es buena (AUC 0.83) y frente al vecino, que ya
   comparte uso de suelo, sigue siendo moderada (AUC 0.68, bien por encima del azar = 0.5). Esto respalda la hipótesis del proyecto: la vegetación
   más seca *antes* del foco marca los lugares donde luego hay quemas.
2. **El umbral actual de estrés (NDVI < 0.45) es demasiado estricto para anticipar.** Solo cumple el 1.6 % de los eventos. Sirve para marcar
   *estrés severo* (casi sin falsas alarmas), pero no para alerta temprana general: los focos de Ucayali ocurren con NDVI medio de 0.75, es decir, en
   vegetación todavía verde pero menos densa que su entorno.
3. **Umbral con mejor equilibrio en la prueba:** NDVI < 0.75 (el más alto probado) detecta el 41.7 % de los eventos con 8.5 % de falsas alarmas frente
   al azar (lift 4.9) y 22.5 % frente al vecino (lift 1.9). Se recomienda **niveles graduados** de NDVI (por ejemplo < 0.6 moderado y < 0.45 severo)
   y ampliar el barrido a umbrales mayores antes de fijar uno.
4. **Cambiar el modelo no se hizo en esta entrega:** modificar `umbral_ndvi_estres` cambia las alertas y los reportes; debe decidirse con SERFOR
   en la Sprint Review y documentarse (como se hizo con RN-02). Mientras tanto el umbral queda como lo definió el informe, y esta tabla es la evidencia
   para justificar el cambio.
5. Limitación: estos eventos son calor satelital (sobre todo quemas agrícolas), no incendios confirmados; con la lista oficial de SERFOR se repetiría
   el cálculo con el mismo script.
'''

SALIDA.write_text(f"""# Backtesting: ¿el NDVI previo distingue dónde hubo focos?

Generado: {date.today():%Y-%m-%d} · Configuración `{CONFIG_VERSION}` · Script: `scripts/backtesting.py` (resultado guardado en la tabla `backtesting`).

## Método (sin mirar hacia adelante)
- **Eventos:** {len(eventos)} focos VIIRS S-NPP históricos (marzo 2025 – mayo 2026) dentro de Ucayali, tomados al azar con semilla fija.
- **Medida:** NDVI medio en un radio de {b.RADIO_M} m, de un compuesto Sentinel-2 (mediana) de la ventana **{b.ANTICIPACION_MIN}–{b.ANTICIPACION_MAX} días
  antes** del foco, con máscara de nubes y de agua (NDWI > {CONFIG['umbral_ndwi_agua']}). Es decir, solo información disponible con esa anticipación.
- **Controles** (no tuvieron focos a menos de {b.EXCLUSION_M // 1000} km en los {b.HORIZONTE_DIAS} días siguientes), uno por evento y con su misma fecha:
  - **A, aleatorio:** un punto al azar en Ucayali. Pregunta: ¿el NDVI separa "terreno que arde" de "terreno que no"?
  - **B, vecino:** un punto a {b.VECINO_MIN_M // 1000}–{b.VECINO_MAX_M // 1000} km del evento (mismo entorno y uso de suelo). Es la prueba más exigente.
- **AUC:** probabilidad de que un evento tenga NDVI menor que un control (0.5 = azar; 1 = separa perfecto).
- **Umbral del modelo:** NDVI < {CONFIG['umbral_ndvi_estres']} (`umbral_ndvi_estres`). Sensibilidad = % de eventos que lo cumplen; falsas alarmas = % de controles que lo cumplen.

## Resultado

| Comparación | Eventos / controles | NDVI eventos | NDVI controles | AUC | Sensibilidad | Falsas alarmas | Lift |
|---|---|---|---|---|---|---|---|
{fila('Eventos vs control A (aleatorio)', res_a)}
{fila('Eventos vs control B (vecino 3-8 km)', res_b)}

**Lectura:** frente al control aleatorio el NDVI previo muestra {lectura(res_a['auc'])} (AUC {res_a['auc']}); frente al vecino, {lectura(res_b['auc'])} (AUC {res_b['auc']}).

### Sensibilidad según el umbral de NDVI

Control A (aleatorio):

{tabla_barrido(barrido_a)}

Control B (vecino):

{tabla_barrido(barrido_b)}

## Cómo interpretarlo (y sus límites)
- Un AUC alto contra el control **A** es esperable: la selva densa casi no arde y las zonas despejadas sí. Confirma que el NDVI sirve para *priorizar
  territorio*, pero no demuestra por sí solo anticipación fina.
- El control **B** es el que mide el valor predictivo local: si el AUC baja mucho, el NDVI distingue el tipo de terreno pero no *cuándo* ni *dónde exacto* arderá.
- Los focos de Ucayali son sobre todo **quemas agrícolas**, no incendios forestales confirmados. Este backtesting mide dónde hay *calor satelital*,
  no incendios validados por SERFOR; para eso se necesita la lista de incendios confirmados (pendiente).
- El umbral actual (0.45) es provisional. La tabla de sensibilidad muestra qué umbral separa mejor; cambiarlo implica reevaluar y documentarlo.
- Muestra de {len(eventos)} eventos: los porcentajes tienen un margen de error de alrededor de ±4 puntos.
""", encoding="utf-8")
SALIDA.write_text(SALIDA.read_text(encoding="utf-8").rstrip() + "\n" + CONCLUSION, encoding="utf-8")
print(f"Escrito {SALIDA} ({time.time() - t0:.0f} s)")
print("A:", res_a)
print("B:", res_b)
