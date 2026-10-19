# Data centre chilled-water pumping and N+1 capacity

How much electricity can a data hall save by slowing its chilled-water pumps at partial load? Will enough flow remain available if one pump is out of service? This independent Python study explores those questions for a conceptual 1 MW data hall with CRAH cooling coils.

The [three-page case study](report/chilled_water_pumping_case_study.pdf) brings the method and findings together. For the illustrative annual load profile, variable speed reduces modelled pumping energy from **95.76 to 50.63 MWh**, a **47.1% saving**. The answer changes with the assumptions: feasible sensitivity cases range from **-7.9% to +58.9%**. The energy boundary covers the secondary distribution pumps.

## Run the project

Use Python 3.10 or newer; the released package was run with Python 3.12. From this folder:

```bash
python -m pip install -r requirements.txt
python run_project.py
```

The full run regenerates results, performs 16 baseline and 17 comparison checks, draws the figures and builds the three-page PDF. It finishes by checking that the report, CSVs and application wording agree with the release.

The PDF and figures use Calibri from your local font installation. The regular, bold, italic and bold italic files must be available. On Windows the scripts check the usual font folders; elsewhere, set `CALIBRI_FONT_DIR` to the folder containing those four files. The PDF embeds its fonts, so readers can view it without installing Calibri. Font files are excluded from the repository. Colours and typography are defined in `visual_style.py`.

To run just the numerical model and engineering checks, using the Python standard library:

```bash
python run_project.py --data-only
```

Once the dependencies are installed, the project runs offline and saves its outputs locally.

## The model

The closed secondary loop includes shared pipework and headers, three parallel pump branches, the secondary side of a plant heat exchanger, and an equivalent balanced CRAH coil/control-valve bank. Adequate external plant maintains 12.5 C supply water. Refrigeration, CRAH fans and heat rejection sit outside the energy boundary.

Full-load heat transfer is 1 MW. Holding the water temperature rise at 5 K gives a required flow of 172.05 m3/h, using density 999.1 kg/m3 and specific heat 4188.55 J/(kg K). Constant temperature rise is a study assumption; actual coil and air-side behaviour would need separate assessment.

Two pumps cover duty and a third provides standby capacity. At most two run. Both control strategies stage the fewest feasible pumps, giving one, two and two at 40%, 70% and 100% load. Fixed speed uses valve throttling. Variable speed resets remote coil-plus-valve differential pressure to the flow-dependent requirement, subject to a 2 m minimum and equipment limits. Assumed VFD efficiency is 97%.

Pump curves, efficiency maps and operating limits are illustrative. Each branch loss uses its own flow; shared losses use total flow. The gross pump head covers both. Elevation cancels around the filled circuit, while absolute fill pressure remains a separate design requirement.

Edit **assumptions.json** to inspect or vary the inputs. Hardware reference flows are fixed explicitly, so a change in heat duty or temperature rise changes demand while preserving the pump and resistance curves.

## Results worth discussing

| Cooling load | Flow, both strategies (m3/h) | Running pumps | Fixed input (kW) | Variable input (kW) |
|---|---:|---:|---:|---:|
| 40% | 68.82 | 1 | 6.890 | 2.405 |
| 70% | 120.44 | 2 | 12.883 | 4.900 |
| 100% | 172.05 | 2 | 15.110 | 14.286 |

The reference year assigns 3504, 3504 and 1752 hours to these loads, totalling 8760. All 18 single-pump-unavailable comparison cases meet required flow in their final steady state. Raising passive and branch resistance by 25%, however, leaves the two remaining pumps short of full-load demand.

Verification independently reproduces the heat balance, units, pump/network intersections, branch continuity, common header pressure and electrical input. It also checks speed, flow, valve and motor limits across 128 feasible comparison records. Infeasible duties receive no annual savings estimate.

- [Operating results](results/comparison_cases.csv): six normal cases and eighteen outage cases.
- [Sensitivity results](results/sensitivity_cases.csv): all 54 annual combinations; blank energy fields identify infeasible duty.
- [Verification evidence](results/comparison_verification.txt) and [technical review](docs/technical_review.md).
- [Application wording](docs/application_wording.md), [six questions](docs/understanding_questions.md) and [answer key](docs/answer_key.md).

## What I would check next

Variable speed with commissioned pressure reset is a promising candidate for the reference partial-load profile. An equipment decision would need real pump/drive maps, critical-path pressure requirements and representative load hours. The combined unfavourable case uses 6.96% more pumping energy, which makes those inputs especially important.

The staging policy also deserves attention. A separate check at 40% load finds that two slower pumps use 1.776 kW, compared with 2.405 kW for one. Annual totals retain the common fewest-feasible-pumps rule so that the main comparison remains consistent.

N+1 here describes **steady-state pumping capacity after substitution**. Coil heat-transfer performance, rack inlet temperatures and transient cooling continuity remain unverified. A real installation would also require detailed component losses, valve selection, fill pressure and NPSH checks. Thermal ride-through would need time-dependent flow, startup and temperature evidence. The study provides no basis for total cooling-energy savings, PUE improvement or financial payback; equipment selection, site implementation, external review and AWS design approval lie beyond its scope.

Some verification checks deliberately retain independent reference answers for the released design. If you change that design, re-derive the checks and review the report before publishing new results. The report builder flags changed inputs so that fixed descriptions cannot quietly become stale. The release manifest records file hashes for consistency.

## Engineering references

- [ITTC water properties, Table 1 p.6](https://www.ittc.info/media/7989/75-02-01-03.pdf): density/viscosity at 15 C.
- [IAPWS SR6-08(2011)](https://iapws.org/technical-guidance/release/LiquidWater.download): specific heat and published checkpoints.
- [Bell & Gossett TEH-471A, p.2](https://prod.xylem.com/siteassets/brand/bell-amp-gossett/resources/manual/teh-471a-hydronic-system-types.pdf): closed-loop head.
- [KSB parallel operation](https://www.ksb.com/en-global/centrifugal-pump-lexicon/article/parallel-operation-1116902): common-head flow addition and check valves.
- [ASHRAE Handbook ch.44](https://handbook.ashrae.org/Handbooks/S20/IP/s20_ch44/s20_ch44_ip.aspx), sections 13-15: pressure control and efficiency.
- [ASHRAE Handbook ch.43](https://handbook.ashrae.org/Handbooks/A23/SI/a23_ch43/a23_ch43_si.aspx), optimal DP set points: terminal-based pressure reset.
