"""Run the 30 manuscript analysis routes.

Requires an authorized input companion configured with configure_bundle.py.
Existing run directories are refused; failed/partial evidence is retained.
"""
from pathlib import Path
import argparse
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ORDER = [
    'natural3d', 'natural-gates', 'literal-baseline', 'historical-geometry',
    'historical-stress', 'constructed', 'typed-constructed', 'operating-envelope',
    'allocation-replay', 'bacterial-duties', 'duty-boundary',
    'bacterial-initial-overlays', 'bacterial-division-overlays', 'common-generate',
    'common-score-generated', 'bacterial-common', 'common-family-census',
    'analyst-path', 'bacterial-full', 'bacterial-natural', 'bacterial-pulse-endpoint',
    'bacterial-stage-archive', 'bacterial-chains', 'bacterial-timing',
    'bacterial-cca', 'native16', 'identity-crosswalk', 'epithelial', 'projection', 'historical-negative',
]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args(); a.output.mkdir(parents=True, exist_ok=False)
    c = json.loads(a.config.read_text(encoding='utf-8-sig')); records = []
    # All dependency paths are written by this run, not inherited from a prior
    # experiment directory. Reference NPZ inputs remain separate from predictions.
    for name, sub in {
        'natural_measurement_root': 'natural3d/measurement',
        'timing_measurement_root': 'bacterial-timing/measurement/measurement',
        'chains_measurement_root': 'bacterial-chains/measurement/measurement',
        'native_window_root': 'native16/measurement',
        'generated_common_root': 'common-generate/measurement/generated_run/generated',
        'duty_authority': 'bacterial-duties/measurement/authority.json',
        'decision_ledger': 'allocation-replay/measurement/decision_ledger.json',
    }.items():
        c[name] = str((a.output / sub).resolve())
    for route in ORDER:
        # Use new allocations for the source-duty controls, and new policies
        # for census/path queries; each upstream output has already been frozen.
        if route in ('common-family-census', 'analyst-path'):
            c['common_carrier_root'] = str((a.output / 'common-score-generated/measurement/inputs').resolve())
        config = a.output / (route + '.config.json')
        config.write_text(json.dumps(c, indent=2), encoding='utf-8')
        result = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(HERE / 'run.py'),
                                 route, '--config', str(config), '--output', str(a.output / route)])
        records.append({'route': route, 'returncode': result.returncode})
        (a.output / 'SUITE_PROGRESS.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
        if result.returncode:
            raise SystemExit(result.returncode)
    (a.output / 'SUITE_COMPLETE.json').write_text(json.dumps({'routes': records,
        'scope': 'Manuscript analysis from fixed scientific inputs, not upstream model training',
        'numerical_comparison_separate': True}, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
