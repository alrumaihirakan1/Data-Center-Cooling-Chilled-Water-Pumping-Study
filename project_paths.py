"""Repository-local paths; no machine-specific directories required."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
REPORT = ROOT / "report"
for directory in (RESULTS, FIGURES, REPORT):
    directory.mkdir(parents=True, exist_ok=True)
