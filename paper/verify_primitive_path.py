"""Independently enumerate a bound path task from its primitive NPZ inputs.

The existing literal component enumerator reads the raw gated cost graph,
never producer supports, potentials or comparison targets to select maps.
Completed enumeration checks exact K/C, stored certificates, full set equality
and the readout. A cap interruption withholds certification. No biological
truth, real-number distance optimum or unrelated cohort is certified.
"""
from pathlib import Path
from types import SimpleNamespace
from fractions import Fraction
from itertools import product
import argparse, hashlib, importlib.util, json, math
import numpy as np

HERE = Path(__file__).resolve().parent

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def require(condition, message):
    if not condition:
        raise ValueError(message)

def graph(path, unit):
    with np.load(path, allow_pickle=False) as z:
        if 'unit' in z:
            stored = z['unit']
            require(stored.shape == () and stored.dtype.kind == 'U', 'Invalid NPZ unit metadata: scalar Unicode required')
            require(stored.item() in ('pixel', 'um'), 'Unsupported NPZ unit metadata')
            require(stored.item() == unit, 'NPZ unit metadata conflicts with declared input unit')
        ids, coords, edges = z['ids'].copy(), z['coords'].astype(np.float64, copy=True), z['edges'].copy()
    require(ids.ndim == 1 and ids.dtype.kind in 'iu', 'Invalid integer IDs')
    require(coords.shape == (len(ids), 4) and np.isfinite(coords).all(), 'Invalid coordinates')
    require(len(set(map(int, ids))) == len(ids), 'Duplicate IDs')
    require(np.equal(coords[:, 0], np.floor(coords[:, 0])).all(), 'Noninteger frames')
    require(edges.ndim == 2 and edges.shape[1] == 2 and edges.dtype.kind in 'iu', 'Invalid edges')
    require(set(map(int, edges.ravel())) <= set(map(int, ids)), 'Unknown edge endpoints')
    require(unit in ('pixel', 'um'), 'Explicit input unit required')
    if unit == 'pixel':
        coords[:, 1:] *= [1.625, .40625, .40625]
    return SimpleNamespace(ids=ids, coords=coords, edges=edges)

def signature(mapping):
    return tuple(sorted((int(r), int(p)) for r, p in mapping.items()))

def check_certificate(ref, pred, frame, gate, cert, independent):
    require(cert['frame'] == frame, 'Certificate frame differs from declared frame')
    require(cert['residual_potentials_order'] == 'reference_ids,prediction_ids,source,sink', 'Unsupported potential ordering')
    ri = sorted(np.flatnonzero(ref.coords[:, 0] == frame), key=lambda i: int(ref.ids[i]))
    pi = sorted(np.flatnonzero(pred.coords[:, 0] == frame), key=lambda i: int(pred.ids[i]))
    rs, ps = [int(ref.ids[i]) for i in ri], [int(pred.ids[i]) for i in pi]
    dist = np.hypot.reduce(ref.coords[ri, None, 1:] - pred.coords[None, pi, 1:], axis=2)
    costs = {(rs[i], ps[j]): Fraction.from_float(float(dist[i, j]))
             for i, j in zip(*np.nonzero(dist <= gate))}
    require(cert['reference_ids'] == rs and cert['prediction_ids'] == ps, 'Certificate endpoint domain mismatch')
    denom = int(cert['exact_cost_denominator'])
    require(denom > 0, 'Invalid cost denominator')
    stored = {}
    for r, p, hx, integer in cert['allowed_costs']:
        require((r, p) not in stored, 'Duplicate candidate cost')
        require(Fraction.from_float(float.fromhex(hx)) == Fraction(int(integer), denom), 'Stored cost representations differ')
        stored[r, p] = Fraction(int(integer), denom)
    require(stored == costs, 'Primitive gate/cost graph differs from certificate')
    base = dict(cert['canonical_pairs'])
    require(len(base) == len(cert['canonical_pairs']) and len(set(base.values())) == len(base), 'Noninjective canonical map')
    require(all(pair in costs for pair in base.items()), 'Canonical uses disallowed pair')
    k = independent['max_cardinality']
    c = Fraction(independent['exact_calculated_distance_sum'])
    require(len(base) == cert['max_cardinality'] == k, 'Maximum cardinality mismatch')
    require(sum((costs[x] for x in base.items()), Fraction()) == c == Fraction(int(cert['canonical_exact_integer_sum']), denom), 'Minimum exact cost mismatch')
    cover = set(map(tuple, cert['minimum_vertex_cover']))
    require(len(cover) == len(cert['minimum_vertex_cover']) == k, 'Invalid cover size')
    require(cover <= {('reference', r) for r in rs} | {('prediction', p) for p in ps}, 'Invalid cover endpoint')
    require(all(('reference', r) in cover or ('prediction', p) in cover for r, p in costs), 'Uncovered gated edge')
    h = list(map(int, cert['residual_potentials']))
    require(len(h) == len(rs) + len(ps) + 2, 'Invalid potential dimension')
    rx, px = {r: i for i, r in enumerate(rs)}, {p: len(rs) + i for i, p in enumerate(ps)}
    s, t = len(rs) + len(ps), len(rs) + len(ps) + 1
    arcs = [(rx[r], s, 0) if r in base else (s, rx[r], 0) for r in rs]
    arcs += [(t, px[p], 0) if p in base.values() else (px[p], t, 0) for p in ps]
    for (r, p), value in costs.items():
        iv = value * denom
        require(iv.denominator == 1, 'Nonintegral scaled cost')
        arcs.append((px[p], rx[r], -int(iv)) if base.get(r) == p else (rx[r], px[p], int(iv)))
    require(all(v + h[u] - h[w] >= 0 for u, w, v in arcs), 'Negative reduced residual cost')
    return {'frame': frame, 'maximum_cardinality': k, 'minimum_calculated_distance_sum': str(c),
            'raw_gated_edges': len(costs), 'full_optimum_maps': len(independent['whole_maps']),
            'partial_injection_leaves': independent['enumerated_partial_injection_leaves'],
            'primitive_cost_graph_cover_and_residual_potentials_checked': True}

