# Evaluation protocol (version 1, October 3, 2026; changes logged at the end)

> **English translation** of `investigacion/protocolo.md`, prepared on 2026-10-08 for the OSF registration. The Spanish original is the sealed document (its SHA-256 is in `sello_v2.json`) and prevails in case of doubt. Translator's notes are in [brackets].

Rules fixed **before the lottery** of cities. Any change to this protocol is logged at the end, with date and reason.

## 1. City groups

| Group | Cities | Purpose | When their crimes are looked at |
|---|---|---|---|
| **Learning** | Pittsburgh (fixed), Chapel Hill, Chicago, Seattle | Build the formula | Always |
| **Practice** | Cincinnati, Gainesville | Test and improve the formula | Many times |
| **Main exam** | Philadelphia (large), Baton Rouge (medium), Tempe (university) | The score of a sealed version | **Only once** |
| **External reserve** (*external holdout*) | Dallas, San Francisco, Boston, Colorado Springs | Clean test of **one** version (see point 3) | **Only once in total** |
| **Zone level** | Austin, Cambridge, Somerville, Los Angeles | Extra check at the zone level | **Only once in total** |
| **Real application** | State College | Use of the formula without public crime data | Its data (Right-to-Know request) are treated as an exam: once, with a sealed version |

**Lottery:** run on 2026-10-03 at 11:44 with the number **4818**, chosen by the author.

- Command: `python investigacion/sorteo_ciudades.py 4818` (Python 3.13.3). Run twice, same result.
- Up to that moment, only the description of the exam cities' datasets had been reviewed (column names and earliest and latest dates). **No crime record.**

## 2. Vault and seal

- The crime data of the main-exam, external-reserve and zone-level cities are downloaded **directly into the vault** (encrypted), without looking at them. The fingerprint (SHA-256) and date of each file are recorded.
- The program that builds the formula **cannot read** the vault, and an automatic check stops it if it tries.
- The formula uses only general features: never street names, coordinates or the identity of the city.
- Before opening any exam, the version of the formula is **sealed**: the file is saved, its fingerprint is published with a date, and the code is frozen with a git tag.

## 3. Versions of the formula: each exam group is a "one-shot bullet"

1. **The first sealed version** is applied **only once** to the **main exam**. It is **v2**: the practice iterations were called v0, v0.1, v1 and v2, and none of them touched the exam. In the following points, "v1" means this first sealed version. Its result is **the main result** and is reported as is, good or bad.
2. **If v1 is modified** (features, parameters, rules, training data), **v2** is born [i.e., a new version]. It is documented in the version registry: what changed, why, and the date. The results of v1 **are neither deleted nor replaced**.
3. **If the external reserve was never opened**, v2 may use it as a clean exam, only once.
4. **If the reserve was already opened with v1**, it is no longer a clean exam for v2: **new, never-seen cities** would be needed.
5. **A city whose result has been seen** (even a single summary number) may later be used for development or learning, but **never again as an independent test**.
6. **The same applies to State College:** once the Right-to-Know crime records are opened, they are no longer a clean exam.
7. **One shot can evaluate several formulas at once**, as long as all were sealed **before** opening. Thus, the formulas of levels 1 to 5 are sealed together and evaluated together in a single opening of the main exam. [Note: "levels 1 to 5" is the earlier naming; since data rules v2 they are the seven levels B, A, C, zona, totales, sin_delitos, solo_mapa.]
8. **Strategy:** since clean cities are few, the reserve **is not opened for v1** unless v1 is declared the final version. If there are improvements after the main exam, the reserve is kept for the improved version.

### Sealing of the exam data (done)

- **2026-10-03, from 22:35 to 22:49 UTC:** the author sealed the 11 cities of `holdout_main`, `holdout_reserve` and `holdout_zona` with `investigacion/caja_fuerte.py` (commit `fa14800`, saved in git **before** running it).
  - The author ran it in their own terminal, with a passphrase only the author knows.
  - All 11 passed the immediate verification without showing any content.
- **Public record:** `investigacion/caja_fuerte/manifiesto.json`, with city, source, date, SHA-256 fingerprints of the original and the encrypted file, salt and IV, and the program's commit. **It does not record file sizes.**
- **Not analyzed:** neither the size of the encrypted files nor the time each download took (the difference between the times in the manifest), because both depend indirectly on how many crimes there are.
- Only the `.enc` files exist on disk. No readable copy was ever written.

**Statement for the paper:**

> The holdout datasets were downloaded and encrypted (AES-256-GCM, scrypt key derivation) by a program executed locally by the author on 2026-10-03; the program was committed to version control before execution, no plaintext copy was written to disk, and the passphrase was never provided to the system used to develop the models. Before the city lottery, only dataset metadata (column names and earliest/latest dates) was inspected; no incident records of holdout cities were inspected before the formulas were frozen.

## 4. Leakage traps (in every exam)

- **Shuffled map:** the values of the best level are randomly shuffled among streets (within each time band).
  - Its quick score must be closer to chance (0.10) than to the real map.
  - On routes, it must avoid less than half of what the real map avoids.
- **Shuffled future:** future crimes are randomly shuffled among streets and scored with the real map. Its quick score must be closer to chance than to the real map. Here, chance is the share of streets that fall in the marked 10%.

If either one "succeeds", there was a leak: that city's exam is declared invalid, investigated and reported.

The **wrong city** trap (one city's prediction against another city's crimes) was replaced by the shuffled-future trap **before opening**. It cannot be done properly, because each city has different streets and there is no way to overlay one on the other.

## 5. Who runs the exams

The exam is run by a separate program that **learns nothing**: `src/multiciudad/09_examen.py`. It only receives the sealed formula and the vault. The author runs it, in their own terminal:

1. `python investigacion/caja_fuerte.py abrir holdout_main --motivo "examen formula v2"` (asks for the passphrase). ["abrir" = open; "motivo" = reason.]
2. `python src/multiciudad/09_examen.py`.
   - First, it checks the model fingerprints against `sello_v2.json`.
   - Then it runs the **reading check**: readable dates, coordinates and categories, with the minimums of the pre-registration.
   - If reading fails, it stops **without computing any result**. Only the file reader is fixed (never the formula or the category tables), the fix is logged as a deviation, and it is run again.
   - Only then does it score.
3. The results are saved in `investigacion/resultados/examen_v2/` and are all reported, as they are.

## Version registry

| Version | Seal date | Fingerprint | What changed | Evaluated on |
|---|---|---|---|---|
| v2 | 2026-10-05 | `investigacion/sello_v2.json` (SHA-256 of the 14 files in `models/multiciudad/v2/`), git tag `formula-v2-sellada` | First sealed version: public features + OSM places + corrected transit schedules; learns from Pittsburgh, Chapel Hill, Chicago and Seattle (see `registro_practica.md`) | Main exam (pending) |

## Changes to this protocol

- 2026-10-03: the reserve is not called a "second exam" but an external reserve (*external holdout*), tied to the version it evaluates (point 3). Proposed by the author.
- 2026-10-03: each exam group is a "one-shot bullet" in total, not one per version (points 3.3 to 3.6). Points 3.7 (one shot can evaluate several formulas sealed together) and 3.8 (reserve strategy) are added. Proposed by the author.
- 2026-10-05, before sealing v2 and before opening any exam:
  - the first sealed version is called v2, because of the practice names (point 3.1);
  - the "wrong city" trap is replaced by the "shuffled future" trap, and numeric criteria for the traps are fixed (section 4);
  - the exam program is named and the reading check is added (section 5).
