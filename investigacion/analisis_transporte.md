# Análisis de transporte para la versión TR-C: plan fijado ANTES de correr (2026-10-09)

**Qué es:** análisis **exploratorios** para presentar el estudio como un artículo de **navegación peatonal**: costo en tiempo, efecto en el sistema y costo de cálculo. Usan los datos del examen que ya están abiertos y los mapas de riesgo ya calculados. No se abre ninguna caja ni se cambia ninguna fórmula. Este plan se guarda en git **antes** de escribir el programa. Se reporta todo lo que salga, y si algo cambia se anota abajo con fecha y motivo.

## A. Curva costo–beneficio: delitos evitados según el tiempo extra aceptado

- **Buscador:** el de la app (`rutas.buscar_rutas`), sin cambios, salvo el **límite de tiempo extra**. En lugar del de la app (el mayor entre 10 minutos y la mitad del tiempo de la ruta más rápida), se fija en **2, 5 y 10 minutos** exactos (`MAX_EXTRA = 0`, `MAX_EXTRA_MIN = límite`). Todo lo demás queda igual: los valores de λ, la búsqueda fina cerca del límite, la mejora mínima de 3% y las reglas de solape.
- **Mapas:**
  - **Detailed (B):** el mejor nivel con datos de delitos por calle;
  - **No crime data:** sin datos de delitos;
  - **el oráculo:** el techo.

  Son los mismos archivos de riesgo del examen (`<ciudad>_riesgo_<mapa>.csv`).
- **Ciudades y viajes:** Filadelfia, Baton Rouge y Tempe; los **mismos 2,000 viajes** (`evaluar_rutas.tareas`).
- **Medidas, por límite:**
  - cambio en los delitos del núcleo del futuro **sobre todos los viajes**: cada viaje toma la ruta de menor riesgo si la app la ofrece, y la más rápida si no;
  - mediana de minutos extra sobre todos los viajes y sobre los viajes con alternativa;
  - parte de los viajes con alternativa.
- **Intervalos:** IC95 remuestreando zonas de 1 km del origen (2,000 remuestreos, semilla 20261010).
- **El punto de la app** (límite por defecto) se toma del examen ya hecho (`<ciudad>_viajes_<mapa>_2000.jsonl`).

## B. Efecto en el sistema: ¿se concentran los peatones?

Con los viajes del examen, con el límite por defecto, para **Detailed (B)** y **No crime data**. Si todos siguieran la sugerencia de la app (la ruta de menor riesgo si se ofrece, y si no la más rápida), se calcula, frente a tomar siempre la más rápida:
- los **tramos distintos usados**;
- la parte de los metros recorridos que cae en el **1% de tramos más usados**;
- el **índice de Gini** de los metros recorridos por tramo.

Es descriptivo: los viajes son una muestra al azar, no la demanda real.

## C. Costo de cálculo

- **Muestra:** los **primeros 200 viajes** de cada ciudad, con el mapa Detailed (B), en un solo proceso.
- **Medida:** el tiempo por consulta de `buscar_rutas`, sin contar la carga de la red (mediana y percentil 95).
- **Informe:** se anota la computadora en la que se midió.

## Orden

1. Ensayo con Gainesville (práctica, 50 viajes, mapas del ensayo del examen).
2. Las 3 ciudades.
3. Informe y nueva presentación del artículo para TR-C.

## Cambios a este plan

- **Los análisis no cambiaron.** Se corrieron tal como se fijaron arriba (commit 4f35e2f, terminado el 2026-10-09 a las 17:29).
- **Chequeos agregados** después de correr, antes de mirar el texto del artículo (`investigacion/verificar_transporte.py`). No cambian ningún número; solo comprueban:
  - que cada límite se respetó;
  - que están los 2,000 viajes;
  - que la ruta más rápida no cambia con el mapa;
  - que la curva está completa.

  Resultado: OK.
- **Una cifra derivada en el texto.** Para el texto se informa también el **cociente de las estimaciones puntuales**: el cambio con el límite de 2 o 5 minutos dividido por el cambio con el límite de la app. Esa cifra no estaba en el plan y no tiene intervalo propio; se presenta como descriptiva.
