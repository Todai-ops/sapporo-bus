"""Small deterministic regression test for the exact loss threshold and menu.

This is a synthetic unit test, not a reconstruction of the Sapporo case.
"""
import unittest

from hold_harmless import (
    INF, Planner, build_packages, exact_menu, metrics, minimum_allowance,
    solve_cached,
)


class ToyFrontierTest(unittest.TestCase):
    def test_identical_packages_keep_earliest_level(self):
        trips = {
            "a": {"stops": [("s", 360, 360), ("t", 370, 370)]}
        }
        packages = build_packages({"A": ["a"]}, trips, 8, 0, 5)
        self.assertEqual(len(packages["A"]), 1)
        self.assertEqual(packages["A"][0]["level"], 1)

    def test_loss_threshold_and_gross_exchange(self):
        cfg = {
            "operators": {
                "Bankei": {"vehicle_cap": 1},
                "Jotetsu": {"vehicle_cap": 1},
            },
            "eligible_route_units": ["A"],
            "mip_rel_gap": 1e-9,
        }
        packages = {
            "A": [
                dict(level=1, trips=frozenset({"a1"}), hours=1, vehicles=1),
                dict(level=2, trips=frozenset({"a1", "a2"}), hours=2, vehicles=1),
            ],
            "B": [dict(level=1, trips=frozenset({"b1"}), hours=2, vehicles=1)],
        }
        support = [
            [frozenset({"a1"})],
            [frozenset({"a2"})],
            [frozenset({"a2"})],
            [frozenset({"a2"})],
            [frozenset({"b1"})],
            [frozenset({"b1"})],
        ]
        planner = Planner(cfg, packages, {"A": "Bankei", "B": "Jotetsu"}, support, [1] * 6)
        planner.caps_h = {"Bankei": 1, "Jotetsu": 2}
        ref_plan = planner.solve(0, INF)
        self.assertEqual(ref_plan["cov"], 3)
        ref = ref_plan["reach"]
        surface = {(K, L): planner.solve(K, L, ref)
                   for K in (0, 1) for L in (0, 1, 2, INF)}
        self.assertEqual(surface[(1, INF)]["cov"], 4)
        self.assertEqual(surface[(1, 0)]["cov"], 3)
        self.assertEqual(surface[(1, 1)]["cov"], 3)

        threshold = minimum_allowance(planner, surface, 1, 4, ref)
        self.assertEqual(threshold, 2)
        self.assertEqual(solve_cached(planner, surface, 1, threshold, ref)["losses"], 2)
        menu = exact_menu(planner, surface, ref, 3, 1, [1, 2])
        self.assertEqual(menu[1], [(1, 2)])
        self.assertEqual(menu[2], [])

        report = metrics(surface, 3, 1, [1, 2], threshold, menu)
        self.assertEqual(report["pop"], 1)
        self.assertEqual(report["coord_gain_unr"], 1)
        self.assertEqual(report["pop_share"], 100)
        self.assertEqual(report["lump_gain"], 1)
        self.assertEqual(report["lump_gross_gain"], 3)
        self.assertEqual(report["losses_at_lump"], 2)
        self.assertEqual(report["exchange"], 1.5)
        self.assertEqual(report["net_exchange"], 0.5)
        self.assertEqual(report["first_infeasible"], 1)


if __name__ == "__main__":
    unittest.main()
