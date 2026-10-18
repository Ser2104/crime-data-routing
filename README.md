# How much crime data does crime-aware pedestrian routing need?

Code, aggregated results and study documents of the paper *How much crime data does crime-aware pedestrian routing need? A pre-registered evaluation in cities a model has never seen* (Sergio Alberto Yacolca Cueva; submitted to *Transportation Research Part C: Emerging Technologies*).

- **Archived release:** [doi.org/10.5281/zenodo.23446917](https://doi.org/10.5281/zenodo.23446917) (Zenodo).
- **Pre-registrations:** [osf.io/x3z9s](https://osf.io/x3z9s) (main exam) and [osf.io/eb5rt](https://osf.io/eb5rt) (Tempe replacement exam).
- **License:** MIT (see `LICENSE`).
- **Status:** research code of a non-commercial prototype; the author receives no income from it.
- **Language:** code comments and most working documents are in Spanish, the author's working language. The paper, the registrations, the English translations in `investigacion/en/` and this README are in English.

## What the study does

- **Models:** one risk model per level of crime data (seven levels, from detailed street-level records to none) is trained on four U.S. cities (Pittsburgh, Chapel Hill, Chicago, Seattle) and sealed.
- **Exam:** the models are tested in three cities they never saw (Philadelphia, Baton Rouge, Tempe), whose crime data stayed encrypted until a pre-registered opening.
- **Scoring:** the router plans 2,000 random walking trips per city, and each route is scored by the violent crimes recorded on its streets in the following year.

## Setup

- **Python 3.13.3.** Developed on Windows 11; other systems are untested.
- **Packages:** `python -m venv .venv`, activate it, then `pip install -r requirements.txt`.
- **Where to run:** every command below runs from the repository root.
- **Data are not included.** Each step downloads or rebuilds them into `data/`:
  - OpenStreetMap is read from Geofabrik state extracts (`.osm.pbf`) with `src/osm_local.py`;
  - Pittsburgh's police incident file is downloaded by hand from the Western Pennsylvania Regional Data Center (`data/raw/pbp_incidents_2024_2026.xlsx`; see `src/multiciudad/02_normalizar_delitos.py`).
- **PDF:** `tectonic investigacion/articulo/main.tex`, or upload the folder to Overleaf.

## Layout

| Folder | Contents |
|---|---|
| `src/multiciudad/` | The multi-city study: steps `01`–`09` and their shared modules (`formula.py`, `rasgos_delitos.py`, `evaluar_rutas.py`, ...). |
| `src/` | The routing engine (`rutas.py`) and the modules it uses; OpenStreetMap reading; simulated pedestrian volumes (`peatones.py` and steps `17`–`19`). |
| `investigacion/` | Protocol, data rules, pre-registrations, vault and seal programs, exam analyses, plans of the exploratory analyses. |
| `investigacion/caja_fuerte/` | Vault manifest (SHA-256 fingerprints of the encrypted exam files), opening log and blind format checks. |
| `investigacion/resultados/` | Aggregated results of the exam and of every exploratory analysis (CSV and JSON). |
| `investigacion/articulo/` | The paper (`main.tex`, `refs.bib`) and the programs that build its tables and figures from the result files. |
| `investigacion/osf_planes/` | Every committed version of the three exploratory analysis plans, with their commit times. |

## Reproducing the paper, in order

Each script explains its options in its first lines.

1. **Groups and rules (already done and recorded).**
   - City lottery: `python investigacion/sorteo_ciudades.py 4818`.
   - Rules: `investigacion/protocolo.md` and `investigacion/reglas_de_datos.md` (English: `investigacion/en/`).
2. **Vault.**
   - `python investigacion/caja_fuerte.py sellar <group>` downloads the exam cities' crime data directly into AES-256-GCM files; it asks for a passphrase that only the author holds.
   - Development scripts import `src/caja_cerrada.py`, which stops them if they try to open vault files.
3. **Development cities.**
   - Run `src/multiciudad/01_descargar_delitos.py` to `07_entrenar_y_practicar.py` in order. Step 07 trains on the learning cities and tests on the practice cities (Cincinnati, Gainesville).
   - The practice log is `investigacion/registro_practica.md`.
4. **Seal.** `python investigacion/sellar_formula.py v2` writes `investigacion/sello_v2.json`; `python investigacion/sellar_formula.py v2 tempe` does the same for the Tempe replacement exam.
5. **Exam (registered).**
   - Open the vault once: `python investigacion/caja_fuerte.py abrir holdout_main --motivo "..."`.
   - Run `python src/multiciudad/09_examen.py`, then `python src/multiciudad/09_examen.py --grupo holdout_tempe2` for Tempe.
6. **Exploratory analyses (paper Section 6).** They read the exam data already opened:

   | Analysis | Program |
   |---|---|
   | Robustness | `investigacion/auditoria_estadistica.py` |
   | Detour budget, concentration and computation | `investigacion/analisis_transporte.py` and `verificar_transporte.py` |
   | Comparison with Galbrun et al. | `investigacion/comparacion_metodos.py` |
   | Sensitivity analyses R1–R10 | `investigacion/revision_*.py`, in the order of `revision_fila.sh` and `revision_fila2.sh` |

7. **Tables, figures and PDF.**
   - Build them with `python investigacion/articulo/generar_tablas.py` and `python investigacion/articulo/generar_figuras.py`.
   - Check the draft with `python investigacion/articulo/revisar_latex.py`.

## What can and cannot be re-run

- **Every table and figure** can be rebuilt from `investigacion/resultados/` without any crime data (step 7).
- **The exam itself** needs the exam cities' police data. They are public and listed in the paper's data statement, but the portals change over time. A new download will not match the sealed files byte for byte; their fingerprints are in `investigacion/caja_fuerte/manifiesto.json`.
- **The trained models** are attached to the OSF registrations. The seal files list their fingerprints.

## Citation

See `CITATION.cff`.
