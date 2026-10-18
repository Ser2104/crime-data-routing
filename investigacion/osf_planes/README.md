# Analysis plans of the exploratory analyses

Paper: *How much crime data does crime-aware pedestrian routing need? A pre-registered evaluation in cities a model has never seen.*

The paper's confirmatory analyses are registered on OSF (osf.io/x3z9s and osf.io/eb5rt). The analyses in its Section 6 are exploratory:
they were run after the exam data had been opened. Each was specified in a plan that was committed to the author's private
version-control (git) repository before its code was written; later changes were added to the same file, with their date and reason.

This folder contains **every committed version** of each plan, exactly as stored in git, so that the original plan and each change can be compared.
The plans are written in Spanish, the author's working language; the paper describes each analysis in English.

**Limits of this evidence.** Commit times are recorded by the author's own computer and repository; they are not certified by a third party.
The OSF upload time of this folder is later than the commits. The analysis code itself is not public (see the paper's Data and code availability).

## Comparison with the published safe-path method of Galbrun et al. (G16); Section 6.3 of the paper.

Original file name: `comparacion_metodos_publicados.md`.

| Version | File in this folder | Commit | Committed (local time, UTC offset) | SHA-256 of the file | Commit message |
|---|---|---|---|---|---|
| 1 | `comparison_v1_e680684.md` | `e6806846c68b30ac6bf0fd3a1a6a923b02878f39` | 2026-10-08 23:30 -0400 | `309371a6e7753bfd…` | Pre-specify the exploratory comparison with Galbrun et al. (2016) before writing code |
| 2 | `comparison_v2_01455c5.md` | `01455c59785cb7d179baf29c40fa2b57eec97ef6` | 2026-10-08 23:34 -0400 | `a3057b38cd0ca102…` | Comparison program for Galbrun et al. (2016); tests pass before any exam-city run |
| 3 | `comparison_v3_2131442.md` | `21314424e26d910f91c91420fc95362edcd9efe5` | 2026-10-08 23:38 -0400 | `c3945354282241ef…` | Comparison plan, change 1 (before exam cities): uniform-sampling G16 variant; per-meter KDE in our router |

## Transport analyses: detour budget, concentration of walking, computation; Sections 4.6 and 6.2.

Original file name: `analisis_transporte.md`.

| Version | File in this folder | Commit | Committed (local time, UTC offset) | SHA-256 of the file | Commit message |
|---|---|---|---|---|---|
| 1 | `transport_v1_140a8b6.md` | `140a8b6ae2012815b872be95e500379f8175ef65` | 2026-10-09 13:58 -0400 | `400685974c44bc6e…` | Pre-specify exploratory transport analyses for the TR-C version (before any code) |
| 2 | `transport_v2_aef301a.md` | `aef301a14213d48fb960f7405c541b586b01fe1e` | 2026-10-09 17:35 -0400 | `4cc12df7d83d5736…` | Transport analyses: results (trade-off curve, concentration, query time), checks OK; article completed for TR-C |

## Sensitivity analyses after the exam (R1 to R10) and their four recorded changes; Section 6.4.

Original file name: `analisis_revision.md`.

| Version | File in this folder | Commit | Committed (local time, UTC offset) | SHA-256 of the file | Commit message |
|---|---|---|---|---|---|
| 1 | `sensitivity_v1_78484c0.md` | `78484c0ab94ee4411350ed7c5ac5c4ac9b7f266e` | 2026-10-09 19:20 -0400 | `83828f6d1fa6bc5a…` | Pre-specify post-exam analyses responding to the external review (before any code) |
| 2 | `sensitivity_v2_94ec94b.md` | `94ec94b36e383ac60167c83181a63c52a9d96145` | 2026-10-09 19:30 -0400 | `73beb91374781610…` | Revision plan, change 1 (before running R6 and before viewing any Tempe description): negation guard and check (d) for Arizona 'aggravated' non-assault offenses; change 2: R4 draws one at a time (memory) |
| 3 | `sensitivity_v3_af49440.md` | `af4944065dbfa0715a63e0a3e287c28ea3118a4d` | 2026-10-09 23:22 -0400 | `bf8caae9703abba0…` | Revision plan, change 3 (post hoc, after viewing Tempe descriptions): R6b re-scores Tempe with the official NIBRS codes embedded in its descriptions; the keyword rules had counted 466 non-core records as core and missed 88 core ones (incl. 18 homicides via 'NON-NEGLIGENT') |
| 4 | `sensitivity_v4_85d276d.md` | `85d276d620a24a99604caca0b06f2faba228254e` | 2026-10-09 23:22 -0400 | `9af05525dbdd6c31…` | Plan change 3: correct the stated time (committed 23:22, before running R6b) |
| 5 | `sensitivity_v5_1f4ad78.md` | `1f4ad7810f07e4615df36b56537577ad4ed9836d` | 2026-10-09 23:55 -0400 | `9249619551ee152f…` | Second review: abstract no longer says 'full benefit'; G16 sentence credits simple maps too (spatial scale); precise wording of the byte-identical rerun (six score files, routes reused); plan change 3 count corrected to 451 (+15 without official code) |
| 6 | `sensitivity_v6_e88b874.md` | `e88b8747f3f0d1412c2d35110afa23c8ef4dd8f8` | 2026-10-10 00:34 -0400 | `f05fe7398cbced56…` | Revision plan, change 4 (before running R3 in Philadelphia and rerunning R5): strip spaces from SEPTA 2025 rail GTFS headers; R5/R3 per city with merged outputs; Philadelphia R5 control not repeated (passed, max diff 5.68e-14); second queue ordered by memory |

## Notes

- **Sensitivity plan, change 3** was decided after viewing Tempe's crime descriptions and is reported in the paper as post hoc.
  It was committed (version 3) before the re-scoring it describes was run.
- **Sensitivity plan, version 5** corrects a count in the description of change 3 (466 to 451 records, plus 15 without an official code).
  The correction is marked in the plan as dated 2026-10-10; it was committed on 2026-10-09 at 23:55 EDT (2026-10-10 03:55 UTC).
  No analysis depended on that count.
- Some commits also changed other files of the project; only the plan files are included here.
- The sensitivity plan calls the critique of the draft that motivated it an "external audit": it was an automated critique produced with
  a generative AI system, not a peer review.
