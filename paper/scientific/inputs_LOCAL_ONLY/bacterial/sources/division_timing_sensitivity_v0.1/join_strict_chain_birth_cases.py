"""Audit the30 strict type-omission examples under a different event-time contract."""
from pathlib import Path
from datetime import datetime, timezone
import json,hashlib
P=Path(__file__).resolve().parent;A=P.parent
L=A/'lineage_consequence_v0.1'/'results_v0.2'
S=P/'actual_v0.1';O=P/'strict_birth_case_join_v0.1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,d):
    with p.open('x',encoding='utf-8') as f:json.dump(d,f,ensure_ascii=False,indent=2)
assert read(S/'RESULT.json')['status']=='ACTUAL_EXISTING29_THREE_POLICY_DIVISION_TIMING_SENSITIVITY_COMPLETE'
O.mkdir(exist_ok=False)
summary=read(L/'RESULT.json')
ids=summary['birth_to_division_chains']['untyped_complete_but_typed_incomplete_baseline']
assert len(ids)==30
pins={str(L/'RESULT.json'):sha(L/'RESULT.json'),str(S/'RESULT.json'):sha(S/'RESULT.json'),str(P/'join_strict_chain_birth_cases.py'):sha(P/'join_strict_chain_birth_cases.py')}
cases=[]
for film,track in ids:
    lp=L/(film+'_RECORDS.json');sp=S/(film+'_EVENTS.json')
    pins[str(lp)]=sha(lp);pins[str(sp)]=sha(sp)
    chains=read(lp)['birth_to_division_chains']
    row=next(x for x in chains if x['track']==track)
    assert not row['recovered']['baseline'] and row['untyped_baseline_recovered']
    assert row['failure_domains']['baseline']=={'birth':True,'continuation':0,'outgoing_daughters':0}
    incoming=[e for e in row['required_edges'] if e[4]==1 and e[3]==track and e[2]==row['start']]
    assert len(incoming)==1
    mother=incoming[0][1]
    events={x['tolerance_frames']:x for x in read(sp) if x['arm']=='baseline'}
    matching={t:[x for x in events[t]['matched_pairs'] if x['reference_mother']==mother] for t in [0,1]}
    assert len(matching[0])==0 and len(matching[1])<=1
    cases.append({'film':film,'chain_track':track,'incoming_reference_relation':incoming[0],
          'strict_type_failure_domains':row['failure_domains']['baseline'],
          'incoming_complete_reference_event_matched_exact':False,
          'incoming_complete_reference_event_matched_tolerance1':bool(matching[1]),
          'matched_event_tolerance1':matching[1][0] if matching[1] else None,
          'strict_chain_certificate_unchanged':False,
          'interpretation':'Event-time sensitivity only; no relaxed whole-chain certification or biological relabeling implied'})
assert all(sha(Path(p))==h for p,h in pins.items())
recovered=[x for x in cases if x['incoming_complete_reference_event_matched_tolerance1']]
result={'UTC':datetime.now(timezone.utc).isoformat(),'status':'ALL30_STRICT_INCOMING_BIRTH_DISCREPANCIES_EVENT_TIME_AUDITED',
    'case_count':len(cases),'incoming_complete_event_exact_matches':0,
    'incoming_complete_event_one_frame_matches':len(recovered),
    'still_no_complete_event_within_one_frame':len(cases)-len(recovered),
    'shift_counts':{str(shift):sum(x['matched_event_tolerance1']['mother_end_shift']==shift for x in recovered) for shift in [-1,0,1]},
    'case_rows':cases,'input_pins':pins,
    'scope':'Different event-time contract; prior30 remain exact-time typed chain discrepancies. Flexible event matching alone neither certifies an entire chain nor establishes the biological correct division frame. No framework utility/same-info advantage/newN/fourarmGT/Major closure.'}
write(O/'RESULT.json',result)
print(json.dumps({k:v for k,v in result.items() if k not in ['case_rows','input_pins']},ensure_ascii=False))
