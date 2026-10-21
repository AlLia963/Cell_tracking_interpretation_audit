import collections,csv,datetime,hashlib,itertools,json,math,sys,time,traceback
from pathlib import Path
from fractions import Fraction
import numpy as np
from scipy.optimize import linear_sum_assignment
D=Path(__file__).resolve().parent;A=D.parent;B=A/'reproduction_LOCAL_ONLY_v0.1';GATE=float(sys.argv[1]);assert GATE in (6.,8.);M=D/f'gate_{int(GATE):02d}'/'margin_v0.1';O=D/f'gate_{int(GATE):02d}'/'family_v0.1'
sys.path.insert(0,str(B/'analysis_framework_v0.8'))
from stage_accounting import load_npz,match
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def emit(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def solve(dist,allowed,penalty,normalizer):
    cost=np.full(dist.shape,penalty);cost[allowed]=dist[allowed]/normalizer
    rr,cc=linear_sum_assignment(cost)
    pairs={int(r):int(c) for r,c in zip(rr,cc) if allowed[r,c]}
    return pairs,math.fsum(float(dist[r,c]) for r,c in pairs.items())
def tol(x,y):return 64*np.finfo(float).eps*max(1,abs(x),abs(y))
def features(histories):
    v=np.asarray(histories,dtype=int).reshape((-1,7));loss=(v[:,:-1]==1)&(v[:,1:]==0);gain=(v[:,:-1]==0)&(v[:,1:]==1)
    final=v[:,-1]==0;persistent=~v.any(axis=1);hasloss=loss.any(axis=1)
    out={'final_missing':int(final.sum()),'persistent_absence':int(persistent.sum()),'final_missing_with_loss':int((final&hasloss).sum()),'changed_reference_identities':int((loss.any(axis=1)|gain.any(axis=1)).sum()),'first_last_loss_disagreements_final_missing':0}
    for k in range(7):out[f'stage_visible_{k}']=int(v[:,k].sum())
    for k in range(1,7):out[f'gain_{k}']=int(gain[:,k-1].sum());out[f'loss_{k}']=int(loss[:,k-1].sum());out[f'final_last_loss_{k}']=0
    out['final_last_loss_persistent']=int((final&~hasloss).sum())
    for i in range(len(v)):
        if final[i] and hasloss[i]:
            losses=np.flatnonzero(loss[i])+1;out[f'final_last_loss_{int(losses[-1])}']+=1
            out['first_last_loss_disagreements_final_missing']+=int(losses[0]!=losses[-1])
    return out
def run():
    O.mkdir(exist_ok=False);start=time.perf_counter()
    small=[D/'PROTOCOL.md',Path(__file__),M/'RESULT.json',M/'NUMERICAL_ALTERNATIVES.json',M/'CANONICAL_HISTORIES.json']
    bindings={str(p):sha(p) for p in small};alts=json.loads(small[3].read_text(encoding='utf-8'));records=json.loads(small[4].read_text(encoding='utf-8'))
    flags=sorted({(x['case']['film'],int(x['case']['stage']),int(x['case']['frame'])) for x in alts})
    supports=[];forced_rows=[];failures=[];movie_data={};variable_candidates={}
    for filmname,stage,frame in flags:
        if filmname not in movie_data:
            root=B/'coordinate_all8'/filmname;paths=[root/'reference.npz']+[root/f'stage_{k}.npz' for k in range(7)]
            for p in paths:bindings[str(p)]=sha(p)
            ref=load_npz(paths[0]);states=[load_npz(p) for p in paths[1:]];maps=[match(s,ref,GATE) for s in states]
            movie_data[filmname]=(ref,states,maps)
        ref,states,maps=movie_data[filmname];s=states[stage]
        ri=np.flatnonzero(ref.coords[:,0]==frame);pi=np.flatnonzero(s.coords[:,0]==frame);ri=ri[np.argsort(ref.ids[ri])];pi=pi[np.argsort(s.ids[pi])]
        delta=ref.coords[ri,None,1:]-s.coords[None,pi,1:];dist=np.hypot.reduce(delta,axis=2);allowed=dist<=GATE
        penalty=float(min(len(ri),len(pi))+2);normalizer=float(dist[allowed].max()) or 1.;base,bsum=solve(dist,allowed,penalty,normalizer)
        cand=collections.defaultdict(list)
        for r in range(len(ri)):
            keep_r=[i for i in range(len(ri)) if i!=r]
            for c in np.flatnonzero(allowed[r]):
                c=int(c);keep_c=[i for i in range(len(pi)) if i!=c]
                sub,ssum=solve(dist[np.ix_(keep_r,keep_c)],allowed[np.ix_(keep_r,keep_c)],penalty,normalizer)
                cardinality=1+len(sub);total=float(dist[r,c])+ssum;accepted=cardinality==len(base) and abs(total-bsum)<=tol(total,bsum)
                forced_rows.append({'film':filmname,'stage':stage,'frame':frame,'reference_id':int(ref.ids[ri[r]]),'prediction_id':int(s.ids[pi[c]]),'forced_cardinality':cardinality,'distance_gap_um':total-bsum,'accepted_optimal_candidate':accepted})
                if accepted:cand[r].append(int(s.ids[pi[c]]))
            sub,ssum=solve(dist[keep_r,:],allowed[keep_r,:],penalty,normalizer)
            accepted=len(sub)==len(base) and abs(ssum-bsum)<=tol(ssum,bsum)
            forced_rows.append({'film':filmname,'stage':stage,'frame':frame,'reference_id':int(ref.ids[ri[r]]),'prediction_id':None,'forced_cardinality':len(sub),'distance_gap_um':ssum-bsum,'accepted_optimal_candidate':accepted})
            if accepted:cand[r].append(None)
        nonempty=[{p for p in options if p is not None} for options in cand.values()]
        if any(a&b for i,a in enumerate(nonempty) for b in nonempty[i+1:]):failures.append({'kind':'competing_candidate_supports','film':filmname,'stage':stage,'frame':frame})
        for r,options in cand.items():
            q=int(ref.ids[ri[r]]);entry={'film':filmname,'stage':stage,'frame':frame,'reference_id':q,'canonical_prediction':maps[stage].get(q),'optimal_predictions':options}
            if len(options)>1:
                if None in options:failures.append({'kind':'match_unmatch_ambiguity','case':entry})
                coords={p:tuple(s.coords[np.flatnonzero(s.ids==p)[0]].tolist()) for p in options if p is not None}
                entry['prediction_coordinates']=coords;entry['exact_duplicate_coordinate_choices']=len(set(coords.values()))==1
                rc=ref.coords[ri[r],1:]
                exact_squared={p:sum((Fraction(float(coords[p][j+1]))-Fraction(float(rc[j])))**2 for j in range(3)) for p in coords}
                entry['squared_distance_exact_fraction']={p:str(v) for p,v in exact_squared.items()}
                entry['exact_equal_distance_choices']=len(set(exact_squared.values()))==1
                if not entry['exact_equal_distance_choices']:failures.append({'kind':'non_equal_exact_distance_optimum','case':entry})
                variable_candidates[filmname,stage,q]=options
            supports.append(entry)
        print(json.dumps({'frame_supports_complete':[filmname,stage,frame],'forced_tests':len(forced_rows)}),flush=True)
    emit(O/'OPTIMAL_CANDIDATE_SUPPORTS.json',supports)
    fields=list(forced_rows[0]) if forced_rows else ['film','stage','frame','reference_id','prediction_id','forced_cardinality','distance_gap_um','accepted_optimal_candidate']
    with (O/'FORCED_PAIR_AND_UNMATCHED.csv').open('x',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(forced_rows)
    if failures:emit(O/'FAILURES.json',failures);raise AssertionError('Cannot justify complete factorized envelope; see failures')
    variables=sorted({(f,q) for f,k,q in variable_candidates})
    groups=[];remaining=set(variables)
    while remaining:
        todo=[remaining.pop()];group=set(todo)
        while todo:
            film,q=todo.pop()
            for r in records:
                if r['film']!=film or q not in r['reference_edge']:continue
                for endpoint in r['reference_edge']:
                    node=(film,endpoint)
                    if node in remaining:remaining.remove(node);group.add(node);todo.append(node)
        groups.append(sorted(group))
    component_outputs=[];affected_keys=set();edge_outputs=[]
    for ci,group in enumerate(groups):
        films={f for f,q in group};assert len(films)==1;film=group[0][0];ref,states,maps=movie_data[film];qs={q for f,q in group}
        affected=[r for r in records if r['film']==film and qs.intersection(r['reference_edge'])]
        for r in affected:affected_keys.add((film,tuple(r['reference_edge'])))
        entries=sorted((k,q,options) for (f,k,q),options in variable_candidates.items() if f==film and q in qs)
        edgesets=[set(map(tuple,s.edges.tolist())) for s in states];all_hist={tuple(r['reference_edge']):set() for r in affected};mins={};maxs={};states_count=0
        config_count=math.prod(len(options) for k,q,options in entries)
        if config_count>1048576:raise ValueError('Whole-component cap exceeded; withhold, do not truncate')
        for picks in itertools.product(*(options for k,q,options in entries)):
            choice={(k,q):p for (k,q,options),p in zip(entries,picks)};hists=[]
            for r in affected:
                a,b=r['reference_edge'];v=[]
                for k in range(7):
                    pair=(choice.get((k,a),maps[k].get(a)),choice.get((k,b),maps[k].get(b)))
                    v.append(int(None not in pair and pair in edgesets[k]))
                hists.append(v);all_hist[tuple(r['reference_edge'])].add(''.join(map(str,v)))
            stats=features(hists)
            for key,val in stats.items():mins[key]=min(mins.get(key,val),val);maxs[key]=max(maxs.get(key,val),val)
            states_count+=1
        component_outputs.append({'component':ci,'variable_reference_nodes':[q for f,q in group],'movie':film,'choices_across_stage_variables':len(entries),'enumerated_full_component_assignments':states_count,'affected_reference_edges':[r['reference_edge'] for r in affected],'canonical_features':features([r['visibility'] for r in affected]),'minimum':mins,'maximum':maxs})
        for r in affected:
            histories=sorted(all_hist[tuple(r['reference_edge'])]);lasts=set();firsts=set();persist=set()
            for h in histories:
                losses=[k for k in range(1,7) if h[k-1:k+1]=='10']
                lasts.add(losses[-1] if h[-1]=='0' and losses else None);firsts.add(losses[0] if losses else None);persist.add('1' not in h)
            edge_outputs.append({'film':film,'reference_edge':r['reference_edge'],'canonical_visibility':r['visibility'],'admissible_visibility_strings':histories,'possible_last_loss_final_missing':sorted(lasts,key=lambda x:-1 if x is None else x),'possible_first_loss':sorted(firsts,key=lambda x:-1 if x is None else x),'possible_persistent_absence':sorted(persist),'final_missing_determinate':len({h[-1] for h in histories})==1,'history_determinate':len(histories)==1,'last_loss_determinate':len(lasts)==1})
    fixed=features([r['visibility'] for r in records if (r['film'],tuple(r['reference_edge'])) not in affected_keys]);canonical=features([r['visibility'] for r in records])
    envelope={key:{'canonical':canonical[key],'minimum':fixed[key]+sum(x['minimum'][key] for x in component_outputs),'maximum':fixed[key]+sum(x['maximum'][key] for x in component_outputs)} for key in canonical}
    emit(O/'COMPONENT_ENUMERATION.json',component_outputs);emit(O/'EDGE_HISTORY_SETS.json',edge_outputs);emit(O/'MARGINAL_HISTORY_ENVELOPE.json',envelope)
    emit(O/'INPUT_BINDINGS.json',bindings);emit(O/'FAILURES.json',failures)
    result={'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'ACTUAL_COMPLETE_EQUIDISTANT_CANDIDATE_HISTORY_ENVELOPE','design':f'Additional retrospective gate{GATE:g} family extension; no preregistration/new cohort','all56_census_source':sha(M/'RESULT.json'),'flagged_frame_stages':len(flags),'forced_pair_or_unmatched_tests':len(forced_rows),'variable_reference_nodes':len(variables),'stage_reference_variables':len(variable_candidates),'independent_ambiguity_components':len(groups),'factorized_enumerated_assignments':sum(x['enumerated_full_component_assignments'] for x in component_outputs),'full_joint_assignments_represented':math.prod(x['enumerated_full_component_assignments'] for x in component_outputs),'affected_reference_edges':len(edge_outputs),'ambiguous_history_edges':sum(not e['history_determinate'] for e in edge_outputs),'ambiguous_last_loss_finalmissing_edges':sum(not e['last_loss_determinate'] for e in edge_outputs),'total_reference_edges':len(records),'marginal_envelope':envelope,'failure_count':len(failures),'compute_seconds':time.perf_counter()-start,'new_biological_N':0,'limitations':['Exact equidistant input candidates permit identity alternatives under this fixed objective, not certified biological correspondences','Census numeric comparison is double-precision; ambiguous candidate squared distances are exactly equal but all other optima have numerical margins','Intervals are separate attainable marginal extrema, not a simultaneous trajectory of all extremes','No superiority over a strong same-information baseline, intervention utility or scientific Major closure','Independent actual audit pending']}
    emit(O/'RESULT.json',result);emit(O/'OUTPUT_HASHES.json',{p.name:sha(p) for p in O.iterdir() if p.is_file()});print(json.dumps(result,ensure_ascii=False),flush=True)
if __name__=='__main__':
    try:run()
    except BaseException:
        if O.exists():emit(O/'EXECUTION_FAILURE.json',{'error':traceback.format_exc(),'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat()})
        raise
