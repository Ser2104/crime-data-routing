# Guide to the attached files (English)

Prepared on 2026-10-08 for the OSF registration, **before** the exam data were opened.

The study was developed in Spanish, the author's working language. The registration form is in English. Three attached documents are sealed originals in Spanish; they cannot be edited, because their SHA-256 fingerprints are recorded in `sello_v2.json`. They are accompanied by English translations. In case of doubt, the Spanish original prevails.

## 1. Files

| File | Language | What it is |
|---|---|---|
| `preregistro.md` | English (with a short Spanish summary at the top) | Pre-registration text: hypotheses, metrics, decision rules. **Sealed.** |
| `protocolo.md` | Spanish | Evaluation protocol: city groups, lottery, vault, one-shot rule, leakage traps. **Sealed.** Translation: `protocol_EN.md`. |
| `reglas_de_datos.md` | Spanish | Data rules: periods, outcome, exclusions, levels, allowed and forbidden data. **Sealed.** Translation: `data_rules_EN.md`. |
| `sello_v2.json` | Spanish keys | The seal: SHA-256 fingerprints of the 14 model files and of the exam code and documents. |
| `formula_v2_modelos.zip` | — | The 7 sealed models (LightGBM text files + category lists). Their fingerprints must match `sello_v2.json`. |
| `manifiesto.json` | Spanish keys | Vault manifest: source and SHA-256 fingerprints (original and encrypted) of each holdout dataset, downloaded on 2026-10-03. |
| `protocol_EN.md`, `data_rules_EN.md` | English | Translations of the two Spanish documents. |

## 2. Glossary of Spanish terms in the JSON files

**`sello_v2.json`** (the seal):

| Key | Meaning |
|---|---|
| `version` | Formula version |
| `fecha_utc` | Date and time of sealing (UTC) |
| `commit` | Git commit at sealing time; the tag `formula-v2-sellada` points to the commit that adds this file |
| `carpeta_modelos` | Model folder |
| `huellas` | SHA-256 of each model file (raw bytes). One model per level: `B`, `A`, `C`, `zona` (zone), `totales` (totals), `sin_delitos` (no crimes), `solo_mapa` (map only). The `.json` files list the categories of the categorical features; they are identical across levels. |
| `codigo` | SHA-256 of the exam code and the sealed documents, with line endings normalized to LF (same result on Windows and Linux) |
| `nota` | Note: the models were trained only on the learning cities and are the same ones evaluated in practice v2 |

**`manifiesto.json`** (one entry per holdout dataset):

| Key | Meaning |
|---|---|
| `ciudad`, `grupo` | City; group (`holdout_main` = main exam, `holdout_reserve` = external reserve, `holdout_zona` = zone level) |
| `dataset`, `url`, `params` | Official source and download request |
| `periodo_solicitado` | Period requested from the server |
| `etag_servidor` | Server ETag, if any |
| `descarga_utc` | Download time (UTC) |
| `archivo` | Encrypted file on the author's disk |
| `sha256_original`, `sha256_cifrado` | SHA-256 of the original stream and of the encrypted file |
| `cifrado`, `kdf`, `iv` | Encryption (AES-256-GCM), key derivation (scrypt: n, r, p, salt) and IV. Salt and IV are not secret by design. |
| `programa_commit`, `python` | Git commit of the vault program and Python version |
| `verificacion_inmediata` | Result of the immediate decrypt-and-check after encryption ("ok"), done without displaying content |

## 3. Precedence and known differences (decided before opening)

**Precedence:** if documents differ, the OSF registration form and `preregistro.md` govern the analysis.

The following differences between the sealed documents and the pre-registration were identified and resolved **before** opening any exam data:

1. **Calibration** (`reglas_de_datos.md`, section 6, listed as a secondary measure: "whether the displayed % is met"). It is **not evaluated** in this exam. The sealed models produce relative risk maps; the app's displayed percentage requires a separate, city-specific calibration step that is not part of formula v2. It is deferred to a later study.
2. **Broad crime definition** (`reglas_de_datos.md`, sections 2 and 6, a secondary measure). The exam program scores only the universal core. Any result with the broad definition will be labeled **exploratory**.
3. **Cities with few cases** (`reglas_de_datos.md`, section 6, anticipated a pre-opening check of case counts with a pooled fallback). Not applied: checking counts before opening would have required looking at crime-derived numbers of the exam cities, which we decided not to do. Instead, every city is reported separately with its confidence interval. The hypotheses require support in all three cities, so a city with few cases makes a claim harder to support, never easier.
4. **The "totals" level** (`reglas_de_datos.md`, section 3, "city total, by month"). It is implemented as a single city-wide annual rate of core crimes per 1,000 residents over the past period (`preregistro.md`, levels table).
5. **Public features of the "map only" level.** `preregistro.md` says "every level also uses" Census, LEHD, GTFS, VIIRS and simulated pedestrians. The `solo_mapa` level is the exception: it uses OpenStreetMap features only, as its own levels table states.
6. **Time of the incident** (`reglas_de_datos.md`, section 2: occurrence time if published; otherwise report time). None of the three exam cities publishes an occurrence time, so the published time is used: dispatch time (Philadelphia), report time (Baton Rouge) and the time the call was received (Tempe).
7. **Old level names** (`protocolo.md`, point 3.7, "levels 1 to 5"). This is the earlier naming. The sealed version has the seven levels listed above.
