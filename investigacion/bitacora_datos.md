# Bitácora de datos por ciudad (ciudades de desarrollo)

Decisiones y hallazgos al preparar los datos. Todo esto se hizo **solo con ciudades de aprender y práctica**. Las de examen siguen selladas.

## Resumen (2024-01-01 a 2026-08-31, `src/multiciudad/02_normalizar_delitos.py`)

| Ciudad | Grupo | Delitos del núcleo por año | Definición amplia por año | Sin ubicación | Sin hora |
|---|---|---|---|---|---|
| Pittsburgh | aprender | 1,268 | 5,806 | 0.1% | 0.6% |
| Chapel Hill | aprender | 92 | 557 | 6.7% | 1.1% |
| Chicago | aprender | 21,782 | 87,463 | 0.6% | 3.4% |
| Seattle | aprender | 3,634 | 9,933 | 15.1% | 8.6% |
| Cincinnati | práctica | 1,606 | (no disponible) | 14.5% | 6.6% |
| Gainesville | práctica | 522 | 2,347 | 0.5% | 5.8% |

## Decisiones por ciudad

- **Pittsburgh.**
  - Archivo original de la policía, con todas las categorías y un delito por reporte (el más importante del núcleo, si lo hay).
  - Hora **del reporte** (la ciudad no publica la de ocurrencia).
  - El código NIBRS viene en cada fila.
- **Chicago.**
  - Traducción por el código FBI (`fbi_code`) y el tipo principal.
  - La "agresión grave" incluye *aggravated battery* (04B), como hace el FBI.
  - Hora de ocurrencia.
- **Seattle.**
  - Código NIBRS directo y hora de ocurrencia.
  - **La ciudad tapa la ubicación ("REDACTED")** de todos los homicidios (95 de 96), del 31% de las agresiones graves y de parte de las amenazas y agresiones simples. Probablemente es por privacidad en casos domésticos.
  - Por eso el núcleo de Seattle casi no tiene homicidios. **Limitación conocida.**
- **Chapel Hill.**
  - Unos 1,900 nombres libres. Se traducen con reglas por palabras (`categorias.py`), y se descartan las llamadas que no son delitos ("disparos escuchados", "investigación de drogas", "sin agresión").
  - **ArcGIS guarda la hora local marcada como si fuera UTC.** Se nota porque la hora más tranquila sale a las 4–5 a. m., como en las demás ciudades. Se usa tal como viene.
  - Hay un pico de horas exactas al mediodía (posible hora por defecto), que no se corrige.
  - Ningún homicidio en el periodo.
- **Cincinnati.**
  - Solo publica categorías gruesas (STARS).
  - Da el núcleo (homicidio, robo, agresión grave, más estrangulación, que el FBI cuenta como agresión grave) y las tres bolsas, pero **no** la definición amplia. Es un caso real del **nivel C**.
  - "Part 1 Violent" sin detalle va a la bolsa violenta, pero no al núcleo.
  - Se juntan dos bases: antes y después del 3 de junio de 2024.
  - Hora de ocurrencia (inicio).
- **Gainesville.**
  - Unos 300 nombres de Florida, traducidos con reglas por palabras.
  - "Robbery by sudden snatching" (Florida) se cuenta como **arrebato** (NIBRS 23B) y no como robo, siguiendo la definición del FBI.
  - "Homicide (attempted)" se cuenta como agresión grave (como en NIBRS). Los homicidios de tránsito y justificados no cuentan.

## Reglas comunes

- **Hora desconocida:** la hora exacta 00:00 se marca como desconocida, igual que en Pittsburgh. Todas las ciudades tienen un pico a medianoche.
- **Delitos sexuales:** excluidos en todas.
- **Ubicación válida:** dentro de EE. UU. continental. El recorte fino a la ciudad se hace al asignar cada delito a una calle.

## Pendiente

- **Peso de Chicago:** tiene 17 veces más delitos del núcleo que Pittsburgh. Al entrenar, cada ciudad debe pesar igual, o la fórmula aprendería sobre todo de Chicago.
- ~~Tablas de traducción de las ciudades de examen~~: hechas el 2026-10-05 (ver abajo).

## Errores encontrados en los horarios de transporte (2026-10-05)

Al revisar los rasgos se encontraron tres problemas en `flujo.buses_gtfs`, que afectaban a los buses por hora y a la simulación de peatones:

