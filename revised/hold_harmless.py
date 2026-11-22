#!/usr/bin/env python3
"""hold_harmless.py: price of the hold-harmless clause in coordinated bus-service cuts.

Usage
    python hold_harmless.py --data data --out out

Requires numpy, scipy >= 1.9 (milp / HiGHS), matplotlib.

Input files (in --data)
    trips.csv       trip_id,route_unit,operator,mode           mode: bus | subway (subway is fixed, never thinned)
    stop_times.csv  trip_id,seq,stop_id,arr,dep                HH:MM, 24 h; 25:10 allowed for after midnight
    queries.csv     origin_stop,dest_stop,dep_time[,weight]
    transfers.csv   from_stop,to_stop,minutes                  optional walking links; list both directions
    config.json     overrides of DEFAULT_CONFIG (at least eligible_route_units)

Output files (in --out)
    coverage.csv     one row per solve (offset, depth, reference, K, L)
    references.csv   reference plans
    metrics.csv      derived metrics per (offset, depth, reference)
    menu.csv         Pareto-minimal (K, L) pairs per target gain
    tab_menu.tex     the same as a LaTeX table
    results.tex      \\newcommand macros read by main.tex
    fig_frontier.pdf
"""
import argparse
import bisect
import csv
import json
import math
import os
import statistics
import sys
import time
from collections import defaultdict

import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import coo_matrix
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DEFAULT_CONFIG = {
    "operators": {"Bankei": {"vehicle_cap": 4}, "Jotetsu": {"vehicle_cap": 23}},
    "eligible_route_units": [],          # route units that may change operator (those serving Makomanai)
    "levels": 8,
    "offsets": [0, 1, 2, 3, 4, 5, 6, 7],
    "main_offset": 0,
    "cut_depths": [0.10, 0.20, 0.30],
    "max_itinerary_minutes": 60,
    "max_bus_boardings": 2,
    "max_subway_boardings": 2,
    "transfer_margin_minutes": 5,
    "turnaround_minutes": 5,
    # A dense plotted grid is helpful, but the first effective allowance is
    # found separately by exact monotone search (possibly beyond this grid).
    "loss_budgets": list(range(21)),
    "max_alt_optima": 25,
    "target_gains": [2, 5, 10],
    "mip_rel_gap": 1e-9,
    # Outside main_offset, only exact price/threshold sensitivity is needed.
    # The full K x L surfaces and Pareto menus are still solved at main_offset.
    "sensitivity_summaries_only": True,
}

INF = None  # loss allowance "unrestricted"


# ---------------------------------------------------------------- input
def hhmm(s):
    h, m = s.strip().split(":")
    return int(h) * 60 + int(m)


def read_csv(path, required=True):
    if not os.path.exists(path):
        if required:
            sys.exit(f"missing input file: {path}")
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load(data_dir):
    trips = {}
    for row in read_csv(os.path.join(data_dir, "trips.csv")):
        trips[row["trip_id"]] = dict(id=row["trip_id"], route=row["route_unit"].strip(),
                                     op=row["operator"].strip(), mode=row["mode"].strip().lower(), stops=[])
    for row in read_csv(os.path.join(data_dir, "stop_times.csv")):
        trips[row["trip_id"]]["stops"].append((int(row["seq"]), row["stop_id"].strip(),
                                               hhmm(row["arr"]), hhmm(row["dep"])))
    for tr in trips.values():
        tr["stops"].sort()
        tr["stops"] = [(s, a, d) for _, s, a, d in tr["stops"]]
        if len(tr["stops"]) < 2:
            sys.exit(f"trip {tr['id']} has fewer than two stops")
    transfers = defaultdict(list)
    for row in read_csv(os.path.join(data_dir, "transfers.csv"), required=False):
        transfers[row["from_stop"].strip()].append((row["to_stop"].strip(), max(1, int(row["minutes"]))))
    queries, weights = [], []
    for row in read_csv(os.path.join(data_dir, "queries.csv")):
        queries.append((row["origin_stop"].strip(), row["dest_stop"].strip(), hhmm(row["dep_time"])))
        weights.append(float(row.get("weight") or 1.0))
    if not queries:
        sys.exit("queries.csv contains no origin-destination-departure queries")
    if any(not math.isfinite(w) or abs(w - 1.0) > 1e-9 for w in weights):
        sys.exit("this study counts equally weighted queries; all query weights must be 1")
    return trips, dict(transfers), queries, weights


def departure_index(trips):
    idx = defaultdict(list)
    for tid, tr in trips.items():
        for pos, (s, a, d) in enumerate(tr["stops"][:-1]):  # no boarding at the last stop
            idx[s].append((d, tid, pos))
    for s in idx:
        idx[s].sort()
    return dict(idx)


