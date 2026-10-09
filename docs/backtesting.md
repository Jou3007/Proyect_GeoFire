# Backtesting: ¿el NDVI previo distingue dónde hubo focos?

Generado: 2026-10-08 · Configuración `a48337cee0` · Script: `scripts/backtesting.py` (resultado guardado en la tabla `backtesting`).

## Método (sin mirar hacia adelante)
- **Eventos:** 500 focos VIIRS S-NPP históricos (marzo 2025 – mayo 2026) dentro de Ucayali, tomados al azar con semilla fija.
- **Medida:** NDVI medio en un radio de 500 m, de un compuesto Sentinel-2 (mediana) de la ventana **15–45 días
  antes** del foco, con máscara de nubes y de agua (NDWI > -0.1). Es decir, solo información disponible con esa anticipación.
- **Controles** (no tuvieron focos a menos de 2 km en los 30 días siguientes), uno por evento y con su misma fecha:
  - **A, aleatorio:** un punto al azar en Ucayali. Pregunta: ¿el NDVI separa "terreno que arde" de "terreno que no"?
  - **B, vecino:** un punto a 3–8 km del evento (mismo entorno y uso de suelo). Es la prueba más exigente.
- **AUC:** probabilidad de que un evento tenga NDVI menor que un control (0.5 = azar; 1 = separa perfecto).
- **Umbral del modelo:** NDVI < 0.45 (`umbral_ndvi_estres`). Sensibilidad = % de eventos que lo cumplen; falsas alarmas = % de controles que lo cumplen.

## Resultado

| Comparación | Eventos / controles | NDVI eventos | NDVI controles | AUC | Sensibilidad | Falsas alarmas | Lift |
|---|---|---|---|---|---|---|---|
| Eventos vs control A (aleatorio) | 499 / 495 | 0.746 | 0.817 | **0.829** | 1.6 % | 0.8 % | 1.98 |
| Eventos vs control B (vecino 3-8 km) | 499 / 485 | 0.746 | 0.785 | **0.681** | 1.6 % | 0.8 % | 1.94 |

**Lectura:** frente al control aleatorio el NDVI previo muestra buena capacidad (AUC 0.829); frente al vecino, capacidad moderada (AUC 0.681).

### Sensibilidad según el umbral de NDVI

Control A (aleatorio):

| Umbral de NDVI | Sensibilidad | Falsas alarmas | Lift |
|---|---|---|---|
| < 0.5 | 1.8 % | 0.8 % | 2.23 |
| < 0.55 | 2.6 % | 1.4 % | 1.84 |
| < 0.6 | 5.2 % | 1.8 % | 2.87 |
| < 0.65 | 9.4 % | 2.4 % | 3.89 |
| < 0.7 | 19.0 % | 4.2 % | 4.49 |
| < 0.75 | 41.7 % | 8.5 % | 4.91 |

Control B (vecino):

| Umbral de NDVI | Sensibilidad | Falsas alarmas | Lift |
|---|---|---|---|
| < 0.5 | 1.8 % | 1.4 % | 1.25 |
| < 0.55 | 2.6 % | 2.5 % | 1.05 |
| < 0.6 | 5.2 % | 3.9 % | 1.33 |
| < 0.65 | 9.4 % | 7.6 % | 1.23 |
| < 0.7 | 19.0 % | 11.8 % | 1.62 |
| < 0.75 | 41.7 % | 22.5 % | 1.85 |

## Cómo interpretarlo (y sus límites)
- Un AUC alto contra el control **A** es esperable: la selva densa casi no arde y las zonas despejadas sí. Confirma que el NDVI sirve para *priorizar
  territorio*, pero no demuestra por sí solo anticipación fina.
- El control **B** es el que mide el valor predictivo local: si el AUC baja mucho, el NDVI distingue el tipo de terreno pero no *cuándo* ni *dónde exacto* arderá.
- Los focos de Ucayali son sobre todo **quemas agrícolas**, no incendios forestales confirmados. Este backtesting mide dónde hay *calor satelital*,
  no incendios validados por SERFOR; para eso se necesita la lista de incendios confirmados (pendiente).
- El umbral actual (0.45) es provisional. La tabla de sensibilidad muestra qué umbral separa mejor; cambiarlo implica reevaluar y documentarlo.
- Muestra de 500 eventos: los porcentajes tienen un margen de error de alrededor de ±4 puntos.

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
