# Reconstructed Sapporo bus-coordination study: verified results

**Status (7 November 2026):** The complete experiment was run successfully.
This is a new, reproducible illustration assembled from public GTFS data, **not**
a reconstruction of the authors' unknown original route-selection or query files.
It combines bus feed service on 9 November 2026 with historical subway service
on 3 February 2020. The schedules are not contemporaneous; the outcome is not
evidence that an operator could implement the resulting plan in Sapporo.

## Source data and experimental setup

| Component | Selection | Count |
|:--|:--|--:|
| Bankei Bus | Three complete GTFS route IDs | 48 trips |
| Jotetsu | Five complete GTFS route IDs | 205 trips |
| Sapporo Subway | Fixed Namboku and Tozai line trips | 678 trips |
| All transit trips | Monday service from the corresponding feeds | 931 |
| Stop-time records | Generated from the selected trips | 15,969 |
| Normalized stop names | Explicit station-name aliases | 135 |
| Origin nodes | Seven peripheral + four other origins | 11 |
| Destination nodes | Five subway/interchange nodes | 5 |
| Departure-time samples | 06:00–21:00, once each hour | 16 |
| Query set | 11×5×16, excluding 48 same-origin/destination cases | **832** |
| Baseline full-timetable reachable queries | 60-minute arrival threshold | **426** |
| Route-package levels | Nested, bit-reversal thinning | 8 |
| Unique packages at main offset | Deduplicated by trip set | 60 |
| Available package/operator choices | Eight route units, seven eligible for reassignment | 112 |
| Minimal itinerary trip supports | Exact enumerated supports | 490 |
| Optimization solves completed | Across cut levels, offsets, and reference plans | **830** |

The reference is the best uncoordinated ($K=0$) plan under each operator's
resource caps. All journeys receive equal weight; a query is reachable if an
itinerary arrives within 60 minutes, with no more than two bus and two subway
boardings and five-minute interchange time. Co-named/explicitly aliased stations
are treated as co-located; there are no other walking links. Vehicle caps
(Bankei 4; Jotetsu 23), the route-reassignment rule, and selection of endpoints
are explicit **experimental assumptions**, not asserted operational facts.

### Main findings (thinning offset 0)

| Hour cut | Uncoordinated $C(0,\infty)$ | Unrestricted $C(7,\infty)$ | Protected $C(7,0)$ | Gain from coordination | Protection price $\Delta$ | Protection share | First effective $L^*$ |
|--:|--:|--:|--:|--:|--:|--:|--:|
| 10% | 419 | 421 | 419 | 2 | 2 | 100% | 3 |
| 20% | 411 | 415 | 411 | 4 | 4 | 100% | 3 |
| 30% | 403 | 406 | 403 | 3 | 3 | 100% | 3 |

**Interpretation.** For the main phase, the clause forbidding any loss of
baseline-reachable queries extinguishes the whole incremental accessibility
benefit of assigning bus routes to another operator. The absolute effects are
modest: the largest is **four of 832 queries (0.48%)**, or 0.97% of the
20% cut's optimized uncoordinated baseline (411). A protection share of 100%
does **not** mean that total network accessibility falls by 100%.

At the 20% cut, the full published composite supports 426 queries, while the
uncoordinated reduced service supports 411, a loss of 15. Permitting one
route reassignment without a hold-harmless rule recovers four of those 15,
or 26.7% of the lost reachable queries in net terms. Full protection removes
that gain. At $K=7,L=\infty$, the optimized coordinated plan gains nine
queries over the reference but loses five others, yielding a net gain of four.

### First effective loss allowances

| Cut | First $L$ allowing any gain over full protection | Newly reachable relative to protected plan | Baseline queries actually lost | Net extra reachable | Gross gain per loss |
|--:|--:|--:|--:|--:|--:|
| 10% | 3 | 5 | 3 | 2 | 1.67 |
| 20% | 3 | 5 | 3 | 2 | 1.67 |
| 30% | 3 | 6 | 3 | 3 | 2.00 |

An allowance of one or two lost baseline queries has no effect in the primary
scenario. This is a discrete timetabling result, not a general mathematical
necessity. The gross gain counts queries newly reachable relative to the
hold-harmless optimum, whereas net gain also subtracts reference-query losses.

### Exact minimum-scope agreement menu

Pairs $(K,L)$ indicate the least number of eligible route reassignments and
the least permissible lost reference queries to achieve a gain of at least
$g$ relative to the optimized $K=0$ baseline. Only Pareto-nondominated pairs
appear. In the primary case, all achievable targets need only one reassignment.

