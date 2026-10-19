"""Independent algebraic and dimensional checks against saved solver output.

Run after hydraulic_model.py. No third-party dependencies.
The checks do not import the hydraulic model or call its head/power functions.
Published water-property verification points check the small property function.
"""

import hashlib
import json
from math import isclose, sqrt
from pathlib import Path
from water_properties import water_cp_at_0p1_MPa


def main():
    here = Path(__file__).resolve().parent
    from project_paths import RESULTS
    a = json.loads((here / "assumptions.json").read_text(encoding="utf-8"))
    r = json.loads((RESULTS / "baseline_results.json").read_text(encoding="utf-8"))
    checks = []

    def check(name, passed, evidence):
        checks.append({"name": name, "passed": bool(passed), "evidence": evidence})

    check("Results correspond to current assumptions",
          r["assumptions_sha256"] == hashlib.sha256((here / "assumptions.json").read_bytes()).hexdigest(),
          r["assumptions_sha256"])
    # Independent unit exponents in base dimensions [mass, length, time, temperature].
    W = (1, 2, -3, 0)
    cp_unit, dT_unit, rho_unit = (0, 2, -2, -1), (0, 0, 0, 1), (1, -3, 0, 0)
    subtract = lambda x, y: tuple(i-j for i, j in zip(x, y))
    mass_flow_unit = subtract(subtract(W, cp_unit), dT_unit)
    volume_flow_unit = subtract(mass_flow_unit, rho_unit)
    power_unit = tuple(sum(x) for x in zip(rho_unit, (0, 1, -2, 0), volume_flow_unit, (0, 1, 0, 0)))
    check("Heat balance and power dimensions", mass_flow_unit == (1, 0, -1, 0)
          and volume_flow_unit == (0, 3, -1, 0) and power_unit == W,
          {"mass_flow": "kg/s", "volume_flow": "m3/s", "rho*g*Q*H": "kg m2/s3 = W",
           "resistance": "m/(m3/s)^2 = s2/m5", "pressure": "rho*g*H = kg/(m s2) = Pa"})
    # Published Table 8 cp values: p.11 of IAPWS SR6-08(2011).
    for T, expected in [(260.0, 4300.17472), (298.15, 4181.44618), (375.0, 4217.74697)]:
        actual = water_cp_at_0p1_MPa(T)
        check(f"IAPWS published cp check at {T} K", abs(actual-expected) < 0.00001,
              {"expected_J_kg_K": expected, "actual_J_kg_K": actual})
    cp_at_15 = water_cp_at_0p1_MPa(288.15)
    check("Rounded cp agrees with sourced correlation", abs(cp_at_15-a["water"]["cp_J_kg_K"]) < 0.005,
          {"unrounded_J_kg_K": cp_at_15, "model_J_kg_K": a["water"]["cp_J_kg_K"]})
    rho, cp, g = a["water"]["density_kg_m3"], a["water"]["cp_J_kg_K"], a["network"]["gravity_m_s2"]
    heat, dT = a["thermal"]["full_load_heat_W"], a["thermal"]["delta_T_K"]
    Qd = heat / (rho * cp * dT)
    check("Independent full-load heat balance", isclose(r["design"]["volume_flow_m3_s"], Qd, rel_tol=1e-12),
          {"mass_flow_kg_s": heat/(cp*dT), "volume_flow_m3_s": Qd,
           "reconstructed_coil_heat_W": rho * r["design"]["volume_flow_m3_s"] * cp * dT})
    full = next(p for p in r["normal_fixed_speed"] if p["load_fraction"] == 1)
    # Numeric full-load hand calculation for the declared baseline: q/qBEP=1.
    # Explicit numbers intentionally make this a frozen reference audit.
    check("One pump design operating point, independently by substitution",
          isclose(full["pump_head_m"], 32-8*1**2, abs_tol=1e-10)
          and isclose(full["header_head_m"], 24-2, abs_tol=1e-10)
          and isclose(full["valve_head_m"], 4, abs_tol=1e-10),
          {"gross_pump_head_m": 24, "branch_loss_m": 2, "shared_header_m": 22,
           "shared_head_budget_m": "6 pipe/header + 4 HX + 8 coil + 4 valve = 22"})
    independent_hydraulic_kW = (heat/(cp*dT)) * 9.81 * 24 / 1000
    independent_electrical_kW = independent_hydraulic_kW / (0.80*0.93*1.0)
    check("Independent full-load electrical power",
          isclose(full["electrical_power_kW"], independent_electrical_kW, rel_tol=1e-12),
          {"hydraulic_kW": independent_hydraulic_kW, "electrical_kW": independent_electrical_kW,
           "shaft_each_kW": independent_hydraulic_kW/2/0.8,
           "gross_head_used_m": 24, "efficiencies": [0.8, 0.93, 1.0]})
    # Independent closed-form network solution versus numerical bisection.
    # u=Q/Qd; q/qBEP=2u/n; Hheader=32-(8+2)*(2u/n)^2.
    max_head_error, max_flow_error, max_sum_error, max_branch_dp_spread = 0., 0., 0., 0.
    for case in r["normal_fixed_speed"] + r["single_pump_outages"]:
        n, Q = case["running_pumps"], case["achieved_flow_m3_s"]
        valve_dimensionless_budget = case["valve_R_s2_m5"] * Qd**2
        expected_Q = Qd*sqrt(32/(18 + valve_dimensionless_budget + 40/n**2))
        max_flow_error = max(max_flow_error, abs(expected_Q-Q))
        max_sum_error = max(max_sum_error, abs(sum(case["branch_flows_m3_s"])-Q))
        independently_calculated_headers = []
        for q in case["branch_flows_m3_s"]:
            header = 32-(8+2)*(q/(Qd/2))**2
            independently_calculated_headers.append(header)
            shared = (18+valve_dimensionless_budget)*(Q/Qd)**2
            max_head_error = max(max_head_error, abs(header-shared))
        max_branch_dp_spread = max(max_branch_dp_spread,
                                  max(independently_calculated_headers)-min(independently_calculated_headers))
    check("Numerical intersections agree with independent closed-form network solution", max_flow_error < 1e-11,
          {"max_flow_difference_m3_s": max_flow_error, "points_checked": 16})
    check("Pump branches balance at same header differential", max_head_error < 1e-9 and max_branch_dp_spread < 1e-9,
          {"max_loop_head_residual_m": max_head_error, "max_branch_header_spread_m": max_branch_dp_spread,
           "note": "Equal flow follows the declared identical branches; this does not validate real pump matching."})
    check("Mass continuity at headers", max_sum_error < 1e-12, {"max_sum_flow_residual_m3_s": max_sum_error})
    check("Normal and one-unavailable cases satisfy requested flow and all declared limits",
          all(p["within_declared_envelope"] and abs(p["flow_error_m3_s"]) < 1e-11
              for p in r["normal_fixed_speed"]+r["single_pump_outages"]),
          {"normal_cases": 4, "outage_cases": 12,
           "outages": "Each of P1, P2 and P3 unavailable at 25, 50, 75, 100% load"})
    check("Outage cases select available pumps only",
          all(p["unavailable_pump_id"] not in p["running_pump_ids"] for p in r["single_pump_outages"]),
          "Failed branch assumed isolated; no check-valve leakage or standby auxiliary power.")
    single_open = r["diagnostics_not_all_admissible"]["one_pump_valves_fully_open"]
    expected_single_open = Qd*sqrt(32/60)
    check("One-pump diagnostic intersection and runout flag",
          isclose(single_open["achieved_flow_m3_s"], expected_single_open, rel_tol=1e-12)
          and not single_open["within_declared_envelope"],
          {"flow_m3_h": expected_single_open*3600, "fraction_of_full_load_flow": sqrt(32/60),
           "per_pump_ratio_to_BEP": 2*sqrt(32/60), "declared_upper_limit": 1.2})
    check("Turbulent regime supports equivalent quadratic pipe model over studied points",
          min(r["design_pipe_checks"][k]["Reynolds_number"] * 0.25 for k in ["common", "pump_branch"]) > 10000,
          {"design_values": r["design_pipe_checks"],
           "note": "Conservative quarter-design Re check. Constant resistance is still an approximation; geometry/roughness not resolved."})
    # These are frozen baseline checks. Changed assumptions may legitimately fail
    # numeric reference checks; review/re-derive reference expectations explicitly.
    output = {"all_passed": all(c["passed"] for c in checks), "checks": checks,
              "interpretation": "Equation and implementation verification for illustrative assumptions; not validation against measured facility or manufacturer data.",
              "frozen_reference_warning": "Some independent checks intentionally use original numeric budgets. Re-derive them when editing those assumptions."}
    (RESULTS / "verification.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    lines = ["BASELINE VERIFICATION", output["interpretation"], ""]
    for c in checks:
        lines += [("PASS" if c["passed"] else "FAIL")+": "+c["name"], json.dumps(c["evidence"]), ""]
    lines += [output["frozen_reference_warning"]]
    (RESULTS / "verification.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"{sum(c['passed'] for c in checks)}/{len(checks)} checks passed")
    for c in checks:
        if not c["passed"]:
            print("FAIL:", c["name"], c["evidence"])
    if not output["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
