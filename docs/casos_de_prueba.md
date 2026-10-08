# Casos de prueba CP-01 a CP-19 (tabla 12.5 del informe)

Ejecutado el 2026-10-08 con `python scripts/evidencia_casos.py` sobre `tests/test_casos_cp.py` y los datos de `tests/datos/`
(focos de ejemplo en Pucallpa, Atalaya, Huánuco, Brasil y Loreto, y escenarios ficticios de riesgo).

Resumen: **19 de 19** casos pasan; 0 omitidos; 0 fallan.
Los casos CP-04, CP-05 y CP-06 usan Earth Engine real y se omiten donde no hay credenciales (p. ej. en el CI de GitHub); CP-11, CP-12 y CP-18
requieren el límite regional cargado.

| ID | Req. | Caso | Resultado esperado | Sprint | Resultado obtenido | Evidencia |
|---|---|---|---|---|---|---|
| CP-01 | RF-01 | Descargar focos de FIRMS de 1 día | Se obtiene un CSV con columnas latitude, longitude, acq_date, frp | S2 | **PASÓ** (2026-10-08) | `test_cp_01_descarga_de_focos_de_1_dia_trae_las_columnas` |
| CP-02 | RF-02 | Foco en Pucallpa y foco en Huánuco | Se guarda el de Pucallpa; el de Huánuco se descarta | S2 | **PASÓ** (2026-10-08) | `test_cp_02_foco_en_pucallpa_se_guarda_y_el_de_huanuco_se_descarta` |
| CP-03 | RF-01 | Repetir la descarga del mismo día | No se duplican registros (ON CONFLICT) | S2 | **PASÓ** (2026-10-08) | `test_cp_03_repetir_la_descarga_del_mismo_dia_no_duplica` |
| CP-04 | RF-04/05 | NDVI de una zona con nubosidad < 30 % | Valor entre -1 y 1 | S3 | **PASÓ** (2026-10-08) | `test_cp_04_ndvi_de_una_zona_esta_entre_menos_1_y_1` |
| CP-05 | RF-06 | NBR de un área quemada conocida | NBR menor que el de la vegetación sana vecina | S3 | **PASÓ** (2026-10-08) | `test_cp_05_el_nbr_de_un_area_quemada_es_menor_que_el_de_la_vegetacion_sana` |
| CP-06 | HU-04 | Píxeles del río Ucayali | Al menos 95 % de píxeles de agua excluidos | S4 | **PASÓ** (2026-10-08) | `test_cp_06_la_mascara_de_agua_excluye_al_menos_95_por_ciento` |
| CP-07 | RF-07 | Foco en ANP y con NDVI de estrés | Nivel CRÍTICO (dos condiciones de RN-02) | S4 | **PASÓ** (2026-10-08) | `test_cp_07_foco_en_anp_con_ndvi_de_estres_es_critico` |
| CP-08 | RF-07 | Foco junto a un aserradero registrado | Nivel BAJO con regla RN-04 | S4 | **PASÓ** (2026-10-08) | `test_cp_08_foco_junto_a_un_aserradero_es_bajo_con_rn_04` |
| CP-09 | RF-12 | Evaluación ALTA | Se crea una alerta en estado ACTIVA | S4 | **PASÓ** (2026-10-08) | `test_cp_09_una_evaluacion_alta_crea_una_alerta_activa` |
| CP-10 | RF-13 | Alerta crítica en zona con guardaparque | Correo enviado y registrado en notificaciones | S4 | **PASÓ** (2026-10-08) | `test_cp_10_una_alerta_critica_envia_el_correo_y_queda_registrada` |
| CP-11 | RF-08/09 | Abrir el visor y activar capas | Mapa centrado en Ucayali con capas superpuestas | S5 | **PASÓ** (2026-10-08) | `test_cp_11_el_visor_abre_centrado_en_ucayali_con_capas_para_superponer` |
| CP-12 | RF-10/11 | Clic en un foco y cambio de ventana a 48 h | Se ven sus atributos; el mapa se actualiza | S5 | **PASÓ** (2026-10-08) | `test_cp_12_cambiar_la_ventana_a_48_h_actualiza_el_mapa_y_los_focos_traen_sus_atributos` |
| CP-13 | RF-16 | Login con clave errónea 5 veces | Cuenta bloqueada y evento en auditoría | S5 | **PASÓ** (2026-10-08) | `test_cp_13_cinco_claves_erroneas_bloquean_la_cuenta_y_quedan_en_auditoria` |
| CP-14 | RF-17 | Guardaparque entra a Administración por URL | Mensaje de acceso denegado | S5 | **PASÓ** (2026-10-08) | `test_cp_14_un_guardaparque_que_abre_administracion_por_url_recibe_acceso_denegado` |
| CP-15 | RF-14 | Guardaparque marca una alerta como confirmada | Estado CONFIRMADA y validación guardada | S6 | **PASÓ** (2026-10-08) | `test_cp_15_el_guardaparque_marca_una_alerta_como_confirmada` |
| CP-16 | RF-15 | Exportar reporte | PDF y CSV con los mismos totales | S6 | **PASÓ** (2026-10-08) | `test_cp_16_el_reporte_pdf_y_csv_traen_los_mismos_totales` |
| CP-17 | RN-05 | Alerta sin validar por más de 6 h | Pasa a REVISION_HISTORICA | S6 | **PASÓ** (2026-10-08) | `test_cp_17_alerta_con_mas_de_6_h_pasa_a_revision_historica` |
| CP-18 | RNF-09 | Cargar el mapa regional 20 veces | Promedio menor a 5 s | S5/S6 | **PASÓ** (2026-10-08) | `test_cp_18_cargar_el_mapa_regional_20_veces_tarda_menos_de_5_s_en_promedio` · promedio 0.59 s, máximo 0.8 s en 20 cargas (solo servidor) |
| CP-19 | RNF-01 | Ciclo completo del job con 200 focos | De la descarga a la alerta en menos de 60 s | S6 | **PASÓ** (2026-10-08) | `test_cp_19_el_ciclo_con_200_focos_tarda_menos_de_60_s` · 0.18 s con 200 focos (Earth Engine simulado); con Earth Engine real: 17 s para 177 focos |

## Observaciones
- Los casos CP-09, CP-10 y CP-19 simulan la respuesta de Earth Engine (y el servidor de correo) para no tocar datos reales ni enviar correos; el resto
  de la cadena (base de datos, motor de riesgo, auditoría, notificaciones) es real. La medición con Earth Engine real quedó en la corrida del ciclo
  automático: 177 focos en 17 s.
- **CP-18 mide solo el servidor.** Con un navegador real el mapa tarda 6.5 s con 1 usuario y 37 s con 10 usuarios simultáneos (con caché):
  la meta de 5 s de RNF-09 se cumple en el servidor pero **no** de extremo a extremo. Detalle y causas en `docs/pruebas_rendimiento.md`.
- Los focos de prueba se crean con una fuente `TEST_*` y se borran al terminar cada caso; la auditoría de prueba se limpia con un permiso especial
  que solo conceden las pruebas.
