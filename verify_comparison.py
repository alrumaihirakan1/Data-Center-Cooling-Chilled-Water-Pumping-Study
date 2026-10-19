"""Independent audit of saved comparison outputs, standard Python only.

No imports from the hydraulic solver or strategy dispatcher. Scalar equations
and unit-consistent heat/power calculations are reconstructed from assumptions.
Run after compare_strategies.py. Assertions fail the run if any check fails.
"""

import hashlib
import json
from math import isclose, sqrt
from pathlib import Path

from project_paths import ROOT, RESULTS
HERE = ROOT


def main():
    raw = (HERE/"assumptions.json").read_bytes()
    a = json.loads(raw)
    r = json.loads((RESULTS/"comparison_results.json").read_text(encoding="utf-8"))
    checks = []

    def check(name, passed, evidence):
        checks.append({"name": name, "passed": bool(passed), "evidence": evidence})

    check("Current assumptions match comparison outputs", r["assumptions_sha256"]==hashlib.sha256(raw).hexdigest(), r["assumptions_sha256"])
    rho, cp, dT = a["water"]["density_kg_m3"], a["water"]["cp_J_kg_K"], a["thermal"]["delta_T_K"]
    g, load_W = a["network"]["gravity_m_s2"], a["thermal"]["full_load_heat_W"]
    Qd = load_W/(rho*cp*dT)
    nominal = r["normal"]+r["single_pump_unavailable"]
    check("All six normal and eighteen one-unavailable duties feasible", len(nominal)==24 and all(p["feasible"] for p in nominal), {"normal": len(r["normal"]), "outages": len(r["single_pump_unavailable"])})

    # Independent worked partial-load point at 70%, two pumps, valve fully open.
    u = .7
    s = sqrt(30*u*u/32)
    Hp = 32*s*s-8*u*u
    x = u/s
    eta = .80-.35*(x-1)**2
    Pel = rho*g*(u*Qd)*Hp/(eta*.93*.97)/1000
    p70 = next(p for p in r["normal"] if p["strategy"]=="variable" and p["load_fraction"]==.7)
    check("Independent 70% VSD head/efficiency/power reproduction",
          isclose(p70["electrical_power_kW"], Pel, rel_tol=1e-12) and isclose(Hp,10.78,abs_tol=1e-10),
          {"flow_m3_s": u*Qd, "speed_fraction": s, "pump_head_m": Hp,
           "pump_efficiency": eta, "motor_efficiency": .93, "drive_efficiency": .97, "input_kW": Pel})
    p40 = next(p for p in r["normal"] if p["strategy"]=="variable" and p["load_fraction"]==.4)
    check("40% flow constraint binds and residual throttling is retained",
          isclose(p40["speed_fraction"],2/3,abs_tol=1e-12)
          and isclose(p40["flow_ratio_to_speed_scaled_BEP"],1.2,abs_tol=1e-12)
          and p40["valve_Kv_fraction_of_max"]<1,
          {"speed_fraction":p40["speed_fraction"], "valve_loss_m":p40["valve_head_m"], "scaled_flow_ratio":p40["flow_ratio_to_speed_scaled_BEP"]})

    # Audit independent equations for nominal, outage and all distinct sensitivity
    # physical settings. Do not repeat the same points for each annual profile.
    collections = [(nominal,1.,2.,a["comparison"]["sensitivity"]["efficiency_packages"]["reference"])]
    for setting in r["factorial_settings"]:
        pkg = a["comparison"]["sensitivity"]["efficiency_packages"][setting["efficiency_package"]]
        collections.append((setting["points"],setting["resistance_multiplier"],setting["terminal_floor_m"],pkg))
    max_flow_error, max_head_error, max_thermal_error, max_power_relative_error = 0.,0.,0.,0.
    constraints_ok, point_count = True,0
    for points,k,floor,pkg in collections:
        for point in points:
            if not point["feasible"]:
                continue
            point_count += 1
            Q, n, s = point["achieved_flow_m3_s"],point["running_pumps"],point["speed_fraction"]
            u, y = Q/Qd, (Q/n)/(Qd/2)
            valve = point["valve_R_s2_m5"]*Q**2
            gross, branch = 32*s*s-8*y*y, 2*k*y*y
            shared = 18*k*u*u+valve
            terminal = 8*k*u*u+valve
            expected_Q = Qd*s*sqrt(32/(18*k+point["valve_R_s2_m5"]*Qd*Qd+(8+2*k)*(2/n)**2))
            eta = pkg["pump_peak_efficiency"]-pkg["pump_efficiency_parabola_coefficient"]*(y/s-1)**2
            drive = 1.0 if point["strategy"]=="fixed" else pkg["future_VFD_efficiency_assumption"]
            power = rho*g*Q*gross/(eta*pkg["motor_efficiency"]*drive)/1000
            shaft_each = rho*g*(Q/n)*gross/eta/1000
            max_flow_error = max(max_flow_error,abs(expected_Q-Q),abs(Q-Qd*point["load_fraction"]),abs(sum(point["branch_flows_m3_s"])-Q))
            max_head_error = max(max_head_error,abs(gross-branch-shared),abs(gross-point["pump_head_m"]),abs(terminal-point["terminal_differential_head_m"]))
            max_thermal_error = max(max_thermal_error,abs(rho*Q*cp*dT-load_W*point["load_fraction"]))
            max_power_relative_error = max(max_power_relative_error,abs(power-point["electrical_power_kW"])/power)
            constraints_ok &= (.5-1e-10<=s<=1+1e-10 and .45-1e-10<=y/s<=1.2+1e-10
                               and terminal>=floor-1e-9 and valve<=30+1e-9
                               and point["valve_R_s2_m5"]>=2/Qd**2-1e-7
                               and point["valve_R_s2_m5"]<=1250/Qd**2+1e-6
                               and shaft_each<=11+1e-8)
    check("Independent hydraulic intersections and flow/branch continuity",max_flow_error<1e-11,{"points":point_count,"max_m3_s_error":max_flow_error})
    check("Independent branch/shared/terminal head balances",max_head_error<1e-9,{"max_head_error_m":max_head_error})
    check("Heat removal at the same assumed 5 K",max_thermal_error<1e-6,{"max_heat_balance_error_W":max_thermal_error})
    check("Independent electrical input at actual head/flow/efficiency",max_power_relative_error<1e-11,{"max_relative_error":max_power_relative_error})
    check("Feasible points satisfy every speed/flow/valve/pressure/motor limit",constraints_ok,{"points_checked":point_count})

    max_strategy_flow_difference = 0.
    for unavailable in [None,"P1","P2","P3"]:
        cases = r["normal"] if unavailable is None else [p for p in r["single_pump_unavailable"] if p["unavailable_pump_id"]==unavailable]
        for load in [.4,.7,1.]:
            f = next(p for p in cases if p["strategy"]=="fixed" and p["load_fraction"]==load)
            v = next(p for p in cases if p["strategy"]=="variable" and p["load_fraction"]==load)
            max_strategy_flow_difference = max(max_strategy_flow_difference,abs(f["achieved_flow_m3_s"]-v["achieved_flow_m3_s"]))
    check("Both strategies deliver equivalent required flow with every availability case",max_strategy_flow_difference<1e-11,{"max_difference_m3_s":max_strategy_flow_difference})
    check("Outage dispatch uses healthy pumps and classifies pre-outage role correctly",
          all(p["unavailable_pump_id"] not in p["running_pump_ids"] and
              (p["role_before_outage"]=="running_duty")== (p["unavailable_pump_id"] in p["running_before_outage"])
              for p in r["single_pump_unavailable"]),
          "At 40% P1 runs, P2 is a staged-off duty pump and P3 is designated standby; at 70/100% P1/P2 run and P3 is standby.")
    power_match = True
    for p in r["single_pump_unavailable"]:
        before = next(q for q in r["normal"] if q["strategy"]==p["strategy"] and q["load_fraction"]==p["load_fraction"])
        power_match &= isclose(p["electrical_power_kW"],before["electrical_power_kW"],rel_tol=1e-12)
    check("Identical healthy pumps reproduce the same final-state power after substitution",power_match,"No detection/startup/changeover dynamics inferred.")

    annual_ok = True
    for name,profile in a["comparison"]["annual_profiles"].items():
        annual_ok &= sum(profile["hours"])==8760
        energies = {}
        for strategy in ("fixed","variable"):
            powers = [next(p["electrical_power_kW"] for p in r["normal"] if p["strategy"]==strategy and p["load_fraction"]==load) for load in [.4,.7,1.]]
            energies[strategy] = sum(h*p for h,p in zip(profile["hours"],powers))
            annual_ok &= isclose(energies[strategy],r["annual_energy_profiles"][name][strategy+"_kWh"],rel_tol=1e-12)
    check("All profiles sum to 8760 h and annual energy is independently weighted",annual_ok,r["annual_energy_profiles"]["reference"])
    infeasible_names = [p for p in r["named_sensitivity"] if not p["comparable"]]
    check("Infeasible duties explicitly omit comparable annual energy",
          len(infeasible_names)==2 and all(p["fixed_kWh"] is None and p["variable_kWh"] is None and p["savings_percent"] is None for p in infeasible_names),
          [{"name":p["name"],"unmet":p["infeasible_duties"]} for p in infeasible_names])
    adverse = next(p for p in r["named_sensitivity"] if p["name"]=="Combined unfavourable")
    check("Unfavourable feasible case retains negative savings",adverse["comparable"] and adverse["savings_kWh"]<0,{"savings_kWh":adverse["savings_kWh"],"savings_percent":adverse["savings_percent"]})
    alternative = r["alternative_staging_challenge"]
    check("Alternative staging challenge is admissible and lower-power but separate",alternative["point"]["feasible"] and alternative["point"]["electrical_power_kW"]<alternative["main_one_pump_kW"],{"two_pumps_kW":alternative["point"]["electrical_power_kW"],"headline_one_pump_kW":alternative["main_one_pump_kW"]})
    capacity = r["high_resistance_full_open_two_pump_capacity"]
    check("High-resistance challenge capacity is below the required full flow",capacity["within_declared_envelope"] and capacity["achieved_flow_m3_s"]<Qd,{"achieved_m3_h":capacity["achieved_flow_m3_h"],"required_m3_h":Qd*3600})
    output = {"all_passed":all(c["passed"] for c in checks),"checks":checks,
              "scope":"Verification of illustrative steady-state model, not real facility validation"}
    (RESULTS/"comparison_verification.json").write_text(json.dumps(output,indent=2),encoding="utf-8")
    lines = [output["scope"],""]
    for c in checks:
        lines += [("PASS" if c["passed"] else "FAIL")+": "+c["name"],json.dumps(c["evidence"]),""]
    (RESULTS/"comparison_verification.txt").write_text("\n".join(lines),encoding="utf-8")
    print(f"{sum(c['passed'] for c in checks)}/{len(checks)} comparison checks passed; {point_count} points independently audited.")
    if not output["all_passed"]:
        for c in checks:
            if not c["passed"]: print(c)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
