# Registro de práctica

Cada versión de la fórmula que se evalúa en las ciudades de **práctica** (Cincinnati, Gainesville) se anota aquí con fecha, qué cambió y la calificación rápida. Así se puede reportar cuántos intentos hubo antes de sellar. Las ciudades del examen no se usan para nada de esto.

**Calificación rápida:** parte de los delitos del núcleo del futuro que cae en el 10% de la red marcado como más riesgoso (por franja). El azar daría 0.10.

## v0 (2026-10-04, ensayo sin Chicago)

- **Qué:** primera versión. Rasgos públicos más los rasgos de delitos de cada nivel, por franja.
- **Aprende con:** Pittsburgh, Chapel Hill y Seattle.
- **Resultado:** funciona de punta a punta.
  - Sin delitos: 0.15–0.19.
  - Con delitos: 0.29–0.57.
  - Los modelos con delitos **no superan** al mapa de calor simple en varias franjas. Ejemplo, Gainesville de noche: nivel B 0.43 contra mapa de calor B 0.54.
- **Decisión:** agregar versiones más estables de la misma información (suma de las 4 franjas y nivel de la zona), derivadas de lo que cada nivel ya tiene.

## v0.1 (2026-10-04, ensayo sin Chicago)

- **Qué:** se agregan, para cada nivel, la suma de las 4 franjas y el nivel de la zona y de la ciudad, derivados de su propia información.
- **Resultado:**
  - Nivel A supera al mapa de calor del núcleo en Cincinnati en todas las franjas (de noche 0.39 contra 0.34) y empata o supera en Gainesville.
  - Nivel C es el mejor en ambas ciudades (Gainesville de noche 0.56).
  - Nivel B sigue algo por debajo del mapa de calor amplio en Gainesville (de noche 0.46 contra 0.54). Gainesville tuvo solo 424 delitos del núcleo en el futuro, así que diferencias de unos pocos puntos pueden ser ruido.
  - Sin delitos: sin cambio, 0.15–0.19.
- **Decisión:** esperar a Chicago (la mayor parte de los datos de aprendizaje) antes de seguir ajustando. Agregar intervalos de confianza a la calificación rápida, para no perseguir ruido.

## v1 (2026-10-04): las 4 ciudades de aprender

- **Qué:** igual que v0.1, ahora aprendiendo con Pittsburgh, Chapel Hill, Chicago y Seattle (3.1 millones de filas; cada ciudad pesa igual).
- **Calificación rápida** (promedio de las 4 franjas, IC95 remuestreando zonas de 1 km; el azar daría 0.10):

| Mapa | Cincinnati | Gainesville |
|---|---|---|
| Oráculo (techo imposible) | 0.99 | 1.00 |
| Mapa de calor amplio (sin fórmula) | (no disponible) | 0.51 (0.42–0.58) |
| **C** (bolsas gruesas) | **0.45** (0.38–0.50) | **0.54** (0.45–0.62) |
| **B** (detallado) | (no disponible) | 0.49 (0.40–0.57) |
| **A** (solo núcleo) | 0.41 (0.36–0.45) | 0.45 (0.36–0.55) |
| Mapa de calor del núcleo (sin fórmula) | 0.34 (0.30–0.40) | 0.39 (0.32–0.48) |
| Por zona | 0.29 (0.24–0.34) | 0.24 (0.18–0.33) |
| Totales | 0.20 (0.14–0.25) | 0.18 (0.13–0.24) |
| Sin delitos | 0.20 (0.14–0.24) | 0.18 (0.12–0.24) |
| Solo mapa | 0.18 (0.13–0.24) | 0.17 (0.11–0.24) |

- **Lectura:**
  - Con delitos del pasado, la fórmula iguala o supera al mapa de calor del mismo tipo de datos (A le gana al mapa de calor del núcleo en las dos ciudades).
  - Sin datos de delitos, la fórmula captura casi el doble que el azar (0.18–0.20 contra 0.10), pero mucho menos que con datos (0.45–0.54).
  - Totales no agrega nada a "sin delitos", como se esperaba: el nivel de la ciudad no cambia qué calles son más riesgosas dentro de ella.
- **Siguiente:** la calificación principal (rutas con el buscador de la app) en las ciudades de práctica.

### v1: prueba principal de rutas (2,000 viajes por ciudad, buscador de la app)

Cambio en delitos del núcleo del futuro, ruta de menor riesgo contra la más rápida (IC95):

| Mapa | Cincinnati | Gainesville |
|---|---|---|
| Oráculo (techo) | −89% (−91 a −86) | −98% (−99 a −96) |
| **C** | **−32%** (−41 a −23) | **−72%** (−77 a −66) |
| **B** | (no disponible) | −67% (−73 a −61) |
| Mapa de calor amplio | (no disponible) | −66% (−71 a −60) |
| **A** | −23% (−33 a −12) | −66% (−72 a −59) |
| Mapa de calor del núcleo | −7% (−18 a +5) | −53% (−60 a −46) |
| Por zona | −31% (−42 a −18) | −39% (−50 a −25) |
| Totales | −13% (−27 a +4) | −47% (−56 a −36) |
| Sin delitos | 0% (−17 a +19) | −48% (−57 a −37) |
| Solo mapa | +2% (−12 a +18) | −52% (−61 a −42) |

