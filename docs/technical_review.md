# Technical review

## Review outcome

The equations and operating points are internally consistent for the declared loop. The reference case gives 47.13% modelled annual pumping-energy savings, and the two remaining pumps can meet steady-state flow demand after any single pump becomes unavailable. Sensitivity testing makes the energy recommendation conditional on pressure requirements, equipment performance and load hours.

## A correction to how edited inputs behave

The earlier code derived the pump's best-efficiency-point flow and the network's reference flow from the current thermal inputs. Changing the water temperature rise could therefore resize the assumed hardware at the same time as changing demand.

Version 1.2 fixes those hardware references explicitly: 0.04779223410152233 m3/s for the network and half that value for each pump's BEP flow. The heat balance calculates demand separately. The published 5 K results are unchanged. A regression check reduces the rise to 4 K and confirms that demand increases by 25% while the hardware curves stay fixed.

This folder contains the single model and assumptions file used for the report. The remaining packaging work concerns portable paths, report generation, documentation and file organisation.

## Engineering checks

| Area | What the review established |
|---|---|
| Heat balance and units | Heat = mass flow x specific heat x temperature rise. Internal calculations use SI units; volume flow is converted to m3/h for display. |
| Pump curves | Affinity scaling gives H(q,s) = 32s^2 - 8(q/q_BEP)^2 for the illustrative curve. Electrical input is calculated at the resulting operating point. |
| Branches and shared losses | Branch loss is deducted before adding parallel flows at common header head. Shared pipes, HX and coils use total flow. Elevation cancels around the filled closed circuit. |
| Control valve | Throttling is solved explicitly for both strategies. Variable speed retains valve loss where speed or flow limits prevent further slowing. |
| Comparable service | Heat demand, the 5 K rise and achieved flow match. Both strategies satisfy the same terminal pressure floor. The fixed-speed valve dissipates surplus head. |
| Power and efficiency | Gross pump head, flow and operating-point pump efficiency give hydraulic/shaft power. Motor and drive losses are applied separately. Maps and limits remain assumptions. |
| Pump unavailability | Each installed pump is removed at every load for both strategies. The review distinguishes standby, staged-off duty and running duty roles, then solves the final substituted state. |
| Annual energy | Calculated electrical input is multiplied by illustrative hours that sum to 8760. The boundary covers secondary pumping electricity. |
| Sensitivity | Resistance, terminal pressure, efficiencies and hours are varied. Negative savings are retained, and infeasible duties are excluded from annual comparisons. |
| Evidence | Independent equation and code checks establish internal consistency. Comparison with real equipment or facility measurements would be needed for physical validation. |

## What limits the recommendation

Feasible sensitivity combinations range from -7.9% to +58.9% savings. The named combined unfavourable case uses 6.96% more pumping energy. With 25% higher passive/branch resistance, two pumps at maximum speed deliver only 164.51 m3/h against 172.05 required. Around 10% higher resistance already uses up nominal full-load margin at the reference terminal floor.

Fewest-feasible-pumps staging leaves room for improvement. The separate 40% check with two slower pumps draws less power; the headline annual totals retain the common staging rule. Real pump, motor and drive maps would be needed to choose a better policy.

Coil performance, rack inlet temperatures, absolute fill pressure/NPSH and transient cooling continuity remain unresolved. Assessing ride-through would require time-dependent flow and startup data, thermal inventory and mixing, coil and air-side performance, IT heat load, initial temperatures and permissible limits.

The packaged code generates the report, CSVs and verification evidence. A manifest records the release's file hashes so that changes can be traced. Engineering confidence still depends on the quality of the assumptions and the checks.
