"""Complete identity contrasts from existing event matches, without new scoring."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

D = Path(__file__).resolve().parent
OUT = D / 'policy_event_identities_v0.1'

def main():
    OUT.mkdir(exist_ok=False)
    rows, pins = [], {str(Path(__file__)): hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    for i in range(1, 30):
        film = f'{i:02d}'
        p = D / 'actual_v0.1' / f'{film}_EVENTS.json'
        b = p.read_bytes(); pins[str(p)] = hashlib.sha256(b).hexdigest()
        grouped = {(r['arm'], r['tolerance_frames']): r for r in json.loads(b)}
        for arm in ('max_area', 'all_components'):
            for tol in (0, 1):
                base = {r['reference_mother']: r for r in grouped['baseline', tol]['matched_pairs']}
                treat = {r['reference_mother']: r for r in grouped[arm, tol]['matched_pairs']}
                gain, loss = sorted(treat.keys() - base.keys()), sorted(base.keys() - treat.keys())
                rows.append({'film': film, 'arm': arm, 'tolerance_frames': tol,
                             'gained_reference_mothers': gain, 'lost_reference_mothers': loss,
                             'gained_pairs': [treat[k] for k in gain], 'lost_pairs': [base[k] for k in loss],
                             'net_matched_reference_events': len(treat) - len(base),
                             'turnover': len(gain) + len(loss)})
    result = {'UTC': datetime.now(timezone.utc).isoformat(),
              'status': 'ALL116_POLICY_EVENT_IDENTITY_CONTRASTS_COMPLETE',
              'all_rows': rows, 'non_null_rows': [r for r in rows if r['turnover']],
              'scope': 'Actual previously scored event identity census; within existing29 cohort, not new inference/N or causal/utility/Major closure evidence.'}
    (OUT / 'RESULT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (OUT / 'INPUT_BINDINGS.json').write_text(json.dumps(pins, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'all_rows'}, ensure_ascii=False))

if __name__ == '__main__':
    main()
