"""Preserve existing7µm producers; generate new6/8µm retrospective extensions."""
from pathlib import Path
import hashlib, json
from datetime import datetime, timezone

D=Path(__file__).resolve().parent
A=D.parent
old=A/'original3d_correspondence_margin_v0.1'

def swap(text, before, after, count=1):
    actual=text.count(before)
    if actual!=count:
        raise ValueError({'expected':count,'actual':actual,'text':before})
    return text.replace(before,after)

margin=(old/'run_margin_census.py').read_text(encoding='utf-8')
margin=swap(margin,"O=D/'actual_v0.1'", "GATE=float(sys.argv[1]);assert GATE in (6.,8.);O=D/f'gate_{int(GATE):02d}'/'margin_v0.1'")
margin=swap(margin,'O.mkdir(exist_ok=False)','O.mkdir(parents=True,exist_ok=False)')
margin=swap(margin,'match(s,ref,7.)','match(s,ref,GATE)')
margin=swap(margin,'dist=np.sqrt(np.sum(delta*delta,axis=2));old_dist=np.hypot.reduce(delta,axis=2)',
    'dist=np.hypot.reduce(delta,axis=2);old_dist=np.sqrt(np.sum(delta*delta,axis=2))')
margin=swap(margin,'allowed=dist<=7.;original_allowed=old_dist<=7.',
    'allowed=dist<=GATE;original_allowed=old_dist<=GATE')
comparison="""    target=B/'fresh_coordinate_all8.json';inputs[str(target)]=sha(target);old=json.loads(target.read_text(encoding='utf-8'))
    for k in ['reference_nodes','reference_edges','final_missing','persistent_absence','final_missing_with_loss']:
        if total[k]!=old['totals'][k]:failures.append({'kind':'original_history_total_disagreement','field':k,'new':total[k],'existing':old['totals'][k]})
"""
margin=swap(margin,comparison,'    # New gate results are frozen before any prior gate-output comparison.\n')
margin=swap(margin,"'scope':'All original eight movies, seven physical-coordinate stages, inclusive7um gate'",
    "'scope':f'All original eight movies, seven physical-coordinate stages, inclusive{GATE:g}um gate'")
margin=margin.replace('Same7um gate/objective only','Same declared gate/objective only')
margin=margin.replace("'No superiority", "'No superiority")

family=(old/'run_complete_tie_envelope_v02.py').read_text(encoding='utf-8')
family=swap(family,"O=D/'tie_envelope_v0.2'", "GATE=float(sys.argv[1]);assert GATE in (6.,8.);M=D/f'gate_{int(GATE):02d}'/'margin_v0.1';O=D/f'gate_{int(GATE):02d}'/'family_v0.1'")
family=swap(family,"D/'TIE_ENVELOPE_PROTOCOL_v0.2.md'", "D/'PROTOCOL.md'")
for name in ['RESULT.json','NUMERICAL_ALTERNATIVES.json','CANONICAL_HISTORIES.json']:
    family=swap(family,"D/'actual_v0.1/"+name+"'", "M/'"+name+"'")
family=swap(family,"maps=[match(s,ref,7.) for s in states]", "maps=[match(s,ref,GATE) for s in states]")
family=swap(family,'dist=np.sqrt((delta*delta).sum(axis=2));allowed=dist<=7.',
    'dist=np.hypot.reduce(delta,axis=2);allowed=dist<=GATE')
family=swap(family,'fields=list(forced_rows[0])',
    "fields=list(forced_rows[0]) if forced_rows else ['film','stage','frame','reference_id','prediction_id','forced_cardinality','distance_gap_um','accepted_optimal_candidate']")
family=swap(family,"for picks in itertools.product(*(options for k,q,options in entries)):",
    "config_count=math.prod(len(options) for k,q,options in entries)\n        if config_count>1048576:raise ValueError('Whole-component cap exceeded; withhold, do not truncate')\n        for picks in itertools.product(*(options for k,q,options in entries)):")
family=swap(family,"sha(D/'actual_v0.1/RESULT.json')", "sha(M/'RESULT.json')") if "sha(D/'actual_v0.1/RESULT.json')" in family else family
family=swap(family,"'design':'Adaptive post-discovery extension; no preregistration/new cohort'",
    "'design':f'Additional retrospective gate{GATE:g} family extension; no preregistration/new cohort'")

outputs={}
for name,text in [('run_multigate_margin_v01.py',margin),('run_multigate_family_v01.py',family)]:
    compile(text,str(D/name),'exec')
    with (D/name).open('x',encoding='utf-8',newline='\n') as stream:stream.write(text)
    outputs[name]=hashlib.sha256((D/name).read_bytes()).hexdigest()
receipt={'UTC':datetime.now(timezone.utc).isoformat(),'status':'NEW_PRODUCER_SOURCES_CREATED_NOT_EXECUTED',
    'inputs':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        [old/'run_margin_census.py',old/'run_complete_tie_envelope_v02.py',D/'PROTOCOL.md',Path(__file__)]},
    'outputs':outputs,'gate_values':[6,8],'source_changes':'Primaryhypot distance, declared gate, newdirectories, no7target comparison, emptyfamily handling, capwithhold.',
    'old_files_modified':False,'scientific_result_or_admission':False}
with (D/'PRODUCER_PREPARATION.json').open('x',encoding='utf-8') as stream:json.dump(receipt,stream,ensure_ascii=False,indent=2)
print(json.dumps(receipt,ensure_ascii=False))
