# Cámaras de vigilancia y delitos violentos (análisis exploratorio)

*5 de octubre de 2026. Ciudades de desarrollo. Código: `src/multiciudad/08_camaras.py`. Tabla: `investigacion/resultados/camaras.csv`.*

## Pregunta

¿Las calles con cámaras, sobre todo **lectores de placas** como las Flock, tuvieron menos delitos violentos (homicidio, robo, agresión grave)?

## Por qué es exploratorio y no prueba causa

- **No se sabe cuándo se instaló cada cámara.** Las de OpenStreetMap están dibujadas hoy, así que no hay "antes y después".
- **Las cámaras no se ponen al azar.** Los lectores de placas van sobre todo en avenidas con mucho tránsito de carros.
- **El dibujo es desparejo entre ciudades.** Por eso las cámaras no son un rasgo de la fórmula.

## Método

1. Una fórmula (nivel A) que **no sabe dónde hay cámaras** y se entrenó **sin la ciudad evaluada** predice los delitos violentos del futuro de cada calle. Se compara lo observado con lo esperado en las calles con cámaras a ≤ 100 m, frente al resto.
2. **Tendencia:** cambio del pasado al futuro frente a calles sin cámara con el mismo nivel de delitos en el pasado.
3. **Robustez:** se compara solo contra calles sin cámara **del mismo tipo y a la misma distancia de una avenida**.

Intervalos del 95% remuestreando zonas de 1 km. En la prueba 3, el ajuste por tipo de calle se fija y no se remuestrea, así que su intervalo es algo más estrecho de lo real.

## Resultados: lectores de placas (1 = igual que lo esperado; menos de 1 = menos delitos)

| Ciudad | Delitos cerca | Contra lo esperado | Tendencia | **Contra calles del mismo tipo** |
|---|---|---|---|---|
| Pittsburgh | 121 | 0.42 (0.28–0.57) | 0.58 (0.40–0.75) | **0.63** (0.46–0.76) |
| Chicago | 1,433 | 0.83 (0.76–0.92) | 0.88 (0.80–0.95) | **1.08** (0.96–1.22) |
| Seattle | 374 | 0.97 (0.66–1.34) | 0.82 (0.63–1.08) | **1.04** (0.70–1.41) |
| Cincinnati | 45 | 0.55 (0.37–0.90) | 0.67 (0.45–1.07) | **0.73** (0.49–1.37) |
| Gainesville | 27 | 0.37 (0.23–0.54) | 0.41 (0.25–0.58) | **0.50** (0.33–0.75) |
| Chapel Hill | 1 | (muy pocos casos) | | |

Las otras cámaras (las que no leen placas) muestran un patrón parecido. Las cifras están en `camaras.csv`.

## Lectura

- **Sin ajustar, parece que hay menos delitos violentos cerca de las cámaras** en casi todas las ciudades.
- **Al comparar con calles del mismo tipo, la señal desaparece en Chicago**, que es la ciudad con más datos (1,433 delitos cerca de lectores), y también en Seattle y Cincinnati. Se mantiene en Pittsburgh y Gainesville, que tienen pocos casos.
- **Conclusión prudente:** no hay evidencia consistente de que los lectores de placas reduzcan los delitos violentos alrededor. Buena parte de la diferencia inicial se explica por **dónde** se ponen (avenidas). Esto coincide con la literatura (Piza et al. 2019; Adams y Mourtgos): efecto en robo de autos, pero no demostrado en delitos violentos.
- **Lo que haría falta para una respuesta causal:** las fechas de instalación (por pedido de información pública a cada policía) y un diseño antes y después con calles de comparación.
