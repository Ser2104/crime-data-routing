# Análisis para responder a la revisión externa: plan fijado ANTES de programarlos (2026-10-09)

**Qué es:** análisis **exploratorios, posteriores al examen**, que responden a una auditoría externa del borrador para TR-C. Se cumplen estas condiciones:
- usan solo lo que ya existe en la computadora: los resultados del examen, los rasgos de delitos por tramo que el examen guardó y los datos del examen **ya abiertos** (`data/examen_abierto/`);
- **no se reabre ninguna caja fuerte, no se reentrena ningún modelo** y se comprueban las huellas del sello antes de usar los modelos;
- ningún resultado registrado cambia; todo lo que salga se reporta, sea favorable o no.

Este plan se guarda en git antes de escribir el programa. Si algo cambia, se anota abajo con su fecha y su motivo.

**Comunes a todos los análisis:**
- Ciudades: Filadelfia, Baton Rouge y Tempe (examen de reemplazo). Se usan los mismos 2,000 viajes del examen (`evaluar_rutas.tareas`) y el mismo buscador, salvo donde se indica.
- **Medidas de rutas:**
  - **la registrada**, sobre los viajes con alternativa, con IC95 remuestreando viajes (semilla 1, como el examen);
  - **sobre todos los viajes**: la de menor riesgo si la app la ofrece y, si no, la más rápida. Su IC95 remuestrea zonas de 1 km del origen.
- **Semilla** de los análisis nuevos: 20261011. Remuestreos: 2,000.
- **Ensayo previo:** cada análisis se prueba primero con Gainesville (práctica) cuando aplica.
- **Salida:** `investigacion/resultados/revision/`.

## R1. Calidad del buscador frente a la mejor ruta posible (cota de Lagrange)

**Pregunta:** ¿cuánto peor es la ruta de menor riesgo que da la app que la mejor ruta posible dentro del mismo límite de tiempo?

**Cómo:** el método del paso 11 (`src/11_verificar_busqueda.py`), con el buscador configurado como en el examen:
- fondo 3×, sin calibración, sin luz;
- mapas **Detailed (B)** y **No crime data**;
- los 2,000 viajes del examen.

Para cada viaje:
- **piso** (cota de Lagrange): el mayor valor de min(exposición + μ·minutos) − μ·límite sobre los 31 precios del paso 11;
- **brecha**: la exposición de la mejor ruta de la app dentro del límite menos el piso, en puntos del % respecto de la más rápida.

**Se reporta:** la mediana y el percentil 95 de la brecha, la parte de viajes con brecha ≤ 1 y ≤ 3 puntos, y la parte con "mejora perdida" de 3 puntos o más (una ruta dentro del límite, encontrada con los 31 precios, 3+ puntos mejor que la de la app).

## R2. Sensibilidad al riesgo de fondo

**Cómo:** se repite el buscador con el riesgo de fondo en **1×** y **10×** el riesgo promedio de la ciudad (el examen usó 3×), con los mapas Detailed (B) y No crime data.

**Se reporta,** para cada valor: las dos medidas de rutas, la parte de viajes con alternativa y la mediana de minutos extra.

## R3. Fuga temporal de los rasgos públicos (OpenStreetMap y horarios de buses)

**Qué se cambia:** los rasgos que salen de OpenStreetMap y de GTFS se rehacen con datos **anteriores al período evaluado** (antes del 2025-09-01):
- **OpenStreetMap:** la copia de Geofabrik del **2025-01-01** (`<estado>-250101.osm.pbf`), la última anterior al período evaluado que Geofabrik conserva. Se lee con `src/osm_local.py` exactamente como en los pasos 3 y 5b, con el mismo recuadro.
- **Horarios (GTFS):** la última versión publicada antes del 2025-09-01 que se pueda obtener públicamente:
  - **Filadelfia:** SEPTA v202508311 (GitHub `septadev/GTFS`, publicada el 2025-08-30; buses y trenes);
  - **Baton Rouge (CATS) y Tempe (Valley Metro):** no se encontró ninguna versión anterior. Se buscó el 2026-10-09 en el Internet Archive, en el portal de datos de Phoenix y en el catálogo público de Mobility Database. Se **mantienen** sus horarios de 2026, así que en esas dos ciudades el análisis aísla solo la parte de OpenStreetMap. Se declara.

