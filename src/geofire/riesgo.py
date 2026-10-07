"""Motor de riesgo (HU-06): aplica RN-02, RN-04 y RN-05 a un foco ya filtrado por RN-01."""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

CONFIG = json.loads(
    (Path(__file__).resolve().parents[2] / "config" / "riesgo.json").read_text(encoding="utf-8")
)


@dataclass
class Foco:
    frp: float
    confianza: str = ""
    antiguedad_h: float = 0.0


@dataclass
class Contexto:
    ndvi: Optional[float] = None
    dist_comunidad_km: Optional[float] = None
    en_anp: bool = False
    cerca_fuente_conocida: bool = False


def evaluar(foco: Foco, ctx: Contexto, cfg: dict = CONFIG) -> dict:
    reglas = ["RN-01"]

    # RN-04: fuente de calor conocida (industrial) salvo intensidad extrema
    if ctx.cerca_fuente_conocida and foco.frp < cfg["frp_p90"]:
        return {"nivel": "BAJO", "puntaje": 0, "reglas": reglas + ["RN-04"], "estado": "FUENTE_CONOCIDA"}

    condiciones = {
        "RN-02.1": ctx.dist_comunidad_km is not None and ctx.dist_comunidad_km < cfg["distancia_comunidad_km"],
        "RN-02.2": ctx.en_anp,
        "RN-02.3": ctx.ndvi is not None and ctx.ndvi < cfg["umbral_ndvi_estres"],
    }
    cumplidas = [k for k, v in condiciones.items() if v]
    puntos = 30 * len(cumplidas) + (10 if foco.confianza.lower() in ("high", "h") else 0)

    if len(cumplidas) >= 2:
        nivel = "CRITICO"
    elif len(cumplidas) == 1:
        nivel = "ALTO"
    elif foco.frp >= cfg["frp_p50"]:
        nivel = "MEDIO"
    else:
        nivel = "BAJO"

    # RN-05: vigencia del dato satelital
    estado = "ACTIVA"
    if foco.antiguedad_h > cfg["vigencia_horas"]:
        reglas.append("RN-05")
        estado = "REVISION_HISTORICA"

    return {"nivel": nivel, "puntaje": min(puntos, 100), "reglas": reglas + cumplidas, "estado": estado}
