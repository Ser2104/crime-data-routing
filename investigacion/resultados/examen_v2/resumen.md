# Examen de la formula v2 (generado por src/multiciudad/09_examen.py)

## filadelfia

Delitos: {'registros': 413305, 'ninguno': 382054, 'sin_ubicacion': 10736, 'lugar_cerrado': 9788, 'lejos_de_calle': 6239, 'sexual': 4425, 'fuera_de_ciudad': 63, 'nucleo_validos': 29799, 'sin_categoria': 0}

| Mapa | Rapida (promedio, IC95) | Rutas: delitos (IC95) | Rutas: por persona (IC95) |
|---|---|---|---|
| mapa_de_calor_A | 0.375 (0.347-0.400) | -27% (-33 a -21) | +5% (-7 a +19) |
| oraculo | 0.840 (0.808-0.859) | -83% (-85 a -80) | -83% (-86 a -79) |
| evitar_avenidas | 0.118 (0.105-0.136) | +11% (+1 a +23) | +12% (-8 a +36) |
| evitar_comercios | 0.136 (0.100-0.174) | -12% (-23 a -1) | +8% (-16 a +38) |
| mapa_de_calor_B | 0.413 (0.387-0.439) | -34% (-40 a -29) | -17% (-29 a -4) |
| B | 0.426 (0.400-0.452) | -36% (-42 a -30) | -13% (-26 a +1) |
| A | 0.397 (0.371-0.427) | -35% (-41 a -28) | -10% (-23 a +3) |
| C | 0.425 (0.394-0.452) | -39% (-45 a -33) | -10% (-23 a +7) |
| zona | 0.321 (0.296-0.350) | -17% (-25 a -8) | +9% (-7 a +28) |
| totales | 0.187 (0.161-0.212) | -11% (-21 a -0) | +40% (+17 a +67) |
| sin_delitos | 0.174 (0.148-0.204) | -8% (-18 a +2) | +47% (+23 a +72) |
| solo_mapa | 0.157 (0.132-0.189) | -7% (-17 a +4) | +11% (-10 a +40) |
| trampa_mapa_mezclado | 0.101 (0.095-0.108) | +2% (-4 a +8) | +28% (+15 a +44) |
| trampa_futuro_mezclado | 0.120 (0.110-0.129) | N.A. | N.A. |

Comparaciones pareadas (rapida: diferencia de captura; rutas: puntos porcentuales, negativo = el segundo evita mas; retencion: cambio del nivel / cambio de B):

| Medida | Base | Comparado | Valor | IC95 |
|---|---|---|---|---|
| rapida | mapa_de_calor_A | A | +0.022 | +0.012 a +0.036 |
| rapida | mapa_de_calor_B | B | +0.012 | +0.006 a +0.018 |
| rapida | evitar_avenidas | sin_delitos | +0.056 | +0.034 a +0.078 |
| rapida | evitar_comercios | sin_delitos | +0.038 | +0.020 a +0.063 |
| rutas | mapa_de_calor_A | A | -1.674 | -6.695 a +2.996 |
| rutas | mapa_de_calor_B | B | +0.142 | -3.724 a +4.364 |
| rutas | evitar_avenidas | sin_delitos | -18.869 | -31.642 a -6.249 |
| rutas | evitar_comercios | sin_delitos | -3.569 | -16.958 a +8.636 |
| retencion_de_B | B | A | +0.997 | +0.893 a +1.119 |
| retencion_de_B | B | C | +1.056 | +0.949 a +1.176 |
| retencion_de_B | B | zona | +0.533 | +0.316 a +0.707 |
| retencion_de_B | B | totales | +0.496 | +0.193 a +0.746 |
| retencion_de_B | B | sin_delitos | +0.438 | +0.125 a +0.688 |
| retencion_de_B | B | solo_mapa | +0.356 | +0.010 a +0.620 |