# ---------------------------------------------------------------- reachability
def enumerate_support(q, trips, dep_idx, transfers, cfg):
    """Minimal sets of bus trips whose availability makes query q reachable (subway always available)."""
    origin, dest, t0 = q
    deadline = t0 + cfg["max_itinerary_minutes"]
    margin = cfg["transfer_margin_minutes"]
    max_bus, max_sub = cfg["max_bus_boardings"], cfg["max_subway_boardings"]
    found, best = set(), {}

    def visit(stop, t, nb, ns, used_bus, used_all):
        if t > deadline:
            return
        key = (stop, used_bus, nb, ns)
        if best.get(key, 10 ** 9) <= t:
            return
        best[key] = t
        if stop == dest:
            found.add(used_bus)
            return
        for s2, w in transfers.get(stop, ()):
            if t + w <= deadline:
                if s2 == dest:
                    found.add(used_bus)
                else:
                    visit(s2, t + w, nb, ns, used_bus, used_all)
        if nb >= max_bus and ns >= max_sub:
            return
        lst = dep_idx.get(stop, [])
        for k in range(bisect.bisect_left(lst, (t, "", 0)), len(lst)):
            dep, tid, pos = lst[k]
            if dep > deadline:
                break
            if tid in used_all:
                continue
            tr = trips[tid]
            if tr["mode"] == "bus":
                if nb >= max_bus:
                    continue
                nb2, ns2, ub2 = nb + 1, ns, used_bus | {tid}
            else:
                if ns >= max_sub:
                    continue
                nb2, ns2, ub2 = nb, ns + 1, used_bus
            ua2 = used_all | {tid}
            stops = tr["stops"]
            for m in range(pos + 1, len(stops)):
                s2, arr2, _ = stops[m]
                if arr2 > deadline:
                    break
                if s2 == dest:
                    found.add(ub2)
                    break
                visit(s2, arr2 + margin, nb2, ns2, ub2, ua2)

    visit(origin, t0, 0, 0, frozenset(), frozenset())
    minimal = []
    # Tie-break equal-size supports canonically: Python's randomized hash
    # ordering must not change the MILP matrix or selected baseline optimum.
    for s in sorted(found, key=lambda s: (len(s), tuple(sorted(s)))):
        if not any(m <= s for m in minimal):
            minimal.append(s)
    return minimal


# ---------------------------------------------------------------- service menu
def bitrev_order(n, offset):
    b = max(1, (n - 1).bit_length())
    N = 1 << b
    rev = lambda v: int(format(v, f"0{b}b")[::-1], 2)
    return sorted(range(n), key=lambda i: rev((i + offset) % N))


def min_vehicles(tids, trips, turnaround):
    """Minimum path cover of within-route trip compatibility (matching terminals, turnaround), n - max matching."""
    info = [(trips[t]["stops"][0][0], trips[t]["stops"][0][2], trips[t]["stops"][-1][0], trips[t]["stops"][-1][1])
            for t in sorted(tids)]
    n = len(info)
    adj = [[j for j in range(n) if j != i and info[j][0] == info[i][2] and info[j][1] >= info[i][3] + turnaround]
           for i in range(n)]
    match = [-1] * n

    def augment(i, seen):
        for j in adj[i]:
            if not seen[j]:
                seen[j] = True
                if match[j] < 0 or augment(match[j], seen):
                    match[j] = i
                    return True
        return False

    m = sum(1 for i in range(n) if augment(i, [False] * n))
    return n - m


def build_packages(by_route, trips, levels, offset, turnaround):
    packages = {}
    for r, tids in by_route.items():
        dirs = defaultdict(list)
        for t in tids:
            dirs[(trips[t]["stops"][0][0], trips[t]["stops"][-1][0])].append(t)
        for d in dirs:
            dirs[d].sort(key=lambda t: trips[t]["stops"][0][2])
        sets = {}
        for m in range(1, levels + 1):
            keep = set()
            for lst in dirs.values():
                n = len(lst)
                order = bitrev_order(n, offset)
                keep.update(lst[i] for i in order[: math.ceil(n * m / levels)])
            # Keep the *lowest* level representing this package. Otherwise a
            # one-trip route appears only at level 8 after deduplication and
            # disappears spuriously from rule-based lower-level references.
            sets.setdefault(frozenset(keep), m)
        pk = []
        for s, m in sorted(sets.items(), key=lambda kv: kv[1]):
            hours = sum(trips[t]["stops"][-1][1] - trips[t]["stops"][0][2] for t in s) / 60.0
            pk.append(dict(level=m, trips=s, hours=hours, vehicles=min_vehicles(s, trips, turnaround)))
        packages[r] = pk
    return packages


