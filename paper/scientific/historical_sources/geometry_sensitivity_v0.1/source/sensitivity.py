"""Frozen, local-only reference-coordinate bounded sensitivity, gate 7 um.

Original packet inputs are read only. Objective is exact sums of calculated
float64 hypot distances. Each scenario uses one perturbed reference per film.
"""
import collections, csv, datetime, gzip, hashlib, itertools, json, math, os
import platform, sys, threading, time, traceback
from fractions import Fraction
from pathlib import Path
import numpy as np
import scipy
import psutil
import reconstruct as R
from stage_accounting import Graph, load_npz, match, account_from_matches

ROOT=Path(__file__).resolve().parents[1]
PACKET=ROOT.parent/'v013_full_fresh_review_v0.1'/'packet'
FAMILY=PACKET/'scientific_routes'/'family'
INPUT=FAMILY/'inputs_LOCAL_ONLY'/'coordinate_all8'
CAP=1048576
SCALE=np.array([1.625,0.40625,0.40625],dtype=np.float64)
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def write(p,value):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    opener=gzip.open if p.suffix=='.gz' else Path.open
    with opener(p,'xt',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,ensure_ascii=False,separators=(',',':'),allow_nan=False);f.write('\n')
def read(p):
    with (gzip.open(p,'rt',encoding='utf-8') if str(p).endswith('.gz') else Path(p).open(encoding='utf-8')) as f:return json.load(f)
def csvwrite(p,rows,fields):
    with (gzip.open(p,'xt',encoding='utf-8',newline='') if str(p).endswith('.gz') else Path(p).open('x',encoding='utf-8',newline='')) as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def exact_solve(nr,npred,allowed,ci):
    """Exact integer successive shortest augmenting paths from empty flow.

    Bellman-Ford uses strict comparisons, with no normalization or tolerance.
    Residual costs are exact integers and capacity one. Each shortest augment
    keeps the flow minimum cost at its cardinality; exhaustion maximizes K.
    """
    mapping={};augmentations=[]
    while True:
        S,T,arcs=R.residual(nr,npred,allowed,ci,mapping);n=T+1
        dist=[None]*n;prev=[None]*n;dist[S]=0
        for _ in range(n-1):
            changed=False
            for u,v,c in arcs:
                if dist[u] is not None and (dist[v] is None or dist[v]>dist[u]+c):
                    dist[v]=dist[u]+c;prev[v]=(u,v,c);changed=True
            if not changed:break
        if dist[T] is None:break
        path=[];v=T;seen=set()
        while v!=S:
            if v in seen or prev[v] is None:raise AssertionError('Invalid exact augmenting predecessor')
            seen.add(v);a=prev[v];path.append(a);v=a[0]
        remove=[];add=[]
        for u,v,c in path:
            if nr<=u<nr+npred and 0<=v<nr:remove.append(v)
            elif 0<=u<nr and nr<=v<nr+npred:add.append((u,v-nr))
        for r in remove:del mapping[r]
        mapping.update(add)
        assert len(mapping)==len(augmentations)+1 and len(set(mapping.values()))==len(mapping)
        augmentations.append({'cardinality':len(mapping),'augmenting_cost':str(dist[T]),'path':[list(x) for x in reversed(path)]})
    return mapping,augmentations

def negative_cycle(n,arcs):
    p=[0]*n;prev=[None]*n;last=None
    for _ in range(n):
        last=None
        for u,v,c in arcs:
            if p[v]>p[u]+c:p[v]=p[u]+c;prev[v]=(u,v,c);last=v
        if last is None:return None
    v=last
    for _ in range(n):v=prev[v][0]
    start=v;cycle=[]
    while True:
        a=prev[v];cycle.append(a);v=a[0]
        if v==start:break
    assert sum(a[2] for a in cycle)<0
    return {'arcs':[list(a) for a in reversed(cycle)],'scaled_integer_sum':str(sum(a[2] for a in cycle))}

