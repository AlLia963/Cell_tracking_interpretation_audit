"""Descriptive full-identity readouts, frozen before independent result comparison."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import csv, hashlib, json, itertools

D=Path(__file__).resolve().parent;A=D.parent;O=D/'readout_v0.1'
old=A/'original3d_correspondence_margin_v0.1'
specs={
    '6_equal_distance':(6,D/'gate_06/margin_v0.1',D/'gate_06/family_v0.1'),
    '7_primary_equal_distance':(7,old/'actual_v0.1',old/'tie_envelope_v0.2'),
    '8_finite_calculated_double':(8,D/'gate_08/margin_v0.1',D/'gate_08/finite_objective_family_v0.4'),
    '8_numerical_tolerance':(8,D/'gate_08/margin_v0.1',D/'gate_08/numerical_family_v0.3'),
}
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def emit(path,obj):
    with path.open('x',encoding='utf-8',newline='\n') as stream:json.dump(obj,stream,ensure_ascii=False,indent=2)
def category(history):
    if history[-1]=='1':return 'not-final-missing'
    losses=[k for k in range(1,7) if history[k-1:k+1]=='10']
    return 'last-loss-'+str(losses[-1]) if losses else 'persistent'
def coarse(cat):return 'observed-loss' if cat.startswith('last-loss-') else cat
def key(row):return (row['film'],tuple(row['reference_edge']))
def csvout(path,rows):
    with path.open('x',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def run():
    O.mkdir(exist_ok=False);pins={};allsets={};summaries=[];scalar=[];identityrows=[]
    for label,(gate,margin,family) in specs.items():
        paths=[margin/'CANONICAL_HISTORIES.json',family/'EDGE_HISTORY_SETS.json',family/'MARGINAL_HISTORY_ENVELOPE.json',family/'RESULT.json']
        pins.update({str(path):sha(path) for path in paths})
        canonical=json.loads(paths[0].read_text(encoding='utf-8'))
        sets={key(row):{''.join(map(str,row['visibility']))} for row in canonical}
        assert len(sets)==len(canonical)==5751
        for row in json.loads(paths[1].read_text(encoding='utf-8')):
            assert key(row) in sets
            sets[key(row)]=set(row['admissible_visibility_strings'])
        env=json.loads(paths[2].read_text(encoding='utf-8'))
        counter=Counter()
        for (film,edge),histories in sorted(sets.items()):
            cats={category(h) for h in histories};broad={coarse(c) for c in cats}
            final={h[-1]=='0' for h in histories}
            counter['history_ambiguous']+=len(histories)>1
            counter['final_missing_status_ambiguous']+=len(final)>1
            counter['determinate_observed_loss']+=broad=={'observed-loss'}
            counter['determinate_persistent']+=broad=={'persistent'}
            counter['determinate_not_final_missing']+=broad=={'not-final-missing'}
            counter['coarse_category_ambiguous']+=len(broad)>1
            counter['last_loss_category_ambiguous']+=len(cats)>1
            identityrows.append({'contract':label,'gate_um':gate,'film':film,'reference_edge':json.dumps(edge),
                'histories':','.join(sorted(histories)),'last_loss_categories':','.join(sorted(cats)),
                'coarse_categories':','.join(sorted(broad))})
        assert counter['determinate_observed_loss']+counter['determinate_persistent']+counter['determinate_not_final_missing']+counter['coarse_category_ambiguous']==5751
        lower=env['persistent_absence']['minimum'];upper=env['final_missing_with_loss']['maximum']
        summaries.append({'contract':label,'gate_um':gate,**dict(counter),
            'final_missing_min':env['final_missing']['minimum'],'final_missing_max':env['final_missing']['maximum'],
            'persistent_min':lower,'persistent_max':env['persistent_absence']['maximum'],
            'observed_loss_min':env['final_missing_with_loss']['minimum'],'observed_loss_max':upper,
            'persistent_dominates_every_admissible_realization':lower>upper})
        for field,values in env.items():scalar.append({'contract':label,'field':field,**values})
        allsets[label]=sets
    assert all(set(data)==set(next(iter(allsets.values()))) for data in allsets.values())
    comparisons=[]
    baseline=allsets['7_primary_equal_distance']
    for label,data in allsets.items():
        if label=='7_primary_equal_distance':continue
        values=Counter()
        for identity,b in baseline.items():
            h=data[identity];bc={category(x) for x in b};hc={category(x) for x in h}
            values['feasible_history_set_changed']+=h!=b
            values['feasible_latest_loss_category_set_changed']+=hc!=bc
            values['latest_loss_category_sets_disjoint']+=not bool(bc&hc)
        comparisons.append({'contract':label,'comparison':'same identities vs7primary;separate contracts, no cross-gate coupling',**dict(values)})
    interval_pairs=[]
    for left,right in itertools.combinations(summaries,2):
        interval_pairs.append({'left':left['contract'],'right':right['contract'],
            'final_missing_intervals_overlap':max(left['final_missing_min'],right['final_missing_min'])<=min(left['final_missing_max'],right['final_missing_max'])})
    for name,rows in [('CONTRACT_READOUTS.csv',summaries),('ALL_31_SCALAR_READOUTS.csv',scalar),
        ('ALL_5751_HISTORY_SETS_BY_CONTRACT.csv',identityrows),('IDENTITY_SET_COMPARISONS_TO7.csv',comparisons),
        ('FINAL_MISSING_INTERVAL_COMPARISONS.csv',interval_pairs)]:csvout(O/name,rows)
    result={'UTC':datetime.now(timezone.utc).isoformat(),'status':'ACTUAL_GATE_FAMILY_PRODUCER_READOUTS_PENDING_INDEPENDENT_ACCEPTANCE',
        'source_pins':pins,'readouts':summaries,'identity_set_comparisons':comparisons,'interval_comparisons':interval_pairs,
        'scope':'Same5751 reference identities, retrospective8films, no new biological N. 8finite and8numerical are distinct added measurement contracts.',
        'limits':['31fields include aliases, not31 independent tests','Separate scalar endpoints, not jointly free vectors',
            'Setwise cross-gate differences are descriptive, not coupled biological histories or gate preference',
            'No coordinate noise/6-or8 temporal constraints/same-information superiority/utility/Majorclosure'],
        'strict8_equal_distance_failure_retained':True,'independent_audit_pending':True}
    emit(O/'RESULT.json',result);emit(O/'OUTPUT_HASHES.json',{p.name:sha(p) for p in O.iterdir() if p.is_file()})
    print(json.dumps({'status':result['status'],'readouts':summaries,'identity_comparisons':comparisons},ensure_ascii=False))

if __name__=='__main__':run()