# ---------------------------------------------------------------- model
class Planner:
    def __init__(self, cfg, packages, o0, support, weights):
        self.cfg, self.packages, self.o0 = cfg, packages, o0
        self.ops = list(cfg["operators"].keys())
        elig = set(cfg["eligible_route_units"])
        self.options, self.route_opts, self.trip_opts = [], defaultdict(list), defaultdict(list)
        for r in sorted(packages):
            for pk in packages[r]:
                for o in (self.ops if r in elig else [o0[r]]):
                    j = len(self.options)
                    self.options.append(dict(route=r, level=pk["level"], op=o, hours=pk["hours"],
                                             veh=pk["vehicles"], trips=pk["trips"], reassigned=(o != o0[r])))
                    self.route_opts[r].append(j)
                    for t in sorted(pk["trips"]):
                        self.trip_opts[t].append(j)
        self.J = len(self.options)
        self.support, self.weights = support, weights
        self.always, self.qvar = set(), []
        for q, S in enumerate(support):
            if not S:
                continue
            (self.always.add(q) if frozenset() in S else self.qvar.append(q))
        self.ycol = {q: self.J + i for i, q in enumerate(self.qvar)}
        self.zcol, col = {}, self.J + len(self.qvar)
        for q in self.qvar:
            for s in range(len(support[q])):
                self.zcol[(q, s)] = col
                col += 1
        self.nvar = col
        self.const_cov = sum(weights[q] for q in self.always)
        rows, cols, vals, ub = [], [], [], []

        def add_row(entries, bound):
            r = len(ub)
            for c_, v in entries:
                rows.append(r); cols.append(c_); vals.append(v)
            ub.append(bound)

        for r in self.route_opts:
            add_row([(j, 1.0) for j in self.route_opts[r]], 1.0)
        self.cap_rows = {}
        for o in self.ops:
            js = [j for j, op in enumerate(self.options) if op["op"] == o]
            self.cap_rows[(o, "h")] = len(ub)
            add_row([(j, self.options[j]["hours"]) for j in js], np.inf)  # overwritten per depth
            self.cap_rows[(o, "v")] = len(ub)
            add_row([(j, float(self.options[j]["veh"])) for j in js], float(cfg["operators"][o]["vehicle_cap"]))
        for q in self.qvar:
            for s, S in enumerate(support[q]):
                zc = self.zcol[(q, s)]
                for t in sorted(S):
                    add_row([(zc, 1.0)] + [(j, -1.0) for j in self.trip_opts[t]], 0.0)
            add_row([(self.ycol[q], 1.0)] + [(self.zcol[(q, s)], -1.0) for s in range(len(support[q]))], 0.0)
        self.static = (rows, cols, vals, ub)
        self.reassign_js = [j for j, op in enumerate(self.options) if op["reassigned"]]
        self.caps_h = None
        self.n_solves = 0

    def solve(self, K, L, ref=None, nogoods=()):
        rows, cols, vals, ub0 = self.static
        rows, cols, vals, ub = list(rows), list(cols), list(vals), list(ub0)
        for o in self.ops:
            ub[self.cap_rows[(o, "h")]] = self.caps_h[o]

        def add_row(entries, bound):
            r = len(ub)
            for c_, v in entries:
                rows.append(r); cols.append(c_); vals.append(v)
            ub.append(bound)

        add_row([(j, 1.0) for j in self.reassign_js], float(K))
        if ref is not None and L is not INF:
            refq = [q for q in ref if q in self.ycol]
            add_row([(self.ycol[q], -1.0) for q in refq], float(L) - len(refq))
        for sel in nogoods:  # excludes exactly that x vector
            sset = set(sel)
            add_row([(j, 1.0 if j in sset else -1.0) for j in range(self.J)], len(sel) - 1.0)
        A = coo_matrix((vals, (rows, cols)), shape=(len(ub), self.nvar)).tocsr()
        c = np.zeros(self.nvar)
        for q in self.qvar:
            c[self.ycol[q]] = -self.weights[q]
        integrality = np.zeros(self.nvar)
        integrality[: self.J] = 1
        res = milp(c, constraints=LinearConstraint(A, -np.inf, np.array(ub)), integrality=integrality,
                   bounds=Bounds(0, 1), options={"disp": False, "mip_rel_gap": self.cfg["mip_rel_gap"]})
        self.n_solves += 1
        if res.status == 2:  # infeasible, normally only after enumeration no-good cuts
            return None
        if res.status != 0 or res.x is None:
            raise RuntimeError(f"HiGHS did not prove optimality (status={res.status}; {res.message})")
        sel = [j for j in range(self.J) if res.x[j] > 0.5]
        out = self.describe(sel, ref)
        if abs(-res.fun + self.const_cov - out["cov"]) > 1e-6:
            raise RuntimeError("solver objective and itinerary-based coverage disagree")
        return out

    def describe(self, sel, ref=None):
        avail = set()
        for j in sel:
            avail |= self.options[j]["trips"]
        reach = set(self.always)
        for q in self.qvar:
            if any(S <= avail for S in self.support[q]):
                reach.add(q)
        out = dict(selected=sel, reach=reach, cov=sum(self.weights[q] for q in reach), n_trips=len(avail),
                   hours={o: sum(self.options[j]["hours"] for j in sel if self.options[j]["op"] == o) for o in self.ops},
                   veh={o: sum(self.options[j]["veh"] for j in sel if self.options[j]["op"] == o) for o in self.ops},
                   reassigned=sorted(self.options[j]["route"] for j in sel if self.options[j]["reassigned"]))
        if ref is not None:
            out["gross_gains"], out["losses"] = len(reach - ref), len(ref - reach)
        return out

    def rule_reference(self):
        """Each operator: deepest common package level that fits its caps, then greedy upgrades, largest route first."""
        pk = self.packages
        plan = {}
        for o in self.ops:
            routes = [r for r in pk if self.o0[r] == o]
            cap_v = self.cfg["operators"][o]["vehicle_cap"]

            def feasible(a):
                h = sum(pk[r][i]["hours"] for r, i in a.items() if i is not None)
                v = sum(pk[r][i]["vehicles"] for r, i in a.items() if i is not None)
                return h <= self.caps_h[o] + 1e-9 and v <= cap_v

            def pk_at(r, m):
                cands = [i for i, p in enumerate(pk[r]) if p["level"] <= m]
                return max(cands, key=lambda i: pk[r][i]["level"]) if cands else None

            assign = None
            for m in range(self.cfg["levels"], 0, -1):
                a = {r: pk_at(r, m) for r in routes}
                if feasible(a):
                    assign = a
                    break
            if assign is None:
                assign = {r: pk_at(r, 1) for r in routes}
                for r in sorted(routes, key=lambda r: len(pk[r][-1]["trips"])):
                    if feasible(assign):
                        break
                    assign[r] = None
            changed = True
            while changed:
                changed = False
                for r in sorted(routes, key=lambda r: -len(pk[r][-1]["trips"])):
                    nxt = 0 if assign[r] is None else assign[r] + 1
                    if nxt < len(pk[r]):
                        trial = dict(assign)
                        trial[r] = nxt
                        if feasible(trial):
                            assign, changed = trial, True
            plan.update(assign)
        sel = []
        for r, i in plan.items():
            if i is not None:
                sel.append(next(j for j in self.route_opts[r]
                                if self.options[j]["level"] == pk[r][i]["level"] and self.options[j]["op"] == self.o0[r]))
        return self.describe(sel)


