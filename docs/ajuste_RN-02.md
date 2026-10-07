# Ajuste a la regla de negocio RN-02 (cercania a asentamientos)

## Regla original (informe, cap. VIII, tabla de reglas)
Una anomalia termica es **Critica** si cumple al menos dos de tres condiciones:
1. a menos de 10 km de un asentamiento humano o comunidad nativa (RN-02.1);
2. dentro de un Area Natural Protegida (RN-02.2);
3. NDVI con estres hidrico severo (RN-02.3).

Con **una** condicion el foco es **Alto**.

## Problema observado en los datos
Con 901 asentamientos de OpenStreetMap dentro de Ucayali y 2,213 focos evaluados (3 al 7 de octubre de 2026):

| Medida | Valor |
|---|---|
| Focos a menos de 10 km de un asentamiento | 1,386 (63 %) |
| Distancia mediana al asentamiento mas cercano | 6.4 km |
| Alertas "Alto" generadas solo por cercania | 1,322 |
| Alertas "Alto" por las otras condiciones | 76 |

La mayoria de los focos en Ucayali son quemas agricolas, y esas quemas ocurren cerca de las comunidades.
Por eso la cercania, usada como condicion suficiente para "Alto", no discrimina: casi dos de cada tres focos
quedarian en alerta y los avisos dejarian de ser accionables.

## Ajuste aplicado
La cercania (RN-02.1) **ya no genera por si sola** una alerta Alta; **agrava** a otra condicion:

| Condiciones cumplidas | Nivel |
|---|---|
| RN-02.2 y RN-02.3 | Critico |
| RN-02.1 + (RN-02.2 o RN-02.3) | Critico |
| solo RN-02.2 o solo RN-02.3 | Alto |
| solo RN-02.1 (cercania) | se clasifica por intensidad (FRP): Medio o Bajo |

Resultado sobre las mismas 2,213 alertas: 64 Criticas, 12 Altas, 1,065 Medias y 1,072 Bajas.
Se conserva el criterio de proteccion de RN-02 (una comunidad cerca de un foco en zona seca o protegida es critica)
sin disparar alertas por quemas agricolas rutinarias.

## Como revertirlo
`config/riesgo.json` -> `"cercania_sola_genera_alto": true` y luego `python scripts/reevaluar.py`.

## Limitaciones
- Los asentamientos vienen de OpenStreetMap, no del registro oficial de comunidades nativas (BDPI).
- El umbral de 10 km y el NDVI de estres (0.45) son provisionales; se ajustan con el backtesting del Sprint 6.
- Pendiente de validar con los usuarios clave (SERFOR, INDECI) en la Sprint Review.
