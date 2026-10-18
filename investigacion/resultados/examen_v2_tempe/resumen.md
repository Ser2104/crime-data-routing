# Examen de la formula v2 (generado por src/multiciudad/09_examen.py)

## tempe

Delitos: {'registros': 76143, 'ninguno': 68679, 'lejos_de_calle': 3626, 'lugar_cerrado': 1304, 'sexual': 1107, 'sin_fecha': 670, 'fuera_de_ciudad': 574, 'sin_ubicacion': 183, 'nucleo_validos': 1736, 'sin_categoria': 41886}

| Mapa | Rapida (promedio, IC95) | Rutas: delitos (IC95) | Rutas: por persona (IC95) |
|---|---|---|---|
| mapa_de_calor_A | 0.444 (0.381-0.500) | -31% (-40 a -22) | -16% (-38 a +11) |
| oraculo | 1.000 (0.998-1.000) | -92% (-95 a -89) | -88% (-97 a -77) |
| evitar_avenidas | 0.306 (0.250-0.377) | -37% (-48 a -25) | -6% (-36 a +39) |
| evitar_comercios | 0.253 (0.162-0.331) | -29% (-42 a -13) | +1% (-40 a +63) |
| mapa_de_calor_B | 0.569 (0.514-0.629) | -54% (-61 a -46) | -23% (-44 a +4) |
| B | 0.575 (0.529-0.630) | -57% (-64 a -49) | -27% (-49 a -0) |
| A | 0.527 (0.477-0.580) | -52% (-60 a -43) | -28% (-49 a -2) |
| C | 0.591 (0.540-0.637) | -52% (-60 a -43) | -16% (-43 a +18) |
| zona | 0.422 (0.347-0.469) | -35% (-44 a -24) | -17% (-39 a +9) |
| totales | 0.356 (0.299-0.419) | -35% (-46 a -24) | -14% (-38 a +16) |
| sin_delitos | 0.355 (0.287-0.436) | -34% (-45 a -22) | -6% (-32 a +29) |
| solo_mapa | 0.346 (0.283-0.405) | -40% (-50 a -29) | -31% (-51 a -5) |
| trampa_mapa_mezclado | 0.074 (0.054-0.094) | +3% (-7 a +16) | +40% (+16 a +69) |
| trampa_futuro_mezclado | 0.121 (0.094-0.150) | N.A. | N.A. |

Comparaciones pareadas (rapida: diferencia de captura; rutas: puntos porcentuales, negativo = el segundo evita mas; retencion: cambio del nivel / cambio de B):

| Medida | Base | Comparado | Valor | IC95 |
|---|---|---|---|---|
| rapida | mapa_de_calor_A | A | +0.083 | +0.051 a +0.147 |
| rapida | mapa_de_calor_B | B | +0.006 | -0.015 a +0.045 |
| rapida | evitar_avenidas | sin_delitos | +0.049 | -0.032 a +0.117 |
| rapida | evitar_comercios | sin_delitos | +0.102 | +0.060 a +0.158 |
| rutas | mapa_de_calor_A | A | -16.505 | -25.997 a -7.862 |
| rutas | mapa_de_calor_B | B | -0.307 | -6.098 a +5.090 |
| rutas | evitar_avenidas | sin_delitos | +2.632 | -8.764 a +14.215 |
| rutas | evitar_comercios | sin_delitos | -4.598 | -17.835 a +8.276 |
| retencion_de_B | B | A | +0.897 | +0.778 a +1.021 |
| retencion_de_B | B | C | +1.005 | +0.902 a +1.112 |
| retencion_de_B | B | zona | +0.616 | +0.452 a +0.769 |
| retencion_de_B | B | totales | +0.640 | +0.459 a +0.798 |
| retencion_de_B | B | sin_delitos | +0.589 | +0.399 a +0.753 |
| retencion_de_B | B | solo_mapa | +0.664 | +0.513 a +0.815 |

Pruebas trampa: mapa_mezclado_rapida pasa (0.074), futuro_mezclado_rapida pasa (0.121), mapa_mezclado_rutas pasa (3.275)
