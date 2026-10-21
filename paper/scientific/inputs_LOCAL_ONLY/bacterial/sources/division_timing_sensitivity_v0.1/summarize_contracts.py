"""Join actual event identities with strict lineage certificates; no new matching."""
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

A = Path(__file__).resolve().parents[1]
D = Path(__file__).resolve().parent
OUT = D / 'contract_comparison_v0.1'

def read(path, pins):
    b = path.read_bytes()
    pins[str(path)] = hashlib.sha256(b).hexdigest()
    return json.loads(b)

def main():
    OUT.mkdir(exist_ok=False)
    pins = {str(Path(__file__)): hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    rows, remainder, contrasts = [], [], []
    by_arm = {a: {'additional_shift_patterns': Counter(), 'exact_total': 0,
                  'relaxed_total': 0, 'remaining_total': 0} for a in ('baseline', 'max_area', 'all_components')}
    exact_eq, cross_eq = [], []
    for i in range(1, 30):
        film = f'{i:02d}'
        v = read(D / 'actual_v0.1' / f'{film}_EVENTS.json', pins)
        old = read(A / 'lineage_consequence_v0.1/results_v0.2' / f'{film}_RECORDS.json', pins)
        events = {int(e['mother']): e for e in old['division_events']}
        domain = set(events)
        grouped = {(r['arm'], r['tolerance_frames']): r for r in v}
        assert len(grouped) == 6
        sets = {}
        for arm in by_arm:
            exact, relaxed = grouped[arm, 0], grouped[arm, 1]
            s0 = {p['reference_mother'] for p in exact['matched_pairs']}
            s1 = {p['reference_mother'] for p in relaxed['matched_pairs']}
            certificate = {k for k, e in events.items() if e['recovered'][arm]}
            assert s0 <= s1 <= domain
            exact_eq.append({'film': film, 'arm': arm, 'equal': s0 == certificate,
                             'event_only': sorted(s0 - certificate), 'certificate_only': sorted(certificate - s0)})
            additional = [p for p in relaxed['matched_pairs'] if p['reference_mother'] not in s0]
            shift_counts = Counter()
            for p in additional:
                pattern = str((p['mother_end_shift'], *p['daughter_start_shifts']))
                shift_counts[pattern] += 1
                by_arm[arm]['additional_shift_patterns'][pattern] += 1
            by_arm[arm]['exact_total'] += len(s0)
            by_arm[arm]['relaxed_total'] += len(s1)
            by_arm[arm]['remaining_total'] += len(domain - s1)
            for mother in sorted(domain - s1):
                e = events[mother]
                remainder.append({'film': film, 'arm': arm, 'reference_mother': mother,
                                  'reference_daughters': e['daughters'], 'reference_frame': e['frame'],
                                  'interpretation': 'Unmatched under stated complete-event contract; cause not inferred'})
            sets[arm] = (s0, s1)
            rows.append({'film': film, 'arm': arm, 'reference_events': len(domain),
                         'exact_TP': len(s0), 'relaxed_TP': len(s1),
                         'additional': len(s1 - s0), 'remaining': len(domain - s1),
                         'additional_shift_patterns': dict(sorted(shift_counts.items()))})
        for arm in ('max_area', 'all_components'):
            cross_eq.append({'film': film, 'arm': arm,
                             'exact_matched_reference_ids_equal_baseline': sets[arm][0] == sets['baseline'][0],
                             'relaxed_matched_reference_ids_equal_baseline': sets[arm][1] == sets['baseline'][1]})
            for tol in (0, 1):
                base, treatment = grouped['baseline', tol], grouped[arm, tol]
                delta = Fraction(treatment['F1_exact']) - Fraction(base['F1_exact'])
                contrasts.append({'film': film, 'arm': arm, 'tolerance_frames': tol,
                                  'TP_delta': treatment['division_TP'] - base['division_TP'],
                                  'FP_delta': treatment['division_FP'] - base['division_FP'],
                                  'FN_delta': treatment['division_FN'] - base['division_FN'],
                                  'F1_delta_exact': str(delta), 'F1_delta': float(delta),
                                  'direction': 'positive' if delta > 0 else 'negative' if delta < 0 else 'null'})
    directions = {}
    for arm in ('max_area', 'all_components'):
        directions[arm] = {str(t): dict(Counter(r['direction'] for r in contrasts if r['arm'] == arm and r['tolerance_frames'] == t)) for t in (0, 1)}
    result = {'UTC': datetime.now(timezone.utc).isoformat(),
              'status': 'ALL87_EVENT_IDENTITY_AND_CERTIFICATE_CONTRACTS_JOINED',
              'all87_exact_event_reference_ids_equal_strict_certificate_ids': all(x['equal'] for x in exact_eq),
              'all58_policy_reference_id_set_comparisons_equal_baseline_at_both_tolerances': all(x['exact_matched_reference_ids_equal_baseline'] and x['relaxed_matched_reference_ids_equal_baseline'] for x in cross_eq),
              'per_arm': by_arm, 'paired_F1_directions': directions,
              'movie_count': 29, 'source_rows': 174, 'paired_F1_contrasts': len(contrasts),
              'unmatched_references': remainder,
              'scope': 'Descriptive join of already executed full-cohort measurements; no independent new raw recomputation, new N, biological cause, whole-chain relaxation, utility advantage, official CTC certification or Major closure.'}
    for name, obj in [('RESULT.json', result), ('ALL87_JOIN.json', rows),
                      ('EXACT_CERTIFICATE_IDENTITIES.json', exact_eq), ('POLICY_MATCHED_IDENTITIES.json', cross_eq),
                      ('INPUT_BINDINGS.json', pins)]:
        (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with (OUT / 'ALL116_PAIRED_F1_CONTRASTS.csv').open('x', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(contrasts[0])); w.writeheader(); w.writerows(contrasts)
    print(json.dumps({k: v for k, v in result.items() if k != 'unmatched_references'}, ensure_ascii=False))

if __name__ == '__main__':
    main()