def enumerate_optima(planner, max_n):
    sols, nogoods, best = [], [], None
    while len(sols) < max_n:
        res = planner.solve(0, INF, None, nogoods)
        if res is None:
            break
        if best is None:
            best = res["cov"]
        if res["cov"] < best - 1e-6:
            break
        sols.append(res)
        nogoods.append(res["selected"])
    distinct = []
    for s in sols:
        if not any(s["reach"] == d["reach"] for d in distinct):
            distinct.append(s)
    return sols, distinct


# ---------------------------------------------------------------- analysis
def solve_cached(planner, surf, K, L, ref):
    """Return a proven optimum, memoizing extra exact-allowance solves."""
    if (K, L) not in surf:
        surf[(K, L)] = planner.solve(K, L, ref)
    return surf[(K, L)]


def minimum_allowance(planner, surf, K, target_cov, ref):
    """Find the globally smallest integer L meeting a target by monotone search.

    The plotted L grid is not sufficient to certify an exact threshold or a
    Pareto-minimal menu: the target could first be attained between grid points
    or beyond the last displayed finite allowance.
    """
    if surf[(K, INF)]["cov"] < target_cov - 1e-9:
        return None
    if surf[(K, 0)]["cov"] >= target_cov - 1e-9:
        return 0
    lo, hi = 0, len(ref)  # at this allowance every reference query may be lost
    while hi - lo > 1:
        mid = (lo + hi) // 2
        achieved = solve_cached(planner, surf, K, mid, ref)["cov"]
        if achieved >= target_cov - 1e-9:
            hi = mid
        else:
            lo = mid
    return hi


def exact_menu(planner, surf, ref, ref_cov, Kmax, targets):
    """Exact finite Pareto frontier, including allowances outside plot grid."""
    menu = {}
    for g in targets:
        feas = []
        for K in range(Kmax + 1):
            L = minimum_allowance(planner, surf, K, ref_cov + g, ref)
            if L is not None:
                feas.append((K, L))
        menu[g] = [p for p in feas if not any(
            q != p and q[0] <= p[0] and q[1] <= p[1] for q in feas
        )]
    return menu


def metrics(surf, ref_cov, Kmax, targets, exact_lump, menu):
    cov = lambda K, L: surf[(K, L)]["cov"]
    m = dict(cov_ref=ref_cov, cov_unr=cov(Kmax, INF), cov_prot=cov(Kmax, 0))
    m["gain_unr"], m["gain_prot"] = m["cov_unr"] - ref_cov, m["cov_prot"] - ref_cov
    m["coord_gain_unr"] = cov(Kmax, INF) - cov(0, INF)
    m["pop"] = m["cov_unr"] - m["cov_prot"]
    m["pop_share"] = (100.0 * m["pop"] / m["coord_gain_unr"]
                      if m["coord_gain_unr"] > 1e-9 else float("nan"))
    lump = exact_lump
    m["lump_L"] = lump
    m["lump_gain"] = (cov(Kmax, lump) - cov(Kmax, 0)) if lump is not None else float("nan")
    m["lump_gross_gain"] = (surf[(Kmax, lump)]["gross_gains"] - surf[(Kmax, 0)]["gross_gains"]
                             if lump is not None else float("nan"))
    m["losses_at_lump"] = (surf[(Kmax, lump)]["losses"] if lump is not None else None)
    # Gross new opportunities, not net coverage change, per opportunity lost.
    m["exchange"] = (m["lump_gross_gain"] / m["losses_at_lump"]
                     if m["losses_at_lump"] else float("nan"))
    m["net_exchange"] = (m["lump_gain"] / m["losses_at_lump"]
                         if m["losses_at_lump"] else float("nan"))
    m["gross_gains_unr"], m["losses_unr"] = surf[(Kmax, INF)]["gross_gains"], surf[(Kmax, INF)]["losses"]
    m["avg_exchange"] = m["gross_gains_unr"] / m["losses_unr"] if m["losses_unr"] else float("nan")
    # C(K,0) is nondecreasing in K by construction, so Kmax is its maximum.
    m["max_gain_prot"] = cov(Kmax, 0) - ref_cov
    for g in targets:
        m[f"minK_unr_{g}"] = next((K for K in range(Kmax + 1) if cov(K, INF) >= ref_cov + g - 1e-9), None)
        m[f"minK_prot_{g}"] = next((K for K in range(Kmax + 1) if cov(K, 0) >= ref_cov + g - 1e-9), None)
    # With unit query weights, this is the first *integer* gain that cannot
    # be achieved under full protection at any reassignment budget.
    m["first_infeasible"] = int(round(m["max_gain_prot"])) + 1
    m["menu"] = menu
    return m


