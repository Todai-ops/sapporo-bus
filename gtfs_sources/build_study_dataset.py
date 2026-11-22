#!/usr/bin/env python3
"""Reconstruct a reproducible eight-route Sapporo pilot from public GTFS.

The selection and interchange assumptions are explicit below. This creates a
new, well-defined pilot; it cannot recover the unknown design used in the
original manuscript without its absent route-selection file.
"""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from io import TextIOWrapper
from pathlib import Path
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "sapporo_reconstruction" / "data"
BUS_DAY = "20261109"       # Monday inside both 2026 GTFS validity windows
SUBWAY_DAY = "20200203"    # Monday inside published 2020 subway feed window

# Entire official route IDs are units: no hand-selected or invented trips.
ROUTES = {
    "R011800001": ("B_MARUYAMA", "Bankei", "円山線"),
    "R011800002": ("B_HASSAMU", "Bankei", "発寒南・真駒内線"),
    "R011800836": ("B_KOMAOKA", "Bankei", "駒岡線"),
    "R010800826": ("J_N95", "Jotetsu", "南95 真駒内駅〜硬石山"),
    "R010800829": ("J_N96", "Jotetsu", "南96 真駒内駅〜中の沢"),
    "R010800031": ("J_N97", "Jotetsu", "南97 真駒内駅〜山水団地前"),
    "R010800032": ("J_N98", "Jotetsu", "南98 真駒内駅〜道路管理事務所"),
    "R010800007": ("J_12_FUJINO", "Jotetsu", "12 真駒内駅〜藤野4条11丁目"),
}

SUBWAY_ROUTE_IDS = {"920001", "920002", "920003", "920004"}
ELIGIBLE = ["B_HASSAMU", "B_KOMAOKA", "J_N95", "J_N96", "J_N97", "J_N98", "J_12_FUJINO"]

# All stop locations sharing a name are treated as one transfer node, and the
# following explicit station-name aliases connect bus and subway feeds. The
# MILP adds five-minute transfer margins after every transit alighting.
STOP_ALIASES = {
    "地下鉄真駒内駅": "真駒内駅",
    "真駒内": "真駒内駅",
    "円山公園駅前": "円山公園駅",
    "円山公園": "円山公園駅",
    "地下鉄発寒南駅": "発寒南駅",
    "発寒南": "発寒南駅",
    "さっぽろ": "札幌駅",
}

ORIGINS = [
    "盤渓", "恵開拓記念碑前", "発寒南駅", "ばんけいの森テニスコート",
    "硬石山", "中の沢", "山水団地前", "道路管理事務所",
    "藤野４条十一丁目", "真駒内駅", "円山公園駅",
]
DESTINATIONS = ["真駒内駅", "円山公園駅", "大通", "札幌駅", "発寒南駅"]
DEPARTURE_HOURS = range(6, 22)  # 06:00--21:00 inclusive

SOURCES = [
    ("bankei_bus.zip", "bus", BUS_DAY, "Bankei"),
    ("joutetsu.zip", "bus", BUS_DAY, "Jotetsu"),
    ("sapporo_subway.zip", "subway", SUBWAY_DAY, "Sapporo Subway"),
]
SOURCE_URLS = {
    "bankei_bus.zip": "https://ckan.hoda.jp/dataset/24d1dd70-5395-4d6b-b41f-0d83e8eabdb9/resource/889906b8-eb1a-41c3-a7b3-75cd69aa891f/download/bankei_bus.zip",
    "joutetsu.zip": "https://ckan.hoda.jp/dataset/24d1dd70-5395-4d6b-b41f-0d83e8eabdb9/resource/fef98fef-6fe2-472f-bde3-9d4f0a509a4a/download/joutetsu.zip",
    "sapporo_subway.zip": "https://ckan.hoda.jp/dataset/24d1dd70-5395-4d6b-b41f-0d83e8eabdb9/resource/3efff7e5-b604-4850-8888-38f0e60bb238/download/gtfs_sapporo1.000.zip",
}


def table(archive, name):
    return list(csv.DictReader(TextIOWrapper(archive.open(name), encoding="utf-8-sig")))


def active_services(archive, yyyymmdd):
    day = datetime.strptime(yyyymmdd, "%Y%m%d").strftime("%A").lower()
    active = {r["service_id"] for r in table(archive, "calendar.txt")
              if r[day] == "1" and r["start_date"] <= yyyymmdd <= r["end_date"]}
    for r in table(archive, "calendar_dates.txt"):
        if r["date"] == yyyymmdd:
            if r["exception_type"] == "1":
                active.add(r["service_id"])
            elif r["exception_type"] == "2":
                active.discard(r["service_id"])
    return active


def canonical_stop(name):
    name = name.strip()
    return STOP_ALIASES.get(name, name)


def write_csv(path, header, records):
    with path.open("w", encoding="utf-8", newline="") as file:
        out = csv.writer(file)
        out.writerow(header)
        out.writerows(records)


