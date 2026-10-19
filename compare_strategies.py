"""Extend the SAME HydraulicModel to three comparison loads and sensitivity.

Run python compare_strategies.py. No third-party numerical dependencies.
All inputs, including profile and pressure floor, live in assumptions.json.
An infeasible thermal duty never receives a fictional annual energy value.
"""

import csv
from copy import deepcopy
import hashlib
from itertools import product
import json
from pathlib import Path
from hydraulic_model import HydraulicModel

from project_paths import ROOT, RESULTS
HERE = ROOT
STRATEGIES = ("fixed", "variable")


def solve(model, load, strategy, available):
    method = model.controlled_fixed_speed if strategy == "fixed" else model.controlled_variable_speed
    try:
        point = method(load, available)
        point.update({"strategy": strategy, "feasible": point["within_declared_envelope"],
                      "speed_rpm": point["speed_fraction"] * model.p["nominal_speed_rpm"]})
        return point
    except ValueError as error:
        # Report unmet duty explicitly. No achieved flow/power is invented.
        return {"strategy": strategy, "load_fraction": load,
                "required_flow_m3_h": model.required_flow(load)*3600,
                "required_flow_m3_s": model.required_flow(load),
                "available_pump_ids": available, "feasible": False,
                "achieved_flow_m3_h": None, "electrical_power_kW": None,
                "reasons": [str(error)]}


def normal_cases(assumptions):
    model = HydraulicModel(assumptions)
    ids = [f"P{i+1}" for i in range(model.p["installed_count"])]
    return [solve(model, load, strategy, ids)
            for strategy in STRATEGIES for load in assumptions["comparison"]["load_fractions"]]


def annual_energy(points, hours, loads):
    if len(hours) != len(loads) or any(h < 0 for h in hours) or sum(hours) != 8760:
        raise ValueError("Annual profile must match load bins and sum to exactly 8760 hours")
    invalid = [p for p in points if not p["feasible"]]
    if invalid:
        return {"comparable": False, "hours": hours,
                "infeasible_duties": [{"strategy": p["strategy"], "load_fraction": p["load_fraction"]} for p in invalid],
                "fixed_kWh": None, "variable_kWh": None, "savings_kWh": None, "savings_percent": None}
    energy, contributions = {}, {}
    for strategy in STRATEGIES:
        powers = [next(p["electrical_power_kW"] for p in points if p["strategy"]==strategy and p["load_fraction"]==load) for load in loads]
        contributions[strategy] = [power*h for power, h in zip(powers, hours)]
        energy[strategy] = sum(contributions[strategy])
    saving = energy["fixed"]-energy["variable"]
    return {"comparable": True, "hours": hours, "fixed_kWh": energy["fixed"],
            "variable_kWh": energy["variable"], "savings_kWh": saving,
            "savings_percent": 100*saving/energy["fixed"], "contributions_kWh": contributions}


def vary(base, resistance=1.0, floor=2.0, efficiency="reference"):
    a = deepcopy(base)
    a["network"]["resistance_multiplier"] = resistance
    a["control"]["terminal_min_differential_head_m"] = floor
    a["pumps"].update(base["comparison"]["sensitivity"]["efficiency_packages"][efficiency])
    return a


