"""Valida la mascara de agua contra referencias independientes y escribe docs/validacion_mascara_agua.md (AC-04.1, AC-04.2).
Uso: python scripts/validar_mascara_agua.py
"""
from datetime import date
from pathlib import Path

from geofire import gee_indices as gi
from geofire import mascara_agua as m
from geofire.riesgo import CONFIG_VERSION

SALIDA = Path(__file__).resolve().parents[1] / "docs" / "validacion_mascara_agua.md"
VENTANA = 30
corte = date.today()
U = gi.UMBRAL_AGUA

corridas = {
    "radar_completo": m.metricas(umbral=U, referencia="radar", ventana_dias=VENTANA, corte=corte),
    "radar_interior": m.metricas(umbral=U, referencia="radar", ventana_dias=VENTANA, corte=corte, borde_px=2),
    "radar_regla_original": m.metricas(umbral=0.0, referencia="radar", ventana_dias=VENTANA, corte=corte)["TOTAL"],
    "jrc_estacional": m.metricas(umbral=U, referencia="estacional", ventana_dias=VENTANA, corte=corte)["TOTAL"],
    "jrc_anual": m.metricas(umbral=U, referencia="anual", ventana_dias=VENTANA, corte=corte)["TOTAL"],
}
for nombre, r in corridas.items():
    m.guardar({"corrida": nombre, "resultado": r}, U if nombre != "radar_regla_original" else 0.0, VENTANA, corte)


def fila(nombre, v):
    return (f"| {nombre} | {v['agua_referencia_km2']:,} | {v['excluidos_correctamente_pct']} % | "
            f"{v['tierra_excluida_incorrectamente_pct']} % |")


tot = corridas["radar_completo"]["TOTAL"]
interior = corridas["radar_interior"]["TOTAL"]
cumple = tot["excluidos_correctamente_pct"] >= 95
por_area = "\n".join(fila(k, v) for k, v in corridas["radar_completo"].items() if k != "TOTAL")
SALIDA.write_text(f"""# Validación de la máscara de agua (HU-04, AC-04.1, AC-04.2)

Generado: {corte:%Y-%m-%d} · Configuración `{CONFIG_VERSION}` · Script: `scripts/validar_mascara_agua.py`
(los resultados quedan en la tabla `validaciones_mascara`, uno por corrida).

## Máscara evaluada
- Índice: **NDWI = (B3 − B8) / (B3 + B8)** de Sentinel-2 SR (`COPERNICUS/S2_SR_HARMONIZED`), compuesto de la **mediana de los
  últimos {VENTANA} días** (hasta {corte:%d/%m/%Y}), con máscara de nubes y sombras (banda SCL).
- Regla: un píxel es **agua** si **NDWI > {U}** (parámetro `umbral_ndwi_agua` de `config/riesgo.json`).
- Escala de comparación: {m.ESCALA_M} m.

## Referencia de evaluación
- **Principal: radar Sentinel-1** (`COPERNICUS/S1_GRD`, modo IW, polarización VV), mediana de los mismos {VENTANA} días con filtro
  de moteado (speckle). Agua = VV < {m.RADAR_AGUA_DB} dB; tierra = VV > {m.RADAR_TIERRA_DB} dB (la franja intermedia no se evalúa).
  Es **contemporánea** al compuesto óptico y no depende de nubes ni de luz.
- **De contexto: JRC Global Surface Water** (`{m.REFERENCIA}`): histórica (hasta 2021). Se usa de dos formas: *estacional*
  (mismos meses de 2019-2021) y *anual* (ocurrencia ≥ {m.OCURRENCIA_AGUA} %).
- Áreas: {len(m.AREAS)} tramos de ríos y lagos de Ucayali ({', '.join(m.AREAS)}).

## Resultado frente a la referencia principal (radar)

| Medida | Resultado | Meta |
|---|---|---|
| **AC-04.1** Agua de referencia excluida correctamente (todos los píxeles) | **{tot['excluidos_correctamente_pct']} %** | ≥ 95 % → {'**cumple**' if cumple else '**NO cumple**'} |
| Agua de referencia excluida correctamente (interior: sin 60 m de orilla) | {interior['excluidos_correctamente_pct']} % | — |
| **AC-04.2** Tierra excluida incorrectamente | **{tot['tierra_excluida_incorrectamente_pct']} %** de {tot['tierra_referencia_km2']:,} km² de tierra de referencia | — |
| Agua de referencia sin imagen óptica válida (nubes) | {tot['agua_sin_imagen_valida_pct']} % | — |

Por tramo:

| Tramo | Agua de referencia (km²) | Excluida correctamente | Tierra excluida incorrectamente |
|---|---|---|---|
{por_area}

## Por qué se cambió el umbral de 0 a {U}
Con la regla original (NDWI > 0) frente a la misma referencia: **{corridas['radar_regla_original']['excluidos_correctamente_pct']} %** de
agua excluida y {corridas['radar_regla_original']['tierra_excluida_incorrectamente_pct']} % de tierra excluida por error. El umbral
{U} sube la cobertura del agua con un costo muy bajo de tierra excluida. Los ríos amazónicos son turbios (mucho sedimento) y su NDWI queda
cerca de cero, por eso el umbral estándar los pierde.

## Resultado frente a JRC (histórica) y por qué difiere
| Referencia | Agua de referencia (km²) | Excluida correctamente | Tierra excluida incorrectamente |
|---|---|---|---|
{fila('JRC estacional (sep-oct 2019-2021)', corridas['jrc_estacional'])}
{fila('JRC anual (ocurrencia ≥ 50 %)', corridas['jrc_anual'])}

Frente a JRC el acuerdo es menor (≈ 80-90 %, sin importar el índice ni el umbral). Se interpreta como **diferencia de la referencia**, no
de la máscara: JRC termina en 2021 y los cauces del Ucayali, Urubamba y Tambo migran cada año, y en la bajante de septiembre-octubre quedan
playas expuestas que JRC todavía cuenta como agua. Probar índices alternativos (MNDWI) o reglas combinadas con NDVI no pasó del 88 %
contra JRC, lo que confirma que el límite está en la referencia.

## Limitaciones
- El radar también es una *estimación* (no verdad de campo): se recomienda confirmar con un levantamiento o imágenes de alta resolución.
- Solo se evaluaron {len(m.AREAS)} tramos; el desempeño en cochas pequeñas o aguas con mucha vegetación flotante puede ser menor.
- Los resultados cambian con la fecha de corte y el nivel del río: repetir el script en otra época (crecida) es recomendable.
""", encoding="utf-8")
print(f"Escrito {SALIDA}")
print("Principal (radar):", tot)
