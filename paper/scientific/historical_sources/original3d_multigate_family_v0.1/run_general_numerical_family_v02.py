"""Actual whole-frame constrained numerical family after the retained8µm failure."""
from pathlib import Path
from fractions import Fraction
from collections import defaultdict
from datetime import datetime, timezone
import csv, hashlib, importlib.util, itertools, json, math, sys, time, traceback
import numpy as np

D=Path(__file__).resolve().parent;A=D.parent;GATE=8.
B=A/'reproduction_LOCAL_ONLY_v0.1'
M=D/'gate_08/margin_v0.1';S=D/'gate_08/family_v0.1';O=D/'gate_08/numerical_family_v0.2'
sys.path.insert(0,str(B/'analysis_framework_v0.8'))
from stage_accounting import load_npz,match
spec=importlib.util.spec_from_file_location('prior_family_features',A/'original3d_correspondence_margin_v0.1/run_complete_tie_envelope_v02.py')
feature_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(feature_module)
features=feature_module.features

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def emit(path,obj):
    with path.open('x',encoding='utf-8',newline='\n') as stream:json.dump(obj,stream,ensure_ascii=False,indent=2)
def tol(a,b):return 64*np.finfo(float).eps*max(1,abs(a),abs(b))

def run():
    O.mkdir(exist_ok=False);start=time.perf_counter()
    inputs=[Path(__file__),D/'PROTOCOL.md',D/'PROTOCOL_ADAPTIVE_NUMERICAL_FAMILY_v02.md',
        M/'RESULT.json',M/'CANONICAL_HISTORIES.json',S/'OPTIMAL_CANDIDATE_SUPPORTS.json',S/'FORCED_PAIR_AND_UNMATCHED.csv',S/'FAILURES.json',
        B/'analysis_framework_v0.8/stage_accounting.py',Path(feature_module.__file__)]
    pins={str(p):sha(p) for p in inputs}
    histories=json.loads((M/'CANONICAL_HISTORIES.json').read_text(encoding='utf-8'))
    supports=json.loads((S/'OPTIMAL_CANDIDATE_SUPPORTS.json').read_text(encoding='utf-8'))
    frames=defaultdict(list)
    for row in supports:frames[(row['film'],row['stage'],row['frame'])].append(row)
    data={};blocks=[];candidate_audit=[];failures=[]
    for (film,stage,frame),rows in sorted(frames.items()):
        variable=[r for r in rows if len(r['optimal_predictions'])>1]
        if not variable:continue
        if film not in data:
            root=B/'coordinate_all8'/film
            paths=[root/'reference.npz']+[root/f'stage_{k}.npz' for k in range(7)]
            pins.update({str(p):sha(p) for p in paths})
            ref=load_npz(paths[0]);states=[load_npz(p) for p in paths[1:]]
            maps=[match(state,ref,GATE) for state in states]
            data[film]=(ref,states,maps)
        ref,states,maps=data[film];state=states[stage]
        ri=np.flatnonzero(ref.coords[:,0]==frame);pi=np.flatnonzero(state.coords[:,0]==frame)
        ri=ri[np.argsort(ref.ids[ri])];pi=pi[np.argsort(state.ids[pi])]
        distance=np.hypot.reduce(ref.coords[ri,None,1:]-state.coords[None,pi,1:],axis=2)
        rindex={int(ref.ids[i]):j for j,i in enumerate(ri)};pindex={int(state.ids[i]):j for j,i in enumerate(pi)}
        canonical={r:p for r,p in maps[stage].items() if r in rindex}
        def costs(mapping):return [float(distance[rindex[r],pindex[p]]) for r,p in sorted(mapping.items())]
        base_costs=costs(canonical);baseline=math.fsum(base_costs)
        exact_baseline=sum(map(Fraction,base_costs),Fraction())
        combinations=math.prod(len(r['optimal_predictions']) for r in variable)
        if combinations>1048576:raise ValueError('Whole-frame assignment cap exceeded; withhold')
        admissible=[]
        for chosen in itertools.product(*(r['optimal_predictions'] for r in variable)):
            mapping=dict(canonical)
            for row,pid in zip(variable,chosen):
                mapping.pop(row['reference_id'],None)
                if pid is not None:mapping[row['reference_id']]=pid
            one_to_one=len(mapping.values())==len(set(mapping.values()))
            cardinality=len(mapping)==len(canonical)
            cs=costs(mapping);total=math.fsum(cs);gap=total-baseline
            exact_gap=sum(map(Fraction,cs),Fraction())-exact_baseline
            if gap < -tol(total,baseline):failures.append({'film':film,'stage':stage,'frame':frame,'negative_gap':gap})
            keep=one_to_one and cardinality and abs(gap)<=tol(total,baseline)
            candidate_audit.append({'film':film,'stage':stage,'frame':frame,'choices':list(chosen),
                'one_to_one':one_to_one,'cardinality_equal':cardinality,'native_distance_sum':total,
                'native_fsum_gap':gap,'exact_calculated_double_sum_gap':str(exact_gap),
                'numeric_threshold':tol(total,baseline),'admitted':keep})
            if keep:admissible.append({row['reference_id']:pid for row,pid in zip(variable,chosen)})
        if not admissible:raise ValueError('Empty whole-frame family')
        blocks.append({'film':film,'stage':stage,'frame':frame,'references':[r['reference_id'] for r in variable],
            'assignments':admissible,'tested_combinations':combinations})
    if failures:emit(O/'FAILURES.json',failures);raise ValueError('Numerical objective failure')
    remaining=set(range(len(blocks)));components=[];edge_outputs=[];affected_keys=set()
    while remaining:
        indices={remaining.pop()}
        changed=True
        while changed:
            changed=False
            film=blocks[next(iter(indices))]['film']
            nodes={q for i in indices for q in blocks[i]['references']}
            touched=[r for r in histories if r['film']==film and nodes.intersection(r['reference_edge'])]
            linked_nodes={q for r in touched for q in r['reference_edge']}
            for i in list(remaining):
                if blocks[i]['film']==film and linked_nodes.intersection(blocks[i]['references']):
                    remaining.remove(i);indices.add(i);changed=True
        indices=sorted(indices);film=blocks[indices[0]]['film'];ref,states,maps=data[film]
        nodes={q for i in indices for q in blocks[i]['references']}
        affected=[r for r in histories if r['film']==film and nodes.intersection(r['reference_edge'])]
        choices_count=math.prod(len(blocks[i]['assignments']) for i in indices)
        if choices_count>1048576:raise ValueError('Coupled component cap exceeded; withhold')
        sets=[set(map(tuple,state.edges.tolist())) for state in states]
        peredge={tuple(r['reference_edge']):set() for r in affected};mins={};maxs={};count=0
        for assignments in itertools.product(*(blocks[i]['assignments'] for i in indices)):
            choice={(blocks[i]['stage'],q):pid for i,assignment in zip(indices,assignments) for q,pid in assignment.items()}
            current=[]
            for row in affected:
                a,b=row['reference_edge'];v=[]
                for k in range(7):
                    pair=(choice.get((k,a),maps[k].get(a)),choice.get((k,b),maps[k].get(b)))
                    v.append(int(None not in pair and pair in sets[k]))
                current.append(v);peredge[tuple(row['reference_edge'])].add(''.join(map(str,v)))
            stats=features(current)
            for key,value in stats.items():mins[key]=min(mins.get(key,value),value);maxs[key]=max(maxs.get(key,value),value)
            count+=1
        components.append({'movie':film,'block_indices':indices,'variable_reference_nodes':sorted(nodes),
            'enumerated_full_component_assignments':count,'affected_reference_edges':[r['reference_edge'] for r in affected],
            'canonical_features':features([r['visibility'] for r in affected]),'minimum':mins,'maximum':maxs})
        for row in affected:
            edge=tuple(row['reference_edge']);strings=sorted(peredge[edge]);affected_keys.add((film,edge))
            lasts={max([k for k in range(1,7) if h[k-1:k+1]=='10'],default=None) if h[-1]=='0' else None for h in strings}
            edge_outputs.append({'film':film,'reference_edge':list(edge),'canonical_visibility':row['visibility'],
                'admissible_visibility_strings':strings,'possible_last_loss_final_missing':sorted(lasts,key=lambda x:-1 if x is None else x),
                'final_missing_determinate':len({h[-1] for h in strings})==1,
                'history_determinate':len(strings)==1,'last_loss_determinate':len(lasts)==1})
    fixed=features([r['visibility'] for r in histories if (r['film'],tuple(r['reference_edge'])) not in affected_keys])
    canonical=features([r['visibility'] for r in histories])
    envelope={key:{'canonical':canonical[key],'minimum':fixed[key]+sum(c['minimum'][key] for c in components),
        'maximum':fixed[key]+sum(c['maximum'][key] for c in components)} for key in canonical}
    for name,value in [('WHOLE_FRAME_FAMILIES.json',blocks),('WHOLE_FRAME_COST_CHECKS.json',candidate_audit),
        ('COMPONENT_ENUMERATION.json',components),('EDGE_HISTORY_SETS.json',edge_outputs),('MARGINAL_HISTORY_ENVELOPE.json',envelope),('INPUT_BINDINGS.json',pins)]:emit(O/name,value)
    result={'UTC':datetime.now(timezone.utc).isoformat(),'status':'ACTUAL_ADAPTIVE_WHOLE_FRAME_NUMERICAL_FAMILY_COMPLETE_PENDING_INDEPENDENT_AUDIT',
        'gate_um':GATE,'whole_frame_blocks':len(blocks),'whole_frame_assignments_tested':len(candidate_audit),
        'whole_frame_assignments_admitted':sum(r['admitted'] for r in candidate_audit),
        'components':len(components),'coupled_assignments_enumerated':sum(c['enumerated_full_component_assignments'] for c in components),
        'affected_reference_edges':len(edge_outputs),'total_reference_edges':len(histories),
        'marginal_envelope':envelope,'compute_seconds':time.perf_counter()-start,'new_biological_N':0,
        'limitations':['Retained strict geometric-equality failure; this is a newly explicit per-frame numerical-tolerance family',
            'Not exact real-distance/biological equality, coordinate noise, temporal or cross-gate constraint validation',
            'Numerical deletion/forced-support coverage conditional on source matching and tolerance; independent audit pending',
            'Scalar endpoints separately feasible; no simultaneous endpoint vector/utility/same-information advantage/Majorclosure']}
    emit(O/'RESULT.json',result);emit(O/'OUTPUT_HASHES.json',{p.name:sha(p) for p in O.iterdir() if p.is_file()})
    print(json.dumps({k:result[k] for k in ['status','gate_um','whole_frame_blocks','components','affected_reference_edges','marginal_envelope','compute_seconds']},ensure_ascii=False))

if __name__=='__main__':
    try:run()
    except BaseException:
        if O.exists() and not (O/'EXECUTION_FAILURE.json').exists():emit(O/'EXECUTION_FAILURE.json',{'UTC':datetime.now(timezone.utc).isoformat(),'traceback':traceback.format_exc()})
        raise
