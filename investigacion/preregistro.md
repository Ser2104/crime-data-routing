# Pre-registro del examen de la fórmula v2

## Resumen en español (para ti)

**Qué es:** el documento que se sube a OSF, con fecha, **antes** de abrir la caja fuerte del examen principal (Filadelfia, Baton Rouge y Tempe). Dice exactamente:

- qué se prueba y con qué números se decide si funcionó;
- qué fórmula se prueba (la v2 sellada: sus huellas digitales están en `investigacion/sello_v2.json`);
- qué se hace si algo sale mal (lectura de los archivos, pruebas trampa).

Así nadie puede decir que se ajustó el análisis después de ver los resultados.

**Las preguntas, en simple:**

1. **H1.** Con datos de delitos del pasado (niveles B, A y C), ¿las rutas de la fórmula evitan delitos del futuro en ciudades que nunca vio?
2. **H2.** ¿La fórmula le gana (o al menos empata) a un simple mapa de calor hecho con los mismos datos?
3. **H3.** Sin ningún dato de delitos, ¿las rutas todavía evitan delitos? ¿Y le ganan a reglas simples como "evitar avenidas" o "evitar comercios"? En la práctica salió bien en Gainesville y mal en Cincinnati, así que es una pregunta abierta.
4. **Sin hipótesis, solo medir:** cuánto del beneficio del nivel B conserva cada nivel con menos información.

**Cuándo se sube:** después del sello (etiqueta `formula-v2-sellada` en git) y **antes** de abrir la caja. Lo subes tú desde tu cuenta de OSF, junto con `sello_v2.json`.

---

# Pre-registration: Transferring street-level pedestrian risk models to unseen cities across levels of crime-data availability

## 1. Study information

**Title.** Can a city with little or no crime data get safe pedestrian routes? A pre-registered leave-cities-out evaluation of street-level risk models across seven levels of data availability.

**Authors.** [Your name]. AI assistance (code and writing) will be disclosed in the paper.

**Research question.** A risk model is trained on four U.S. cities and sealed. In three U.S. cities it never saw, given only the crime information each "level" allows, does it choose pedestrian routes that avoid future violent crime? How much of the benefit survives as the crime information decreases, down to none?

**Hypotheses.** The primary metric is defined in §3.1. Each hypothesis is tested separately in each of the three exam cities. A hypothesis is supported for a level only if it holds in **all three** cities (intersection–union test, so no multiplicity correction is needed for the claim).

- **H1 (street-level crime data transfers).** For each of the levels B, A and C, lowest-risk routes reduce future core crimes relative to the fastest route. The upper bound of the 95% CI of the change is below 0%.
- **H2 (model vs. heat map of the same data).** The paired difference in route change is computed for model A vs. heat map A and for model B vs. heat map B (negative = the model avoids more).
  - **Non-inferiority:** the upper bound of the 95% CI is below +5 percentage points.
  - **Superiority:** the upper bound is below 0.
- **H3 (no crime data).**
  - **H3a:** the `sin_delitos` level reduces future core crimes (upper 95% CI bound below 0%).
  - **H3b:** in paired comparisons, `sin_delitos` beats each simple rule, "avoid arterials" and "avoid commercial areas" (upper 95% CI bound of the difference below 0).
  - Practice results were mixed (§4), so no direction is assumed. Both outcomes will be reported.
- **Estimands without hypotheses.**
  - Retention of the level-B benefit for each other level (change of the level ÷ change of B), with a 95% CI.
  - The per-person change (secondary metric).
  - The quick-capture score of every map.

## 2. Design

**Cities.** Groups were assigned by a lottery run on 2026-10-03 with the number 4818 (`investigacion/sorteo_ciudades.py`):

- **Learning:** Pittsburgh, Chapel Hill, Chicago, Seattle.
- **Practice:** Cincinnati, Gainesville.
- **Main exam (this registration):** Philadelphia PA, Baton Rouge LA, Tempe AZ.
- **External reserve** (Dallas, San Francisco, Boston, Colorado Springs) and **zone check** (Austin, Cambridge, Somerville, Los Angeles): **not opened** in this study.

**Holdout custody.** The crime data of every exam, reserve and zone city were handled as follows:

- Downloaded on 2026-10-03 directly into AES-256-GCM-encrypted files (scrypt key derivation), by a program committed to git before it ran (`investigacion/caja_fuerte.py`).
- No plaintext was ever written to disk.
- The passphrase is known only to the author and was never given to the AI system used for development.
- SHA-256 fingerprints of the original and the encrypted files are in `investigacion/caja_fuerte/manifiesto.json`.
- Development code is blocked from reading those files (`src/caja_cerrada.py`).
- The exam program can read only the opened main-exam folder.

**Periods** (all cities). Past: 2024-01-01 to 2025-08-31, which the maps may use. Future: 2025-09-01 to 2026-08-31, which is scored.

**Outcome: the universal core.** FBI violent crime without rape (`investigacion/reglas_de_datos.md`, v3):

- murder and non-negligent manslaughter (NIBRS 09A);
- robbery (120);
- aggravated assault (13A).

Each incident counts 1 (no severity weights).

**Translation of each exam city's categories.** Written on 2026-10-05 **before opening**, from official documentation only (`src/multiciudad/categorias.py`):

- **Philadelphia:** UCR hundreds (`ucr_general`); negligent and justifiable homicide are excluded from 09A.
- **Baton Rouge:** NIBRS code (`nibrs_code`). One incident per case: when a case has several charges, the most serious core class is kept.
- **Tempe:** generic keyword rules applied to `OffenseCustom`.

The times are the dispatch, report or call times that each city publishes.

**Exclusions** (identical in all cities, `src/multiciudad/preparar.py`): incidents that are

