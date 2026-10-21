"""Join every existing policy/movie endpoint; retrospective descriptive comparison."""
from pathlib import Path
from fractions import Fraction
from collections import Counter
import csv
import json
import hashlib
from datetime import datetime, timezone

P=Path(__file__).resolve().parent
A=P.parent
O=P/'endpoint_comparison_v0.1'
O.mkdir(exist_ok=False)
paths={
    'CCA':P/'actual_v0.1'/'IDENTITIES_AND_LENGTHS.json',
    'typed_edges':A/'clean_runtime_COPY_v0.1'/'clean_external_full_v0.1'/'RESULT.json',
    'lineage':A/'lineage_consequence_v0.1'/'results_v0.2'/'RESULT.json',
    'lineage_independent_ROOT':A/'lineage_consequence_v0.1'/'ROOT_INDEPENDENT_ACTUAL_ACCEPTED_v0.1.json'
}
pins={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths.values()}
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,d):
    with p.open('x',encoding='utf-8') as f:json.dump(d,f,ensure_ascii=False,indent=2)
save(O/'START.json',{'UTC':datetime.now(timezone.utc).isoformat(),'input_pins':pins,
     'question':'How do all58 policy/movie paired endpoint directions differ? Existing whole-policy outcomes and4 CCA movie examples already inspected; descriptive retrospective all-domain join, not preregistration.',
     'domain':'All29 movies x max_area/all_components vs baseline; no exclusions or outcome selection'})
cca={(x['film'],x['arm']):x for x in read(paths['CCA'])}
edge={(x['film'],x['arm']):x for x in read(paths['typed_edges'])['rows']}
lineage={x['film']:x for x in read(paths['lineage'])['movies']}
assert len(cca)==len(edge)==87 and len(lineage)==29
def exact(x):return Fraction(x['CCA_exact_numerator'],x['CCA_exact_denominator'])
def sign(x):return 'positive' if x>0 else 'negative' if x<0 else 'null'
rows=[]
for i in range(1,30):
    film=f'{i:02d}';b=edge[(film,'baseline')];cb=cca[(film,'baseline')];l=lineage[film]
    for arm in ['max_area','all_components']:
        e=edge[(film,arm)];c=cca[(film,arm)]
        cd=exact(c)-exact(cb);td=e['typed_TP']-b['typed_TP'];fd=e['typed_FP']-b['typed_FP']
        chain=l['chain_recovered'][arm]-l['chain_recovered']['baseline']
        rows.append({'film':film,'arm':arm,'baseline_typed_TP':b['typed_TP'],'policy_typed_TP':e['typed_TP'],
            'typed_TP_delta':td,'typed_FP_delta':fd,'typed_TP_direction':sign(td),
            'baseline_CCA':float(exact(cb)),'policy_CCA':float(exact(c)),
            'CCA_delta_exact':str(cd),'CCA_direction':sign(cd),
            'baseline_typed_chains':l['chain_recovered']['baseline'],'policy_typed_chains':l['chain_recovered'][arm],
            'chain_delta':chain,'chain_direction':sign(chain),
            'events_delta':l['event_recovered'][arm]-l['event_recovered']['baseline'],
            'CCA_undefined':False})
def ids(predicate):return [{'film':x['film'],'arm':x['arm']} for x in rows if predicate(x)]
result={'UTC':datetime.now(timezone.utc).isoformat(),'status':'ALL58_EXISTING_POLICY_MOVIE_ENDPOINTS_JOINED',
    'all_rows':58,
    'TP_vs_CCA_direction_table':{a:dict(Counter(x['typed_TP_direction']+'/'+x['CCA_direction'] for x in rows if x['arm']==a)) for a in ['max_area','all_components']},
    'higher_TP_same_or_lower_FP_but_lower_CCA':ids(lambda x:x['typed_TP_delta']>0 and x['typed_FP_delta']<=0 and x['CCA_direction']=='negative'),
    'higher_CCA_lower_TP_and_more_FP':ids(lambda x:x['CCA_direction']=='positive' and x['typed_TP_delta']<0 and x['typed_FP_delta']>0),
    'unchanged_CCA_but_chain_loss':ids(lambda x:x['CCA_direction']=='null' and x['chain_delta']<0),
    'scope':'Retrospective same29 nested descriptive endpoints; CCA measures cycle length distributions, custom typed chain certificates require exact reference relations. Direction differences are different estimands, not proof that CCA is erroneous or framework is more informative than a strong same-info method.',
    'new_biological_N':0,'SF_M1':'MAJOR_OPEN','input_pins':pins}
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in pins.items())
with (O/'ALL58_ENDPOINTS.csv').open('x',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
save(O/'RESULT.json',result)
print(json.dumps(result,ensure_ascii=False))
