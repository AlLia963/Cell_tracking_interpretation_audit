"""Actual original3D all56 matching replacement-margin census; protocol first."""
import collections,csv,datetime,hashlib,json,math,sys,time,traceback
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment
D=Path(__file__).resolve().parent;A=D.parent
B=A/'reproduction_LOCAL_ONLY_v0.1';ROOT=B/'coordinate_all8';GATE=float(sys.argv[1]);assert GATE in (6.,8.);O=D/f'gate_{int(GATE):02d}'/'margin_v0.1'
sys.path.insert(0,str(B/'analysis_framework_v0.8'))
from stage_accounting import load_npz,match,account_from_matches

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def emit(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def compare_rule(b,a):return 64*np.finfo(np.float64).eps*max(1,abs(b),abs(a))
def pairs(cost,allowed):
    rr,cc=linear_sum_assignment(cost)
    return {int(r):int(c) for r,c in zip(rr,cc) if allowed[r,c]}

def run():
    O.mkdir(parents=True,exist_ok=False);beg=time.perf_counter()
    inputs={str(p):sha(p) for p in [D/'PROTOCOL.md',Path(__file__),B/'analysis_framework_v0.8/stage_accounting.py']}
    failures=[];frame_rows=[];margin_rows=[];alternate_rows=[];history_rows=[];summary=[]
    counters=collections.Counter();global_min=None;max_discrepancy=0.
    films=sorted(p for p in ROOT.iterdir() if p.is_dir() and (p/'reference.npz').exists())
    assert len(films)==8
    for film in films:
        refpath=film/'reference.npz';inputs[str(refpath)]=sha(refpath);ref=load_npz(refpath)
        assert ref.unit=='um'
        states=[];maps=[];pending_alternatives=[]
        for stage in range(7):
            p=film/f'stage_{stage}.npz';inputs[str(p)]=sha(p);s=load_npz(p)
            assert s.unit=='um';states.append(s);canonical=match(s,ref,GATE);actual={}
            stage_min=None;stage_tried=0
            for t in np.unique(ref.coords[:,0]):
                ri=np.flatnonzero(ref.coords[:,0]==t);pi=np.flatnonzero(s.coords[:,0]==t)
                ri=ri[np.argsort(ref.ids[ri])];pi=pi[np.argsort(s.ids[pi])]
                if not len(pi):
                    frame_rows.append({'film':film.name,'stage':stage,'frame':int(t),'reference_nodes':len(ri),'prediction_nodes':0,'matched_nodes':0,'allowed_pairs':0,'minimum_same_cardinality_gap_um':None,'numerical_alternatives':0})
                    continue
                delta=ref.coords[ri,None,1:]-s.coords[None,pi,1:]
                dist=np.hypot.reduce(delta,axis=2);old_dist=np.sqrt(np.sum(delta*delta,axis=2))
                max_discrepancy=max(max_discrepancy,float(np.max(np.abs(dist-old_dist))))
                allowed=dist<=GATE;original_allowed=old_dist<=GATE
                if not np.array_equal(allowed,original_allowed):failures.append({'kind':'gate_float_route_disagreement','film':film.name,'stage':stage,'frame':int(t)})
                normalizer=float(dist[allowed].max()) if allowed.any() else 1.
                normalizer=normalizer or 1.;penalty=float(min(len(ri),len(pi))+2)
                cost=np.full(dist.shape,penalty);cost[allowed]=dist[allowed]/normalizer
                base=pairs(cost,allowed);base_ids={int(ref.ids[ri[r]]):int(s.ids[pi[c]]) for r,c in base.items()}
                old_ids={r:p for r,p in canonical.items() if r in set(map(int,ref.ids[ri]))}
                if base_ids!=old_ids:failures.append({'kind':'canonical_map_disagreement','film':film.name,'stage':stage,'frame':int(t),'independent':base_ids,'existing':old_ids})
                actual.update(base_ids);bsum=math.fsum(float(dist[r,c]) for r,c in base.items())
                row_degree=allowed.sum(axis=1);col_degree=allowed.sum(axis=0)
                frame_min=None;frame_alternatives=0
                for r,c in base.items():
                    counters['selected_pairs']+=1;stage_tried+=1
                    out={'film':film.name,'stage':stage,'frame':int(t),'reference_id':int(ref.ids[ri[r]]),'prediction_id':int(s.ids[pi[c]]),'base_cardinality':len(base),'base_sum_distance_um':bsum,'same_cardinality_gap_um':None,'numerical_threshold_um':None}
                    if row_degree[r]==1 and col_degree[c]==1:
                        counters['isolated_cardinality_forced']+=1;out['status']='ISOLATED_CARDINALITY_FORCED'
                        margin_rows.append(out);continue
                    forbidden=allowed.copy();forbidden[r,c]=False;replacement=cost.copy();replacement[r,c]=penalty
                    alt=pairs(replacement,forbidden);counters['actual_deletion_solver_calls']+=1
                    if len(alt)<len(base):
                        counters['deletion_reduces_cardinality']+=1;out['status']='DELETION_REDUCES_CARDINALITY';out['alternative_cardinality']=len(alt)
                        margin_rows.append(out);continue
                    if len(alt)>len(base):
                        failures.append({'kind':'greater_cardinality_after_deletion','film':film.name,'stage':stage,'frame':int(t),'r':r,'c':c})
                    asum=math.fsum(float(dist[x,y]) for x,y in alt.items());gap=asum-bsum;tol=compare_rule(bsum,asum)
                    out.update({'alternative_cardinality':len(alt),'same_cardinality_gap_um':gap,'numerical_threshold_um':tol})
                    frame_min=gap if frame_min is None else min(frame_min,gap)
                    stage_min=gap if stage_min is None else min(stage_min,gap)
                    if global_min is None or gap<global_min['same_cardinality_gap_um']:global_min=dict(out)
                    if gap < -tol:
                        failures.append({'kind':'lower_cost_alternative','case':out})
                    if gap<=tol:
                        out['status']='NUMERICALLY_INDISTINGUISHABLE_ALTERNATIVE';counters['numeric_alternative_deletions']+=1;frame_alternatives+=1
                        alt_ids={int(ref.ids[ri[x]]):int(s.ids[pi[y]]) for x,y in alt.items()}
                        changes=[{'reference_id':q,'canonical':base_ids.get(q),'alternative':alt_ids.get(q)} for q in sorted(set(base_ids)|set(alt_ids)) if base_ids.get(q)!=alt_ids.get(q)]
                        pending_alternatives.append((stage,base_ids,alt_ids,dict(out)))
                        alternate_rows.append({'case':dict(out),'changes':changes})
                    else:out['status']='POSITIVE_REPLACEMENT_MARGIN';counters['positive_margin_deletions']+=1
                    margin_rows.append(out)
                frame_rows.append({'film':film.name,'stage':stage,'frame':int(t),'reference_nodes':len(ri),'prediction_nodes':len(pi),'matched_nodes':len(base),'allowed_pairs':int(allowed.sum()),'minimum_same_cardinality_gap_um':frame_min,'numerical_alternatives':frame_alternatives})
                counters['frames']+=1
            maps.append(actual);assert set(actual.items())==set(canonical.items()),'See retained canonical-map discrepancy'
            print(json.dumps({'film':film.name,'stage':stage,'selected_pairs':stage_tried,'minimum_gap_um':stage_min}),flush=True)
        records=account_from_matches(states,ref,maps)
        for r in records:r['film']=film.name;r['last_loss']=r['loss_stages'][-1] if r['final_missing'] and r['loss_stages'] else None
        history_rows.extend(records)
        for stage,base_ids,alt_ids,case in pending_alternatives:
            changed_maps=[dict(m) for m in maps]
            for q in base_ids:changed_maps[stage].pop(q,None)
            changed_maps[stage].update(alt_ids)
            alt_records=account_from_matches(states,ref,changed_maps)
            changes=[]
            for old,new in zip(records,alt_records):
                newlast=new['loss_stages'][-1] if new['final_missing'] and new['loss_stages'] else None
                if old['visibility']!=new['visibility']:
                    changes.append({'reference_edge':old['reference_edge'],'canonical_visibility':old['visibility'],'alternative_visibility':new['visibility'],'canonical_last_loss':old['last_loss'],'alternative_last_loss':newlast,'canonical_persistent_absence':old['persistent_absence'],'alternative_persistent_absence':new['persistent_absence']})
            alternate_rows.append({'case':case,'single_frame_history_changes':changes})
        summary.append({'film':film.name,'reference_nodes':len(ref.ids),'reference_edges':len(ref.edges),'selected_correspondences_all7':sum(map(len,maps)),'final_missing':sum(r['final_missing'] for r in records),'persistent_absence':sum(r['persistent_absence'] for r in records),'final_missing_with_loss':sum(r['final_missing'] and bool(r['loss_stages']) for r in records)})
    # Compare the actual original histories only after freezing this census.
    emit(O/'CANONICAL_HISTORIES.json',history_rows);emit(O/'NUMERICAL_ALTERNATIVES.json',alternate_rows)
    total={k:sum(x[k] for x in summary) for k in ['reference_nodes','reference_edges','selected_correspondences_all7','final_missing','persistent_absence','final_missing_with_loss']}
    # New gate results are frozen before any prior gate-output comparison.
    def write_csv(path,rows):
        fields=list(dict.fromkeys(k for row in rows for k in row))
        with path.open('x',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    write_csv(O/'PAIR_REPLACEMENT_MARGINS.csv',margin_rows);write_csv(O/'FRAME_CENSUS.csv',frame_rows);write_csv(O/'PER_MOVIE.csv',summary)
    emit(O/'INPUT_BINDINGS.json',inputs);emit(O/'FAILURES.json',failures)
    result={'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'ACTUAL_CENSUS_COMPLETE' if not failures else 'ACTUAL_CENSUS_DISCREPANCY','scope':f'All original eight movies, seven physical-coordinate stages, inclusive{GATE:g}um gate','films':8,'stage_exports':56,'reference_movie_frames':len(frame_rows),'new_biological_N':0,'total':total,'replacement_counts':dict(counters),'minimum_same_cardinality_replacement':global_min,'maximum_sqrt_vs_hypot_distance_difference_um':max_discrepancy,'numeric_alternative_single_frame_history_changes':sum(len(x.get('single_frame_history_changes',[])) for x in alternate_rows),'failures':len(failures),'comparison_rule':'64epsilon*max(1,baselineSum,alternativeSum), numerical not exact-arithmetic certificate','elapsed_compute_seconds':time.perf_counter()-beg,'limitations':['Original retrospective selected annotated cohort; not new biological observations','Floating input coordinates and double-precision optimum; not a coordinate-noise model or biological correspondence truth','Same declared gate/objective only; no generic or causal attribution proof','Single-deletion alternative histories are not an enumeration of all joint ambiguous histories','Strong same-information baseline equivalence and research-increment Major remain open']}
    emit(O/'RESULT.json',result)
    emit(O/'OUTPUT_HASHES.json',{p.name:sha(p) for p in O.iterdir() if p.is_file()})
    print(json.dumps(result,ensure_ascii=False),flush=True)
if __name__=='__main__':
    try:run()
    except BaseException:
        if O.exists():emit(O/'EXECUTION_FAILURE.json',{'error':traceback.format_exc(),'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat()})
        raise