Minutos extra (mediana): de 0.6 a 1.9 según el mapa.

- **Lectura:**
  - C es el mejor nivel en las dos ciudades, y las fórmulas con delitos superan al mapa de calor del mismo tipo de datos.
  - **Los resultados sin datos de delitos cambian muchísimo entre ciudades:** 0% en Cincinnati y alrededor de −50% en Gainesville, casi lo mismo que el mapa de calor del núcleo.
- **Sospecha a revisar:** en Gainesville los delitos violentos podrían concentrarse en las avenidas comerciales. Entonces cualquier mapa que aleje de las avenidas los evita. Hace falta una **línea base sin fórmula** del tipo "evitar avenidas y zonas comerciales", para saber si la fórmula sin delitos aporta algo más que eso.

## v2 (2026-10-05): lugares, horarios corregidos y comparaciones simples

- **Correcciones de datos**, válidas para todas las ciudades (ver bitácora de datos): día de referencia de los horarios, espacios invisibles en Gainesville, paradas sin hora. Se recalcularon los rasgos públicos de las 9 ciudades.
- **Rasgos nuevos:** escuelas, universidades, hospitales (sin clínicas), comisarías, gasolineras, estaciones de tren o metro, estadios y paradas de bus de los horarios oficiales.
- **Quedan fuera** porque están dibujados de forma muy despareja entre ciudades. Se decidió **solo con datos públicos, sin mirar delitos**:

| Rasgo | Por qué queda fuera |
|---|---|
| Edificios | Baton Rouge: 54 por 1,000 habitantes; las demás, 207–377 |
| Uso del suelo | Falta en el 43–89% de las calles |
| Cajeros | 1.4 a 42 por 100 mil |
| Tiendas de licor | 0 en Baton Rouge: en Luisiana el licor se vende en supermercados |

- **Comparaciones simples nuevas** (sin fórmula ni delitos): "evitar avenidas" (riesgo mayor cerca de avenidas) y "evitar comercios" (riesgo según los comercios a 400 m).
- **Medida secundaria nueva:** delitos por persona que pasa (peatones simulados).

### v2: prueba principal de rutas (2,000 viajes por ciudad)

Cambio en delitos del núcleo del futuro (ruta de menor riesgo contra la más rápida) y, aparte, **por persona** (delitos ÷ peatones simulados de cada tramo). IC95 entre paréntesis.

| Mapa | Cincinnati: delitos | Cincinnati: por persona | Gainesville: delitos | Gainesville: por persona |
|---|---|---|---|---|
| Oráculo | −89% | −79% | −98% | −94% |
| **C** | **−37%** (−46 a −28) | **−10%** (−28 a +12) | **−70%** (−75 a −64) | **−71%** (−84 a −55) |
| B | (no disponible) | | −69% (−74 a −63) | −62% (−81 a −39) |
| Mapa de calor amplio | (no disponible) | | −66% (−72 a −60) | −58% (−76 a −26) |
| A | −25% (−35 a −14) | +31% (+5 a +63) | −63% (−69 a −55) | −41% (−68 a −3) |
| Mapa de calor del núcleo | −7% (−18 a +5) | +94% (+54 a +144) | −53% (−60 a −46) | −43% (−70 a +3) |
| Por zona | −32% (−43 a −19) | +33% (−5 a +80) | −35% (−46 a −23) | −25% (−55 a +19) |
| Totales | −9% (−23 a +6) | +65% (+21 a +129) | −46% (−55 a −35) | −27% (−58 a +21) |
| Sin delitos | −15% (−27 a −1) | +40% (0 a +94) | −43% (−53 a −31) | −34% (−68 a +31) |
| Solo mapa | 0% (−12 a +16) | +51% (+14 a +100) | −46% (−56 a −35) | −48% (−75 a −14) |
| Regla: evitar comercios | −27% (−41 a −10) | −3% (−36 a +47) | −10% (−29 a +15) | −6% (−47 a +75) |
| Regla: evitar avenidas | −7% (−20 a +9) | +16% (−6 a +47) | −18% (−34 a −1) | +35% (−25 a +141) |

- **Lectura:**
  1. **C es el mejor nivel** en las dos ciudades, en delitos y por persona.
  2. **Sin delitos, la fórmula supera claramente a las reglas simples en Gainesville** (−43% contra −10% y −18%). En Cincinnati, la regla "evitar comercios" la iguala o supera (−27% contra −15%).
  3. **En Cincinnati, casi todos los mapas evitan delitos pero *aumentan* el riesgo por persona**. Las rutas dejan las calles con mucha gente (más delitos en total) y pasan por calles vacías (más riesgo para cada persona). Solo el nivel C no empeora. En Gainesville, las dos medidas van juntas.
  4. **v1 contra v2: diferencias dentro del ruido**, salvo Cincinnati sin delitos (de 0% a −15%), probablemente por los horarios corregidos y los lugares.
- **Ojo:** la medida por persona depende de los peatones simulados, validados con Spearman 0.67 en Nueva York, y del piso usado para las calles casi vacías. Es una medida secundaria.