**Qué no cambia:**
- la **red caminable** (2026), para que los tramos coincidan con los delitos guardados (fuga residual muy chica: la forma de la red);
- el Censo 2020, LODES 2023 y la luz VIIRS (hasta el 2025-08-31), que no tienen fuga;
- los rasgos de delitos por tramo (`<ciudad>_mapa_delitos.csv`).

**Qué se recalcula:**
- la forma de la calle que depende de OSM (calles principales, locales, paradas, parques);
- la actividad por franja (buses, locales, bares);
- los peatones simulados;
- los lugares (escuelas, universidades, hospitales, comisarías, gasolineras, estaciones, estadios) y las paradas con horario.

El constructor usa las mismas funciones que los pasos 5 y 5b. **Validación antes de usarlo:** con las entradas originales de 2026 de Gainesville, debe reproducir sus archivos `tramos.csv` y `tramos_lugares.csv` (diferencia relativa máxima ≤ 1e-6 en cada columna que usa el modelo).

**Mapas evaluados:** los 7 niveles con los modelos sellados, más las reglas "evitar avenidas" y "evitar comercios".

**Se reporta:** las dos medidas de rutas de cada mapa, junto al valor del examen.

## R4. Sobredispersión de los delitos (en lugar de Poisson)

**Cómo:**
1. Con los datos abiertos, se cuentan los delitos del núcleo del futuro por tramo (los conservados, con fecha) en dos mitades: **sep–feb** y **mar–ago**.
2. Con p̂ = (total de la primera mitad) / (total del año), la dispersión es φ = Σ(h1 − p̂·n)² / Σ n·p̂·(1 − p̂), sobre los tramos con n ≥ 1. φ = 1 es Poisson; φ > 1 indica agrupamiento en el tiempo.
3. Se repite el intervalo "zonas + delitos re-sorteados" de la auditoría (`auditoria_estadistica.py`). El sorteo es **binomial negativo** con media = el conteo observado y varianza = φ·media (gamma-Poisson; si φ ≤ 1, Poisson), el mismo sorteo para todos los viajes que pasan por un tramo.

**Mapas:** B, A, C y No crime data. **Se reporta:** φ por ciudad y los nuevos IC95.

## R5. Sensibilidad a las exclusiones de delitos

**Variantes:** con los datos abiertos y el resto igual al examen:
- **"lugares"**: no se excluyen los delitos a menos de 30 m de cárceles, hospitales, comisarías y centros sociales;
- **"calle_100"**: el máximo de distancia a una calle caminable pasa de 50 m a **100 m**.

Cada variante rehace los rasgos de delitos del pasado y los delitos del futuro (`rasgos_delitos.construir`).

**Mapas:**
- **B** se vuelve a predecir con el modelo sellado y se recalculan sus rutas;
- **No crime data** conserva su mapa y sus rutas, pero se vuelven a contar sus delitos.

**Se reporta:** los conteos excluidos por motivo en cada variante y las dos medidas de rutas.

## R6. Auditoría de las categorías de Tempe

**Cómo:** con los datos abiertos de Tempe (reemplazo), en el período del estudio, se lista cada descripción (`OffenseCustom`) con su conteo, su código asignado y su clase del núcleo.

**Chequeos fijados de antemano:**
- **(a)** descripciones **sin** clase del núcleo cuyo texto nombra un delito del núcleo: MURDER, HOMICIDE o MANSLAUGHTER (sin NEGLIGENT, JUSTIFIABLE, VEHICULAR ni ATTEMPT), ROBBERY, CARJACK, AGGRAVATED, AGG ASSAULT;
- **(b)** descripciones **con** clase del núcleo cuyo texto nombra **otro** delito del núcleo;
- **(c)** para transparencia, una tabla con las 25 descripciones más frecuentes de cada clase del núcleo y las 25 más frecuentes sin clase.

**Corrección (exploratoria):** si (a) o (b) encuentran descripciones cuyo texto nombra **exactamente un** delito del núcleo, se recodifican a esa clase y se repite Tempe con los mapas B, A, C y No crime data. Si no hay ninguna, solo se reporta la auditoría.

## R7. Medida por persona: sensibilidad

**Variantes:** el piso de peatones en el **percentil 25** y en el **75** de los tramos con peatones (el registrado usa la mediana), y una variante **sin las franjas nocturnas** (madrugada y noche), cuyos peatones no se validaron.

**Mapas:** los 7 niveles. Se usan las rutas del examen; no se recalcula ninguna ruta.