ONES = ["Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve",
        "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def words(n):
    n = int(round(n))
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + (ONES[n % 10] if n % 10 else "")
    return "X" + "".join(ONES[int(d)] for d in str(n))


def fmt(v, nd=0):
    if v is None:
        return "--"
    if isinstance(v, float) and math.isnan(v):
        return "n/a"
    return f"{v:.{nd}f}" if nd else f"{int(round(v))}"


def rng(vals, nd=0):
    vals = [v for v in vals if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if not vals:
        return "n/a"
    lo, hi = min(vals), max(vals)
    return fmt(lo, nd) if abs(hi - lo) < 1e-9 else f"{fmt(lo, nd)}--{fmt(hi, nd)}"


def plot_frontier(surfaces, cfg, Kmax, path):
    depths, Lgrid, mo = cfg["cut_depths"], cfg["loss_budgets"], cfg["main_offset"]
    fig, axes = plt.subplots(1, len(depths), figsize=(3.3 * len(depths), 3.0), sharey=True)
    axes = np.atleast_1d(axes)
    # Numeric spacing for finite allowances; the last point denotes no cap.
    xmax = max(Lgrid)
    xs = list(Lgrid) + [xmax + 2]
    ticks = sorted(set([0, xmax] + list(range(0, xmax + 1, max(1, math.ceil(xmax / 4))))))
    for ax, depth in zip(axes, depths):
        surf, ref_cov = surfaces[(mo, depth, "opt")]
        # Several reassignment budgets can have exactly the same frontier.
        # Plot each *distinct* curve only once to avoid seven overlapping
        # traces and an unreadable legend in the small-format manuscript.
        distinct = {}
        for K in range(Kmax + 1):
            ys = [surf[(K, L)]["cov"] - ref_cov for L in Lgrid] + [surf[(K, INF)]["cov"] - ref_cov]
            distinct.setdefault(tuple(ys), []).append(K)
        for i, (ys, ks) in enumerate(distinct.items()):
            label = (f"$K={ks[0]}$" if len(ks) == 1 else
                     f"$K={ks[0]}$--${ks[-1]}$")
            color = ["#355c7d", "#c05a3a", "#3f8069", "#8165a4"][i % 4]
            ax.step(xs, ys, where="post", color=color, lw=1.9, label=label)
            ax.scatter([xs[0], xs[-1]], [ys[0], ys[-1]], color=color, s=9, zorder=3)
        ax.axvline(x=xmax + 1, ls=":", lw=0.7, color="gray")
        ax.set_xticks(ticks + [xmax + 2])
        ax.set_xticklabels([str(t) for t in ticks] + [r"$\infty$"], fontsize=7)
        ax.set_title(f"{int(round(depth * 100))}% cut", fontsize=9)
        ax.set_xlabel("Loss allowance $L$", fontsize=8)
        ax.grid(axis="y", color="#dddddd", linewidth=0.4)
    axes[0].set_ylabel("Gain over reference (queries)", fontsize=8)
    axes[-1].legend(fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="out")
    args = ap.parse_args()
    cfg = dict(DEFAULT_CONFIG)
    cpath = os.path.join(args.data, "config.json")
    if os.path.exists(cpath):
        with open(cpath, encoding="utf-8") as f:
            cfg.update(json.load(f))
    cfg["loss_budgets"] = sorted(set(int(L) for L in cfg["loss_budgets"]))
    os.makedirs(args.out, exist_ok=True)

    trips, transfers, queries, weights = load(args.data)
    bus = {t: tr for t, tr in trips.items() if tr["mode"] == "bus"}
    routes = sorted({tr["route"] for tr in bus.values()})
    o0, by_route = {}, defaultdict(list)
    for t, tr in bus.items():
        o0.setdefault(tr["route"], tr["op"])
        if o0[tr["route"]] != tr["op"]:
            sys.exit(f"route unit {tr['route']} has two operators")
        if tr["op"] not in cfg["operators"]:
            sys.exit(f"operator {tr['op']} missing from config")
        by_route[tr["route"]].append(t)
    elig = [r for r in routes if r in set(cfg["eligible_route_units"])]
    Kmax = len(elig)
    if Kmax == 0:
        print("warning: no eligible route units; set eligible_route_units in config.json")

    t0 = time.time()
    dep_idx = departure_index(trips)
    support = [enumerate_support(q, trips, dep_idx, transfers, cfg) for q in queries]
    full_cov = sum(w for S, w in zip(support, weights) if S)
    print(f"reachability: {len(queries)} queries, {full_cov:g} reachable with the full timetable, "
          f"{sum(len(S) for S in support)} minimal trip sets, {time.time() - t0:.1f}s")

    records, ref_rows, surfaces, analysis_aux = [], [], {}, {}
    planner_main, packages_main = None, None
    Lgrid, depths, mo = cfg["loss_budgets"], cfg["cut_depths"], cfg["main_offset"]
    n_solves = 0
    for offset in cfg["offsets"]:
        packages = build_packages(by_route, trips, cfg["levels"], offset, cfg["turnaround_minutes"])
        full_h = {o: sum(packages[r][-1]["hours"] for r in routes if o0[r] == o) for o in cfg["operators"]}
        planner = Planner(cfg, packages, o0, support, weights)
        if offset == mo:
            planner_main, packages_main = planner, packages
        for depth in depths:
            planner.caps_h = {o: (1.0 - depth) * full_h[o] for o in full_h}
            if offset == mo:
                sols, distinct = enumerate_optima(planner, cfg["max_alt_optima"])
            else:
                s = planner.solve(0, INF)
                sols, distinct = [s], [s]
            refs = [("opt", distinct[0])] + [(f"alt{i}", d) for i, d in enumerate(distinct[1:], 1)]
            refs.append(("rule", planner.rule_reference()))
            for name, rsol in refs:
                ref, ref_cov = rsol["reach"], rsol["cov"]
                row = dict(offset=offset, depth=depth, reference=name, cov=ref_cov, n_trips=rsol["n_trips"],
                           n_alt_optima=len(sols), n_alt_distinct=len(distinct))
                row.update({f"hours_{o}": round(rsol["hours"][o], 3) for o in planner.ops})
                row.update({f"veh_{o}": rsol["veh"][o] for o in planner.ops})
                ref_rows.append(row)
                surf = {}
                # Only the base reference at the main offset needs the full
                # K x L surface and exact target-gain menu. Every alternative
                # reference and other phase still receives *exact* prices and
                # first-effective allowances via monotone search.
                sensitivity_only = (cfg.get("sensitivity_summaries_only", True) and
                                    (offset != mo or name != "opt"))
                K_values = sorted({0, Kmax}) if sensitivity_only else range(Kmax + 1)
                L_values = [0] if sensitivity_only else Lgrid
                for K in K_values:
                    unr = planner.solve(K, INF, ref)
                    surf[(K, INF)] = unr
                    for L in L_values:
                        surf[(K, L)] = unr if L >= unr["losses"] else planner.solve(K, L, ref)
                    for L in list(L_values) + [INF]:
                        r_ = surf[(K, L)]
                        rec = dict(offset=offset, depth=depth, reference=name, ref_cov=ref_cov, K=K,
                                   L=("inf" if L is INF else L), cov=r_["cov"], gain=r_["cov"] - ref_cov,
                                   gross_gains=r_["gross_gains"], losses=r_["losses"], n_trips=r_["n_trips"],
                                   reassigned=" ".join(r_["reassigned"]))
                        rec.update({f"hours_{o}": round(r_["hours"][o], 3) for o in planner.ops})
                        rec.update({f"veh_{o}": r_["veh"][o] for o in planner.ops})
                        records.append(rec)
                lump = minimum_allowance(planner, surf, Kmax, surf[(Kmax, 0)]["cov"] + 1, ref)
                menu = ({} if sensitivity_only else
                        exact_menu(planner, surf, ref, ref_cov, Kmax, cfg["target_gains"]))
                analysis_aux[(offset, depth, name)] = (lump, menu)
                # Make an exact threshold beyond the display grid inspectable
                # in coverage.csv, without computing all intervening points.
                if lump is not None and lump not in Lgrid:
                    r_ = surf[(Kmax, lump)]
                    rec = dict(offset=offset, depth=depth, reference=name, ref_cov=ref_cov, K=Kmax,
                               L=lump, cov=r_["cov"], gain=r_["cov"] - ref_cov,
                               gross_gains=r_["gross_gains"], losses=r_["losses"], n_trips=r_["n_trips"],
                               reassigned=" ".join(r_["reassigned"]))
                    rec.update({f"hours_{o}": round(r_["hours"][o], 3) for o in planner.ops})
                    rec.update({f"veh_{o}": r_["veh"][o] for o in planner.ops})
                    records.append(rec)
                surfaces[(offset, depth, name)] = (surf, ref_cov)
            print(f"offset {offset} depth {depth:.2f}: {len(refs)} references, "
                  f"{planner.n_solves} solves so far ({time.time() - t0:.0f}s)")
        n_solves += planner.n_solves

    def write_csv(path, rows):
        if not rows:
            return
        keys = []
        for r in rows:
            keys += [k for k in r if k not in keys]
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)

    write_csv(os.path.join(args.out, "coverage.csv"), records)
    write_csv(os.path.join(args.out, "references.csv"), ref_rows)

    targets = cfg["target_gains"]
    M = {key: metrics(surf, ref_cov, Kmax,
                      [] if (key[0] != mo or key[2] != "opt") and
                      cfg.get("sensitivity_summaries_only", True) else targets,
                      *analysis_aux[key])
         for key, (surf, ref_cov) in surfaces.items()}
    mrows, menu_rows = [], []
    inf_tex = r"$\infty$"
    for (offset, depth, name), m in sorted(M.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
        row = dict(offset=offset, depth=depth, reference=name)
        row.update({k: v for k, v in m.items() if k != "menu"})
        mrows.append(row)
        for g, pairs in m["menu"].items():
            menu_rows.append(dict(offset=offset, depth=depth, reference=name, target=g,
                                  pairs="; ".join(f"({K}, {'inf' if L is INF else L})" for K, L in pairs)))
    write_csv(os.path.join(args.out, "metrics.csv"), mrows)
    write_csv(os.path.join(args.out, "menu.csv"), menu_rows)

    tab = [r"\begin{table}[H]", r"\centering", r"\small",
           r"\caption{Pareto-minimal (reassignments $K$, allowance $L$) for each net coverage target; "
           r"optimized reference, offset 0. `None' indicates an unattainable target.}",
           r"\label{tab:menu}", r"\begin{tabularx}{\linewidth}{@{}l*{3}{>{\centering\arraybackslash}X}@{}}",
           r"\toprule", r"Cut depth & Gain $+2$ & Gain $+4$ & Gain $+5$\\", r"\midrule"]
    for depth in depths:
        m = M[(mo, depth, "opt")]
        cells = []
        for g in targets:
            pairs = "; ".join("(" + str(K) + ", " + (inf_tex if L is INF else str(L)) + ")" for K, L in m["menu"][g])
            cells.append(pairs or "none")
        tab.append(f"{int(round(depth * 100))}\\% & " + " & ".join(cells) + r"\\")
    tab += [r"\bottomrule", r"\end{tabularx}", r"\end{table}"]
    with open(os.path.join(args.out, "tab_menu.tex"), "w", encoding="utf-8") as f:
        f.write("\n".join(tab) + "\n")

    lines = []
    mac = lambda name, val: lines.append(f"\\newcommand{{\\{name}}}{{{val}}}")
    mac("nQueries", len(queries)); mac("covFull", fmt(full_cov)); mac("nRouteUnits", len(routes))
    mac("nTrips", len(bus)); mac("nEligible", Kmax); mac("nOffsets", len(cfg["offsets"]))
    mac("nLevels", cfg["levels"]); mac("nPackages", sum(len(packages_main[r]) for r in routes))
    mac("nOptions", planner_main.J); mac("nSolves", n_solves)
    g1 = targets[0]
    price_bits, threshold_bits = [], []
    for depth in depths:
        D = words(depth * 100)
        m = M[(mo, depth, "opt")]
        mr = M[(mo, depth, "rule")]
        alts = [M[k] for k in M if k[0] == mo and k[1] == depth and (k[2] == "opt" or k[2].startswith("alt"))]
        offs = [M[k] for k in M if k[1] == depth and k[2] == "opt"]
        mac("covRef" + D, fmt(m["cov_ref"])); mac("covRule" + D, fmt(mr["cov_ref"])); mac("nAlt" + D, len(alts))
        mac("covUnr" + D, fmt(m["cov_unr"])); mac("covProt" + D, fmt(m["cov_prot"]))
        mac("gainUnr" + D, fmt(m["gain_unr"])); mac("gainProt" + D, fmt(m["gain_prot"]))
        mac("coordGain" + D, fmt(m["coord_gain_unr"]))
        mac("pop" + D, fmt(m["pop"])); mac("popShare" + D, fmt(m["pop_share"]))
        if m["coord_gain_unr"] > 1e-9:
            price_sentence = (f"At a {int(round(depth * 100))}\\% cut, unrestricted reassignment "
                              f"adds {fmt(m['coord_gain_unr'])} reachable queries over the "
                              f"$K=0$ optimum; full protection forgoes {fmt(m['pop'])} "
                              f"({fmt(m['pop_share'])}\\% of that gain).")
        else:
            price_sentence = (f"At a {int(round(depth * 100))}\\% cut, reassignment "
                              f"does not improve the $K=0$ optimum; the percentage "
                              f"price of protection is undefined.")
        mac("priceSentence" + D, price_sentence)
        mac("abstractFinding" + D, price_sentence)
        if m["coord_gain_unr"] > 1e-9:
            price_bits.append(f"{int(round(depth * 100))}\\%: reassignment +{fmt(m['coord_gain_unr'])}, "
                              f"protection cost {fmt(m['pop'])} ({fmt(m['pop_share'])}\\%)")
        else:
            price_bits.append(f"{int(round(depth * 100))}\\%: no reassignment gain")
        mac("popShareRange" + D, rng([x["pop_share"] for x in offs]))
        mac("popShareMed" + D, fmt(statistics.median([x["pop_share"] for x in offs
                                                      if not math.isnan(x["pop_share"])] or [float("nan")])))
        mac("popShareRule" + D, fmt(mr["pop_share"])); mac("popShareAltRange" + D, rng([x["pop_share"] for x in alts]))
        if m["coord_gain_unr"] > 1e-9:
            valid_offs = [x["pop_share"] for x in offs if not math.isnan(x["pop_share"])]
            missing_offs = len(offs) - len(valid_offs)
            phase_phrase = (f"{rng(valid_offs)}\\% across {len(valid_offs)} phases with a gain"
                            if missing_offs else f"{rng(valid_offs)}\\% across all phases")
            if missing_offs:
                phase_phrase += f" ({missing_offs} undefined)"
            robustness_sentence = (f"At a {int(round(depth * 100))}\\% cut, the percentage price is "
                                   f"{phase_phrase} and {rng([x['pop_share'] for x in alts])}\\% "
                                   f"over the examined optimal references; it is "
                                   f"{fmt(mr['pop_share'])}\\% for the rule-based reference.")
        else:
            robustness_sentence = ("The percentage price cannot be compared across "
                                   "phases and references when reassignment has zero gain.")
        mac("robustnessSentence" + D, robustness_sentence)
        mac("lumpL" + D, fmt(m["lump_L"])); mac("lumpGain" + D, fmt(m["lump_gain"]))
        mac("lumpGross" + D, fmt(m["lump_gross_gain"])); mac("lumpLosses" + D, fmt(m["losses_at_lump"]))
        mac("exchange" + D, fmt(m["exchange"], 1)); mac("lumpRange" + D, rng([x["lump_L"] for x in offs]))
        mac("netExchange" + D, fmt(m["net_exchange"], 1))
        if m["lump_L"] is None:
            threshold_sentence = "No allowance improves on full protection at this cut depth."
            threshold_bits.append(f"{int(round(depth * 100))}\\%: no improvement")
        else:
            threshold_sentence = (f"The first improvement occurs at $L={fmt(m['lump_L'])}$: "
                                  f"gross gains rise by {fmt(m['lump_gross_gain'])} queries "
                                  f"and {fmt(m['losses_at_lump'])} reference queries are lost "
                                  f"(net gain {fmt(m['lump_gain'])}).")
            threshold_bits.append(f"{int(round(depth * 100))}\\%: "
                                  f"$L^*={fmt(m['lump_L'])}$, "
                                  f"gross gain +{fmt(m['lump_gross_gain'])}, "
                                  f"losses {fmt(m['losses_at_lump'])}, "
                                  f"net gain +{fmt(m['lump_gain'])}")
        mac("thresholdSentence" + D, threshold_sentence)
        if m["lump_L"] is None:
            exchange_sentence = "No first-threshold exchange rate is defined at this cut depth."
        else:
            exchange_sentence = (f"At a {int(round(depth * 100))}\\% cut, "
                                 f"the first-threshold exchange rate is "
                                 f"{fmt(m['exchange'], 1)} gross gains "
                                 f"per reference query lost.")
        mac("exchangeSentence" + D, exchange_sentence)
        mac("lumpLRule" + D, fmt(mr["lump_L"])); mac("lumpLAltRange" + D, rng([x["lump_L"] for x in alts]))
        mac("gainsAtUnr" + D, fmt(m["gross_gains_unr"])); mac("lossesAtUnr" + D, fmt(m["losses_unr"]))
        mac("avgExchange" + D, fmt(m["avg_exchange"], 1))
        mac("minKunr" + D, fmt(m[f"minK_unr_{g1}"])); mac("minKprot" + D, fmt(m[f"minK_prot_{g1}"]))
        mac("maxGainProt" + D, fmt(m["max_gain_prot"])); mac("firstInfeasible" + D, fmt(m["first_infeasible"]))
        mac("scopeSentence" + D,
            f"At a {int(round(depth * 100))}\\% cut, full protection caps the gain "
            f"at {fmt(m['max_gain_prot'])} queries; a larger target requires an allowance, "
            f"regardless of reassignment scope.")
    mac("priceOverview", "For the phase-0 optimized reference, full-protection prices are: "
        + "; ".join(price_bits) + ".")
    mac("thresholdOverview", "The corresponding first-effective allowances are: "
        + "; ".join(threshold_bits) + ".")
    with open(os.path.join(args.out, "results.tex"), "w", encoding="utf-8") as f:
        f.write("% written by hold_harmless.py\n" + "\n".join(lines) + "\n")

    plot_frontier(surfaces, cfg, Kmax, os.path.join(args.out, "fig_frontier.pdf"))
    print(f"done: {n_solves} solves, outputs in {args.out} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
