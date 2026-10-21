"""Primitive NPZ -> certified exact frame families -> untyped local reports.

Manifest names, views and cohort are
data, not source constants. The unchanged backend uses calculated binary64
distances and independently checks the canonical map with exact residual duals.
This wrapper exposes only its EXACT finite family; numerical families are not
reported. No biological type is inferred from graph degree.
"""
import argparse, collections, datetime, hashlib, itertools, json, math
import os, platform, sys, time, traceback
from pathlib import Path
import numpy as np
import scipy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'scientific_backend'))
from reconstruct import frame_family, load_npz, match
from local_graph_core import history_projection, final_category, independent_edge_relaxation

def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def emit(p, x):
    with p.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(x, f, ensure_ascii=False, separators=(',', ':')); f.write('\n')
def pin(p): return {'path': str(p), 'bytes': p.stat().st_size, 'sha256': sha(p)}
def adjacency(g):
    out = {int(q): set() for q in g.ids}; inc = {int(q): set() for q in g.ids}
    for a, b in g.edges:
        out[int(a)].add(int(b)); inc[int(b)].add(int(a))
    return out, inc
def node_coords(g): return {int(q): tuple(map(float, c)) for q, c in zip(g.ids, g.coords)}
def positive_int(x, name):
    if type(x) is not int or x < 1: raise ValueError(name + ' must be a positive integer')
    return x
def validate_manifest(m):
    if m.get('schema') != 'coordinate-local-workflow/0.1': raise ValueError('Unsupported manifest schema')
    if m.get('objective') != 'max_cardinality_then_exact_sum_calculated_binary64_distance':
        raise ValueError('Objective must be explicitly declared')
    if m.get('coordinate_unit') not in ('um', 'pixel'): raise ValueError('Explicit unit required')
    gate = m.get('inclusive_gate')
    if type(gate) not in (int, float) or not math.isfinite(gate) or gate <= 0:
        raise ValueError('Positive finite inclusive gate required')
    names = []
    if not isinstance(m.get('cohort'), list) or not m['cohort']: raise ValueError('Nonempty cohort required')
    for f in m['cohort']:
        name = f.get('name'); views = f.get('ordered_views')
        if not isinstance(name, str) or not name or name in names: raise ValueError('Unique nonempty cohort name required')
        names.append(name)
        if not isinstance(views, list) or len(views) < 2: raise ValueError('At least two ordered views required')
        labels = [v.get('label') for v in views]
        if any(not isinstance(s, str) or not s for s in labels) or len(set(labels)) != len(labels):
            raise ValueError('Unique view labels required')
        for row in [f['reference']] + views:
            if not isinstance(row.get('npz'), str) or not row['npz']: raise ValueError('Primitive NPZ path required')
            if Path(row['npz']).is_absolute(): raise ValueError('Input NPZ paths must be relative to explicit input root')
    for k in ('frame_screen_cap', 'component_cap', 'query_cap'): positive_int(m[k], k)
    conventions = m.get('conventions')
    if not isinstance(conventions, list) or not conventions or len(set(conventions)) != len(conventions):
        raise ValueError('Nonempty unique conventions required')
    if set(conventions) - {'per_view_product', 'unchanged_geometry_equality'}:
        raise ValueError('Unsupported convention')

def census(name, ref):
    out, inc = adjacency(ref); coord = node_coords(ref); queries = []; excluded = []
    for q in sorted(coord):
        parents, children = sorted(inc[q]), sorted(out[q]); t = coord[q][0]
        for kind in ('binary_fork', 'three_node_path'):
            reasons = []; nodes = None
            if kind == 'binary_fork':
                if len(children) != 2: reasons.append('outgoing_distinct_child_count_not_2')
                else:
                    if coord[children[0]][0] != coord[children[1]][0]: reasons.append('children_acquisition_indices_differ')
                    if any(coord[c][0] <= t for c in children): reasons.append('children_not_strictly_later')
                    if any(inc[c] != {q} for c in children): reasons.append('child_incoming_parent_count_not_1')
                    nodes = [q] + children
            else:
                if len(parents) != 1: reasons.append('incoming_distinct_parent_count_not_1')
                if len(children) != 1: reasons.append('outgoing_distinct_child_count_not_1')
                if len(parents) == len(children) == 1:
                    nodes = [parents[0], q, children[0]]
                    if len(set(nodes)) != 3: reasons.append('three_nodes_not_distinct')
                    if not coord[nodes[0]][0] < t < coord[nodes[2]][0]: reasons.append('path_acquisition_indices_not_strictly_increasing')
            row = {'query_id': name + ':' + kind + ':' + str(q), 'film': name,
                   'kind': kind, 'anchor_reference_id': q, 'selected': not reasons,
                   'exclusion_reasons': reasons, 'time_gap_policy': 'strict increase; gaps retained'}
            if reasons: excluded.append(row)
            else:
                row['nodes'] = nodes; row['node_acquisition_indices'] = [int(coord[n][0]) for n in nodes]
                queries.append(row)
    return queries, excluded