1. **Día de referencia.** Se usaba el 2º miércoles del archivo de horarios. En Chapel Hill caía en las vacaciones de invierno de la universidad: 33 viajes en vez de 1,080. En el tren ligero de Seattle: 160 en vez de 805. Ahora se usa **el miércoles con más viajes** del periodo (el primero si hay empate).
2. **Espacios invisibles.** El archivo de Gainesville trae un tabulador delante de cada código de servicio ("\tWB"): ningún viaje coincidía con el calendario, así que Gainesville quedó **sin buses**. Ahora se limpian los textos.
3. **Paradas sin hora.** Los horarios pueden dejar sin hora las paradas intermedias. En Gainesville son el 89%, y se descartaban. Ahora toman la hora de la parada anterior del mismo viaje.

Se recalcularon los pasos 5 y 5b de las 9 ciudades. Los resultados de práctica v1 (registro de práctica) se hicieron con estos errores: en Gainesville, el nivel "sin delitos" se evaluó sin buses.

## Ciudades de examen: lectura y traducción (2026-10-05, ANTES de abrir)

Escrito solo con la documentación oficial de cada portal y la descripción pública de sus columnas (nombres y tipos, nunca filas). Código: `src/multiciudad/categorias.py` (tablas) y `src/multiciudad/09_examen.py` (`leer_examen`).

- **Filadelfia** (OpenDataPhilly, `incidents_part1_part2`).
  - **Categoría:** código UCR del FBI redondeado a centenas (`ucr_general`): 100 homicidio, 300 robo, 400 agresión grave, etc.
  - **Homicidio:** el texto distingue "Criminal" de "Gross Negligence" y "Justifiable". Solo el primero es 09A.
  - **Hora:** la del despacho (`dispatch_date` + `dispatch_time`, hora local). Si falta, se usa la columna `hour`.
  - **Ubicación:** `point_x` / `point_y`, redondeadas a la cuadra.
- **Baton Rouge** (data.brla.gov, `pbin-pcm7`).
  - **Categoría:** código NIBRS (`nibrs_code`), como Pittsburgh y Seattle.
  - **Un renglón por cargo:** se deja un delito por caso (`incident_number`), el de la clase más importante del núcleo, igual que Pittsburgh.
  - **Fecha y hora:** la del reporte (`report_date`).
  - El CSV usa los nombres visibles de las columnas ("NIBRS DESCRIPTION"); el lector acepta los dos nombres.
- **Tempe** (ArcGIS, General Offenses).
  - **Categoría:** descripción libre (`OffenseCustom`), traducida con reglas **genéricas** por palabras, armadas con las de las ciudades de desarrollo.
  - **Hora:** la de la llamada a la policía (`OccurrenceDatePart` + `OccurrenceHour`). Si faltan, `OccurrenceDatetime` pasado a la hora de Arizona (sin horario de verano).
  - **Ubicación:** Tempe desplaza las direcciones al azar dentro de la cuadra (`ObfuscatedAddress`).
- **Prueba de los lectores:** con archivos inventados que imitan cada formato. Encontró un error, el nombre visible de Baton Rouge, que se corrigió antes de abrir.

## Tempe: descarga directa y hora corregida (2026-10-08, antes del examen de reemplazo)

- **Descarga:** la copia de ArcGIS Hub que bajó la caja fuerte estaba desactualizada (terminaba en 2024-06; el servicio llega a 2026-10). La caja fuerte tiene ahora un tipo de descarga **directa del servicio oficial** (FeatureServer), por páginas. Antes de sellar comprueba la cobertura del periodo y que se bajaron todas las filas, y solo responde OK o REVISAR. Se probó con Chapel Hill (desarrollo): se niega a sellar si no hay cobertura, no deja restos y baja todas las filas.
- **Hora:**
  - **El hallazgo:** `OccurrenceDatetime` viene marcado "+00", pero es **hora local**. En el archivo viejo coincidió en el 100% con las columnas de año, mes, día y hora de Tempe.
  - **El error que tenía el lector:** convertía esa hora a la de Arizona, lo que corría un día la fecha de un 21% de los registros (la hora salía bien porque venía de otra columna).
  - **Ahora:** se usa tal cual, como en Chapel Hill. `OccurrenceDatePart` es solo el **día del mes**, no una fecha.
- **Chequeo de lectura:** ahora exige al menos un registro en **todos los meses** de 2024-01 a 2026-08.
