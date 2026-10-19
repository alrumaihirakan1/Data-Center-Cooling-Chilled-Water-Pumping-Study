"""Release consistency checks and a manifest; numerical/visual roles are separate.

The PDF was rendered and visually inspected for the released version. These
automated checks guard content/data consistency, not visual layout fidelity.
"""

from copy import deepcopy
import csv
import hashlib
import json
from math import isclose
import re
from pypdf import PdfReader
from hydraulic_model import HydraulicModel
from project_paths import ROOT, RESULTS, REPORT


def main():
    a=json.loads((ROOT/"assumptions.json").read_text(encoding="utf-8"))
    r=json.loads((RESULTS/"comparison_results.json").read_text(encoding="utf-8"))
    digest=hashlib.sha256((ROOT/"assumptions.json").read_bytes()).hexdigest()
    assert r["assumptions_sha256"]==digest
    for name in ["verification.json","comparison_verification.json"]:
        assert json.loads((RESULTS/name).read_text(encoding="utf-8"))["all_passed"],name

    # Regression for the actual final-review correction: demand changes cannot
    # silently resize pump/network curves.
    original=HydraulicModel(a)
    edited=deepcopy(a)
    edited["thermal"]["delta_T_K"]=4.0
    edited["thermal"]["water_return_design_C"]=edited["thermal"]["water_supply_C"]+4.0
    changed=HydraulicModel(edited)
    assert isclose(changed.required_flow(1)/original.required_flow(1),1.25,rel_tol=1e-12)
    for field in ["q_bep","Q_reference","R_passive","R_branch","R_valve_min","R_pump"]:
        assert getattr(changed,field)==getattr(original,field),field
    assert changed.pump_head(.02,.8)==original.pump_head(.02,.8)

    pdf=REPORT/"chilled_water_pumping_case_study.pdf"
    reader=PdfReader(pdf)
    assert len(reader.pages)==3,"Report must be exactly three pages"
    # Every used face is embedded Calibri, including bold table headings.
    font_names=set()
    for page in reader.pages:
        for reference in page['/Resources']['/Font'].values():
            font=reference.get_object()
            assert 'Calibri' in str(font['/BaseFont']),font['/BaseFont']
            assert '/FontFile2' in font['/FontDescriptor'].get_object(),font['/BaseFont']
            font_names.add(str(font['/BaseFont']))
    assert any('Bold' in name for name in font_names),font_names
    text=" ".join("\n".join(page.extract_text() for page in reader.pages).split())
    assert '\ufffd' not in text,"PDF replacement glyph"
    for p in r["normal"]:
        for field,precision in [("achieved_flow_m3_h",2),("pump_head_m",2),("valve_head_m",2),("electrical_power_kW",3)]:
            assert f"{p[field]:.{precision}f}" in text,(field,p[field])
    annual=r["annual_energy_profiles"]["reference"]
    for field in ["fixed_kWh","variable_kWh","savings_kWh"]:
        assert f"{annual[field]/1000:.2f}" in text,field
    assert f"{annual['savings_percent']:.1f}%" in text
    for wording in ["illustrative","steady-state","Coil heat-transfer performance","rack inlet temperatures","transient cooling continuity"]:
        assert wording.lower() in text.lower(),wording
    with (RESULTS/"comparison_cases.csv").open(newline="",encoding="utf-8") as file:
        csvrows=list(csv.DictReader(file))
    points=r["normal"]+r["single_pump_unavailable"]
    assert len(csvrows)==len(points)==24
    for row,p in zip(csvrows,points):
        assert row['strategy']==p['strategy'] and row['case']==p['case']
        for field in ['achieved_flow_m3_h','electrical_power_kW','speed_rpm','pump_head_m']:
            assert isclose(float(row[field]),p[field],rel_tol=1e-12),field

    wording=(ROOT/"docs/application_wording.md").read_text(encoding="utf-8")
    bullets=[line[2:] for line in wording.splitlines() if line.startswith('- ')]
    assert len(bullets)==2 and all(30<=len(b.split())<=40 for b in bullets)
    interview=wording.split('## Approximately 60 seconds')[1].strip()
    assert 120<=len(interview.split())<=155
    for doc in ['understanding_questions.md','answer_key.md']:
        assert len(re.findall(r'^[1-6]\. ',(ROOT/'docs'/doc).read_text(encoding="utf-8"),re.M))==6,doc

    # No intermediate render files or local paths are needed to reproduce.
    hashes={}
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file() or '__pycache__' in path.parts or '.git' in path.parts or path.name=='release_manifest.json':
            continue
        hashes[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    manifest={"model_version":a['study']['version'],"assumptions_sha256":digest,
              "report_pages":3,"engineering_checks":{"baseline":16,"comparison":17},
              "release_checks":"Fixed-hardware regression, input hashes, three-page PDF/data/CSV consistency, embedded Calibri, wording lengths and six-question/key structure passed",
              "scope":"Internal reproducibility and file integrity; physical validation would require equipment or facility measurements",
              "sha256":hashes}
    (ROOT/'release_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('Release checks passed: fixed hardware, three-page Calibri report, matching CSV/data, application wording and answer key.')


if __name__=='__main__':
    main()
