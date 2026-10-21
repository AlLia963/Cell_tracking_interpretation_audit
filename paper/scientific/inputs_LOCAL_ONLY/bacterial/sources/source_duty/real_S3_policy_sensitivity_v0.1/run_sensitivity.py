import sys
sys.dont_write_bytecode = True
import ast
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[2]
SOURCE = WORKSPACE / '08_Kaggle实验' / 'stage_export' / 'stage_export_pipeline.py'
GRAPHS = WORKSPACE / '08_Kaggle实验' / 'stage_graphs_float' / 'tight55'


def producer_namespace():
    tree = ast.parse(SOURCE.read_text(encoding='utf-8-sig'))
    environment = {}
    # Only top-level literal environment assignments, never executable pipeline.
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Subscript) and ast.unparse(target.value) == 'os.environ':
                try:
                    key, value = ast.literal_eval(target.slice), ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    continue
                environment[key] = value
    namespace = {'np': np, 'math': math, 'cKDTree': cKDTree,
                 'os': SimpleNamespace(environ=environment), 'VOXEL_SCALE_UM': (1.625, .40625, .40625)}
    wanted = {'OUTPUT_SAFE_DIVISIONS', 'DEEPCENTER_SAFE_DIV_VETO', 'DEEPCENTER_SAFE_DIV_THRESHOLD'}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in wanted or name.startswith('SAFE_DIV_'):
                exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), 'exec'), namespace)
        if isinstance(node, ast.FunctionDef) and node.name in ['edge_distance_um', 'node_point', '_position_um', 'add_safe_divisions_postlink']:
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), 'exec'), namespace)
    return namespace, environment


def load_graph(path):
    with np.load(path) as data:
        ids, coords = data['node_ids'], data['coords']
        edges = ids[data['edges']]
    nodes = {int(i): dict(zip(['t', 'z', 'y', 'x'], map(float, c))) for i, c in zip(ids, coords)}
    return nodes, [{'source_id': int(a), 'target_id': int(b)} for a, b in edges]


def main():
    output = ROOT / 'results'
    output.mkdir(exist_ok=False)
    namespace, environment = producer_namespace()
    rows, hashes = [], {}
    for film in sorted(p for p in GRAPHS.iterdir() if p.is_dir()):
        paths = [film / 'S2_gap_closing.npz', film / 'S3_safe_divisions.npz']
        before_nodes, before = load_graph(paths[0])
        after_nodes, after = load_graph(paths[1])
        assert before_nodes == after_nodes
        old_edges = {(e['source_id'], e['target_id']) for e in before}
        actual_edges = {(e['source_id'], e['target_id']) for e in after}
        assert old_edges <= actual_edges
        actual = actual_edges - old_edges
        hashes.update({str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
        for arm, accepted in [('veto_accept_all', True), ('veto_reject_all', False)]:
            queried_points = []
            def veto(dataset, frame, point, *args):
                queried_points.append((frame, *point))
                return accepted
            namespace['deepcenter_accept_repair_point'] = veto
            stats = defaultdict(int)
            result = namespace['add_safe_divisions_postlink'](before_nodes, before, stats, dataset=film.name)
            appended = {(e['source_id'], e['target_id']) for e in result} - old_edges
            point_to_ids = defaultdict(set)
            for identifier, node in before_nodes.items():
                point_to_ids[(int(node['t']), node['z'], node['y'], node['x'])].add(identifier)
            queried_ids = set().union(*(point_to_ids[q] for q in queried_points)) if queried_points else set()
            rows.append({'film': film.name, 'arm': arm, 'actual_S3_additions': len(actual),
                         'counterfactual_additions': len(appended),
                         'actual_also_counterfactual': len(actual & appended),
                         'actual_not_counterfactual': len(actual - appended),
                         'counterfactual_not_actual': len(appended - actual),
                         'veto_queries': len(queried_points), 'queried_unique_targets': len(queried_ids),
                         'actual_targets_not_queried': sum(b not in queried_ids for a, b in actual),
                         'stats': dict(stats), 'appended_edges': sorted(appended)})
            print(film.name, arm, 'actual', len(actual), 'counterfactual', len(appended), 'queries', len(queried_points), flush=True)
    parameters = {k: v for k, v in namespace.items() if k.startswith('SAFE_DIV_') or k in ['OUTPUT_SAFE_DIVISIONS', 'DEEPCENTER_SAFE_DIV_VETO', 'DEEPCENTER_SAFE_DIV_THRESHOLD']}
    report = {'rows': rows, 'static_parameters': parameters, 'literal_source_environment': environment,
              'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(), 'input_hashes': hashes,
              'scope': 'Graph-only veto counterfactual, not historical image-veto replay, no GT use, no real duty/violation attribution'}
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
