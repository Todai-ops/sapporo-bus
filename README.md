# Journey protection in coordinated bus-service cuts — reproducibility repository

Computational material accompanying *The Accessibility Cost of Protecting Journeys in Coordinated Bus-Service Cuts* (Adhar Sharma; revised submission to *Findings*, November 2026).

**Status:** Author/reviewer reproduction package. This repository reproduces a **specified illustrative eight-route Sapporo model**, not a real-world operating recommendation or rider-level effect estimate.

## Key results (main 60-minute, offset-zero scenario)

| Operator revenue-hour cut | Fixed assignments `C(0,∞)` | Unrestricted coordination `C(7,∞)` | Full protection `C(7,0)` | First effective loss allowance |
|---|---:|---:|---:|---:|
| 10% | 419 | 421 | 419 | 3 |
| 20% | 411 | 415 | 411 | 3 |
| 30% | 403 | 406 | 403 | 3 |

At the 20% cut, **one** modelled reassignment of Bankei's Komaoka route unit to Jotetsu is sufficient for the unrestricted total of 415 reachable *sampled departure-time queries*, with nine gained and five lost relative to the selected post-cut reference. At an allowance of three reference-query losses the best result is 413 (five gained, three lost). Full protection means preserving the 411 *post-cut reference query identities*, not preserving original 2026 service or travel times.

These percentages and loss thresholds are **not universal**: see the 45/75/90-minute and alternative-package sensitivity outputs in `revision_analysis/new_sensitivity_results.csv` and the supplement.

## Contents

| Path | Description |
|---|---|
| `gtfs_sources/` | Exact historical feed ZIPs, dataset-construction script and source checks |
| `sapporo_reconstruction/data/` | Deterministic derived GTFS route/trip/stop/query data, case configuration and provenance |
| `revised/hold_harmless.py` | Original mixed-integer model and finite package/itinerary construction |
| `revised/test_hold_harmless.py` | Synthetic algorithm regression tests |
| `sapporo_reconstruction/final_analysis/` | Original November 7 baseline solution CSVs, tables and figure |
| `revision_analysis/*.py` | Verified model replay/830-solve log, individual query/resource audit, additional sensitivity designs |
| `revision_analysis/*.csv,*.json` | Saved solver logs, alternative reference and scenario outcomes, 20% case audits |
| `paper/` | Revised LaTeX source, bibliography with direct Jotetsu GTFS resource, and compiled manuscript |
| `supplement/` | Supplementary reproducibility documentation in LaTeX and PDF |
| `docs/` | Original November 7 computational research summary (citation link corrected) |
| `reproduce.py` | Portable command-line runner for quick tests or full experiment replay |
| `scripts/verify_sources.py` | Feed checksum, provenance and basic dataset consistency checks |
| `scripts/compare_outputs.py` | Compare replayed results with the frozen original/updated outputs |

## Requirements

- Python **3.12 or 3.13** (confirmed using Python 3.13, pinned dependencies below).
- `numpy==2.3.5`, `scipy==1.17.0` (HiGHS MILP), `matplotlib==3.10.8` from `requirements.txt`.
- Optional: pdfLaTeX and BibTeX to rebuild the manuscript and supplement PDFs. The precompiled PDFs are included.
- **No network connection is needed to run the model once the ZIP snapshots and dependencies are installed.** Never silently replace the archived GTFS inputs with current downloads: the live sources can change.

```sh
python -m pip install -r requirements.txt
python reproduce.py --quick
python reproduce.py --full
```

- `--quick` verifies the archived source hashes, rebuilds the study dataset, runs synthetic algorithm tests and reconstructs the 20% worked example.
- `--full` also replays the original experiment and 830-call ledger, repeats the seven sensitivity experiments, and checks replayed output tables against the frozen CSVs. Expected duration depends on machine and solver.
- You can run individual scripts from the project root: `python revised/hold_harmless.py --data sapporo_reconstruction/data --out reproduced/main` and `python revision_analysis/run_sensitivity.py`.

> `PYTHONHASHSEED=0` is set by `reproduce.py` for subprocesses to make ordering deterministic. If manually running Python scripts, set that environment variable yourself.

## Sources and model boundary

The experiment takes **48 Bankei + 205 Jotetsu + 678 subway trips**, sampled on **9 November 2026** for both bus operators and **3 February 2020** for subway service. There are 832 equally weighted origin–destination–departure queries, including initial waiting time in the 60-minute reachability limit. Journeys may use up to two bus and two subway boardings with five-minute interchange time. Seven route units are eligible for reassignment; each route is thinned by eight nested packages based on bit-reversal ordering. The primary scenario uses fixed operator-specific revenue-hour budgets and **experimental**, not observed, fleet caps (Bankei 4, Jotetsu 23). No cross-unit vehicle interlining, deadhead, fares, walking links outside normalized same-name stations, observed passenger demand, or rider preferences are modeled.

Full source URLs, publication entities, dates, route IDs, explicit stop aliases, the full query list and **SHA-256 hashes** are recorded in `sapporo_reconstruction/data/provenance.json` and `LICENSE_AND_ATTRIBUTION.md`. The stable Jotetsu source landing page is https://ckan.hoda.jp/dataset/gtfs-data/resource/fef98fef-6fe2-472f-bde3-9d4f0a509a4a (the generic HODA catalogue link in an earlier bibliography was insufficiently specific).

## Citation and archive integrity

Please cite the paper plus the corresponding frozen repository commit or archival DOI (if deposited). `CITATION.cff` gives the author metadata; **no DOI is claimed yet**. All GTFS data are attributed separately in `LICENSE_AND_ATTRIBUTION.md`. Do not confuse the distinct 848-query exploratory study of 6 November 2026 with the **832-query final reproduction**.

For interpretation, model details and caveats, see `supplement/supplementary_information.pdf`. The original publication/reviewer response is not included because it is not necessary to reproduce the experiments and may be part of a private editorial exchange.