def derive_links(blocks, bases, states, stages):
    domains = {(b['stage'], q): sorted({a[str(q)] for a in b['assignments']}, key=repr)
               for b in blocks for q in b['references']}
    coords = {s: node_coords(g) for s, g in zip(stages, states)}; links = []; rejected = []
    for q in sorted({q for s, q in domains}):
        for left, right in zip(stages, stages[1:]):
            ld = domains.get((left, q), [bases[left].get(q)])
            rd = domains.get((right, q), [bases[right].get(q)])
            same_domain = ld == rd
            same_coords = same_domain and all(p is None or coords[left][p] == coords[right][p] for p in ld)
            row = {'reference_id': q, 'left': left, 'right': right, 'left_domain': ld, 'right_domain': rd}
            if same_coords and (left, q) in domains and (right, q) in domains: links.append(row)
            elif not same_coords: rejected.append(dict(row, reason='domain_changed' if not same_domain else 'coordinate_changed'))
    return links, rejected

def components(blocks, links, bases, cap):
    parent = list(range(len(blocks)))
    def root(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    block_owner = {(b['stage'], q): i for i, b in enumerate(blocks) for q in b['references']}
    for l in links:
        a = root(block_owner[l['left'], l['reference_id']]); b = root(block_owner[l['right'], l['reference_id']]); parent[b] = a
    groups = collections.defaultdict(list)
    for i in range(len(blocks)): groups[root(i)].append(i)
    result = []; owner = {}; failures = []
    for indices in sorted(groups.values(), key=lambda x: min(x)):
        cid = len(result); required = math.prod(len(blocks[i]['assignments']) for i in indices)
        c = {'id': cid, 'block_indices': indices, 'raw_product': required, 'configurations': [], 'default': 0}
        applicable = [l for l in links if block_owner[l['left'], l['reference_id']] in indices]
        if required > cap:
            failures.append({'reason': 'component_cap', 'id': cid, 'required': required, 'cap': cap})
        else:
            for choices in itertools.product(*(range(len(blocks[i]['assignments'])) for i in indices)):
                mapping = {(blocks[i]['stage'], int(q)): p for i, ai in zip(indices, choices)
                           for q, p in blocks[i]['assignments'][ai].items()}
                if any(mapping.get((l['left'], l['reference_id']), bases[l['left']].get(l['reference_id'])) !=
                       mapping.get((l['right'], l['reference_id']), bases[l['right']].get(l['reference_id'])) for l in applicable):
                    continue
                c['configurations'].append(list(choices))
            if not c['configurations']: failures.append({'reason': 'no_feasible_component', 'id': cid})
        for bi in indices:
            for q in blocks[bi]['references']: owner[blocks[bi]['stage'], q] = cid
        result.append(c)
    return result, owner, failures

def project_query(q, stages, bases, blocks, comps, owner, adj, convention, cap, failures):
    header = dict(q, convention=convention, stage_order=stages)
    if failures:
        return dict(header, status='WITHHELD_INCOMPLETE_CONSTRUCTION', failures=failures,
                    pair_recovery=None, structural_consistency=None, witnesses=None)
    relevant = sorted({owner[s, n] for s in stages for n in q['nodes'] if (s, n) in owner})
    required = math.prod(len(comps[i]['configurations']) for i in relevant)
    if required > cap:
        return dict(header, status='WITHHELD_QUERY_CAP', required=required, cap=cap,
                    pair_recovery=None, structural_consistency=None, witnesses=None)
    paired = {}; edge0 = set(); edge1 = set()
    for chosen in itertools.product(*(range(len(comps[i]['configurations'])) for i in relevant)):
        ci = {i: c['default'] for i, c in enumerate(comps)}; ci.update(zip(relevant, chosen))
        repl = {}
        for i in relevant:
            c = comps[i]
            for bi, ai in zip(c['block_indices'], c['configurations'][ci[i]]):
                repl.update({(blocks[bi]['stage'], int(n)): p for n, p in blocks[bi]['assignments'][ai].items()})
        def lookup(s, n): return repl.get((s, n), bases[s].get(n))
        r, c, e0, e1 = history_projection(q['kind'], q['nodes'], stages, lookup, adj)
        edge0.add(e0); edge1.add(e1)
        paired.setdefault((r, c), {'component_configuration_indices': [ci[i] for i in range(len(comps))],
                                  'mapped_query_nodes_by_view': [[lookup(s, n) for n in q['nodes']] for s in stages]})
    def readout(index):
        hs = sorted({x[index] for x in paired}); witnesses = {}
        for h in hs: witnesses[h] = paired[next(x for x in sorted(paired) if x[index] == h)]
        return {'histories': hs, 'categories': sorted({final_category(h) for h in hs}),
                'per_view_possibilities': [sorted({int(h[k]) for h in hs}) for k in range(len(stages))],
                'history_witnesses': witnesses}
    return dict(header, status='COMPLETE', relevant_component_indices=relevant, relevant_combinations=required,
                pair_recovery=readout(0), structural_consistency=readout(1),
                joint_history_pairs=[list(x) for x in sorted(paired)],
                independent_incident_edge_relaxation=independent_edge_relaxation(sorted(edge0), sorted(edge1)),
                witness_extension='All unrelated components use the explicitly feasible default index 0',
                not_biological_type=True, not_joint_whole_graph_extrema=True)

def run(manifest_path, input_root, output):
    if not __debug__:
        raise RuntimeError('CONSTRUCTOR_ASSERTIONS_DISABLED: run without -O and PYTHONOPTIMIZE')
    start = time.perf_counter(); output.mkdir(parents=True, exist_ok=False)
    manifest_path = manifest_path.resolve(); input_root = input_root.resolve(); inputs = [pin(manifest_path)]
    m = json.loads(manifest_path.read_text(encoding='utf-8-sig')); validate_manifest(m)
    emit(output/'RUN_START.json', {'UTC': utc(), 'argv': sys.argv, 'pid': os.getpid(),
         'python': sys.version, 'numpy': np.__version__, 'scipy': scipy.__version__, 'platform': platform.platform(),
         'manifest': pin(manifest_path), 'input_root': str(input_root), 'producer_consumes_old_families': False})
    def consume(row):
        p = (input_root / row['npz']).resolve()
        if not p.is_relative_to(input_root): raise ValueError('Input escapes explicit input root')
        record = pin(p)
        if row.get('sha256') is not None and row['sha256'] != record['sha256']: raise ValueError('Input hash mismatch')
        inputs.append(record); g = load_npz(p)
        if g.unit != m['coordinate_unit']: raise ValueError('Graph unit differs from manifest')
        return g
    totals = collections.Counter(); reports = output/'REPORTS.jsonl'
    with reports.open('x', encoding='utf-8', newline='\n') as report_handle:
        for film_index, f in enumerate(m['cohort']):
            name = f['name']; ref = consume(f['reference']); states = [consume(v) for v in f['ordered_views']]
            stages = [v['label'] for v in f['ordered_views']]; bases = {}; blocks = []; certificates = []; failures = []
            for s, state in zip(stages, states):
                base = match(state, ref, m['inclusive_gate']); bases[s] = base
                for frame in sorted(set(ref.coords[:, 0])):
                    cert, finite, _, failure = frame_family(ref, state, base, m['inclusive_gate'], frame, m['frame_screen_cap'])
                    cert['stage'] = s; certificates.append(cert)
                    if failure: failures.append(dict(failure, stage=s, acquisition_index=int(frame)))
                    if finite is not None:
                        finite['stage'] = s; finite['id'] = len(blocks); blocks.append(finite)
            adj = {s: adjacency(g) for s, g in zip(stages, states)}
            queries, exclusions = census(name, ref)
            links, rejected = derive_links(blocks, bases, states, stages)
            assemblies = {}
            for convention in m['conventions']:
                comps, owner, cf = components(blocks, links if convention == 'unchanged_geometry_equality' else [], bases, m['component_cap'])
                af = failures + cf
                assemblies[convention] = {'components': comps, 'failures': af,
                   'complete_factorization': not af, 'global_complete_map_count': math.prod(len(c['configurations']) for c in comps) if not af else None,
                   'proof': 'Whole-frame maps already certify injection/cardinality/exact cost. Frame domains partition object IDs. Explicit equality links join all connected blocks. No remaining constraint crosses components. Every unrelated component has a saved feasible default; each query can extend to a complete global map.'}
                for q in queries:
                    row = project_query(q, stages, bases, blocks, comps, owner, adj, convention, m['query_cap'], af)
                    report_handle.write(json.dumps(row, ensure_ascii=False, separators=(',', ':'))+'\n')
                    totals[row['status']] += 1
                    if row['status'] == 'COMPLETE':
                        totals['ambiguous_histories_'+convention] += len(row['pair_recovery']['histories']) > 1
                        totals['ambiguous_categories_'+convention] += len(row['pair_recovery']['categories']) > 1
            emit(output/f'film_{film_index:04d}_construction.json', {'film': name, 'stage_order': stages,
                 'canonical_maps': {s: [[q, p] for q, p in sorted(base.items())] for s, base in bases.items()},
                 'finite_blocks': blocks, 'frame_certificates': certificates, 'links': links, 'rejected_links': rejected,
                 'assemblies': assemblies, 'family_convention': 'exact calculated binary64 distance only'})
            emit(output/f'film_{film_index:04d}_census.json', {'film': name, 'queries': queries, 'exclusions': exclusions})
            totals['queries'] += len(queries); totals['binary_fork'] += sum(q['kind']=='binary_fork' for q in queries)
            totals['three_node_path'] += sum(q['kind']=='three_node_path' for q in queries)
            totals['frame_certificates'] += len(certificates)
            print(json.dumps({'film': name, 'queries': len(queries), 'frame_certificates': len(certificates), 'frame_failures': len(failures)}, ensure_ascii=False), flush=True)
    emit(output/'INPUTS_CONSUMED.json', {'UTC': utc(), 'files': inputs})
    sources = [pin(p) for p in [Path(__file__).resolve(), HERE/'local_graph_core.py',
                 HERE/'scientific_backend/reconstruct.py', HERE/'scientific_backend/sources/executed/stage_accounting.py']]
    emit(output/'RUN_COMPLETE.json', {'UTC': utc(), 'status': 'EXECUTED_WITH_EXPLICIT_OUTCOME_COUNTS',
         'counts': dict(totals), 'cohort': len(m['cohort']), 'elapsed_compute_seconds': time.perf_counter()-start,
         'producer_scientific_source_files': sources, 'new_biological_N': 0,
         'data_redistribution_permission_inferred': False})
    rows = [pin(p) for p in sorted(output.iterdir()) if p.is_file()]
    for r in rows: r['path'] = str(Path(r['path']).relative_to(output))
    emit(output/'OUTPUT_FREEZE.json', {'UTC': utc(), 'self_excluded': True, 'files': rows})

if __name__ == '__main__':
    if not __debug__:
        raise RuntimeError('CONSTRUCTOR_ASSERTIONS_DISABLED: run without -O and PYTHONOPTIMIZE')
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--manifest', type=Path, required=True); ap.add_argument('--input-root', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True); a = ap.parse_args()
    try: run(a.manifest, a.input_root, a.output)
    except Exception as error:
        if a.output.is_dir() and not (a.output/'RUN_FAILURE.json').exists():
            emit(a.output/'RUN_FAILURE.json', {'UTC': utc(), 'status': 'FAILED_NO_COMPLETE_REPORT_CERTIFICATION',
                 'error_type': type(error).__name__, 'error': str(error), 'traceback': traceback.format_exc()})
        raise
