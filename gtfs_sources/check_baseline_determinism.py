"""Print stable fingerprints of the K=0 optimum for hash-seed checks."""
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "revised"))
from hold_harmless import Planner, INF, DEFAULT_CONFIG, build_packages, load, departure_index, enumerate_support

base = Path(__file__).resolve().parents[1] / "sapporo_reconstruction" / "data"
with (base / "config.json").open(encoding="utf-8") as f:
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(json.load(f))
trips, transfers, queries, weights = load(str(base))
idx = departure_index(trips)
support = [enumerate_support(q, trips, idx, transfers, cfg) for q in queries]
routes, o0, byroute = {}, {}, defaultdict(list)
for tid, tr in trips.items():
    if tr["mode"] == "bus":
        o0[tr["route"]] = tr["op"]
        byroute[tr["route"]].append(tid)
packages = build_packages(byroute, trips, cfg["levels"], cfg["main_offset"], cfg["turnaround_minutes"] if "turnaround_minutes" in cfg else 5)
planner = Planner(cfg, packages, o0, support, weights)
full_hours = {o: sum(packages[r][-1]["hours"] for r in packages if o0[r] == o) for o in cfg["operators"]}
for depth in cfg["cut_depths"]:
    planner.caps_h = {o: (1-depth)*h for o,h in full_hours.items()}
    sol = planner.solve(0, INF)
    signature = ",".join(str(j) for j in sol["selected"]) + "|" + ",".join(str(q) for q in sorted(sol["reach"]))
    print(depth, int(sol["cov"]), sol["n_trips"], hashlib.sha256(signature.encode()).hexdigest()[:20])
