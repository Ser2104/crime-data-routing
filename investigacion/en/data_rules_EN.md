# Data rules by level (version 3, October 5, 2026)

> **English translation** of `investigacion/reglas_de_datos.md`, prepared on 2026-10-08 for the OSF registration. The Spanish original is the sealed document (its SHA-256 is in `sello_v2.json`) and prevails in case of doubt. Translator's notes are in [brackets]. Where this document and the registration differ, see `attachments_guide_EN.md`, section "Precedence and known differences".

These rules are fixed **before** developing the formula. They are the same for all cities. Any change is logged at the end with date and reason, and if it comes after a version of the formula has been sealed, it creates a new version (`protocolo.md`, point 3).

**Central idea:** what is **scored** (future crimes) is **the same in every city and every level**. What changes by level is **which past information** the formula may use.

## 1. Periods (same for all cities)

- **Past** (what may be used to build a city's map): 2024-01-01 to 2025-08-31.
- **Future** (what is scored): 2025-09-01 to 2026-08-31.

## 2. What is scored: the universal core

**Primary measure:** number of **universal core** crimes in the future. It is the FBI definition of violent crime, without rape:

| Class | NIBRS code | Includes |
|---|---|---|
| `homicidio` (homicide) | 09A | Murder and non-negligent manslaughter |
| `robo` (robbery) | 120 | Robbery with violence or threat (mugging) |
| `agresion_grave` (aggravated assault) | 13A | Aggravated assault (with a weapon or serious injury) |

- **No severity weights.** Each crime counts 1. This way the measure does not depend on details, such as weapon type, that not all cities publish.
- **Time:** the time of **occurrence** if the city publishes it; otherwise, the time of the report. Which one was used is recorded.
- **Secondary measure** (only in cities that allow separating categories; **reported separately and never compared across cities with a different definition**): Pittsburgh's broad definition, which adds simple assault, threats, weapons, purse-snatching, pocket-picking, kidnapping and drugs.

**Translation of each city's categories** (file `src/multiciudad/categorias.py`):

- by **standard codes** (NIBRS or UCR) when the city publishes them;
- otherwise, by the **category name**;
- for exam cities, the table is written **before opening**, using only the city's official data dictionary (its documents), never its records;
- anything not in the table is excluded, and the report says how many cases there were.

**Excluded in all cities** (only rules that can be applied equally everywhere):

- crimes without a location;
- sexual offenses (Pittsburgh hides their location for privacy; same rule for all);
- crimes outside the city boundary or more than 50 m from a walkable street;
- crimes less than 30 m from prisons, hospitals, police stations or social-service centers (from OpenStreetMap).

The "domestic violence" flag is **not** used to exclude in the primary measure, because not all cities publish it.

**Location:** as published by the city. Locations rounded to the block are accepted.

## 3. What past information the formula may use

All formulas may use **what was learned in the "learning" cities**, with all their information. What changes by level is which data **of the evaluated city**, and **only from the past**, may enter:

| Level | Past crimes of the evaluated city | Public data of the evaluated city |
|---|---|---|
| **B: Detailed** | All crimes, with location and their broad category (section 2) | All allowed data (section 4) |
| **A: Core only** | Only universal-core crimes, with location | All allowed data |
| **C: Coarse** | All crimes, with location, but only in three bags: `violento` (violent: the core plus violent crimes without detail; rape is excluded in all cities), `propiedad` (property: theft, vehicle theft, burglary, arson) and `otro` (everything else) | All allowed data |
| **Zone (zona)** | Core counts by **Census block group** | All allowed data |
| **Totals (totales)** | Only the **city total** of the core, by month (like what is reported to the FBI) | All allowed data |
| **No crimes (sin_delitos)** | **None** | All allowed data |
| **Map only (solo_mapa)** | **None** | **OpenStreetMap only** (streets, places, mapped street lamps) |

- **A and C are branches, not steps:** A has the exact category but fewer cases; C has all cases but mixed. Comparing B with A and C answers: **how much does knowing about past minor crimes help predict violent ones?**
- **B is each city's reference:** "the best with all of that city's data". The result of the other levels is expressed as a **percentage of B's benefit in the same city**.
- **Level C can be simulated in any city** by grouping its categories. Cincinnati, which publishes this way, is a real case of C.

## 4. Allowed public data

| Data | Detail |
|---|---|
| OpenStreetMap | Streets, shops, parking, parks, mapped street lamps, buildings (Geofabrik extracts). Since version 3: schools, universities, hospitals, police stations, gas stations, liquor stores, ATMs, train or metro stations, stadiums, land use (residential, commercial, industrial) and building density |
| 2020 Census population | **Block totals only** |
| LEHD LODES jobs | **Block totals only** (C000) |
| Transit schedules | GTFS (buses per hour and nearby stops; stops come from official schedules, not OpenStreetMap, except at the "map only" level) |
| Light | VIIRS satellite (NASA) and official street-lamp inventories |
| Simulated pedestrians | `src/peatones.py`, which uses only the above |
| 311 | **Only categories unrelated to crime** (street lamps, potholes…) |

[Note: "allowed" does not mean "used". Formula v2 excludes some allowed OSM features (buildings, land use, ATMs, liquor stores) because they are mapped very unevenly across cities; see `registro_practica.md`, v2.]

## 5. Forbidden (at every level)

- **Race, ethnicity, income or poverty**, from any source. Also places that mainly indicate poverty: pawn shops, payday loans and check cashing, shelters and social-service centers (the latter are used only to exclude crimes that occurred next to them, section 2). Also no victim or suspect data (age, race, gender); they are not even downloaded when this can be avoided.
- **Any data derived from crimes** of the evaluated city, except what its level allows in the table of section 3. This includes:
  - FBI totals (they are information of the "Totals" level);
  - crime maps, neighborhood rankings and news;
  - crime-related 311 categories (for example "drug activity").
- **As formula features:** street or neighborhood names, coordinates, segment identifiers and the identity of the city.
- **Manual adjustments for a particular city or neighborhood.** The formula is the same for all and is built only with code.
- **Using exam data** (vault) for anything before the registered opening.

## 6. How scoring works (same in every city and level)

- **Trips:** 2,000 random walking trips per city, 500 to 3,000 m in a straight line, at 2 a.m., 9 a.m., 3 p.m. and 9 p.m. Each city's seed is fixed before opening.
- **Primary measure:** change in **universal core** crimes of the **future** on the streets of the lowest-risk route, versus the fastest, with its 95% confidence interval (bootstrap).
- **Secondary measures:**
  - share of future core crimes that fall in the 10% of the network marked as riskiest;
  - whether the displayed % is met (calibration);
  - the broad measure (section 2), only where it exists and reported separately.
- **Cities with few cases:** before opening the exam, it is computed whether each city has enough cases for a conclusion. If any does not, it is declared in advance that its result is combined with that of other cities (joint result), and it is not interpreted alone.
- **Leakage traps** (`protocolo.md`, point 4).

## Changes to these rules

- **2026-10-05 (version 3), requested by the author.** OpenStreetMap place features are added: schools, universities, hospitals, police stations, gas stations, liquor stores, ATMs, train or metro stations, stadiums, land use and building density. Bus stops now come from official schedules (in Philadelphia they are barely mapped in OpenStreetMap). The city rate ("totals" level) is computed with the population inside the boundary, not with the 1-km margin.
  - Places that mainly indicate poverty are explicitly forbidden.
  - Surveillance cameras do **not** enter as a feature: they are mapped very unevenly across cities. They are studied separately.
  - No formula was sealed. Previous versions (v0 to v1) remain in the practice log.
- **2026-10-04 (version 2), proposed by the author.** What is **scored** is separated from what the formula **may use**:
  - The primary measure becomes the **universal core** (homicide, robbery, aggravated assault, unweighted) in all cities.
  - Levels are reorganized into a ladder according to past crime information: B, A, C, zone, totals, no crimes and map only. The former levels 1 to 5 correspond to B, zone, totals, no crimes and map only.
  - Sexual offenses are excluded in all cities. Domestic violence is no longer used to exclude. Downloading victim or suspect data is also forbidden when it can be avoided.
  - **Reason:** in the development cities, categories vary a lot. Cincinnati (practice) mixes simple assaults, weapons and drugs in a single bag ("Part 2"), and Chapel Hill (learning) uses about 1,900 free-text names. Scoring with different definitions would make the comparison unfair.
  - No data from the exam cities was used for this change, and no formula was sealed.
- **2026-10-04 (version 2).** The "concentrated points" rule (10 or more crimes at the same coordinate) is removed, and "outside the city" and "more than 50 m from a street" are added, as in Pittsburgh.
  - **Reason:** each city publishes locations with different precision. Seattle rounds them to the block center (14% unique coordinates): the rule would delete 29% of its violent crimes, which are real. Cincinnati jitters each point (93% unique coordinates) and would never trigger it.
  - What the rule was meant to catch (hidden institutions) is already covered by the OpenStreetMap institutions rule, the same for all.
  - Measured only in development cities.
- **2026-10-04 (minor correction, version 2).** The `violento` bag of level C no longer says "core + rape", because rape is excluded in all cities. It is now the core plus violent crimes without detail (for example, Cincinnati's "Part 1 Violent").