- without a valid date or location;
- sexual offenses;
- outside the city boundary;
- more than 50 m from a walkable street;
- less than 30 m from a prison, hospital, police station or social facility (OpenStreetMap).

**Levels: the information each map may use.**

| Level | Information |
|---|---|
| B | Detailed categories of past crime, street by street |
| A | Past core crime only, street by street |
| C | Past crime in three coarse bags (violent / property / other) |
| zona | Past core crime aggregated to Census block groups |
| totales | City-wide past core rate per 1,000 residents |
| sin_delitos | No crime data; all public features |
| solo_mapa | OpenStreetMap only |

Every level also uses public, nationally available features:

- the OpenStreetMap street network and places;
- Census population;
- LEHD jobs;
- GTFS transit;
- VIIRS night lights;
- simulated pedestrian volumes.

Crime features are relative to the city mean. The models do not use coordinates, identifiers or the city name. No race, income or poverty-proxy variables are used.

**Model under test.** Formula v2: one LightGBM model per level (Tweedie loss, 400 rounds), trained on the four learning cities with equal city weights. It is sealed as follows:

- the model files are in `models/multiciudad/v2/`;
- their SHA-256 fingerprints are in `investigacion/sello_v2.json`;
- the code is frozen at git tag `formula-v2-sellada`.

The exam program refuses to run if any fingerprint differs.

**Comparators.** None of these is a trained formula:

- **heat map A:** past core crime spread to nearby streets;
- **heat map B:** the detailed definition, spread the same way;
- **avoid arterials:** risk rises near main roads;
- **avoid commercial areas:** risk rises with the number of shops within 400 m;
- **oracle:** future core crime spread to nearby streets. This is an impossible ceiling, reported for scale only.

**Route simulation.** Uses the app's own router (`src/rutas.py`, via `src/multiciudad/evaluar_rutas.py`):

- 2,000 random walking trips per city, 500–3,000 m apart in a straight line;
- four hours (2 a.m., 9 a.m., 3 p.m., 9 p.m.);
- seed `crc32("viajes-<city>")`.

For each trip, the router returns the fastest route and the lowest-risk route under each map.

## 3. Analysis plan

### 3.1 Metrics

- **Primary: route change.** Total future core crimes on the street segments of the lowest-risk routes ÷ the same total on the fastest routes − 1, over trips where both routes exist. The 95% CI comes from a bootstrap of trips (2,000 resamples).
- **Paired comparisons** (H2, H3b, retention): the same trips and the same bootstrap resamples for both maps.
- **Secondary.**
  - **Per-person change:** crimes ÷ simulated pedestrians on each segment, with a floor at the median of segments with pedestrians.
  - **Median extra minutes.**
  - **Quick capture:** the share of future core crimes in the top 10% of network length ranked by the map, averaged over four time bands. Its 95% CI comes from resampling 1-km zones (300 resamples); paired differences resample the same zones.

Bootstrap seeds are `crc32("examen-<city>")`.

### 3.2 Reading check (before any score)

The exam program first reads all three cities and checks only the file format:

| Check | Minimum share of records |
|---|---|
| Valid date | 90% |
| Valid location | 70% |
| Recognized category | 30% |

At least one core incident must also fall in the period.

If any city fails:

- the program stops before computing **any** result;
- only the file reader may be fixed, never the formula, the models or the category tables;
- the fix is logged as a deviation and the program is run again.

### 3.3 Leakage traps

Each trap passes if it scores closer to chance than to the real map:

1. **Shuffled map:** the best level's values are permuted among street segments within each time band. Quick capture must be ≤ the midpoint between 0.10 and the real score. The route reduction must be less than half of the real reduction.
2. **Shuffled future:** future crimes are permuted among segments within each time band and scored against the real map. Quick capture must be ≤ the midpoint between its chance level and the real score. The chance level is the share of segments in the top 10%.

The original protocol planned a "wrong city" trap: one city's predictions scored against another city's crimes. That trap is infeasible because the cities' street segments differ. It was replaced by trap 2 before opening (`protocolo.md`, change of 2026-10-05).

If a trap fails, that city's exam is declared invalid, the cause is investigated, and all of this is reported.

### 3.4 Reporting

- Every level, every comparator, every city and every metric is reported, whatever the result. Nothing is selected afterwards.
- The category translation is not changed after opening. The report gives, per city, the number of unrecognized records and every exclusion count.
- Any analysis not described here is labeled **exploratory**. Examples: a corrected category table, or a different time window.

### 3.5 Precision

The cities were fixed by the lottery, so no sample size can be chosen. The authors did not look at the exam cities' crime volumes.

In practice cities, the 95% CIs of the route change were about ±6 percentage points in Gainesville and about ±9 in Cincinnati. Precision in the exam cities will be reported as observed.

## 4. Already observed before registration

**Learning and practice cities.** All results; four practice iterations of the formula (v0, v0.1, v1, v2) are logged in `investigacion/registro_practica.md`. Practice v2 route changes:

| Level | Cincinnati | Gainesville |
|---|---|---|
| C | −37% | −70% |
| A | −25% | −63% |
| sin_delitos | −15% | −43% |
| Rule "avoid commercial areas" | −27% | −10% |

Level B was not available for Cincinnati.

**Exam cities, observed:**

- public data only (OpenStreetMap, Census, LEHD, GTFS, VIIRS), used to compute features;
- the metadata of their crime datasets: column names and the earliest and latest dates, before the lottery;
- the column names again on 2026-10-05, to write the file readers.

**Exam cities, not observed:**

- no crime record, count or file size;
- no crime ranking, crime map, news or crime-related 311 data.

## 5. Out of scope

- **State College** (application city): registered separately before its Right-to-Know data are opened.
- **External reserve:** kept for a later, improved version (`protocolo.md`, point 3.8).
