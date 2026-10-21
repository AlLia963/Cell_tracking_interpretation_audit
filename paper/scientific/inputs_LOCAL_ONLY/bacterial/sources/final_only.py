"""Actual finite-cohort identifiability, not a trained final-only classifier.

First freeze canonical complete final-state tokens without reading histories,
then join independently evaluated last-loss targets. Distinguishable final
states are not declared impossible to classify. No extra biological sample.
"""
from pathlib import Path
import collections, datetime, hashlib, json, numpy as np

A = Path(__file__).resolve().parent
B = A / 'reproduction_LOCAL_ONLY_v0.1'
O = A / 'final_only_actual_observation_classes_v0.1'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def save(p, value):
    with Path(p).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


def final_token(p):
    # Only stage3 members are decoded; stage0-2 and generator fault receipts
    # are not input to this observation. Native IDs are preserved, rows sorted.
    with np.load(p, allow_pickle=False) as z:
        ids = z['ids3']
        masks = z['masks3']
        edges = z['edges3']
        division = z['division3']
    assert ids.ndim == 1 and len(set(map(int, ids))) == len(ids)
    assert masks.ndim == 3 and masks.shape[0] == len(ids)
    assert masks.dtype == np.dtype('bool')
    order = np.argsort(ids)
    h = hashlib.sha256()
    h.update(json.dumps({'ids': list(map(int, ids[order])), 'shape': list(masks.shape),
                         'edges': sorted(set(map(tuple, edges.tolist()))),
                         'division': sorted(set(map(tuple, division.tolist())))},
                        separators=(',', ':'), sort_keys=True).encode())
    h.update(np.ascontiguousarray(masks[order]).tobytes())
    return h.hexdigest()


def summarize(rows, label):
    groups = collections.defaultdict(list)
    for r in rows:
        groups[(r['film'], tuple(r['reference_edge']), r['final_state_token'])].append(r)
    majority_ceiling = 0
    conflict_rows = 0
    groups_out = []
    for key, group in sorted(groups.items()):
        targets = collections.Counter(str(r['last_loss']) for r in group)
        majority_ceiling += max(targets.values())
        conflict = len(targets) > 1
        conflict_rows += len(group) if conflict else 0
        groups_out.append({'film': key[0], 'reference_edge': list(key[1]), 'final_state_token': key[2],
                           'case_ordinals': [r['case_ordinal'] for r in group],
                           'last_loss_counts': dict(targets), 'conflicting_targets': conflict})
    result = {'domain': label, 'cases': len(rows), 'observation_classes': len(groups),
              'conflicting_classes': sum(g['conflicting_targets'] for g in groups_out),
              'cases_in_conflicting_classes': conflict_rows,
              'unavoidable_errors_of_single_valued_final_only_predictor_in_this_empirical_cohort': len(rows) - majority_ceiling,
              'oracle_in_sample_majority_ceiling_correct': majority_ceiling,
              'groups': groups_out,
              'interpretation': 'Exact collisions prove non-identifiability within these observed classes. The majority ceiling is an in-sample bound with cohort target frequencies, not trained/held-out performance, calibrated probability or deployment accuracy. Distinct classes may be separable; refusal of all cases is a conservative policy, not a demonstrated necessity for every case.'}
    save(O / (label + '.json'), result)
    return {k: v for k, v in result.items() if k not in ('groups', 'interpretation')}


def main():
    O.mkdir(exist_ok=False)
    protocol = '''All 290 existing actual-support overlays; no target replacement or new data. Before joining histories, decode only full stage3 IDs, mask supports, raw pairs and division membership. Canonicalize row order by supplied identity and set order; preserve complete final observable semantics. Film and requested reference relation are fixed query context. No arm tag, earlier graph, origin receipt or last-loss label enters the final-state hash. Freeze tokens first. Then join the existing independently evaluated oracle. Report separately the 130 eligible final-missing known-last-loss task and all determinate final-missing cases including no-observed-loss targets. Ambiguous and reference-ineligible histories remain excluded, with counts. Exact observational collisions with contradictory labels demonstrate non-identifiability only in those classes. Empirical majority ceiling is a combinatorial in-sample bound, not classifier validation or knowledge available to a deployed observer. No new N, accuracy superiority over equal-information differencing, biological causal responsibility or human utility. Retrospective analysis after prior controls were known; no pre-registration claim.'''
    with (O / 'PROTOCOL.md').open('x', encoding='utf-8') as f:
        f.write(protocol)
    receipts_path = B / 'native_noisy_controls_v0.2/generator_receipts.json'
    results_path = B / 'native_noisy_validation_v0.3/case_records.json'
    receipts = read(receipts_path)
    bindings = []
    tokens = []
    ordinal = 0
    for video in receipts['videos']:
        for case in video['cases']:
            p = B / 'native_noisy_controls_v0.2' / case['fixture']
            assert sha(p) == case['sha256']
            tokens.append({'case_ordinal': ordinal, 'film': video['video'],
                           'final_state_token': final_token(p)})
            bindings.append({'ordinal': ordinal, 'fixture_sha256': case['sha256']})
            ordinal += 1
    assert len(tokens) == 290
    save(O / 'FINAL_OBSERVATIONS_BEFORE_LABEL_JOIN.json', tokens)
    save(O / 'BEFORE_LABEL_JOIN.json', {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'source_sha256': sha(__file__), 'protocol_sha256': sha(O / 'PROTOCOL.md'),
          'final_observations_sha256': sha(O / 'FINAL_OBSERVATIONS_BEFORE_LABEL_JOIN.json'),
          'generator_receipt_sha256': sha(receipts_path), 'oracle_result_current_sha256': sha(results_path),
          'fixture_bindings': bindings, 'oracle_results_opened_yet': False,
          'generator_tags': 'locator enumeration only, never predictor/observation token inputs'})
    measured = read(results_path)
    assert len(measured) == len(tokens)
    joined = []
    excluded = collections.Counter()
    for token, r in zip(tokens, measured):
        assert token['film'] == r['video']
        if r['status'] != 'evaluated-controlled-path':
            excluded[r['status']] += 1
            continue
        path = r['oracle_visibility']
        assert len(path) == 4 and all(v in (0, 1) for v in path)
        if path[-1]:
            excluded['determinate_final_visible_not_last_loss_task'] += 1
            continue
        joined.append(dict(token, reference_edge=r['reference_edge'],
                           last_loss=r['oracle_last_observed_loss_when_final_missing'],
                           known_last_loss_eligible=r['boundary_task_eligible']))
    known = [r for r in joined if r['known_last_loss_eligible']]
    assert len(known) == 130
    outputs = [summarize(known, 'known_last_loss_130'),
               summarize(joined, 'all_determinate_final_missing')]
    save(O / 'RESULT.json', {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                          'summaries': outputs, 'excluded': dict(excluded), 'new_biological_N': 0,
                          'major_scientific_contribution_closed': False,
                          'final_only_refusal_is_prespecified_not_optimal_classifier': True})
    print(json.dumps(outputs))


if __name__ == '__main__':
    main()