Pruebas trampa: mapa_mezclado_rapida pasa (0.101), futuro_mezclado_rapida pasa (0.120), mapa_mezclado_rutas pasa (2.163)

## baton_rouge

Delitos: {'registros': 67021, 'ninguno': 54379, 'sin_ubicacion': 7497, 'lejos_de_calle': 3462, 'sexual': 749, 'lugar_cerrado': 701, 'fuera_de_ciudad': 233, 'nucleo_validos': 4282, 'sin_categoria': 0}

| Mapa | Rapida (promedio, IC95) | Rutas: delitos (IC95) | Rutas: por persona (IC95) |
|---|---|---|---|
| mapa_de_calor_A | 0.378 (0.341-0.411) | -20% (-29 a -9) | +6% (-20 a +38) |
| oraculo | 1.000 (0.998-1.000) | -91% (-94 a -87) | -88% (-95 a -80) |
| evitar_avenidas | 0.077 (0.058-0.097) | +13% (-4 a +33) | +25% (-13 a +85) |
| evitar_comercios | 0.106 (0.078-0.139) | -20% (-38 a +0) | -16% (-55 a +46) |
| mapa_de_calor_B | 0.436 (0.400-0.468) | -28% (-36 a -19) | -4% (-26 a +26) |
| B | 0.467 (0.427-0.502) | -36% (-45 a -27) | -29% (-46 a -8) |
| A | 0.456 (0.416-0.488) | -28% (-37 a -18) | -21% (-40 a +4) |
| C | 0.472 (0.426-0.514) | -33% (-42 a -24) | -27% (-49 a +3) |
| zona | 0.294 (0.249-0.332) | -22% (-34 a -9) | -13% (-32 a +12) |
| totales | 0.191 (0.159-0.230) | -20% (-32 a -5) | -39% (-54 a -18) |
| sin_delitos | 0.192 (0.160-0.237) | -23% (-34 a -10) | -31% (-49 a -9) |
| solo_mapa | 0.172 (0.143-0.200) | +4% (-11 a +23) | +7% (-20 a +46) |
| trampa_mapa_mezclado | 0.109 (0.092-0.128) | +11% (+0 a +22) | +15% (-8 a +43) |
| trampa_futuro_mezclado | 0.129 (0.103-0.159) | N.A. | N.A. |

Comparaciones pareadas (rapida: diferencia de captura; rutas: puntos porcentuales, negativo = el segundo evita mas; retencion: cambio del nivel / cambio de B):

| Medida | Base | Comparado | Valor | IC95 |
|---|---|---|---|---|
| rapida | mapa_de_calor_A | A | +0.078 | +0.042 a +0.108 |
| rapida | mapa_de_calor_B | B | +0.031 | +0.009 a +0.048 |
| rapida | evitar_avenidas | sin_delitos | +0.116 | +0.083 a +0.163 |
| rapida | evitar_comercios | sin_delitos | +0.086 | +0.041 a +0.139 |
| rutas | mapa_de_calor_A | A | -10.019 | -19.425 a -1.623 |
| rutas | mapa_de_calor_B | B | -7.981 | -14.107 a -2.174 |
| rutas | evitar_avenidas | sin_delitos | -26.768 | -43.247 a -12.327 |
| rutas | evitar_comercios | sin_delitos | -9.091 | -28.000 a +9.093 |
| retencion_de_B | B | A | +0.768 | +0.583 a +0.946 |
| retencion_de_B | B | C | +0.953 | +0.814 a +1.100 |
| retencion_de_B | B | zona | +0.542 | +0.264 a +0.767 |
| retencion_de_B | B | totales | +0.453 | +0.138 a +0.722 |
| retencion_de_B | B | sin_delitos | +0.589 | +0.284 a +0.856 |
| retencion_de_B | B | solo_mapa | +0.010 | -0.600 a +0.408 |

Pruebas trampa: mapa_mezclado_rapida pasa (0.109), futuro_mezclado_rapida pasa (0.129), mapa_mezclado_rutas pasa (10.507)
