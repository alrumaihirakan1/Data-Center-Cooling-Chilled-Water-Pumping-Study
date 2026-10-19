"""Reproduce the numerical study, verification, figures and three-page report.

python run_project.py             # complete deliverables
python run_project.py --data-only # numerical model/checks, standard library only
"""
import argparse
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-only", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    steps = ["hydraulic_model.py", "verify_baseline.py", "compare_strategies.py", "verify_comparison.py"]
    if not args.data_only:
        steps += ["make_visuals.py", "make_comparison_plots.py", "build_report.py", "validate_release.py"]
    for step in steps:
        print(f"\nRunning {step}", flush=True)
        subprocess.run([sys.executable, str(root / step)], cwd=root, check=True)


if __name__ == "__main__":
    main()