| Cut | Gain $g=2$ | Gain $g=4$ | Gain $g=5$ |
|--:|:--:|:--:|:--:|
| 10% | (1,3) | Unattainable | Unattainable |
| 20% | (1,3) | (1,5) | Unattainable |
| 30% | (1,3) | Unattainable | Unattainable |

The program solves the plotted $L=0,\ldots,20$ grid and uses additional exact
binary-search solves for thresholds and the minimal agreement menu, so a
reported threshold is not just a coarse-grid interpolation.

### Sensitivity: eight departure-thinning offsets

| Cut | Offsets with positive coordination gain | Protection share, only positive-gain offsets | Offsets forfeiting all gain | First-effective allowance range (where defined) |
|--:|--:|:--:|--:|:--:|
| 10% | 6 of 8 | 0–100% | 4 of 6 | 1–3 |
| 20% | 7 of 8 | 100% | 7 of 7 | 1–3 |
| 30% | 8 of 8 | 75–100% | 7 of 8 | 1–8 |

At offset 0, enumeration found four, two, and five distinct optimum reference
reachability sets for cuts of 10%, 20%, and 30%, respectively (up to 25
candidate optimized plans sought per cut). Their respective protection-price
shares are 100%, 100%, and 66.7–100%. Thus the 100% primary result is stable
over the examined optimal references for 10% and 20% cuts, but is **not**
universal across every time offset or at 30%.

The rule-based uncoordinated reference has lower coverages—407, 400, and 393
queries at cuts of 10%, 20%, and 30%, respectively—than the corresponding
optimized $K=0$ baselines (419, 411, 403). Since their protected query sets
differ, the corresponding protection-price percentages are not direct
comparisons of the same travelers.

## Public sources and provenance

- Sapporo Bankei public GTFS: <https://ckan.hoda.jp/dataset/gtfs-data/resource/889906b8-eb1a-41c3-a7b3-75cd69aa891f>.
- Jotetsu public GTFS: <https://ckan.hoda.jp/dataset/gtfs-data/resource/fef98fef-6fe2-472f-bde3-9d4f0a509a4a>, resource ID `fef98fef-6fe2-472f-bde3-9d4f0a509a4a`.
- Sapporo Subway public GTFS: <https://ckan.hoda.jp/dataset/gtfs-data/resource/3efff7e5-b604-4850-8888-38f0e60bb238>.
- Sapporo City public transport plan: <https://www.city.sapporo.jp/sogokotsu/documents/gaiyou.pdf>.

The Hokkaido platform identifies its dataset license as Creative Commons
Attribution. Publisher names, feed validity dates, GTFS route IDs, date
selection, station-name aliases, source URLs, and exact source ZIP SHA-256
hashes are recorded in `sapporo_reconstruction/data/provenance.json`. The
original downloaded archives are bundled under `gtfs_sources/`.

## How to reproduce

From the extracted package root, with Python 3.12 and dependencies installed
from the supplied version-pinned `requirements.txt`:

```bash
python -m pip install -r requirements.txt
python gtfs_sources/build_study_dataset.py
PYTHONHASHSEED=0 python revised/hold_harmless.py \
    --data sapporo_reconstruction/data \
    --out sapporo_reconstruction/final_analysis
python -m unittest discover -s revised -p 'test_*.py' -v
```

The solve takes approximately 110 seconds in the supplied environment.
It creates `coverage.csv`, `metrics.csv`, `references.csv`, `menu.csv`,
`results.tex`, `tab_menu.tex`, and `fig_frontier.pdf`. Exact agreement
surfaces and phase-by-phase outcomes are available in the CSVs.
`gtfs_sources/render_frontier.py` can regenerate only the figure from saved
solve records without rerunning the optimizer.

To compile the paper, copy the three generated TeX/PDF include files into
`sapporo_reconstruction/paper/`, and run `pdflatex`, `bibtex`, then `pdflatex`
twice on `main.tex`. It uses `plainnat.bst`, not a Chicago bibliography style.
In this environment, TeX format/font-map variables require a local workaround;
the PDF is already included.

## Scientific caveats

This exercise establishes the behavior of the specified model, not a policy
estimate. Its limitations include a historically mismatched subway feed,
chosen origin/destination set, unweighted trips, interchangeable operators
with no depot or labor agreement, stylized vehicle caps, collapsed same-name
stations, omitted pedestrian transfers, and one-hour cumulative reachability.
General claims require contemporaneous data, real passenger demand and
contractual constraints, and independent route-selection validation.
