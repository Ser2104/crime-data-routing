# Pre-registro del examen de reemplazo de Tempe

## Resumen en español (para ti)

**Qué es:** el plan del examen de reemplazo de Tempe, que se sube a OSF **antes** de abrir sus datos nuevos. Es un registro **nuevo y aparte**. El original (https://osf.io/x3z9s) no se modifica.

**Por qué existe:** en el examen principal, la caja fuerte recibió de ArcGIS Hub una copia **desactualizada** de los delitos de Tempe. Terminaba en junio de 2024, y el servicio oficial llega hasta octubre de 2026. Por eso Tempe no se pudo evaluar, y **nadie ha visto ningún resultado de Tempe del año calificado**.

**Qué se hace:**
1. Se descargan los datos de Tempe **directo del servicio oficial**, cifrados y sellados.
2. Se aplica la **misma fórmula v2**, sin cambiar nada: modelos, semillas, reglas y tablas de categorías.
3. Se abre **una sola vez** y se califica con los mismos criterios.

**Lo que se corrigió antes de registrar, sin tocar la fórmula:**
- la hora de Tempe se usa tal como viene, porque es hora local;
- el chequeo de lectura exige registros en todos los meses del estudio;
- las pruebas trampa tienen una aclaración para cuando el mapa real no supera al azar. La encontró el simulacro con datos inventados; con un mapa real fuerte, la regla es la misma de antes;
- se precisan otras reglas (N.A., retención, semillas) que podían interpretarse mal.

Todo se probó de punta a punta con un **simulacro con datos inventados** antes de registrar.

---

# Pre-registration: Replacement exam for Tempe, AZ (frozen formula v2)

## 1. Background and reason

This registration complements the pre-registration of the main exam, https://osf.io/x3z9s (2026-10-08). That registration is not modified.

**What happened in the main exam.** The main exam (Philadelphia, Baton Rouge, Tempe) was opened once on 2026-10-08.
- Tempe's encrypted file was a **stale pregenerated ArcGIS Hub export**: its last record is dated 2024-06-29.
- The live official service holds records through 2026-10 (min/max query on 2026-10-08: 1900-06-10 to 2026-10-07; the same minimum as the export).
- The scored future period (2025-09-01 to 2026-08-31) therefore had **no records**, and Tempe was declared **not evaluable** (`investigacion/desviaciones_examen_v2.md`).
- **No result of Tempe containing future-period information was ever observed,** because none could exist with that file.

**What was observed about Tempe** in that run: the format and coverage check of the stale file (12,445 records and 383 core incidents in 2024-01 to 2024-06), and the date and hour columns of that file (used to diagnose coverage and time format).

**What was observed in the other two cities:** the results of Philadelphia and Baton Rouge (`informes/cambios/2026-10-08_examen_v2.md`).

## 2. Hypotheses

The same hypotheses, metrics and decision rules as the main registration are applied to **Tempe alone**:

- **H1:** levels B, A and C each reduce future core crimes on lowest-risk routes vs. fastest routes. The upper 95% CI bound of the route change must be below 0%.
- **H2:** model A (B) vs. heat map A (B), paired difference in route change.
  - **Non-inferiority:** upper 95% CI bound below +5 percentage points.
  - **Superiority:** upper bound below 0.
- **H3a:** the "sin_delitos" level reduces future core crimes (upper bound below 0%).
- **H3b:** "sin_delitos" beats "avoid arterials" and, separately, "avoid commercial areas" (upper bound of the paired difference below 0).
- **Estimands:** retention of B for each level, the per-person change and the quick capture.

**Link to the original three-city criterion.** The original registration required support in all three cities. Philadelphia and Baton Rouge are already observed: H1 and H2 (non-inferiority) held in both; H3a failed in Philadelphia; H3b held vs. "avoid arterials" and failed vs. "avoid commercial areas" in both. Therefore:
- the original criterion **can no longer be met** for H3a and for H3b vs. "avoid commercial areas";
- for H1, H2 and H3b vs. "avoid arterials", it now depends only on Tempe.

We will report the combined three-city result as an **assessment completed with a replacement download** (a documented deviation), never as the original confirmatory test. The primary result of this registration is the Tempe result itself.

## 3. Design (identical to the main exam unless stated)

- **Model:** formula v2, unchanged.
  - The exam program checks the models against the original seal, `investigacion/sello_v2.json`.
  - The code for this exam is fingerprinted in `investigacion/sello_v2_tempe.json` (git tag `examen-tempe-v2-sellado-r2`).
- **Data:** Tempe "General Offenses (Open Data)".
  - **Download:** directly from the official ArcGIS FeatureServer (layer 0), by pages ordered by OBJECTID, straight into an AES-256-GCM-encrypted file (vault group `holdout_tempe2`).
  - **Checks before sealing:** that the data cover 2024-01-01 to 2026-08-31, and that every record the server reports was downloaded. Only OK or REVISAR is printed, never dates or counts.
  - **Fingerprints:** in `investigacion/caja_fuerte/manifiesto.json`.
- **Periods:** past 2024-01-01 to 2025-08-31; future 2025-09-01 to 2026-08-31.
- **Outcome, exclusions and category translation:** unchanged. The universal core is NIBRS 09A, 120 and 13A; the exclusion rules are the same; Tempe's keyword table is the one written on 2026-10-05.
- **Public features of Tempe:** unchanged; computed before the main exam.
- **Trips and seeds:** 2,000 trips, seed `crc32("viajes-tempe")`; bootstrap seed `crc32("examen-tempe")`.
- **Maps:** 7 levels, 5 comparators, 1 shuffled-map trap; plus the shuffled-future trap.

**Changes made before this registration, all in reading or checking, never in the model:**
1. **Time of Tempe's records.** `OccurrenceDatetime` is published with a "+00" label, but it is local time: on the stale file it matched Tempe's own year, month, day and hour columns in 100% of records. It is now used as is. Previously it was converted to Arizona time, which shifted the date of about 21% of records by one day. If it is missing, the record is rebuilt from Tempe's year, month, day and hour columns. (`OccurrenceDatePart` is the day of the month, not a date.)
2. **Coverage in the reading check.** Every month from 2024-01 to 2026-08 must have at least one record, or the program stops before computing any result.
3. **Download.** The vault now downloads directly from the service, with the coverage and completeness checks described above.
4. **Code robustness.** A map with no lowest-risk route is recorded as N.A. This was already applied, and documented, in the main exam.
5. **Leakage-trap rule clarified** (details in section 4). A dry run with synthetic data showed that the original rule can declare a perfect trap a "leak" when the real map itself is at chance level. The rule is unchanged whenever the real map beats chance, which was the case for every trap in Philadelphia and Baton Rouge: the verdicts there are identical under both versions.
6. **Dry run.** The whole exam program was run end to end on a synthetic Tempe file with the exact format of the new download (`investigacion/simulacro_tempe.py`). No real exam data were involved and the sealed code was called unchanged. Results on synthetic data are meaningless by construction and were used only to check that everything runs.

## 4. Analysis plan

The analysis is the same as in the main registration (osf.io/x3z9s), stated here in full with the clarifications decided before this registration.

**Uncertainty (bootstrap):**
- **Route change and per-person change of each map:** 2,000 resamples of trips. The random seed is fixed at 1 in `evaluar_rutas.calificar`. The main registration stated "CRC32 of examen-city" for this step; that text was wrong, and the code used seed 1 there too (a documentation error recorded as a deviation of the main exam).
- **Paired comparisons and retention:** 2,000 resamples of the same trips for both maps, with seed CRC32 of "examen-tempe".
- **Quick capture and paired quick-capture differences:** 300 resamples of 1-km zones, with seed CRC32 of "examen-tempe".

**Decision rules** (95% CIs read one-sided; no p-values):
- **H1:** supported for a level if the upper bound of the 95% CI of its route change is below 0%. A level whose route result is N.A. (no trip with a lowest-risk route) does **not** support H1.
- **H2:** non-inferiority if the upper bound of the paired difference is below +5 percentage points; superiority if it is below 0. If either map is N.A., H2 is not supported.
- **H3a:** as H1, for sin_delitos.
- **H3b:** superiority if the upper bound of the paired difference is below 0, tested separately vs. "avoid arterials" and "avoid commercial areas". If either map is N.A., H3b is not supported.
- **Retention of B:** reported, but **interpreted only if level B reduces crimes** (upper bound of B's route-change CI below 0). Otherwise it is reported as not interpretable, because a ratio over a non-reduction has no meaning.

**Positive control (oracle):** if the oracle does not reduce future core crimes (upper 95% CI bound at or above 0%), **or its route result is N.A.**, the pipeline is investigated before any interpretation.

**Negative controls (leakage traps)** — "real map" means level B:
- **Quick capture, shuffled map** (chance level = 0.10) and **shuffled future** (chance level = the share of street segments in the riskiest 10%):
  - If the real map beats chance (the lower bound of its quick-capture 95% CI is above the chance level), the trap passes if its value is at most the midpoint between the chance level and the real score. This is the original rule.
  - Otherwise, the trap passes if it is compatible with chance: the lower bound of its 95% CI is at or below the chance level.
- **Routes, shuffled map:**
  - If the real map reduces crimes (upper bound of its 95% CI below 0), the trap passes if its route change is above half of the real change, i.e., it avoids less than half of what the real map avoids. This is the original rule.
  - Otherwise, the trap passes if it shows no clear reduction: the upper bound of its 95% CI is at or above 0.
- **If any trap fails,** the exam is declared invalid, investigated and reported.

The exam program computes these verdicts and writes them in `tempe_trampas.json`.

**Reporting:** all maps and metrics, whatever the results.

## 5. Single opening

The `holdout_tempe2` group is opened once (logged in `investigacion/caja_fuerte/aperturas.json`) and the program runs to completion. If the reading check fails, only the reader may be fixed, and the fix is reported as a deviation.
