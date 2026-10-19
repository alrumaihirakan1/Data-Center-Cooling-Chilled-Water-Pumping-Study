"""Steady-state equivalent chilled-water network, SI units throughout.

Run: python hydraulic_model.py
Or:  python hydraulic_model.py --assumptions path/to/assumptions.json --out path/to/results
No third-party packages needed for the numerical model. See README.md.

Q = total loop flow [m3/s]; q = one running pump's flow [m3/s].
H = head [m water]; resistance R in H=R*Q^2 has units s2/m5.
Identical parallel branches and equal pump speeds are assumed. Each branch's
loss is deducted BEFORE constructing the combined net-header pump curve.
"""

import argparse
import csv
import hashlib
import json
from math import pi, sqrt
from pathlib import Path


class HydraulicModel:
    def __init__(self, assumptions):
        self.a = assumptions
        self.t, self.w = assumptions["thermal"], assumptions["water"]
        self.net, self.p, self.ctrl = (
            assumptions["network"], assumptions["pumps"], assumptions["control"]
        )
        self.validate()
        self.m_design = self.t["full_load_heat_W"] / (self.w["cp_J_kg_K"] * self.t["delta_T_K"])
        self.Q_design = self.m_design / self.w["density_kg_m3"]
        # Hardware references are fixed inputs, not resized when demand changes.
        self.Q_reference = self.net["reference_total_flow_m3_s"]
        self.q_bep = self.p["reference_BEP_flow_m3_s"]
        self.H0 = self.p["shutoff_head_at_nominal_m"]
        self.A = self.H0 - self.p["design_pump_head_m"]
        self.R_pump = self.A / self.q_bep**2
        self.resistance_multiplier = self.net.get("resistance_multiplier", 1.0)
        self.terminal_min_head = self.ctrl.get("terminal_min_differential_head_m", 0.0)
        self.R_branch = self.resistance_multiplier * self.net["each_pump_branch_design_head_m"] / self.q_bep**2
        self.H_passive_design = self.resistance_multiplier * sum(self.net[key] for key in (
            "common_pipe_headers_design_head_m", "external_HX_secondary_design_head_m",
            "equivalent_coil_bank_design_head_m"
        ))
        self.R_passive = self.H_passive_design / self.Q_reference**2
        self.R_coil = self.resistance_multiplier * self.net["equivalent_coil_bank_design_head_m"] / self.Q_reference**2
        self.R_upstream = self.R_passive - self.R_coil
        self.R_valve_min = self.net["valve_fully_open_design_head_m"] / self.Q_reference**2
        self.R_valve_max = self.R_valve_min * self.net["valve_Kv_rangeability"]**2

    def validate(self):
        """Reject inconsistent physical inputs rather than silently correcting them."""
        for d, keys in [(self.t, ["full_load_heat_W", "delta_T_K"]),
                        (self.w, ["density_kg_m3", "cp_J_kg_K", "dynamic_viscosity_Pa_s"]),
                        (self.net, ["gravity_m_s2", "common_pipe_internal_diameter_m",
                                    "pump_branch_internal_diameter_m", "valve_fully_open_design_head_m",
                                    "valve_max_differential_head_m", "reference_total_flow_m3_s"]),
                        (self.p, ["reference_BEP_flow_m3_s"])]:
            if any(d[k] <= 0 for k in keys):
                raise ValueError("Heat, delta T, properties, gravity, diameters and valve limits must be positive")
        if abs(self.t["water_return_design_C"] - self.t["water_supply_C"] - self.t["delta_T_K"]) > 1e-8:
            raise ValueError("Supply/return temperatures must agree with delta_T_K")
        if self.net["static_operating_head_m"] != 0:
            raise ValueError("Closed-loop operating static head must be zero")
        if not self.p["shutoff_head_at_nominal_m"] > self.p["design_pump_head_m"] > 0:
            raise ValueError("Illustrative pump requires positive downward-sloping curve")
        for key in ["motor_efficiency", "pump_peak_efficiency", "fixed_speed_drive_efficiency",
                    "future_VFD_efficiency_assumption"]:
            if not 0 < self.p[key] <= 1:
                raise ValueError(f"Invalid efficiency: {key}")
        if not 0 < self.p["min_running_speed_fraction"] <= self.p["max_running_speed_fraction"] <= 1:
            raise ValueError("Speed envelope must be positive and bounded by nominal speed")
        if not 0 < self.p["min_flow_ratio_to_speed_scaled_BEP"] < self.p["max_flow_ratio_to_speed_scaled_BEP"]:
            raise ValueError("Invalid flow envelope")
        if not 1 <= self.p["design_duty_count"] <= self.ctrl["maximum_running_count"] < self.p["installed_count"]:
            raise ValueError("This N+1 study needs at least one installed spare")
        for key in ["common_pipe_headers_design_head_m", "external_HX_secondary_design_head_m",
                    "equivalent_coil_bank_design_head_m", "each_pump_branch_design_head_m"]:
            if self.net[key] < 0:
                raise ValueError("Loss budgets cannot be negative")
        if self.net["valve_Kv_rangeability"] < 1 or self.p["motor_shaft_rating_kW_each"] <= 0:
            raise ValueError("Invalid valve rangeability or motor rating")
        if any(not 0 < load <= 1 for load in self.t["load_fractions"]):
            raise ValueError("This baseline studies loads strictly above zero and at most full load")
        if self.net.get("resistance_multiplier", 1.0) <= 0 or self.ctrl.get("terminal_min_differential_head_m", 0.0) < 0:
            raise ValueError("Resistance multiplier must be positive and pressure minimum nonnegative")
        if self.p["pump_efficiency_parabola_coefficient"] < 0:
            raise ValueError("Efficiency curvature cannot be negative")

    def required_flow(self, load_fraction):
        return self.Q_design * load_fraction

    def pump_head(self, q, speed=1.0):
        """Gross head across a pump; branch friction is NOT included."""
        return self.H0 * speed**2 - self.R_pump * q**2

    def header_head(self, total_flow, running, speed=1.0):
        """Net available head between common suction and discharge reference nodes."""
        q = total_flow / running
        return self.pump_head(q, speed) - self.R_branch * q**2

    def system_head(self, total_flow, valve_resistance):
        """Shared loop only: common pipes + HX + equivalent coils + valve."""
        return (self.R_passive + valve_resistance) * total_flow**2

    def operating_flow(self, running, valve_resistance, speed=1.0):
        """Numerically intersect combined net pump curve with the shared system curve.

        The monotonic residual guarantees one positive intersection. Bounds cover
        the mathematical curve, then operating envelopes are checked separately.
        This deliberately does not substitute the requested flow as achieved flow.
        """
        if running < 1 or valve_resistance < 0 or speed <= 0:
            raise ValueError("Need positive running count/speed and nonnegative resistance")
        lo, hi = 0.0, running * self.q_bep * speed * sqrt(self.H0 / self.A)
        for _ in range(90):
            mid = (lo + hi) / 2
            residual = self.header_head(mid, running, speed) - self.system_head(mid, valve_resistance)
            if residual > 0:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    def evaluate(self, total_flow, running, valve_resistance, speed=1.0, drive_efficiency=None):
        """Evaluate a point, reporting all violated limits rather than hiding them."""
        if drive_efficiency is None:
            drive_efficiency = self.p["fixed_speed_drive_efficiency"]
        q = total_flow / running
        x = q / (speed * self.q_bep)
        eta = self.p["pump_peak_efficiency"] - self.p["pump_efficiency_parabola_coefficient"] * (x - 1)**2
        Hp = self.pump_head(q, speed)
        Hbranch = self.R_branch * q**2
        Hheader = Hp - Hbranch
        Hvalve = valve_resistance * total_flow**2
        Hterminal = self.R_coil * total_flow**2 + Hvalve
        rho, g = self.w["density_kg_m3"], self.net["gravity_m_s2"]
        hydraulic_W = rho * g * total_flow * Hp
        shaft_each_W = hydraulic_W / (running * eta) if eta > 0 else float("inf")
        electric_W = running * shaft_each_W / (self.p["motor_efficiency"] * drive_efficiency)
        reasons = []
        if not self.p["min_running_speed_fraction"] - 1e-9 <= speed <= self.p["max_running_speed_fraction"] + 1e-9:
            reasons.append("speed outside declared envelope")
        if not self.p["min_flow_ratio_to_speed_scaled_BEP"] - 1e-9 <= x <= self.p["max_flow_ratio_to_speed_scaled_BEP"] + 1e-9:
            reasons.append("per-pump flow outside declared envelope")
        if not self.R_valve_min - 1e-7 <= valve_resistance <= self.R_valve_max + 1e-7:
            reasons.append("valve resistance outside declared controllable range")
        if Hvalve > self.net["valve_max_differential_head_m"] + 1e-9:
            reasons.append("valve differential head too high")
        if Hterminal < self.terminal_min_head - 1e-9:
            reasons.append("terminal differential pressure below required minimum")
        if shaft_each_W > self.p["motor_shaft_rating_kW_each"] * 1000 + 1e-6:
            reasons.append("motor shaft rating exceeded")
        if not 0 < eta <= 1 or Hp <= 0:
            reasons.append("nonphysical pump head or efficiency")
        return {
            "running_pumps": running, "speed_fraction": speed,
            "achieved_flow_m3_s": total_flow, "achieved_flow_m3_h": total_flow * 3600,
            "branch_flows_m3_s": [q] * running,
            "per_pump_flow_m3_h": q * 3600, "flow_ratio_to_speed_scaled_BEP": x,
            "pump_head_m": Hp, "branch_loss_m": Hbranch, "header_head_m": Hheader,
            "header_heads_by_branch_m": [self.pump_head(q, speed) - self.R_branch * q**2 for _ in range(running)],
            "header_differential_kPa": rho * g * Hheader / 1000,
            "pump_differential_kPa": rho * g * Hp / 1000,
            "passive_shared_loss_m": self.R_passive * total_flow**2,
            "terminal_differential_head_m": Hterminal,
            "terminal_min_differential_head_m": self.terminal_min_head,
            "valve_head_m": Hvalve, "valve_R_s2_m5": valve_resistance,
            "valve_Kv_fraction_of_max": sqrt(self.R_valve_min / valve_resistance) if valve_resistance > 0 else None,
            "pump_efficiency": eta, "motor_efficiency": self.p["motor_efficiency"],
            "drive_efficiency": drive_efficiency,
            "hydraulic_power_kW": hydraulic_W / 1000,
            "shaft_power_each_kW": shaft_each_W / 1000,
            "electrical_power_kW": electric_W / 1000,
            "valve_dissipation_kW": rho * g * total_flow * Hvalve / 1000,
            "loop_balance_residual_m": Hheader - self.system_head(total_flow, valve_resistance),
            "within_declared_envelope": not reasons, "constraint_violations": reasons
        }

    def controlled_fixed_speed(self, load_fraction, available_pump_ids):
        """Fewest feasible pumps; flow-feedback valve disposes of excess head."""
        Q_req = self.required_flow(load_fraction)
        candidates = []
        for n in range(1, min(len(available_pump_ids), self.ctrl["maximum_running_count"]) + 1):
            Rv = self.header_head(Q_req, n) / Q_req**2 - self.R_passive
            point = self.evaluate(Q_req, n, Rv)
            if not point["within_declared_envelope"]:
                candidates.append({"running": n, "violations": point["constraint_violations"]})
                continue
            Q_achieved = self.operating_flow(n, Rv)
            result = self.evaluate(Q_achieved, n, Rv)
            result.update({
                "load_fraction": load_fraction, "coil_heat_W": load_fraction * self.t["full_load_heat_W"],
                "required_flow_m3_s": Q_req, "required_flow_m3_h": Q_req * 3600,
                "running_pump_ids": available_pump_ids[:n],
                "available_pump_ids": available_pump_ids,
                "available_standby_count": len(available_pump_ids) - n,
                "flow_error_m3_s": Q_achieved - Q_req, "rejected_lower_count_candidates": candidates
            })
            return result
        raise ValueError(f"No feasible fixed-speed point for load={load_fraction}, available={available_pump_ids}; {candidates}")

    def minimum_header_head(self, total_flow):
        """Reset target at common headers, before branch-loss compensation.

        Remote DP is across the representative coil + two-way-valve terminal.
        Minimum remote DP is max(coil + fully-open valve losses, declared floor).
        Upstream common pipes and plant HX are added once. The pressure floor is
        a control/service requirement, not an elevation/static head term.
        """
        terminal = max((self.R_coil + self.R_valve_min) * total_flow**2,
                       self.terminal_min_head)
        return self.R_upstream * total_flow**2 + terminal

    def variable_speed_candidate(self, load_fraction, running):
        """Solve minimum permissible speed for a specified duty-pump count.

        Bounds account for hydraulic head, terminal DP, speed-scaled pump flow,
        valve controllable resistance and differential. A binding flow or minimum
        speed limit can leave excess head, absorbed by the same physical valve.
        This minimises head for the given count; it is not a universal optimiser
        for arbitrary real efficiency maps.
        """
        Q = self.required_flow(load_fraction)
        q = Q / running
        combined_branch_curve = (self.R_pump + self.R_branch) * q**2
        lower = {
            "minimum_running_speed": self.p["min_running_speed_fraction"],
            "hydraulic_pressure_requirement": sqrt((self.minimum_header_head(Q) + combined_branch_curve) / self.H0),
            "maximum_speed_scaled_flow": q / (self.p["max_flow_ratio_to_speed_scaled_BEP"] * self.q_bep)
        }
        upper = {
            "maximum_running_speed": self.p["max_running_speed_fraction"],
            "minimum_speed_scaled_flow": q / (self.p["min_flow_ratio_to_speed_scaled_BEP"] * self.q_bep),
            "valve_rangeability": sqrt(((self.R_passive + self.R_valve_max)*Q**2 + combined_branch_curve) / self.H0),
            "valve_maximum_differential": sqrt((self.R_passive*Q**2 + self.net["valve_max_differential_head_m"] + combined_branch_curve) / self.H0)
        }
        speed, ceiling = max(lower.values()), min(upper.values())
        bounds = {"lower_speed_bounds": lower, "upper_speed_bounds": upper,
                  "minimum_feasible_speed": speed, "maximum_feasible_speed": ceiling}
        if speed > ceiling + 1e-10:
            return {"feasible": False, "running_pumps": running, **bounds,
                    "reasons": ["Required minimum speed exceeds permitted upper bound"]}
        drive_eta = self.p["future_VFD_efficiency_assumption"]
        Rv = self.header_head(Q, running, speed)/Q**2 - self.R_passive
        target = self.evaluate(Q, running, Rv, speed, drive_eta)
        if not target["within_declared_envelope"]:
            return {"feasible": False, "running_pumps": running, **bounds,
                    "reasons": target["constraint_violations"]}
        # Independently find achieved flow at the now-fixed valve setting/speed.
        achieved = self.operating_flow(running, Rv, speed)
        point = self.evaluate(achieved, running, Rv, speed, drive_eta)
        point.update({"feasible": point["within_declared_envelope"], **bounds,
                      "minimum_required_header_head_m": self.minimum_header_head(Q),
                      "binding_lower_speed_bounds": [k for k, value in lower.items() if abs(value-speed) < 1e-9],
                      "load_fraction": load_fraction,
                      "coil_heat_W": load_fraction * self.t["full_load_heat_W"],
                      "required_flow_m3_s": Q, "required_flow_m3_h": Q*3600,
                      "flow_error_m3_s": achieved-Q})
        return point

    def controlled_variable_speed(self, load_fraction, available_pump_ids):
        """Preserve baseline's fewest-feasible-pumps staging rule."""
        rejected = []
        for n in range(1, min(len(available_pump_ids), self.ctrl["maximum_running_count"]) + 1):
            point = self.variable_speed_candidate(load_fraction, n)
            if not point["feasible"]:
                rejected.append(point)
                continue
            point.update({"running_pump_ids": available_pump_ids[:n],
                          "available_pump_ids": available_pump_ids,
                          "available_standby_count": len(available_pump_ids)-n,
                          "rejected_lower_count_candidates": rejected})
            return point
        raise ValueError(f"No feasible variable-speed point for load={load_fraction}, available={available_pump_ids}; {rejected}")

    def diagnostic_point(self, running, valve_resistance):
        Q = self.operating_flow(running, valve_resistance)
        result = self.evaluate(Q, running, valve_resistance)
        result["equivalent_coil_heat_at_5K_W"] = Q * self.w["density_kg_m3"] * self.w["cp_J_kg_K"] * self.t["delta_T_K"]
        return result

    def pipe_checks(self, point):
        rho, mu = self.w["density_kg_m3"], self.w["dynamic_viscosity_Pa_s"]
        out = {}
        for name, flow, D in [
            ("common", point["achieved_flow_m3_s"], self.net["common_pipe_internal_diameter_m"]),
            ("pump_branch", point["branch_flows_m3_s"][0], self.net["pump_branch_internal_diameter_m"])
        ]:
            velocity = flow / (pi * D**2 / 4)
            out[name] = {"velocity_m_s": velocity, "Reynolds_number": rho * velocity * D / mu}
        return out


