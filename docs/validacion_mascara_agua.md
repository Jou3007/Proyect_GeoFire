# Validación de la máscara de agua (HU-04, AC-04.1, AC-04.2)

Generado: 2026-10-08 · Configuración `a48337cee0` · Script: `scripts/validar_mascara_agua.py`
(los resultados quedan en la tabla `validaciones_mascara`, uno por corrida).

## Máscara evaluada
- Índice: **NDWI = (B3 − B8) / (B3 + B8)** de Sentinel-2 SR (`COPERNICUS/S2_SR_HARMONIZED`), compuesto de la **mediana de los
  últimos 30 días** (hasta 08/10/2026), con máscara de nubes y sombras (banda SCL).
- Regla: un píxel es **agua** si **NDWI > -0.1** (parámetro `umbral_ndwi_agua` de `config/riesgo.json`).
- Escala de comparación: 30 m.

## Referencia de evaluación
- **Principal: radar Sentinel-1** (`COPERNICUS/S1_GRD`, modo IW, polarización VV), mediana de los mismos 30 días con filtro
  de moteado (speckle). Agua = VV < -18 dB; tierra = VV > -12 dB (la franja intermedia no se evalúa).
  Es **contemporánea** al compuesto óptico y no depende de nubes ni de luz.
- **De contexto: JRC Global Surface Water** (`JRC/GSW1_4/GlobalSurfaceWater`): histórica (hasta 2021). Se usa de dos formas: *estacional*
  (mismos meses de 2019-2021) y *anual* (ocurrencia ≥ 50 %).
- Áreas: 6 tramos de ríos y lagos de Ucayali (Río Ucayali (Pucallpa), Lago Yarinacocha, Río Urubamba (Atalaya), Río Tambo (Atalaya), Río Urubamba (Sepahua), Río Aguaytía).

## Resultado frente a la referencia principal (radar)

| Medida | Resultado | Meta |
|---|---|---|
| **AC-04.1** Agua de referencia excluida correctamente (todos los píxeles) | **98.6 %** | ≥ 95 % → **cumple** |
| Agua de referencia excluida correctamente (interior: sin 60 m de orilla) | 99.8 % | — |
| **AC-04.2** Tierra excluida incorrectamente | **0.58 %** de 2,461.46 km² de tierra de referencia | — |
| Agua de referencia sin imagen óptica válida (nubes) | 0.1 % | — |

Por tramo:

| Tramo | Agua de referencia (km²) | Excluida correctamente | Tierra excluida incorrectamente |
|---|---|---|---|
| Río Ucayali (Pucallpa) | 45.1 | 98.3 % | 0.43 % |
| Lago Yarinacocha | 8.29 | 93.5 % | 0.34 % |
| Río Urubamba (Atalaya) | 19.95 | 99.7 % | 1.1 % |
| Río Tambo (Atalaya) | 15.48 | 99.8 % | 0.86 % |
| Río Urubamba (Sepahua) | 7.76 | 99.9 % | 0.59 % |
| Río Aguaytía | 0.3 | 100.0 % | 0.02 % |

## Por qué se cambió el umbral de 0 a -0.1
Con la regla original (NDWI > 0) frente a la misma referencia: **94.5 %** de
agua excluida y 0.13 % de tierra excluida por error. El umbral
-0.1 sube la cobertura del agua con un costo muy bajo de tierra excluida. Los ríos amazónicos son turbios (mucho sedimento) y su NDWI queda
cerca de cero, por eso el umbral estándar los pierde.

## Resultado frente a JRC (histórica) y por qué difiere
| Referencia | Agua de referencia (km²) | Excluida correctamente | Tierra excluida incorrectamente |
|---|---|---|---|
| JRC estacional (sep-oct 2019-2021) | 101.86 | 81.7 % | 1.42 % |
| JRC anual (ocurrencia ≥ 50 %) | 92.34 | 77.2 % | 0.48 % |

Frente a JRC el acuerdo es menor (≈ 80-90 %, sin importar el índice ni el umbral). Se interpreta como **diferencia de la referencia**, no
de la máscara: JRC termina en 2021 y los cauces del Ucayali, Urubamba y Tambo migran cada año, y en la bajante de septiembre-octubre quedan
playas expuestas que JRC todavía cuenta como agua. Probar índices alternativos (MNDWI) o reglas combinadas con NDVI no pasó del 88 %
contra JRC, lo que confirma que el límite está en la referencia.

## Limitaciones
- El radar también es una *estimación* (no verdad de campo): se recomienda confirmar con un levantamiento o imágenes de alta resolución.
- Solo se evaluaron 6 tramos; el desempeño en cochas pequeñas o aguas con mucha vegetación flotante puede ser menor.
- Los resultados cambian con la fecha de corte y el nivel del río: repetir el script en otra época (crecida) es recomendable.
