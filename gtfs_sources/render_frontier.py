#!/usr/bin/env python3
"""Regenerate the publication frontier figure from saved exact solve records.

This operation does not re-solve any integer programs. To regenerate both
the CSVs and figures from GTFS, execute the full hold_harmless.py workflow.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "revised"))
from hold_harmless import DEFAULT_CONFIG, plot_frontier

DATA = ROOT / "sapporo_reconstruction" / "data"
ANALYSIS = ROOT / "sapporo_reconstruction" / "final_analysis"


def main():
    config = dict(DEFAULT_CONFIG)
    config.update(json.loads((DATA / "config.json").read_text(encoding="utf-8")))
    grouped = {}
    with (ANALYSIS / "coverage.csv").open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if int(row["offset"]) != config["main_offset"] or row["reference"] != "opt":
                continue
            depth = float(row["depth"])
            if depth not in config["cut_depths"]:
                continue
            if depth not in grouped:
                grouped[depth] = ({}, float(row["ref_cov"]))
            surface, ref = grouped[depth]
            assert float(row["ref_cov"]) == ref
            allowance = None if row["L"] == "inf" else int(row["L"])
            surface[(int(row["K"]), allowance)] = {"cov": float(row["cov"])}
    surfaces = {(config["main_offset"], d, "opt"): result for d, result in grouped.items()}
    plot_frontier(surfaces, config, len(config["eligible_route_units"]), ANALYSIS / "fig_frontier.pdf")
    print("Regenerated concise frontier PDF from exact coverage.csv")


if __name__ == "__main__":
    main()