def main():
    here = Path(__file__).resolve().parent
    from project_paths import RESULTS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assumptions", type=Path, default=here / "assumptions.json")
    parser.add_argument("--out", type=Path, default=RESULTS)
    args = parser.parse_args()
    raw = args.assumptions.read_bytes()
    a = json.loads(raw)
    model = HydraulicModel(a)
    ids = [f"P{i+1}" for i in range(model.p["installed_count"])]
    normal = [model.controlled_fixed_speed(f, ids) for f in model.t["load_fractions"]]
    outage = []
    for failed in ids:
        for f in model.t["load_fractions"]:
            case = model.controlled_fixed_speed(f, [i for i in ids if i != failed])
            case["unavailable_pump_id"] = failed
            outage.append(case)
    controlled_design = model.controlled_fixed_speed(1.0, ids)
    diagnostics = {
        "two_pumps_valves_fully_open": model.diagnostic_point(2, model.R_valve_min),
        "one_pump_valves_fully_open": model.diagnostic_point(1, model.R_valve_min),
        "one_pump_full_load_valve_setting_frozen": model.diagnostic_point(1, controlled_design["valve_R_s2_m5"])
    }
    design = {"mass_flow_kg_s": model.m_design, "volume_flow_m3_s": model.Q_design,
              "volume_flow_m3_h": model.Q_design * 3600, "per_pump_BEP_m3_h": model.q_bep * 3600,
              "R_passive_s2_m5": model.R_passive, "R_branch_s2_m5": model.R_branch,
              "R_valve_min_s2_m5": model.R_valve_min,
              "one_pump_flow_limit_total_load_fraction": model.p["max_flow_ratio_to_speed_scaled_BEP"] / model.p["design_duty_count"]}
    output = {"study_version": a["study"]["version"],
              "assumptions_sha256": hashlib.sha256(raw).hexdigest(),
              "design": design, "normal_fixed_speed": normal, "single_pump_outages": outage,
              "diagnostics_not_all_admissible": diagnostics,
              "design_pipe_checks": model.pipe_checks(controlled_design)}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "baseline_results.json").write_text(json.dumps(output, indent=2, allow_nan=False), encoding="utf-8")
    columns = ["load_fraction", "running_pumps", "required_flow_m3_h", "achieved_flow_m3_h",
               "per_pump_flow_m3_h", "pump_head_m", "branch_loss_m", "header_head_m",
               "valve_head_m", "valve_Kv_fraction_of_max", "pump_efficiency",
               "hydraulic_power_kW", "electrical_power_kW"]
    with (args.out / "baseline_results.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(normal)
    print(f"Design: {model.m_design:.6f} kg/s; {model.Q_design*3600:.6f} m3/h")
    for r in normal:
        print(f"Load {r['load_fraction']:.0%}: {r['running_pumps']} pumps, "
              f"{r['achieved_flow_m3_h']:.3f} m3/h, gross H={r['pump_head_m']:.3f} m, "
              f"electrical={r['electrical_power_kW']:.3f} kW")
    print(f"Solved {len(outage)} single-pump-outage cases; all within declared envelope.")


if __name__ == "__main__":
    main()