def hhmm(s):
    h, m, sec = map(int, s.split(":"))
    if sec != 0:
        raise ValueError(f"nonzero GTFS seconds are not handled: {s}")
    return f"{h:02d}:{m:02d}"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    trips_out, stop_times_out = [], []
    feed_audit, names = [], set()
    for filename, mode, day, provider in SOURCES:
        path = HERE / filename
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        with ZipFile(path) as archive:
            services = active_services(archive, day)
            stops = {r["stop_id"]: canonical_stop(r["stop_name"])
                     for r in table(archive, "stops.txt")}
            route_names = {r["route_id"]: r["route_long_name"]
                           for r in table(archive, "routes.txt")}
            info = table(archive, "feed_info.txt")[0]
            tripmap = {}
            for r in table(archive, "trips.txt"):
                if r["service_id"] not in services:
                    continue
                rid = r["route_id"]
                if mode == "bus" and (rid not in ROUTES or ROUTES[rid][1] != provider):
                    continue
                if mode == "subway" and rid not in SUBWAY_ROUTE_IDS:
                    continue
                trip_id = ("S_" if mode == "subway" else "B_" if provider == "Bankei" else "J_") + r["trip_id"]
                route_unit = ROUTES[rid][0] if mode == "bus" else "SUBWAY_FIXED_" + rid
                tripmap[r["trip_id"]] = trip_id
                trips_out.append([trip_id, route_unit, provider if mode == "bus" else "Subway", mode])
            seen = Counter()
            selected_route_ids = sorted({r["route_id"] for r in table(archive, "trips.txt")
                                         if r["trip_id"] in tripmap})
            for r in table(archive, "stop_times.txt"):
                key = tripmap.get(r["trip_id"])
                if key is None:
                    continue
                stop = stops[r["stop_id"]]
                names.add(stop)
                stop_times_out.append([key, int(r["stop_sequence"]), stop,
                                       hhmm(r["arrival_time"]), hhmm(r["departure_time"])])
                seen[key] += 1
            if any(v < 2 for v in seen.values()) or len(seen) != len(tripmap):
                raise RuntimeError(f"missing stop_times for trips in {filename}")
            feed_audit.append({"filename": filename, "source_url": SOURCE_URLS[filename],
                               "sha256": sha, "publisher": info["feed_publisher_name"],
                               "valid_from": info["feed_start_date"],
                               "valid_to": info["feed_end_date"],
                               "sample_service_date": day, "selected_trips": len(tripmap),
                               "selected_gtfs_route_ids": selected_route_ids})
    missing_names = set(ORIGINS + DESTINATIONS) - names
    if missing_names:
        raise RuntimeError(f"query stops missing from built feed: {sorted(missing_names)}")
    # Exclude zero-length OD queries: origin == destination is trivially
    # reachable without service and would inflate coverage by 48 observations.
    queries = [[o, d, f"{hour:02d}:00"]
               for o in ORIGINS for d in DESTINATIONS if o != d
               for hour in DEPARTURE_HOURS]
    write_csv(OUT / "trips.csv", ["trip_id", "route_unit", "operator", "mode"], trips_out)
    write_csv(OUT / "stop_times.csv", ["trip_id", "seq", "stop_id", "arr", "dep"], stop_times_out)
    write_csv(OUT / "queries.csv", ["origin_stop", "dest_stop", "dep_time"], queries)
    # Names are identified as co-located platforms; there are no additional
    # pedestrian transfer links outside identically named nodes.
    config = {
        "operators": {"Bankei": {"vehicle_cap": 4}, "Jotetsu": {"vehicle_cap": 23}},
        "eligible_route_units": ELIGIBLE,
        "levels": 8,
        "offsets": list(range(8)),
        "main_offset": 0,
        "cut_depths": [0.1, 0.2, 0.3],
        "loss_budgets": list(range(21)),
        "max_alt_optima": 25,
        "target_gains": [2, 4, 5],
        "mip_rel_gap": 1e-9,
    }
    (OUT / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audit = {
        "description": "Illustrative 8-route composite reconstructed from official GTFS feeds",
        "bus_date": BUS_DAY, "subway_date": SUBWAY_DAY,
        "routes": [{"gtfs_route_id": rid, "route_unit": unit, "operator": op, "name": name,
                    "eligible_for_reassignment": unit in ELIGIBLE}
                   for rid, (unit, op, name) in ROUTES.items()],
        "subway_gtfs_routes": sorted(SUBWAY_ROUTE_IDS),
        "station_aliases": STOP_ALIASES,
        "query_origins": ORIGINS, "query_destinations": DESTINATIONS,
        "query_times": [f"{h:02d}:00" for h in DEPARTURE_HOURS],
        "origin_equals_destination_excluded": True,
        "same_name_stops_collapsed": True, "walk_transfers_beyond_same_name": False,
        "number_of_queries": len(queries), "bus_trip_count": sum(1 for row in trips_out if row[3] == "bus"),
        "subway_trip_count": sum(1 for row in trips_out if row[3] == "subway"),
        "feeds": feed_audit,
        "limitation": "The 2020 subway feed is not contemporaneous with 2026 bus schedules; this is a hypothetical composite, not a deployable operating plan. GTFS route and query selection is newly specified, not recovered from the earlier paper.",
    }
    (OUT / "provenance.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"generated {len(trips_out)} trips ({audit['bus_trip_count']} bus, "
          f"{audit['subway_trip_count']} subway), {len(stop_times_out)} stop_times, "
          f"{len(queries)} queries; {len(names)} stops")
    for row in feed_audit:
        print(row["filename"], "trip count", row["selected_trips"], "source SHA256", row["sha256"][:12])


if __name__ == "__main__":
    main()