## R8. Viajes ponderados por peatones

**Cómo:** cada viaje pesa según los peatones simulados por hora en su franja a lo largo de su ruta más rápida (promedio ponderado por largo). Así cuentan más los viajes por calles donde camina más gente. Se calculan las dos medidas de rutas ponderadas: Σ w·b / Σ w·a − 1. El IC95 remuestrea zonas de 1 km.

**Mapas:** los 7 niveles, con las rutas del examen.

## R9. Modelo frente a mapa de delitos del pasado, sobre todos los viajes

**Cómo:** diferencias pareadas del cambio sobre todos los viajes, en puntos porcentuales (negativo = el modelo evita más), para B frente al mapa de calor B y A frente al mapa de calor A. El IC95 remuestrea zonas de 1 km.

## R10. G16: ancho de banda y dos variantes más

**Ancho de banda (descriptivo):** el ancho de la regla de Scott en metros, por eje (raíz de la diagonal de la covarianza del KDE), con los delitos del núcleo y con todos los delitos del pasado.

**Variantes:** las mismas que en `comparacion_metodos.py` ("como se publicó" y "muestreo uniforme"), con los delitos del núcleo y con todos:
- **"por franja"**: el KDE de cada franja usa solo los delitos del pasado de esa franja (los de hora desconocida entran con peso 1/4 en cada una), y cada viaje usa el riesgo de su franja. Galbrun et al. (2014) proponen filtrar por hora aunque en sus experimentos no lo hicieron; aquí se usa la misma información horaria que tienen nuestros modelos.
- **"isotrópico"**: el núcleo de su ecuación 1 (un solo ancho h para los dos ejes), con h² = factor de Scott² × (σx² + σy²)/2, en lugar de la covarianza completa.

**Se reporta:** el cambio sobre todos los viajes (IC95 por zonas) y la diferencia pareada con nuestros mapas.

## Documentación (sin calcular nada nuevo)

- La tabla de exclusiones por motivo (del `resumen.md` del examen).
- El apéndice de rasgos y ajustes del modelo (de `formula.py`):
  - los rasgos de cada nivel;
  - la normalización;
  - LightGBM con semilla 7, 400 rondas y lambda_l2 = 1;
  - el peso igual por ciudad;
  - el período de entrenamiento.
- **Una limitación que se agrega:** las ciudades de aprendizaje usaron los mismos períodos que el examen (pasado 2024-01 a 2025-08, futuro 2025-09 a 2026-08). Una app real entrenaría con un año anterior.

## Orden

1. Este plan, a git.
2. Programa, y ensayo con Gainesville (R1, R2, R3 con la validación del constructor, R5, R7, R8 y R10).
3. Las 3 ciudades.
4. Informe, artículo (resultados exploratorios posteriores al examen, en una sección aparte y un apéndice) y PDF.

## Cambios a este plan

1. **R6, antes de correrlo y antes de mirar ninguna descripción de Tempe (2026-10-09).** Al programarlo se vieron dos huecos en los chequeos:
   - **Negaciones:** una palabra precedida de NON o NOT (por ejemplo "NON-AGGRAVATED") no cuenta como que el texto nombre ese delito.
   - **Nuevo chequeo (d):** en Arizona hay delitos "agravados" que no son agresiones (aggravated DUI, aggravated criminal damage, aggravated harassment, aggravated identity theft). La regla genérica (AGGRAVAT → 13A) pudo contarlos como agresión grave. Se marcan las descripciones asignadas a agresión grave cuyo texto no tiene ninguna palabra de agresión: ASSAULT, BATTERY, ADW/A.D.W., DEADLY WEAPON, DANGEROUS INSTRUMENT, SHOOT, STAB, STRANGUL, CHOK, MAIM, INJUR, o MURDER/HOMICIDE con ATTEMPT. Se recodifican como **no núcleo** solo si el texto nombra otro delito de esta lista: DUI, DWI, DRIV, CRIMINAL DAMAGE, DAMAGE, HARASS, IDENTITY, THEFT, TAKING, TRESPASS, FRAUD, FORGER, SHOPLIFT, BURGL, LARCENY, ARSON, ESCAPE, ANIMAL. Las demás se listan sin recodificar.
2. **R4, al programarlo (2026-10-09):** los sorteos se generan uno por uno (el mismo sorteo para los 4 mapas), en vez de guardarlos todos juntos, por memoria. El método no cambia.
