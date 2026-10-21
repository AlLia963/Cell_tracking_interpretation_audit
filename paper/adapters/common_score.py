"""Score freshly generated common-carrier policies using the pinned scorer.

The input predictions are frozen by generate_common before reference loading.
Only the original script's root binding is replaced; scientific bodies and
the source-relative FP definition remain unchanged.
"""
from pathlib import Path
import argparse
import ast
import hashlib
import json
import shutil
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    c = json.loads(a.config.read_text(encoding='utf-8-sig'))
    rt = Path(c['runtime_root'])
    predictions = Path(c['generated_common_root'])
    reference = Path(c['common_carrier_root'])
    assert len(list(predictions.glob('*.npz'))) == 96
    a.output.mkdir(parents=True, exist_ok=False)
    inputs = a.output / 'inputs'; inputs.mkdir()
    pins = {}
    for f in [*predictions.glob('*.npz'), *reference.glob('*_reference_pixel.npz')]:
        shutil.copy2(f, inputs / f.name)
        pins[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
    code = rt / 'inputs_LOCAL_ONLY/bacterial/inputs_LOCAL_ONLY/common_carrier96/reproduce96.py'
    sys.path.insert(0, str(code.parent))
    tree = ast.parse(code.read_text(encoding='utf-8-sig'))
    ns = {'__file__': str(code), '__name__': '__fresh_common_score__'}
    previous = sys.argv
    sys.argv = [str(code), '--output', str(a.output / 'RESULT.json')]
    try:
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'root' for t in node.targets):
                ns['root'] = inputs
            else:
                exec(compile(ast.Module(body=[node], type_ignores=[]), str(code), 'exec'), ns)
    finally:
        sys.argv = previous
    (a.output / 'INPUT_PINS.json').write_text(json.dumps(pins, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
