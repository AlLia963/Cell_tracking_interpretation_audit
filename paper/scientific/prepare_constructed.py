"""Isolate the existing primitive source's constructed-input specification.

The original mixed natural/constructed preparer is not executed. This entry
creates only its six existing synthetic examples, under an absent explicit root.
The construction is not a new natural dataset or a grant of code rights.
"""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np


def save(path, obj):
    with path.open('x', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def manifest(cohort, **caps):
    return {'schema': 'coordinate-local-workflow/0.1', 'coordinate_unit': 'pixel',
            'objective': 'max_cardinality_then_exact_sum_calculated_binary64_distance',
            'inclusive_gate': 1.25,
            'frame_screen_cap': caps.get('frame_screen_cap', 1048576),
            'component_cap': caps.get('component_cap', 1048576),
            'query_cap': caps.get('query_cap', 1048576),
            'conventions': ['per_view_product', 'unchanged_geometry_equality'], 'cohort': cohort}


def npz(path, ids, coords, edges):
    np.savez_compressed(path, ids=np.asarray(ids, dtype=np.int64),
                        coords=np.asarray(coords, dtype=np.float64),
                        edges=np.asarray(edges, dtype=np.int64).reshape(-1, 2), unit=np.asarray('pixel'))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args(); root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    primitive = root/'constructed_inputs'; primitive.mkdir(); cohort = []
    for count in (2, 3, 5):
        for ambiguous in (False, True):
            name = f'constructed_{count}views_' + ('ambiguous' if ambiguous else 'unique')
            dest = primitive/name; dest.mkdir()
            npz(dest/'reference.npz', [1, 2, 3], [[0, 0, 0, 0], [1, 0, 0, 0], [2, 0, 0, 0]], [[1, 2], [2, 3]])
            if ambiguous:
                ids = [101, 102, 103, 104]
                coords = [[0, 0, 0, 0], [1, 0, 0, -1], [1, 0, 0, 1], [2, 0, 0, 0]]
                edges = [[101, 102], [103, 104]]
            else:
                ids = [201, 202, 203]
                coords = [[0, 0, 0, 0], [1, 0, 0, 0], [2, 0, 0, 0]]
                edges = [[201, 202], [202, 203]]
            views = []
            for k in range(count):
                filename = f'view_{k}.npz'; npz(dest/filename, ids, coords, edges)
                views.append({'label': f'arbitrary_name_{k}', 'npz': f'{name}/{filename}'})
            cohort.append({'name': name, 'reference': {'npz': f'{name}/reference.npz'}, 'ordered_views': views})
    save(root/'CONSTRUCTED_VARIABLE_VIEWS.json', manifest(cohort))
    ambiguous_five = [row for row in cohort if row['name'] == 'constructed_5views_ambiguous']
    for filename, cap in [('QUERY_CAP_REFUSAL.json', 'query_cap'), ('FRAME_CAP_REFUSAL.json', 'frame_screen_cap'),
                          ('COMPONENT_CAP_REFUSAL.json', 'component_cap')]:
        save(root/filename, manifest(ambiguous_five, **{cap: 1}))
    invalid = manifest([cohort[0]]); invalid['coordinate_unit'] = 'um'
    save(root/'INVALID_UNIT_DOMAIN.json', invalid)
    save(root/'CONSTRUCTION_RECEIPT.json', {'source_specification': 'Constructed-only section of generic_raw_local_workflow_v0.1/prepare_inputs.py',
         'original_mixed_preparer_not_executed': True, 'constructing_only_synthetic_coordinates': True,
         'new_biological_N': 0, 'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    print(json.dumps({'cases': len(cohort), 'npz_count': len(list(primitive.rglob('*.npz'))), 'output': str(root)}))


if __name__ == '__main__':
    main()