def main():
    raw = (HERE/"assumptions.json").read_bytes()
    a = json.loads(raw)
    model = HydraulicModel(a)
    loads, profiles = a["comparison"]["load_fractions"], a["comparison"]["annual_profiles"]
    normal = normal_cases(a)
    all_ids = [f"P{i+1}" for i in range(model.p["installed_count"])]
    outages = []
    for strategy in STRATEGIES:
        for load in loads:
            before = next(p for p in normal if p["strategy"]==strategy and p["load_fraction"]==load)
            for unavailable in all_ids:
                remaining = [p for p in all_ids if p != unavailable]
                point = solve(model, load, strategy, remaining)
                point.update({"unavailable_pump_id": unavailable,
                              "role_before_outage": ("running_duty" if unavailable in before["running_pump_ids"]
                                                     else "designated_standby" if unavailable==all_ids[-1]
                                                     else "idle_staged_duty"),
                              "running_before_outage": before["running_pump_ids"],
                              "case": f"{unavailable}_unavailable"})
                outages.append(point)
    for p in normal:
        p["case"] = "normal"
    annual = {name: annual_energy(normal, profile["hours"], loads) for name, profile in profiles.items()}

    config = a["comparison"]["sensitivity"]
    grid, settings = [], []
    for k, floor, efficiency in product(config["resistance_multipliers"], config["terminal_pressure_floors_m"], config["efficiency_packages"]):
        points = normal_cases(vary(a, k, floor, efficiency))
        settings.append({"resistance_multiplier": k, "terminal_floor_m": floor,
                         "efficiency_package": efficiency, "points": points})
        for profile_name, profile in profiles.items():
            grid.append({"resistance_multiplier": k, "terminal_floor_m": floor,
                         "efficiency_package": efficiency, "profile": profile_name,
                         **annual_energy(points, profile["hours"], loads)})

    named_specs = [
        ("Reference", 1.0, 2.0, "reference", "reference"),
        ("Resistance -20%", .8, 2.0, "reference", "reference"),
        ("Resistance +10%", 1.1, 2.0, "reference", "reference"),
        ("Terminal minimum 8 m", 1.0, 8.0, "reference", "reference"),
        ("Terminal minimum 12 m", 1.0, 12.0, "reference", "reference"),
        ("Adverse efficiencies", 1.0, 2.0, "adverse", "reference"),
        ("More partial-load hours", 1.0, 2.0, "reference", "partial_load_heavy"),
        ("More full-load hours", 1.0, 2.0, "reference", "full_load_heavy"),
        ("Combined unfavourable", 1.1, 8.0, "adverse", "full_load_heavy"),
        ("Resistance +25%: capacity challenge", 1.25, 2.0, "reference", "reference"),
        ("Terminal minimum 14 m: capacity challenge", 1.0, 14.0, "reference", "reference")
    ]
    named = []
    for name, k, floor, efficiency, profile in named_specs:
        inputs = vary(a, k, floor, efficiency)
        points = normal_cases(inputs)
        named.append({"name": name, "resistance_multiplier": k, "terminal_floor_m": floor,
                      "efficiency_package": efficiency, "profile": profile,
                      **annual_energy(points, profiles[profile]["hours"], loads), "points": points})

    # Challenge the inherited fewest-pumps policy without folding alternative
    # staging into the main energy result (which would confound the comparison).
    two_at_40 = model.variable_speed_candidate(.4, 2)
    alternative = {"description": "Two VSD pumps at 40%, same equations/limits; excluded from main annual totals",
                   "point": two_at_40,
                   "main_one_pump_kW": next(p["electrical_power_kW"] for p in normal if p["strategy"]=="variable" and p["load_fraction"]==.4)}
    challenge_model = HydraulicModel(vary(a, 1.25))
    high_resistance_capacity = challenge_model.diagnostic_point(2, challenge_model.R_valve_min)
    feasible_grid = [g for g in grid if g["comparable"]]
    envelope = {"cases_total": len(grid), "cases_comparable": len(feasible_grid),
                "cases_infeasible": len(grid)-len(feasible_grid),
                "min_savings_percent": min(g["savings_percent"] for g in feasible_grid),
                "max_savings_percent": max(g["savings_percent"] for g in feasible_grid),
                "min_savings_kWh": min(g["savings_kWh"] for g in feasible_grid),
                "max_savings_kWh": max(g["savings_kWh"] for g in feasible_grid),
                "positive_savings_cases": sum(g["savings_kWh"]>0 for g in feasible_grid),
                "interpretation": "Scenario range, not statistical confidence; infeasible duties excluded, never counted as savings"}
    output = {"assumptions_sha256": hashlib.sha256(raw).hexdigest(),
              "normal": normal, "single_pump_unavailable": outages,
              "annual_energy_profiles": annual, "named_sensitivity": named,
              "factorial_settings": settings, "factorial_energy_cases": grid,
              "sensitivity_envelope": envelope, "alternative_staging_challenge": alternative,
              "high_resistance_full_open_two_pump_capacity": high_resistance_capacity}
    (RESULTS/"comparison_results.json").write_text(json.dumps(output, indent=2, allow_nan=False), encoding="utf-8")
    columns = ["case", "strategy", "load_fraction", "unavailable_pump_id", "role_before_outage", "running_pump_ids",
               "feasible", "required_flow_m3_h", "achieved_flow_m3_h", "speed_rpm", "pump_head_m", "header_head_m",
               "terminal_differential_head_m", "valve_head_m", "valve_Kv_fraction_of_max", "pump_efficiency",
               "drive_efficiency", "electrical_power_kW"]
    with (RESULTS/"comparison_cases.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, columns, extrasaction="ignore")
        writer.writeheader()
        for point in normal+outages:
            row = dict(point)
            row["running_pump_ids"] = "+".join(point.get("running_pump_ids", []))
            writer.writerow(row)
    with (RESULTS/"sensitivity_cases.csv").open("w", newline="", encoding="utf-8") as f:
        columns = ["resistance_multiplier", "terminal_floor_m", "efficiency_package", "profile", "comparable", "fixed_kWh", "variable_kWh", "savings_kWh", "savings_percent"]
        writer = csv.DictWriter(f, columns, extrasaction="ignore")
        writer.writeheader(); writer.writerows(grid)
    for p in normal:
        print(f"{p['strategy']:8} {p['load_fraction']:.0%}: n={p.get('running_pumps')}, "
              f"rpm={p.get('speed_rpm',0):.2f}, flow={p.get('achieved_flow_m3_h',0):.3f}, "
              f"gross H={p.get('pump_head_m',0):.3f}, input={p.get('electrical_power_kW',0):.3f} kW")
    print("Annual reference:", annual["reference"])
    print("Sensitivity envelope:", envelope)
    for case in named:
        print(case["name"], "saving %", case["savings_percent"], "comparable", case["comparable"])


if __name__ == "__main__":
    main()
