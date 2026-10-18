# Deviations of the formula v2 exam (English)

> **English translation** of `investigacion/desviaciones_examen_v2.md`, prepared on 2026-10-08 for the OSF registration of the Tempe replacement exam. The Spanish original prevails in case of doubt.

This is a record of everything that did not go as planned in the pre-registration (https://osf.io/x3z9s/overview, 2026-10-08), each with date, reason and effect. It was written **before looking at any Tempe result** and before interpreting the results of Philadelphia and Baton Rouge.

- **Vault opening:** once, on 2026-10-08 at 07:08 UTC (`investigacion/caja_fuerte/aperturas.json`, commit `e75e2af`). It was not reopened. Everything below uses only the data left in `data/examen_abierto/holdout_main/`.

## Deviation 1 (post-seal, code): a map with no "Lowest risk" route is recorded as N.A.

- **What happened:** the exam program stopped with an error (`KeyError: ['Lowest risk']`) when comparing routes in Tempe. With the **oracle** map, the router returned no "Lowest risk" route in any of the 2,000 trips, only "Fastest" and "Alternate route". Only the route types were inspected to establish this, not the results.
- **Fix:** in `src/multiciudad/09_examen.py`, if a map has no trip with both routes, its route result and its paired comparisons are recorded as **"N.A." (not available)** instead of stopping the program. This is what the pre-registration already states ("Missing data": *trips where the router does not return both routes are dropped… reported as not available*); the code had a bug in applying it.
- **What does NOT change:** the models (their fingerprints are still those in `sello_v2.json`), the category tables, the rules, the seeds and the results already computed for Philadelphia and Baton Rouge. Both cities had finished all 13 maps before the error, and their routes are reused as is from the saved files.
- **Verification:** a test with invented trips. A map with no "Lowest risk" route gives N.A., and a normal map gives the same result as before. The rerun of Philadelphia and Baton Rouge reproduced the first run byte for byte.

## Deviation 2: Tempe is not evaluable because of insufficient coverage

- **Signal:** Tempe's reading check passed the minimums, but only 12,445 of its 317,766 records fell in the study period (2024-01-01 to 2026-08-31), with 383 core incidents. Then Tempe's oracle produced no lowest-risk route. The pre-registration requires investigating the city in that case ("Positive control").
- **Investigation:** temporal coverage only. Only the date columns of Tempe's file were read (`OccurrenceDatetime`, `OccurrenceYear`, `OccurrenceMonth`, `OccurrenceDatePart`), with no locations, categories, maps or results.
  - **The file ends on 2024-06-29.** Two independent readings confirm it: the exam reader and Tempe's own year and month columns. There is no record after June 2024.
  - **Monthly counts are normal until the end:** about 2,000–2,300 per month from 2013 to May 2024, and 1,322 in June 2024, an incomplete month.
  - **Of the study period,** Tempe has only January to June 2024 (6 of the 20 "past" months) and **no record of the "future"** (2025-09-01 to 2026-08-31), which is what is scored.
- **Decision** (mechanical rule set by the author on 2026-10-08, before seeing any Tempe result): **Tempe is not evaluable in this exam because of insufficient coverage.** The study period is not changed to "save" the city.
- **Consequences:**
  - Hypotheses H1, H2 and H3 required support in all three cities, so they **cannot be confirmed**. This is reported as such.
  - Philadelphia and Baton Rouge are reported normally, city by city, as the pre-registration requires.
  - Tempe's partial files, computed before the error, were moved without being opened to `investigacion/resultados/examen_v2/tempe_no_evaluable/`. They are not interpreted.
- **Why it was not detected earlier** (corrected on 2026-10-08):
  - **Before the lottery,** the metadata review queried Tempe's **official service** (FeatureServer) directly and obtained `OccurrenceDatetime: 1900-06-10 to 2026-10-03`. The service **did have data through October 2026**.
  - **The vault** downloaded through the **ArcGIS Hub** link (`hub.arcgis.com/api/v3/datasets/.../downloads/data`), which serves a **pregenerated copy** of the file. That copy was **outdated**: it ends on 2024-06-29. Both are the same dataset, since the earliest date matches (1900-06-10).
  - **Cause:** neither Tempe stopping publication nor a reader error. It was a **stale download** from the chosen channel (Hub instead of the live service). The reading check did not catch it because it only checked that dates were readable, not that they covered the period.
  - **Effect on the decision:** none for this exam. The sealed and opened file does not contain the scored period, and it cannot be replaced by a file downloaded after opening without breaking the protocol.
  - **What was never observed:** a Tempe result. Its file had no future crimes, so no Tempe result contains information about the scored period. One past figure was observed: 383 core incidents from January to June 2024, in the reading check.
  - **Lessons:**
    1. Always download from the live service, not from pregenerated copies.
    2. Before sealing, compare the service's maximum date with the downloaded file's (metadata only, without reading records).
    3. Add a minimum of **future-period coverage** to the reading check.
    4. Review the external reserve's sources with the same criterion before using it, especially Boston, which was also downloaded as a static file.
- **Note on Tempe's reader:** `OccurrenceDatePart` turned out to be the **day of the month** (1–31), not a full date, so the reader in practice used its fallback, `OccurrenceDatetime` converted to Arizona time. A later check (see the follow-up) showed that this conversion was itself wrong, because the value is already local time.

## Follow-up: replacement exam for Tempe (decided on 2026-10-08)

- **Author's decision:** repeat the exam **in Tempe only**, with the **same formula v2** and a direct download from the official service. The plan is `investigacion/preregistro_tempe.md`, registered on OSF as a new registration before opening.
- **Why Tempe and not another city:**
  - no Tempe result for the scored year ever existed;
  - Tempe was chosen by the original lottery;
  - its public features, reader and category table were written before opening.
- **Before sealing, only the reading and the checks change, never the formula:**
  1. **Tempe's time is used as is,** because it is local time. On the old file, `OccurrenceDatetime` matched Tempe's own year, month, day and hour columns in 100% of records. The previous conversion to Arizona time shifted the date of about 21% of records by one day.
  2. **The reading check requires coverage of every month** from 2024-01 to 2026-08.
  3. **The vault downloads directly from the service,** sealing only if the data cover the study period and every row was downloaded.
- **Status:**
  - The replacement data were sealed on 2026-10-08 at 20:17 UTC (vault group `holdout_tempe2`), with coverage OK and the download complete. The blind format check gave OK.
  - The exam code was sealed in `sello_v2_tempe.json` (tag `examen-tempe-v2-sellado-r2`), with the same model fingerprints as `sello_v2.json`.
- **The external reserve remains closed**, kept for v3.

## Deviation 3 (documentation): seed of the route confidence intervals

- **What happened:** the full review of 2026-10-08 found that the registration ("Statistical models") says the CIs of the **route change** use the seed "CRC32 of examen-city". The sealed code (`evaluar_rutas.calificar`, called without a seed from `09_examen.py`) uses a **fixed seed of 1** for that step, and likewise for the per-person change.
  - Paired comparisons, retention and quick capture **do** use "CRC32 of examen-city", as registered.
- **Effect:** none on validity. Seed 1 was fixed in the sealed code before opening, so it could not be chosen after seeing the data either. This is an error in the text, not in the analysis. It is reported as a deviation, and the Tempe registration already states the correct seed.

## Note: clarification of the leakage-trap rule (decided before the Tempe exam)

- **The problem:** the dry run on synthetic data showed that the rule "the trap must be closer to chance than to the real map" can flag a perfect trap as a "leak" when the real map itself is at chance level. The same happens on routes when the real map does not reduce crime.
- **The clarification:** in those cases, the trap is judged by whether it is compatible with chance (its confidence interval). When the real map beats chance, the original rule applies.
- **In Philadelphia and Baton Rouge, the verdicts are identical under both versions** (checked with their numbers): the real maps clearly beat chance and every trap passed.
