# Cross-platform reproducibility: objective versus timetable identity

A mixed-integer solver can return different optimal package combinations on different platforms, even when their **maximum number of reachable queries is identical**. Different optimal timetables can gain and lose different query IDs. Requiring `coverage.csv`, `references.csv`, or the solver-call ledger to match byte-for-byte across machines is therefore not a valid test of the stated objective.

The **830-call count** is the number observed in the original archived November 7 run. A separate replay using Apple Silicon / Python 3.12.13 yielded **809** calls, all optimal. The call count depends on enumeration paths, tied solutions, caching, and solver behavior. A fresh replay reports its actual count rather than claiming it must be 830.

The archived 20% offset-zero **411-query reference IDs and route-package choices** are frozen in `revision_analysis/worked_example_20pct.json`. Two distinct 415-query solutions are frozen there as `K1_unrestricted` and `K1_L5`. The first loses five Nakanosawa queries; the second loses five Fujino queries. Both are verified against the same 411-query reference, with separate operator caps.

For temporal-spacing sensitivity, `revision_analysis/temporal_reference_sets_frozen.json` stores three distinct reference sets, each serving 414 queries, and route/package choices proving those sets are feasible fixed-operator optima. Zero-loss maxima are **415, 416, and 414**, respectively. The first set matches the originally archived reference (ID 634 included, ID 467 excluded). The second swaps those IDs. The reported 75% protection-cost share pertains to the **first archived reference**; across all three shares are 75%, 50%, and 100%.

The archived reference sets for each of the seven time-limit/package sensitivity cases are preserved in `revision_analysis/new_sensitivity_results.json`, and the original three primary offset-zero reference sets are stored in `revision_analysis/frozen_primary_references.json`. The sensitivity runner uses *frozen reference ID sets* rather than choosing a new one from a tied fresh solve.

Run from the repository root:

```shell
python -m pip install -r requirements.txt
python reproduce.py --quick   # source checks, dataset, unit tests and frozen identity/schedule checks
python reproduce.py --full    # also full solver analyses, stable-objective comparisons and live call ledger
```

The quick check reconstructs archived solution schedules and independently computes every query identity and operator resources; it also verifies the global optimum with a fresh solver call. The full cross-platform comparator checks **stable objective values** and separately checks **archived query identity sets** for frozen plans. It does not require identical tie-selected timetables or equal MILP call counts. Machine-specific differences in the solve count or tied query allocation are documented rather than misreported as failed optimization.
