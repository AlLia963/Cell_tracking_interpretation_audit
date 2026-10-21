"""Run every generic CLI on constructed inputs and check important outcomes."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / 'examples'


def run(argv, *, expected_returncode=0):
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    result = subprocess.run([sys.executable, *map(str, argv)], cwd=ROOT,
                            text=True, encoding='utf-8', capture_output=True, env=env)
    if result.returncode != expected_returncode:
        raise RuntimeError(f'Unexpected exit {result.returncode}: {argv}\n{result.stdout}\n{result.stderr}')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    ref = EXAMPLES / 'coordinate_reference.json'
    stages = ['--stage', EXAMPLES / 'coordinate_stage_0.json',
              '--stage', EXAMPLES / 'coordinate_stage_1.json']
    commands = {
        'family-history': ['--reference', ref, *stages, '--families', EXAMPLES / 'coordinate_families.json'],
        'coupled-bounds': ['--reference', ref, *stages, '--families', EXAMPLES / 'coordinate_families.json'],
        'coordinate-match': ['--reference', ref, '--pred', EXAMPLES / 'coordinate_stage_0.json', '--radius', '0.01'],
        'mask-match': ['--reference', EXAMPLES / 'mask_reference.json', '--pred', EXAMPLES / 'mask_prediction.json', '--gate', '0.5'],
        'mask-envelope': ['--reference', EXAMPLES / 'mask_reference.json', '--pred', EXAMPLES / 'mask_prediction.json'],
        'typed-history': ['--reference', EXAMPLES / 'typed_reference.json',
                          '--stage', EXAMPLES / 'typed_raw_stage.json', '--stage', EXAMPLES / 'typed_raw_stage.json',
                          '--matches', EXAMPLES / 'typed_matches.json', '--types', EXAMPLES / 'typed_views.json',
                          '--relation', 'continuation', '--ambiguity', 'unique_under_declared_rule'],
        'joint-history': ['--joint-family', EXAMPLES / 'constructed_joint_histories.json'],
    }
    for name, arguments in commands.items():
        run(['-m', 'portable_analysis_candidate', name, *arguments, '--output', out / f'{name}.json'])

    # Replay every supplied-map extremizer; each scalar may use a different map.
    from portable_analysis_candidate import history_features
    from portable_analysis_candidate.io import load_graph_json, load_families_json
    reference = load_graph_json(ref)
    graphs = [load_graph_json(EXAMPLES / f'coordinate_stage_{k}.json') for k in (0, 1)]
    families, _ = load_families_json(EXAMPLES / 'coordinate_families.json')
    result = json.loads((out / 'coupled-bounds.json').read_text(encoding='utf-8'))['result']
    for feature, bounds in result['scalar_bounds'].items():
        for side in ('minimum', 'maximum'):
            witness = bounds[f'{side}_witness']
            maps = [family[index] for family, index in zip(families, witness['whole_map_index_per_stage'])]
            edges = [set(map(tuple, graph.edges.tolist())) for graph in graphs]
            total = sum(history_features(tuple(int((mapping.get(int(a)), mapping.get(int(b))) in edge_set)
                                               for mapping, edge_set in zip(maps, edges)))[feature]
                        for a, b in reference.edges)
            assert total == bounds[side] == witness['reproduced_scalar']
    typed = json.loads((out / 'typed-history.json').read_text(encoding='utf-8'))['result']['records'][0]
    assert typed['visibility'] == [1, 0]
    assert typed['loss_pathways'][0]['raw_pair_deleted'] is False

    # The NPZ workflow infers frame families rather than receiving expected maps.
    inputs = out / 'generated_coordinate_inputs'
    run([EXAMPLES / 'generate_coordinate_inputs.py', '--output', inputs])
    workflow = ROOT / 'workflows/coordinate/workflow.py'
    run([workflow, '--manifest', inputs / 'CONSTRUCTED_VARIABLE_VIEWS.json',
         '--input-root', inputs / 'constructed_inputs', '--output', out / 'coordinate-workflow'])
    completed = json.loads((out / 'coordinate-workflow/RUN_COMPLETE.json').read_text(encoding='utf-8'))
    assert completed['cohort'] == 6
    assert completed['counts']['COMPLETE'] > 0
    for name in ('QUERY_CAP_REFUSAL', 'FRAME_CAP_REFUSAL', 'COMPONENT_CAP_REFUSAL'):
        directory = out / name.lower()
        run([workflow, '--manifest', inputs / f'{name}.json',
             '--input-root', inputs / 'constructed_inputs', '--output', directory])
        rows = [json.loads(line) for line in (directory / 'REPORTS.jsonl').read_text(encoding='utf-8').splitlines()]
        assert rows and all(row['status'] != 'COMPLETE' for row in rows)
    run([workflow, '--manifest', inputs / 'INVALID_UNIT_DOMAIN.json',
         '--input-root', inputs / 'constructed_inputs', '--output', out / 'invalid-unit'], expected_returncode=1)
    # CLI overwrite refusal is a deliberate invalid-input check, not a lost result.
    run(['-m', 'portable_analysis_candidate', 'coordinate-match', *commands['coordinate-match'],
         '--output', out / 'coordinate-match.json'], expected_returncode=2)
    summary = {'generic_commands': len(commands), 'whole_map_scalar_witnesses_replayed': True,
               'typed_relabel_raw_pair_preserved': True, 'generated_npz_cohort': 6,
               'cap_checks': 3, 'invalid_unit_rejected': True, 'overwrite_rejected': True,
               'competition_data_used': False}
    (out / 'CHECKS_COMPLETE.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
