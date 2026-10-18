# Desviaciones del examen de la fórmula v2

Registro de todo lo que no salió como estaba previsto en el pre-registro (https://osf.io/x3z9s/overview, 2026-10-08). Cada desviación tiene fecha, motivo y efecto. Se anotó **antes de mirar cualquier resultado de Tempe** y antes de interpretar los de Filadelfia y Baton Rouge.

- **Apertura de la caja fuerte:** una sola vez, el 2026-10-08 a las 07:08 UTC (`investigacion/caja_fuerte/aperturas.json`, commit `e75e2af`). No se volvió a abrir. Todo lo que sigue usa solo los datos que quedaron en `data/examen_abierto/holdout_main/`.

## Desviación 1 (post-sello, código): un mapa sin rutas "Lowest risk" se registra como N.A.

- **Qué pasó:** el programa del examen se detuvo con un error (`KeyError: ['Lowest risk']`) al comparar rutas en Tempe. Con el mapa del **oráculo**, el buscador no devolvió ninguna ruta "Lowest risk" en los 2,000 viajes; solo "Fastest" y "Alternate route". Para saberlo se miraron únicamente los tipos de ruta, no los resultados.
- **Arreglo:** en `src/multiciudad/09_examen.py`, si un mapa no tiene ningún viaje con las dos rutas, su resultado de rutas y sus comparaciones pareadas se registran como **"N.A." (not available)** en vez de detener el programa. Es lo que el pre-registro ya dice ("Missing data": *trips where the router does not return both routes are dropped… reported as not available*). El código tenía un error al aplicarlo.
- **Qué NO cambia:** los modelos (las huellas siguen siendo las de `sello_v2.json`), las tablas de categorías, las reglas, las semillas y los resultados ya calculados de Filadelfia y Baton Rouge. Esas dos ciudades habían terminado los 13 mapas antes del error, y sus rutas se reutilizan tal cual desde los archivos guardados.
- **Comprobación:** prueba con viajes inventados. Un mapa sin rutas "Lowest risk" da N.A. y un mapa normal da el mismo resultado que antes.

## Desviación 2: Tempe no es evaluable por cobertura insuficiente

- **Señal:** el chequeo de lectura de Tempe pasó los mínimos, pero solo 12,445 de sus 317,766 registros caían en el periodo del estudio (2024-01-01 a 2026-08-31), con 383 del núcleo. Luego, el oráculo de Tempe no produjo ninguna ruta de menor riesgo. El pre-registro manda investigar la ciudad en ese caso ("Positive control").
- **Investigación:** solo de cobertura temporal. Se leyeron únicamente las columnas de fecha del archivo de Tempe (`OccurrenceDatetime`, `OccurrenceYear`, `OccurrenceMonth`, `OccurrenceDatePart`), sin ubicaciones, categorías, mapas ni resultados.
  - **El archivo termina el 2024-06-29.** Lo confirman dos lecturas independientes: el lector del examen y las columnas de año y mes que publica la propia Tempe. No hay ningún registro posterior a junio de 2024.
  - **Los registros por mes son normales hasta el final:** unos 2,000–2,300 por mes de 2013 a mayo de 2024, y 1,322 en junio de 2024, que es un mes incompleto.
  - **Del periodo del estudio,** Tempe solo tiene enero a junio de 2024 (6 de los 20 meses del "pasado") y **ningún registro del "futuro"** (2025-09-01 a 2026-08-31), que es lo que se califica.
- **Conclusión:** el problema es la **cobertura del archivo publicado**, no la lectura de fechas.
- **Decisión** (regla mecánica fijada por el autor el 2026-10-08, antes de ver ningún resultado de Tempe): **Tempe queda no evaluable por cobertura insuficiente.** No se cambia el periodo para "salvar" la ciudad.
- **Consecuencias:**
  - Las hipótesis H1, H2 y H3 exigían apoyo en las tres ciudades, así que **no pueden confirmarse**. Se reporta así.
  - Filadelfia y Baton Rouge se reportan normalmente, ciudad por ciudad, como manda el pre-registro.
  - Los archivos parciales de Tempe calculados antes del error se apartaron, sin abrirlos, a `investigacion/resultados/examen_v2/tempe_no_evaluable/`. No se interpretan.
- **Por qué no se detectó antes.** *Corregido el 2026-10-08.* Una primera versión de este punto suponía que la fecha "hasta oct 2026" era la de actualización de la ficha. **Era falso**, y se corrigió al revisar el registro de la conversación del 3 de octubre:
  - **Antes del sorteo,** la revisión de metadatos consultó directamente el **servicio oficial** de Tempe (FeatureServer) y obtuvo `OccurrenceDatetime: 1900-06-10 a 2026-10-03`. El servicio **sí tenía datos hasta octubre de 2026**.
  - **La caja fuerte** descargó por el enlace de **ArcGIS Hub** (`hub.arcgis.com/api/v3/datasets/.../downloads/data`). Hub entrega una **copia pregenerada** del archivo, y esa copia estaba **desactualizada**: termina el 2024-06-29. Las dos fuentes son el mismo conjunto de datos, porque la fecha más antigua coincide (1900-06-10).
  - **Causa:** no es que Tempe dejara de publicar ni un error del lector. Es una **descarga desactualizada** del canal elegido (Hub en vez de consultar el servicio directo). El chequeo de lectura no lo detectó porque solo revisaba que las fechas se pudieran leer, no que cubrieran el periodo.
  - **Efecto sobre la decisión:** ninguno para este examen. El archivo sellado y abierto no tiene el periodo calificado, y no se puede reemplazar por otro descargado después de abrir sin romper el protocolo. Tempe sigue **no evaluable en este examen**.
  - **Lo que no se llegó a ver:** el resultado de Tempe. Su archivo no tenía delitos del futuro, así que ningún resultado de Tempe contiene información del periodo calificado. Sí se vio un dato del pasado: 383 delitos del núcleo entre enero y junio de 2024, en el chequeo de lectura.
  - **Lecciones:**
    1. Descargar siempre del servicio directo, no de copias pregeneradas.
    2. Antes de sellar, comparar la fecha máxima del servicio con la del archivo descargado (solo metadatos, sin leer registros).
    3. Agregar al chequeo de lectura un mínimo de **cobertura del periodo futuro**.
    4. Revisar con el mismo criterio las fuentes de la reserva externa antes de usarla. En particular Boston, que también se descargó como un archivo estático.
- **Nota sobre el lector de Tempe** (no afecta la decisión):
  - `OccurrenceDatePart` resultó ser el **día del mes** (1–31), no una fecha completa. Por eso el lector usó en la práctica su respaldo, `OccurrenceDatetime` pasado a la hora de Arizona.
  - Los conteos por mes coinciden con las columnas de año y mes de Tempe con diferencias menores al 1%, por registros cerca del cambio de mes.

## Seguimiento: examen de reemplazo de Tempe (decidido el 2026-10-08)

- **Decisión del autor:** repetir el examen **solo en Tempe**, con la **misma fórmula v2** y una descarga directa del servicio oficial. El plan es `investigacion/preregistro_tempe.md`, que se registra en OSF como un registro nuevo antes de abrir.
- **Por qué Tempe y no otra ciudad:** ningún resultado de Tempe del año calificado llegó a existir. Tempe además la eligió el sorteo original, y sus datos públicos, su lector y su tabla de categorías se escribieron antes de abrir.
- **Antes de sellar, cambia solo la lectura y los chequeos, nunca la fórmula:**
  1. la hora de Tempe se usa tal cual (es local);
  2. el chequeo de lectura exige cobertura de todos los meses;
  3. la caja fuerte descarga directo del servicio.
- **La reserva externa sigue cerrada**, guardada para v3.

## Desviación 3 (documentación): semilla de los intervalos de las rutas

- **Qué pasó:** la revisión completa del 2026-10-08 encontró que el registro (página "Statistical models") dice que los intervalos del **cambio en las rutas** usan la semilla "CRC32 de examen-ciudad". El código sellado (`evaluar_rutas.calificar`, llamado sin semilla desde `09_examen.py`) usa una semilla **fija de 1** para ese paso, y lo mismo para el cambio por persona.
  - Las comparaciones pareadas, la retención y la calificación rápida **sí** usan "CRC32 de examen-ciudad", como dice el registro.
- **Efecto:** ninguno sobre la validez. La semilla 1 quedó fijada en el código sellado antes de abrir, así que tampoco se pudo elegir después de ver los datos. Es un error del texto, no del análisis. Se reporta como desviación y el registro de Tempe ya describe la semilla correcta.

## Nota: aclaración de la regla de las pruebas trampa (decidida antes del examen de Tempe)

- **El problema:** el simulacro con datos inventados mostró que la regla "la trampa debe quedar más cerca del azar que del mapa real" puede declarar "fuga" una trampa perfecta cuando el mapa real también está en el azar. Lo mismo pasa en rutas cuando el mapa real no reduce delitos.
- **La aclaración:** para esos casos, la trampa se juzga por si es compatible con el azar (su intervalo de confianza). Cuando el mapa real supera al azar, la regla es la original.
- **En Filadelfia y Baton Rouge, los veredictos son idénticos con las dos versiones** (comprobado con sus números): los mapas reales superaban claramente al azar y todas las trampas pasaron.
