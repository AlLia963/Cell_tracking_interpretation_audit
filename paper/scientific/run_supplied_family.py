"""Explicit local entry to the copied supplied-family engine."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE/'sources/portable/src'))
from portable_analysis_candidate.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