def frame_matrix(ref,state,t):
    ri=np.flatnonzero(ref.coords[:,0]==t);pi=np.flatnonzero(state.coords[:,0]==t)
    ri=ri[np.argsort(ref.ids[ri])];pi=pi[np.argsort(state.ids[pi])]
    d=np.hypot.reduce(ref.coords[ri,None,1:]-state.coords[None,pi,1:],axis=2)
    allowed=d<=7.;ratios={(int(r),int(c)):float(d[r,c]).as_integer_ratio() for r,c in zip(*np.nonzero(allowed))}
    denominator=max((b for a,b in ratios.values()),default=1)
    ci={key:a*(denominator//b) for key,(a,b) in ratios.items()}
    return ri,pi,d,allowed,ci,denominator

def repair_frame(ref,state,mapping,t,error):
    ri,pi,d,allowed,ci,den=frame_matrix(ref,state,t)
    rids=list(map(int,ref.ids[ri]));pids=list(map(int,state.ids[pi]));rix={q:i for i,q in enumerate(rids)};pix={p:i for i,p in enumerate(pids)}
    old={rix[q]:pix[p] for q,p in mapping.items() if q in rix}
    S,T,arcs=R.residual(len(ri),len(pi),allowed,ci,old)
    cycle=negative_cycle(T+1,arcs)
    fixed,steps=exact_solve(len(ri),len(pi),allowed,ci)
    for q in rids:mapping.pop(q,None)
    mapping.update({rids[r]:pids[c] for r,c in fixed.items()})
    oldcost=sum(ci[r,c] for r,c in old.items());newcost=sum(ci[r,c] for r,c in fixed.items())
    return {'frame':int(t),'original_exception':error,'original_pairs':[[rids[r],pids[c]] for r,c in sorted(old.items())],
      'original_cardinality':len(old),'original_exact_integer_cost':str(oldcost),'exact_cost_denominator':str(den),
      'negative_cycle_evidence':cycle,'sink_reachable_from_source':T in R.reachable(T+1,arcs,S),
      'repair_pairs':[[rids[r],pids[c]] for r,c in sorted(fixed.items())], 'repair_cardinality':len(fixed),
      'repair_exact_integer_cost':str(newcost),'exact_same_cardinality_cost_improvement':str(Fraction(oldcost-newcost,den)) if len(old)==len(fixed) else None,
      'exact_solver_augmentations':steps,'objective_changed':False,'original_failed_output_retained':True}

def partition(hist):
    c=collections.Counter()
    for x in hist:
        cats=x['categories'];hs=x['admissible_visibility_strings']
        c['reference_relations']+=1;c['ambiguous_history']+=len(hs)>1
        c['ambiguous_category']+=len(cats)>1
        c['certain_final_missing']+=all(h[-1]=='0' for h in hs)
        c['possible_final_missing']+=any(h[-1]=='0' for h in hs)
        if len(cats)>1:c['partition_ambiguous']+=1
        elif cats==['final_present']:c['partition_final_present']+=1
        elif cats==['persistent_absence']:c['partition_persistent_absence']+=1
        else:c['partition_observed_loss']+=1
    keys=['reference_relations','ambiguous_history','ambiguous_category','certain_final_missing','possible_final_missing','partition_final_present','partition_persistent_absence','partition_observed_loss','partition_ambiguous']
    c={k:c[k] for k in keys};assert sum(c[k] for k in keys[-4:])==c['reference_relations'];return c

def branch_summary(res,derived,records,baseline):
    hist=derived['histories'];bykey={(x['film'],*x['reference_edge']):x for x in hist}
    out={**partition(hist),'canonical_history_changed_from_primary':0,'canonical_category_changed_from_primary':0,
      'category_set_changed_from_primary':0,'admissible_history_set_changed_from_primary':0,'canonical_feature_totals':R.total_features(r['history'] for r in records)}
    for key,x in bykey.items():
        b=baseline[key]
        out['canonical_history_changed_from_primary']+=x['canonical_history']!=b['canonical_history']
        out['canonical_category_changed_from_primary']+=R.categories([x['canonical_history']])!=R.categories([b['canonical_history']])
        out['category_set_changed_from_primary']+=x['categories']!=b['categories']
        out['admissible_history_set_changed_from_primary']+=x['admissible_visibility_strings']!=b['admissible_visibility_strings']
    out.update({'whole_graph_joint_assignments_represented':res['whole_graph_joint_assignments_represented'],
      'component_raw_product_counts':res['component_raw_product_counts'],'component_configurations':res['component_configurations'],
      'component_count':len(derived['witnesses']),'fixed_relations':res['fixed_edges'],'all31_scalar_bounds':derived['bounds'],
      'reference_relations':len(hist),'frame_cap':CAP,'component_cap':CAP,'status':res['status']})
    return out

def profile(cert,ref,state,t,mapping):
    ri,pi,d,allowed,ci,den=frame_matrix(ref,state,t)
    counts=allowed.sum(axis=1);signed=7.-d
    closest=np.min(d,axis=1) if len(pi) else np.full(len(ri),np.inf)
    pidx={int(p):i for i,p in enumerate(state.ids[pi])}
    rows=[]
    for i,q in enumerate(map(int,ref.ids[ri])):
        p=mapping.get(q);md=float(d[i,pidx[p]]) if p is not None else None
        rows.append([q,int(counts[i]),float(closest[i]) if math.isfinite(closest[i]) else None,
          None if not len(pi) else float(np.min(np.abs(signed[i]))),p,md,None if md is None else 7.-md])
    cert['candidate_geometry_profile_columns']=['reference_id','eligible_candidate_count','nearest_prediction_distance_um','nearest_absolute_gate_boundary_margin_um','canonical_prediction_id_or_null','canonical_match_distance_um','canonical_gate_slack_um']
    cert['candidate_geometry_profile']=rows
    cert['minimum_absolute_gate_boundary_margin_um']=float(np.min(np.abs(signed))) if d.size else None
    cert['candidate_count_histogram']={str(k):v for k,v in sorted(collections.Counter(map(int,counts)).items())}
    cert['finite_whole_frame_map_count']=sum(x['finite_admitted'] for x in cert.get('whole_map_checks',[])) if 'whole_map_checks' in cert else None
    cert['numerical_whole_frame_map_count']=sum(x['numerical_admitted'] for x in cert.get('whole_map_checks',[])) if 'whole_map_checks' in cert else None

def verify_freeze():
    frozen=read(ROOT/'PROTOCOL_FREEZE.json')
    for rel,digest in frozen['sha256'].items():assert sha(ROOT/rel)==digest,rel
    return frozen

def run():
    freeze=verify_freeze();beg=time.perf_counter();process=psutil.Process();samples=[];stop=threading.Event()
    def monitor():
        while not stop.is_set():
            try:samples.append((time.perf_counter()-beg,process.memory_info().rss))
            except psutil.Error:pass
            stop.wait(.02)
    thread=threading.Thread(target=monitor,daemon=True);thread.start()
    write(ROOT/'execution'/'RUN_START.json',{'UTC':now(),'PID':os.getpid(),'argv':sys.argv,'python':sys.executable,'python_version':sys.version,
      'numpy':np.__version__,'scipy':scipy.__version__,'psutil':psutil.__version__,'platform':platform.platform(),'protocol_freeze_sha256':sha(ROOT/'PROTOCOL_FREEZE.json')})
    manifest=read(ROOT/'INPUT_CONSUMPTION_MANIFEST.json');raw={};baseline={};baseline_contracts={}
    for film in manifest['films']:
        f=INPUT/film;raw[film]=(load_npz(f/'reference.npz'),[load_npz(f/f'stage_{k}.npz') for k in range(7)])
    for contract in ['finite/unconstrained','finite/geometry_constrained','numerical/unconstrained']:
        old=read(FAMILY/'actual_run_v0.1'/'gate_07'/contract/'ALL5751_HISTORY_SETS.json')
        baseline_contracts[contract]={(x['film'],*x['reference_edge']):x for x in old}
    baseline=baseline_contracts['finite/unconstrained']
    scenario_summaries=[];filmrows=[];boundsrows=[];framerows=[];comparisonrows=[];failures=[]
    try:
        for scenario in read(ROOT/'SCENARIOS.json'):
            sb=time.perf_counter();sid=scenario['scenario_id'];sd=ROOT/'outcomes'/sid;sd.mkdir(parents=True)
            rng=np.random.Generator(np.random.PCG64(scenario['seed'])) if scenario['seed'] is not None else None
            data={};records=[];finiteblocks=[];numericblocks=[];caps=[];repairs=[];perturb=[]
            for film in sorted(raw):
                fb=time.perf_counter();ref,states=raw[film];coords=ref.coords.copy();order=np.argsort(ref.ids)
                if rng is None:
                    offset=np.zeros((len(ref.ids),3));offset[:,scenario['axis_index']]=scenario['sign']*scenario['amplitude']*SCALE[scenario['axis_index']]
                else:
                    offset=np.zeros((len(ref.ids),3));offset[order]=rng.uniform(-scenario['amplitude'],scenario['amplitude'],size=(len(ref.ids),3))*SCALE
                coords[:,1:]+=offset;pert=Graph(ref.ids,coords,ref.edges,ref.unit)
                assert np.array_equal(pert.ids,ref.ids) and np.array_equal(pert.edges,ref.edges) and np.array_equal(pert.coords[:,0],ref.coords[:,0])
                perturb.append({'film':film,'reference_ids_numeric_sorted':list(map(int,ref.ids[order])),'offset_zyx_um':offset[order].tolist(),
                  'perturbed_coordinate_sha256':hashlib.sha256(pert.coords.tobytes()).hexdigest(),'coordinates_reused_for_all_seven_stages':True})
                maps=[match(state,pert,7.) for state in states];originalmaps=[m.copy() for m in maps]
                certs=[];filmfb=[];filmnb=[];filmrep=[]
                for k,state in enumerate(states):
                    for t in np.unique(pert.coords[:,0]):
                        try:cert,f,n,c=R.frame_family(pert,state,maps[k],7.,t,CAP)
                        except ValueError:
                            error=traceback.format_exc();repair=repair_frame(pert,state,maps[k],t,error);repair.update({'film':film,'stage':k,'scenario_id':sid})
                            filmrep.append(repair);repairs.append(repair)
                            cert,f,n,c=R.frame_family(pert,state,maps[k],7.,t,CAP)
                        cert.update({'film':film,'stage':k,'gate_um':7,'scenario_id':sid});profile(cert,pert,state,t,maps[k]);certs.append(cert)
                        framerows.append({'scenario_id':sid,'film':film,'stage':k,'frame':int(t),'K':cert['max_cardinality'],
                          'reference_nodes':len(cert['reference_ids']),'prediction_nodes':len(cert['prediction_ids']),'eligible_pairs':len(cert['allowed_costs']),
                          'screened_combinations':cert['screened_combinations'],'finite_whole_maps':cert['finite_whole_frame_map_count'],
                          'numerical_whole_maps':cert['numerical_whole_frame_map_count'],'minimum_abs_gate_margin_um':cert['minimum_absolute_gate_boundary_margin_um'],
                          'max_candidate_count':max(map(int,cert['candidate_count_histogram']),default=0),'frame_cap':CAP})
                        if f:f.update({'film':film,'stage':k});filmfb.append(f)
                        if n:n.update({'film':film,'stage':k});filmnb.append(n)
                        if c:caps.append({'film':film,'stage':k,'frame':int(t),**c})
                finiteblocks.extend(filmfb);numericblocks.extend(filmnb);data[film]=(pert,states,maps)
                write(sd/(film+'.json.gz'),{'film':film,'scenario_id':sid,'reference_perturbation':perturb[-1],
                  'input_hashes_reused_from_single_manifest':{x['relative_path']:x['sha256'] for x in manifest['scientific_inputs'] if x['film']==film},
                  'original_canonical_maps':[[[q,p] for q,p in sorted(m.items())] for m in originalmaps],
                  'certified_canonical_maps':[[[q,p] for q,p in sorted(m.items())] for m in maps],
                  'original_matcher_failure_and_exact_repairs':filmrep,'frame_certificates':certs,'finite_blocks':filmfb,'numerical_blocks':filmnb,'withheld':caps})
                rr=account_from_matches(states,pert,maps)
                records.extend({'film':film,'reference_edge':r['reference_edge'],'history':''.join(map(str,r['visibility'])),'matched_pairs':r['matched_pairs']} for r in rr)
                print(json.dumps({'UTC':now(),'scenario':sid,'film':film,'frames':len(certs),'repairs':len(filmrep),'seconds':time.perf_counter()-fb}),flush=True)
                del certs
            assert len(records)==5751
            write(sd/'REFERENCE_OFFSETS_AND_COORDINATE_IDENTITIES.json.gz',perturb)
            write(sd/'CANONICAL_HISTORIES.json.gz',records)
            write(sd/'ORIGINAL_MATCHER_FAILURES_AND_EXACT_REPAIRS.json.gz',repairs)
            if caps:
                summary={'scenario_id':sid,'status':'WITHHELD_FRAME_CAP','caps':caps,'all31_scalar_bounds':None};write(sd/'RESULT.json',summary);scenario_summaries.append(summary);continue
            branchresults={}
            for name,blocks in [('finite',finiteblocks),('numerical',numericblocks)]:
                ls=R.links_from_geometry(data,blocks);write(sd/name/'WHOLE_FRAME_FAMILIES.json.gz',blocks)
                write(sd/name/'GEOMETRY_LINKS_AND_REJECTIONS.json.gz',ls)
                variants=[('unconstrained',[])]+([('geometry_constrained',ls['links'])] if name=='finite' else [])
                for variant,links in variants:
                    branch=f'{name}/{variant}';bd=sd/name/variant
                    try:res,doc,derived=R.joint_readout(data,records,blocks,links,CAP)
                    except ValueError:
                        failed={'status':'ACTUAL_GEOMETRY_CONSTRAINT_FAILURE_RETAINED','exception':traceback.format_exc(),'all31_scalar_bounds':None}
                        write(bd/'FAILURE.json',failed);branchresults[branch]=failed;failures.append({'scenario_id':sid,'branch':branch,**failed});continue
                    write(bd/'RESULT.json',res)
                    if doc is None:branchresults[branch]=res;continue
                    write(bd/'JOINT_INPUT.LOCAL_ONLY.json.gz',doc);write(bd/'ALL5751_HISTORY_SETS.json.gz',derived['histories'])
                    write(bd/'ALL31_SCALAR_BOUNDS.json',derived['bounds']);write(bd/'COMPLETE_MAPPING_CONFIGURATION_WITNESSES.json.gz',derived['witnesses'])
                    summary=branch_summary(res,derived,records,baseline_contracts[branch]);summary['geometry_links_accepted']=len(ls['links']);summary['geometry_boundaries_rejected']=len(ls['rejected'])
                    summary['geometry_rejection_reason_counts']=dict(collections.Counter(x['reason'] for x in ls['rejected']))
                    summary['whole_frame_blocks']=len(blocks);summary['whole_frame_assignments']=sum(len(b['assignments']) for b in blocks)
                    branchresults[branch]=summary
                    for film in sorted(data):
                        localhist=[x for x in derived['histories'] if x['film']==film];fixedstats=R.total_features(x['history'] for x in doc['fixed_histories'] if x['reference_edge_id'][0]==film)
                        cw=[w for w in derived['witnesses'] if w['film']==film];fstats=R.total_features(x['canonical_history'] for x in localhist)
                        fsummary={'scenario_id':sid,'film':film,'branch':branch,**partition(localhist),
                          'canonical_history_changed_from_primary':sum(x['canonical_history']!=baseline_contracts[branch][film,*x['reference_edge']]['canonical_history'] for x in localhist),
                          'canonical_category_changed_from_primary':sum(R.categories([x['canonical_history']])!=R.categories([baseline_contracts[branch][film,*x['reference_edge']]['canonical_history']]) for x in localhist),
                          'component_count':len(cw),'joint_assignments_represented':math.prod(w['feasible_configurations'] for w in cw),
                          'component_raw_product_counts':json.dumps([w['raw_product_configurations_before_links'] for w in cw]),'component_feasible_counts':json.dumps([w['feasible_configurations'] for w in cw]),
                          'geometry_links_accepted':sum(x['film']==film for x in ls['links']),'geometry_boundaries_rejected':sum(x['film']==film for x in ls['rejected']),
                          'canonical_final_missing':fstats['final_missing'],'canonical_observed_loss':fstats['final_missing_with_loss'],'canonical_persistent_absence':fstats['persistent_absence'],
                          'status':res['status'],'frame_cap':CAP,'component_cap':CAP}
                        filmrows.append(fsummary)
                        for field in fstats:
                            boundsrows.append({'scenario_id':sid,'film':film,'branch':branch,'scalar':field,'canonical':fstats[field],
                              'minimum':fixedstats[field]+sum(w['minimum'][field] for w in cw),'maximum':fixedstats[field]+sum(w['maximum'][field] for w in cw)})
                    for field,b in derived['bounds'].items():boundsrows.append({'scenario_id':sid,'film':'ALL8','branch':branch,'scalar':field,**b})
                    for x in derived['histories']:
                        b=baseline_contracts[branch][x['film'],*x['reference_edge']]
                        comparisonrows.append({'scenario_id':sid,'branch':branch,'film':x['film'],'reference_a':x['reference_edge'][0],'reference_b':x['reference_edge'][1],
                          'primary_canonical_history':b['canonical_history'],'scenario_canonical_history':x['canonical_history'],
                          'primary_history_set':'|'.join(b['admissible_visibility_strings']),'scenario_history_set':'|'.join(x['admissible_visibility_strings']),
                          'primary_categories':'|'.join(b['categories']),'scenario_categories':'|'.join(x['categories']),
                          'canonical_history_changed':int(b['canonical_history']!=x['canonical_history']),
                          'canonical_category_changed':int(R.categories([b['canonical_history']])!=R.categories([x['canonical_history']])),
                          'history_set_changed':int(b['admissible_visibility_strings']!=x['admissible_visibility_strings']),
                          'category_set_changed':int(b['categories']!=x['categories'])})
                    del doc,derived
            ss={'scenario':scenario,'status':'SCENARIO_FINISHED','original_matcher_repaired_frames':len(repairs),'branches':branchresults,'elapsed_seconds':time.perf_counter()-sb}
            write(sd/'RESULT.json',ss);scenario_summaries.append(ss)
            print(json.dumps({'UTC':now(),'scenario_complete':sid,'seconds':ss['elapsed_seconds'],'repairs':len(repairs)}),flush=True)
        csvwrite(ROOT/'SCENARIO_FILM_PARTITIONS.csv',filmrows,list(filmrows[0]))
        csvwrite(ROOT/'ALL31_SCALAR_BOUNDS_BY_SCENARIO_FILM.csv',boundsrows,list(boundsrows[0]))
        csvwrite(ROOT/'FRAME_CANDIDATE_MARGIN_AND_FAMILY_PROFILE.csv.gz',framerows,list(framerows[0]))
        csvwrite(ROOT/'ALL_IDENTITY_CHANGES_VS_PRIMARY.csv.gz',comparisonrows,list(comparisonrows[0]))
        summary={'UTC':now(),'status':'ALL30_SCENARIOS_EXECUTED','scenario_count':len(scenario_summaries),'reference_relations_per_scenario':5751,
          'film_count':8,'stages':7,'gate_um':7,'source_scale_interpretation':'source_coordinate_grid_sensitivity_only; no verified voxel calibration or localization error',
          'primary_result_preserved':True,'zero_perturbation_recomputed':False,'post_review_design':True,'preregistered':False,'blinded':False,
          'sampled_bounded_scenarios_only':True,'continuous_domain_worst_case_claimed':False,'probability_calibration_or_CI':False,'new_biological_N':0,
          'prediction_only_tested':False,'joint_registration_tested':False,'all_adverse_and_null_scenarios_retained':True,
          'frame_cap':CAP,'component_cap':CAP,'withhold_not_truncate':True,'failures':failures,'scenarios':scenario_summaries}
        write(ROOT/'RESULT.json',summary)
    except BaseException:
        write(ROOT/'execution'/f'ACTUAL_FAILURE_{os.getpid()}_{int(time.time())}.json',{'UTC':now(),'traceback':traceback.format_exc(),'status':'ACTUAL_FAILURE_RETAINED'});raise
    finally:
        stop.set();thread.join();mem=process.memory_info()
        write(ROOT/'execution'/'RESOURCE_MEASUREMENT.json',{'UTC':now(),'elapsed_seconds':time.perf_counter()-beg,
          'sampled_peak_process_RSS_bytes':max((v for t,v in samples),default=None),'RSS_sampling_interval_seconds':.02,'samples':len(samples),
          'Windows_process_peak_working_set_bytes':getattr(mem,'peak_wset',None),'Windows_process_peak_pagefile_bytes':getattr(mem,'peak_pagefile',None),
          'cpu_times':process.cpu_times()._asdict(),'scope':'this one Python process, includes loading/serialization/report tables; excludes shell and prior preparation'})
        csvwrite(ROOT/'execution'/'MEMORY_SAMPLES.csv.gz',[{'seconds':t,'RSS_bytes':v} for t,v in samples],['seconds','RSS_bytes'])

if __name__=='__main__':run()