def verify(directory, reference=None, prediction=None, cap=1048576):
    require(type(cap) is int and cap > 0, 'Positive verification cap required')
    directory = Path(directory).resolve()
    binding = json.loads((directory / 'REPORT_BINDING.json').read_text(encoding='utf8'))
    require(binding['schema'] == 'bound-path-audit/1.2', 'Unsupported binding')
    required = {'INPUT_AND_QUERY_CONTRACT.json', 'REPORT.json', 'COMPLETE_FRAME_FAMILIES.json'}
    require(set(binding['files']) == required, 'Incomplete binding file set')
    for name, expected in binding['files'].items():
        require(sha(directory / name) == expected, 'Bound artifact hash mismatch')
    contract = json.loads((directory / 'INPUT_AND_QUERY_CONTRACT.json').read_text(encoding='utf8'))
    report = json.loads((directory / 'REPORT.json').read_text(encoding='utf8'))
    require(report['status'] == 'COMPLETE', 'A withheld task cannot be certified as complete')
    paths = {'reference': Path(reference or contract['reference']['path']), 'prediction': Path(prediction or contract['prediction']['path'])}
    for kind, path in paths.items():
        require(sha(path) == contract[kind]['sha256'], 'Primitive input hash mismatch: ' + kind)
    ref, pred = [graph(paths[k], contract['unit_in']) for k in ('reference', 'prediction')]
    gate = contract['gate_um_inclusive']
    require(math.isfinite(gate) and gate > 0, 'Invalid gate')
    require(contract['objective'] == 'maximum cardinality then exact binary-rational sum of numpy.hypot.reduce float64 distances', 'Unsupported objective')
    require(contract['convention'] == 'independent complete optimal maps across acquisition frames of one fixed snapshot', 'Unsupported convention')
    require(contract['query'] == 'pair_recovery of both incident pairs under shared complete maps' and report['query_name'] == 'pair_recovery', 'Unsupported or inconsistent query identity')
    require(type(contract['proposed_value']) is int and contract['proposed_value'] in (0,1), 'Invalid contract proposal')
    require(type(report['proposed_value']) is int and report['proposed_value'] == contract['proposed_value'], 'Report proposal differs from contract')
    a, b, c = contract['reference_path']
    times = dict(zip(map(int, ref.ids), map(int, ref.coords[:, 0])))
    require(len({a,b,c}) == 3 and all(q in times for q in (a,b,c)), 'Invalid reference path IDs')
    frames = [times[q] for q in (a,b,c)]
    require(frames[0] < frames[1] < frames[2], 'Invalid reference frame order')
    require({(a,b),(b,c)} <= set(map(tuple, ref.edges.tolist())), 'Reference path edges missing')
    ff = json.loads((directory / 'COMPLETE_FRAME_FAMILIES.json').read_text(encoding='utf8'))
    require(ff['frames'] == frames and len(ff['certificates']) == len(ff['whole_maps']) == 3, 'Frame family domain mismatch')
    baseline_path = HERE / 'scientific/extensions/natural/literal_constrained_baseline_v03.py'
    spec = importlib.util.spec_from_file_location('independent_literal_baseline', baseline_path)
    baseline = importlib.util.module_from_spec(spec); spec.loader.exec_module(baseline)
    domains, checks = [], []
    try:
        for frame, certificate, supplied in zip(frames, ff['certificates'], ff['whole_maps']):
            _, _, independent = baseline.build_frame(ref, pred, frame, gate, cap)
            actual = [tuple(map(tuple, m)) for m in independent['whole_maps']]
            expected = [signature(m) for m in supplied]
            require(len(expected) == len(set(expected)) and set(actual) == set(expected), 'Incomplete or incorrect supplied optimum family')
            checks.append(check_certificate(ref, pred, frame, gate, certificate, independent))
            domains.append([dict(m) for m in actual])
        if math.prod(map(len, domains)) > cap:
            raise OverflowError('WITHHELD_LITERAL_JOINT_OUTPUT_CAP')
    except OverflowError as e:
        return {'status': 'WITHHELD_INDEPENDENT_ENUMERATION', 'reason': str(e), 'complete_family_certified': False}
    pairs = set(map(tuple, pred.edges.tolist())); truth = []; inc = [set(),set()]; values = set()
    for maps in product(*domains):
        m = {r:p for item in maps for r,p in item.items()}
        bits = [int(x in m and y in m and (m[x],m[y]) in pairs) for x,y in ((a,b),(b,c))]
        value = bits[0] * bits[1]; values.add(value)
        for i in range(2): inc[i].add(bits[i])
        truth.append((tuple(m.get(q) for q in (a,b,c)), tuple(bits), value))
    supplied_truth = report['complete_joint_truth_table']
    require(len(supplied_truth) == len(truth), 'Joint truth table incomplete')
    seen = set(); supplied_values = []
    for row in supplied_truth:
        ix = row['whole_frame_map_indices']
        require(len(ix) == 3 and all(type(i) is int and 0 <= i < len(f) for i,f in zip(ix,ff['whole_maps'])), 'Invalid truth-table map index')
        require(tuple(ix) not in seen, 'Duplicate truth-table configuration'); seen.add(tuple(ix))
        m = {int(r):int(p) for i,f in zip(ix,ff['whole_maps']) for r,p in f[i].items()}
        require(row['mapped_path'] == [m.get(q) for q in (a,b,c)], 'Indexed truth-table path differs')
        bits = [int(x in m and y in m and (m[x],m[y]) in pairs) for x,y in ((a,b),(b,c))]
        require(row['incident_visibility'] == bits and row['pair_recovery'] == math.prod(bits), 'Indexed truth-table readout differs')
        supplied_values.append((tuple(row['mapped_path']),tuple(bits),math.prod(bits)))
    require(sorted(truth, key=repr) == sorted(supplied_values,key=repr), 'Joint truth-table set differs')
    relaxed = sorted({x*y for x,y in product(*inc)})
    admitted = contract['proposed_value'] in values
    require(report['attainable_values'] == sorted(values), 'Incorrect attainable set')
    require(report['independent_edge_relaxation_values'] == relaxed and report['strict_relaxation_difference'] == (set(relaxed)!=values), 'Incorrect marginal relaxation')
    require(report['proposal_admitted'] == admitted and report['proposal_status'] == ('WITNESSED' if admitted else 'REJECTED_UNATTAINABLE'), 'Incorrect reporting decision')
    require(report['complete_frame_family_sizes'] == list(map(len, domains)), 'Incorrect family sizes')
    require(set(report['whole_frame_witness_indices']) == {str(v) for v in values}, 'Witness-value coverage differs')
    for value, ix in report['whole_frame_witness_indices'].items():
        require(tuple(ix) in seen, 'Witness index outside joint table')
        require(any(row['whole_frame_map_indices'] == ix and row['pair_recovery'] == int(value) for row in supplied_truth), 'Incorrect witness value')
    return {'status':'PRIMITIVE_PATH_VERIFICATION_PASS', 'frames':checks, 'attainable_values':sorted(values),
            'independent_edge_relaxation_values':relaxed, 'proposal_status':report['proposal_status'],
            'complete_family_certified':True, 'calculated_distance_optimality_checked':True,
            'certificate_and_full_family_and_readout_checked':True, 'biological_truth_checked':False,
            'baseline_source_sha256':sha(baseline_path), 'binding_sha256':sha(directory/'REPORT_BINDING.json')}

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--report',type=Path,required=True); ap.add_argument('--reference',type=Path); ap.add_argument('--prediction',type=Path)
    ap.add_argument('--cap',type=int,default=1048576); ap.add_argument('--output',type=Path,required=True)
    args = ap.parse_args(); result = verify(args.report,args.reference,args.prediction,args.cap)
    with args.output.open('x',encoding='utf8') as f: json.dump(result,f,indent=2); f.write('\n')
    print(json.dumps({'status':result['status']}))
    if result['status'] != 'PRIMITIVE_PATH_VERIFICATION_PASS': raise SystemExit(2)

if __name__ == '__main__': main()
