"""Frozen constructed raw-coordinate stress experiment. No biological data or inference.

Run prepare once, then run. Workers isolate generation, configuration construction,
given-family readout, and literal validation. All outputs are exclusive-create.
"""
import argparse, csv, ctypes, datetime, fractions, gzip, hashlib, importlib.util
import itertools, json, math, os, platform, shutil, subprocess, sys, threading, time, traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NS = (2,3,4,5,6,7,8,16,32)
KINDS = ('unique_sparse','unique_dense','exact_degenerate','small_nonzero_margin')
CAP = 65536
SOURCE_ROOT = ROOT.parent/'v013_full_fresh_review_v0.1'/'packet'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def emit(p, data):
    p = Path(p); p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(data,f,ensure_ascii=False,indent=2); f.write('\n')
def gz_emit(p,data):
    with gzip.open(p,'xt',encoding='utf-8') as f: json.dump(data,f,ensure_ascii=False,separators=(',',':'))
def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def table(p,rows):
    rows=list(rows); names=list(dict.fromkeys(k for r in rows for k in r))
    with Path(p).open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=names); w.writeheader()
        for r in rows:
            w.writerow({k:'NA' if v is None else json.dumps(v,ensure_ascii=False,separators=(',',':')) if isinstance(v,(list,dict)) else v for k,v in r.items()})

class PMC(ctypes.Structure):
    _fields_=[('cb',ctypes.c_ulong),('PageFaultCount',ctypes.c_ulong),('PeakWorkingSetSize',ctypes.c_size_t),
              ('WorkingSetSize',ctypes.c_size_t),('QuotaPeakPagedPoolUsage',ctypes.c_size_t),('QuotaPagedPoolUsage',ctypes.c_size_t),
              ('QuotaPeakNonPagedPoolUsage',ctypes.c_size_t),('QuotaNonPagedPoolUsage',ctypes.c_size_t),
              ('PagefileUsage',ctypes.c_size_t),('PeakPagefileUsage',ctypes.c_size_t)]
def native_memory():
    if os.name!='nt': return None
    kernel=ctypes.windll.kernel32; psapi=ctypes.windll.psapi
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(PMC),ctypes.c_ulong]
    counters=PMC(); counters.cb=ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(counters),counters.cb):
        raise ctypes.WinError()
    return int(counters.WorkingSetSize),int(counters.PeakWorkingSetSize)
class Profile:
    def __init__(self,phase): self.phase=phase; self.stop=threading.Event(); self.samples=[]
    def sample(self):
        m=native_memory()
        if m: self.samples.append(m[0])
    def poll(self):
        while not self.stop.wait(.002): self.sample()
    def __enter__(self):
        self.sample(); self.baseline=self.samples[0] if self.samples else None
        self.thread=threading.Thread(target=self.poll,daemon=True); self.thread.start()
        self.start=time.perf_counter(); return self
    def __exit__(self,*args):
        self.seconds=time.perf_counter()-self.start; self.sample(); self.stop.set(); self.thread.join()
        m=native_memory()
        self.result={'phase':self.phase,'runtime_seconds':self.seconds,'phase_baseline_working_set_bytes':self.baseline,
                     'phase_sampled_peak_working_set_bytes':max(self.samples) if self.samples else None,
                     'phase_sampled_peak_increase_bytes':max(self.samples)-self.baseline if self.samples else None,
                     'native_process_lifetime_peak_working_set_bytes':m[1] if m else None,
                     'working_set_samples':len(self.samples),'poll_target_seconds':.002,
                     'memory_scope':'actual Windows OS working set; sampled phase peak is a lower bound; native lifetime peak includes imports and earlier input preparation',
                     'timer_scope':'phase code only; result serialization excluded; import/startup excluded',
                     'process_id':os.getpid(),'phase_failed':bool(args and args[0])}

def modules():
    sys.path.insert(0,str(ROOT/'sources'))
    import numpy as np
    import reconstruct as raw
    from stage_accounting import Graph, match, account_from_matches
    spec=importlib.util.spec_from_file_location('frozen_joint_history',ROOT/'sources'/'joint_history.py')
    joint=importlib.util.module_from_spec(spec); spec.loader.exec_module(joint)
    return np,raw,Graph,match,account_from_matches,joint
def graphs(case):
    np,raw,Graph,match,account,joint=modules()
    def build(g): return Graph(np.asarray(g['ids'],dtype=np.int64),np.asarray(g['coords'],dtype=float),np.asarray(g['edges'],dtype=np.int64).reshape(-1,2),g['unit'])
    return build(case['reference']),[build(g) for g in case['stages']],(np,raw,Graph,match,account,joint)
def canonical_histories(case,maps):
    pairs=[set(map(tuple,g['edges'])) for g in case['stages']]
    return [''.join(str(int((m.get(a),m.get(b)) in es)) for m,es in zip(maps,pairs)) for a,b in case['reference']['edges']]
def independent_features(histories):
    names=('final_missing','persistent_absence','final_missing_with_loss','visibility_transition_edges',
           'first_last_loss_disagreements_final_missing','final_last_loss_persistent',
           'stage_visible_0','stage_visible_1','gain_1','loss_1','final_last_loss_1')
    total=dict.fromkeys(names,0)
    for h in histories:
        x,y=map(int,h)
        vals=(1-y,int(x==y==0),int(x==1 and y==0),int(x!=y),0,int(x==y==0),x,y,int(x==0 and y==1),int(x==1 and y==0),int(x==1 and y==0))
        for key,value in zip(names,vals): total[key]+=value
    return total

def prepare():
    import numpy as np, scipy
    if (ROOT/'INPUT_SOURCE_FREEZE.json').exists(): raise FileExistsError('Already frozen')
    sources=ROOT/'sources'; (sources/'sources'/'executed').mkdir(parents=True)
    originals={
       'reconstruct.py':SOURCE_ROOT/'scientific_routes'/'family'/'reconstruct.py',
       'stage_accounting.py':SOURCE_ROOT/'scientific_routes'/'family'/'sources'/'executed'/'stage_accounting.py',
       'joint_history.py':SOURCE_ROOT/'analysis_code'/'portable_analysis_candidate_v0.5'/'src'/'portable_analysis_candidate'/'joint_history.py',
    }
    copied=[]
    for name,p in originals.items():
        dest=sources/name; shutil.copyfile(p,dest)
        copied.append({'original':str(p),'copy':str(dest.relative_to(ROOT)),'sha256':sha(dest),'unaltered_copy':sha(p)==sha(dest)})
    shutil.copyfile(sources/'stage_accounting.py',sources/'sources'/'executed'/'stage_accounting.py')
    copied.append({'copy':'sources/sources/executed/stage_accounting.py','sha256':sha(sources/'sources'/'executed'/'stage_accounting.py'),'reason':'preserved reconstruct import layout'})
    (ROOT/'inputs').mkdir(); (ROOT/'results').mkdir(); cases=[]
    for kind in KINDS:
        for n in NS:
            cid=f'{kind}_n{n:02d}'
            if kind=='unique_sparse': step=3.0
            elif kind=='unique_dense': step=2.0**-6
            elif kind=='small_nonzero_margin': step=2.0**-30
            else: step=0.0
            ids=list(range(2*n)); pids=list(range(10000,10000+2*n))
            coords=[[t,0.0,0.0,i*step] for t in range(2) for i in range(n)]
            predcoords=[[t,1.0 if kind=='exact_degenerate' else 0.0,0.0,i*step] for t in range(2) for i in range(n)]
            refedges=[[0,n+j] for j in range(n)]
            stageedges=[[[10000+i,10000+n+((i+k)%n)] for i in range(n)] for k in range(2)]
            case={'case_id':cid,'kind':kind,'n_per_frame':n,'frame_count':2,'stage_count':2,'gate_um':1.0,'frame_cap':CAP,'component_cap':CAP,
                  'coordinate_spacing_um':step,'constructed':True,'biological_N':0,
                  'reference':{'ids':ids,'coords':coords,'edges':refedges,'unit':'um'},
                  'stages':[{'ids':pids,'coords':predcoords,'edges':e,'unit':'um'} for e in stageedges],
                  'cross_stage_constraints':'none_in_correspondence_estimand',
                  'expected_frame_finite_count_analytic':str(math.factorial(n) if kind=='exact_degenerate' else 1),
                  'expected_component_map_product_analytic':str(math.factorial(n)**4 if kind=='exact_degenerate' else 1),
                  'expected_minimum_noncanonical_exact_gap_um':'0' if kind=='exact_degenerate' else 'no_same_cardinality_alternative_in_gate' if kind=='unique_sparse' else str(fractions.Fraction.from_float(2*step)),
                  'construction_note':'Deliberate raw coordinate stress; repeated coordinates for exact equidistance are not measured microscopy noise; star schema validity is not a biological structure assertion.'}
            path=ROOT/'inputs'/f'{cid}.json'; emit(path,case)
            cases.append({'case_id':cid,'kind':kind,'n':n,'path':str(path.relative_to(ROOT)),'sha256':sha(path),'input_bytes':path.stat().st_size})
    design={'frozen_utc':utc(),'design_fixed_before_execution':True,'n':list(NS),'kinds':list(KINDS),'cases':36,
            'physical_frames_per_case':2,'saved_stages_per_case':2,'frame_cap':CAP,'component_cap':CAP,
            'objective':'maximum gated matching cardinality, then exact sums of already calculated float64 distances (finite contract)',
            'gate_um':1.0,'inclusive_gate':True,'unique_dense_spacing_um':2**-6,'small_margin_spacing_um':2**-30,
            'exact_degenerate':'all references co-located at origin and predictions co-located one um away in each frame; all n^2 distances exactly 1',
            'star_reference':'n edges share reference 0 in frame 0 and have distinct endpoints in frame 1; stage edges form a shifted bijection',
            'coupling':'whole-frame injectivity and shared reference-edge incidence; no extra equality links and no cross-stage constraints',
            'production_cap':'screen-product cap BEFORE whole-map enumeration; no cap increase; component product pre-rejection before actual joint enumeration',
            'literal_validation':'n<=8 only; independent itertools.permutations and math.dist binary rational sums; cap-refused production families remain refused even if literal counts known',
            'large_n_validation':'analytic factorial counts only; no factorial enumeration',
            'resource':'fresh isolated subprocess for each phase; perf_counter runtime; actual Windows working-set sampled every 2 ms and native process lifetime peak; serialization excluded; skipped measurements NA',
            'given_family_readout':'generic joint_history module on generated complete joint configurations; caller declarations audited independently, module does not infer family completeness',
            'report_scope':'separate scalar endpoint witnesses only, arbitrary scalar integer interiors and endpoint vectors are not certified',
            'no_biological_replication':True,'no_model_inference':True,'source_reuse_is_not_novel_algorithm':True,
            'potential_release':'constructed input examples; no public location or license assertion',
            'fixed_cases':cases,'source_copies':copied,'python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__}
    emit(ROOT/'DESIGN_FREEZE.json',design)
    paths=[ROOT/'run_stress.py',ROOT/'DESIGN_FREEZE.json']+sorted(sources.rglob('*.py'))+sorted((ROOT/'inputs').glob('*.json'))
    emit(ROOT/'INPUT_SOURCE_FREEZE.json',{'frozen_utc':utc(),'files':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p),'bytes':p.stat().st_size} for p in paths]})
    print(json.dumps({'prepared_cases':len(cases),'freeze_sha256':sha(ROOT/'INPUT_SOURCE_FREEZE.json')},ensure_ascii=False))

def generation(case,out):
    ref,stages,mod=graphs(case); np,raw,Graph,match,account,joint=mod
    frames=[]; certs=[]; frame_rows=[]
    with Profile('raw_coordinate_family_generation') as prof:
        start=time.perf_counter(); maps=[match(s,ref,case['gate_um']) for s in stages]; match_seconds=time.perf_counter()-start
        for k,state in enumerate(stages):
            for t in range(2):
                start=time.perf_counter(); cert,finite,numerical,cap=raw.frame_family(ref,state,maps[k],case['gate_um'],t,CAP); duration=time.perf_counter()-start
                framebase={r:p for r,p in maps[k].items() if int(ref.coords[list(ref.ids).index(r),0])==t}
                assignments=finite['assignments'] if finite else [{}]
                members=None if cap else [{**framebase,**{int(r):p for r,p in a.items()}} for a in assignments]
                options=[fractions.Fraction(gap) for r,p,gap,keep in cert['forced_options'] if gap is not None and framebase.get(r)!=p]
                positive=[g for g in options if g>0]
                row={'case_id':case['case_id'],'stage':k,'frame':t,'n_reference':case['n_per_frame'],'n_prediction':case['n_per_frame'],
                     'matched_nodes':cert['max_cardinality'],'allowed_candidate_pairs':len(cert['allowed_costs']),
                     'candidate_density':len(cert['allowed_costs'])/(case['n_per_frame']**2),
                     'support_screen_product':cert['screened_combinations'],'cap':CAP,'cap_reason':cap['status'] if cap else None,
                     'finite_whole_map_count':len(members) if members is not None else None,
                     'numerical_whole_map_count':None if cap else len(numerical['assignments']) if numerical else 1,
                     'whole_map_checks':len(cert.get('whole_map_checks',[])) if not cap else None,
                     'injectivity_rejections':sum(not c['one_to_one'] for c in cert.get('whole_map_checks',[])) if not cap else None,
                     'minimum_noncanonical_forced_same_cardinality_gap_um':str(min(options)) if options else None,
                     'minimum_positive_forced_same_cardinality_gap_um':str(min(positive)) if positive else None,
                     'canonical_native_fsum_um':cert['canonical_native_fsum_um'],'exact_cost_denominator':cert['exact_cost_denominator'],
                     'frame_family_runtime_seconds':duration,'complete_generated_family':not bool(cap)}
                frame_rows.append(row); certs.append((k,t,cert))
                frames.append({'stage':k,'frame':t,'complete':not bool(cap),'canonical_map':framebase,'members':members,'cap':cap,
                               'certificate_file':f'frame_stage{k}_time{t}.certificate.json.gz'})
    prof.result['canonical_match_runtime_seconds']=match_seconds
    for k,t,cert in certs: gz_emit(out/f'frame_stage{k}_time{t}.certificate.json.gz',cert)
    canonical={'canonical_maps':maps,'histories':canonical_histories(case,maps),'reference_edges':case['reference']['edges'],
               'scalar_report':independent_features(canonical_histories(case,maps)),'report_source':'actual raw matcher canonical maps, same input graph edges'}
    emit(out/'canonical_report.json',canonical); gz_emit(out/'frame_members.json.gz',{'case_id':case['case_id'],'frames':frames})
    table(out/'frame_results.csv',frame_rows); emit(out/'generation_profile.json',prof.result)
    emit(out/'generation_status.json',{'case_id':case['case_id'],'status':'COMPLETE_FINITE_FRAME_FAMILIES' if all(f['complete'] for f in frames) else 'WITHHELD_WHOLE_FRAME_CAP',
         'all_four_frame_families_complete':all(f['complete'] for f in frames),'frame_rows':frame_rows,
         'raw_points_across_reference_and_stages':6*case['n_per_frame'],'reference_nodes':2*case['n_per_frame'],'reference_edges':case['n_per_frame'],
         'stages':2,'physical_frames':2,'independent_biological_N':0,'input_bytes':(ROOT/'inputs'/f"{case['case_id']}.json").stat().st_size})

def joint_construction(case,out):
    with Profile('actual_joint_configuration_construction_or_cap_precheck') as prof:
        with gzip.open(out/'frame_members.json.gz','rt',encoding='utf-8') as f: family=json.load(f)
        canonical=read(out/'canonical_report.json'); frames=family['frames']
        if not all(f['complete'] for f in frames):
            status={'status':'WITHHELD_UPSTREAM_WHOLE_FRAME_CAP','scalar_bounds':None,'actual_component_product':None,'actual_joint_configurations':None,
                    'analytic_expected_component_map_product':case['expected_component_map_product_analytic'],'reason':'No complete production frame family; independent literal validation cannot substitute.'}
        else:
            count=math.prod(len(f['members']) for f in frames)
            if count>CAP:
                status={'status':'WITHHELD_COMPONENT_ENUMERATION_CAP','scalar_bounds':None,'actual_component_product':count,'actual_joint_configurations':None,
                        'cap':CAP,'reason':'Actual complete frame-family product checked before joint configuration enumeration; no trimming or cap increase.'}
            else:
                pairs=[set(map(tuple,s['edges'])) for s in case['stages']]; rows=[]; configs=[]
                for choices in itertools.product(*(range(len(f['members'])) for f in frames)):
                    maps=[{},{}]
                    for frame,i in zip(frames,choices): maps[frame['stage']].update({int(r):p for r,p in frame['members'][i].items()})
                    hs=[''.join(str(int((maps[k].get(a),maps[k].get(b)) in pairs[k])) for k in range(2)) for a,b in case['reference']['edges']]
                    vals=independent_features(hs)
                    rows.append({'configuration_index':len(rows),'frame_member_indices':list(choices),'histories':hs,**vals}); configs.append(hs)
                is_variable=any(len(f['members'])>1 for f in frames)
                ids=[[case['case_id'],a,b] for a,b in case['reference']['edges']]
                doc={'reference_edge_ids':ids,'stage_count':2,
                     'fixed_histories':[] if is_variable else [{'reference_edge_id':q,'history':h} for q,h in zip(ids,configs[0])],
                     'components':[{'reference_edge_ids':ids,'configurations':configs}] if is_variable else [],
                     'completeness_asserted_by_caller':True,'product_factorization_asserted_by_caller':True,
                     'joint_family_rule':'Four complete finite frame families certified by raw residual dual/maximum-cardinality cover and exhaustive whole-map tests; actual Cartesian configurations join both physical frames and stages via star edge incidence. No cross-stage correspondence constraints. Single component or fixed complement.'}
                status={'status':'COMPLETE_ACTUAL_JOINT_CONFIGURATIONS','actual_component_product':count,'actual_joint_configurations':len(configs),
                        'distinct_joint_visibility_configurations':len(set(map(tuple,configs))),'scalar_bounds':None,
                        'frame_member_report':'frame_members.json.gz','canonical_report':'canonical_report.json','actual_member_report':'joint_member_report.csv',
                        'mapping_provenance':'Each actual configuration row stores four member indices in stage0/frame0, stage0/frame1, stage1/frame0, stage1/frame1 order; maps are exact saved frame members.'}
    emit(out/'joint_construction_profile.json',prof.result); emit(out/'joint_construction_status.json',status)
    if status['status']=='COMPLETE_ACTUAL_JOINT_CONFIGURATIONS':
        emit(out/'joint_input.json',doc); table(out/'joint_member_report.csv',rows)

def given_readout(case,out):
    np,raw,Graph,match,account,joint=modules()
    with Profile('given_complete_joint_family_readout') as prof:
        doc=read(out/'joint_input.json'); report=joint.account_joint_history_components(doc,max_configurations_per_component=CAP)
    emit(out/'given_family_readout_profile.json',prof.result); emit(out/'generic_joint_readout.json',report)
    canonical=read(out/'canonical_report.json')
    with (out/'joint_member_report.csv').open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    endpoint_rows=[]; value_sets={}; evidence={}
    for name,bounds in report['scalar_bounds'].items():
        vals=[int(r[name]) for r in rows]; value_sets[name]=sorted(set(vals))
        assert (min(vals),max(vals))==(bounds['minimum'],bounds['maximum'])
        endpoint_rows.append({'field':name,'canonical':canonical['scalar_report'][name],**bounds,
                              'minimum_witness_configuration_index':vals.index(min(vals)),
                              'maximum_witness_configuration_index':vals.index(max(vals)),
                              'actual_attainable_scalar_values':sorted(set(vals))})
    maxvector={k:b['maximum'] for k,b in report['scalar_bounds'].items()}
    evidence={'all_separate_scalar_endpoints_have_actual_member_witness':True,
              'generic_readout_matches_independent_member_report_minmax':True,
              'attainable_scalar_values':value_sets,
              'all_field_maximum_vector_attainable':any(all(int(r[k])==v for k,v in maxvector.items()) for r in rows),
              'arbitrary_scalar_integer_interior_certified':False,
              'arbitrary_endpoint_vector_certified':False,
              'member_report_schema':'all actual correspondence configurations including repeated visibility rows; repeated rows are not independent N'}
    if case['kind']=='exact_degenerate':
        evidence.update({'infeasible_pair_of_scalar_claims':{'persistent_absence':case['n_per_frame']-1,'visibility_transition_edges':2},
          'pair_is_infeasible_by_full_member_report':not any(int(r['persistent_absence'])==case['n_per_frame']-1 and int(r['visibility_transition_edges'])==2 for r in rows),
          'missing_integer_inside_transition_bound':1,'missing_integer_not_attainable':1 not in value_sets['visibility_transition_edges']})
    table(out/'scalar_endpoint_witnesses.csv',endpoint_rows); emit(out/'joint_scalar_evidence.json',evidence)

def literal_validation(case,out):
    n=case['n_per_frame']; results=[]; opt={}; allclaims=[]
    if n>8:
        emit(out/'literal_validation.json',{'status':'ANALYTIC_ONLY_NOT_ENUMERATED','expected_frame_count':case['expected_frame_finite_count_analytic'],
             'production_family_complete':read(out/'generation_status.json')['all_four_frame_families_complete'],
             'analytic_proof':'Co-located degenerate case has complete bipartite equal-cost distances => each of n! bijections minimum. Unique diagonal zero and every off-diagonal positive => unique minimum. Sparse only diagonal eligible.'})
        emit(out/'literal_validation_profile.json',{'phase':'independent_literal_permutation_validation','runtime_seconds':None,
             'phase_sampled_peak_working_set_bytes':None,'native_process_lifetime_peak_working_set_bytes':None,'reason':'n>8 factorial enumeration intentionally not run'})
        return
    with Profile('independent_literal_permutation_validation') as prof:
        with gzip.open(out/'frame_members.json.gz','rt',encoding='utf-8') as f: generated=json.load(f)['frames']
        for k in range(2):
            for t in range(2):
                ref=[c[1:] for c in case['reference']['coords'] if c[0]==t]
                pred=[c[1:] for c in case['stages'][k]['coords'] if c[0]==t]
                d=[[math.dist(a,b) for b in pred] for a in ref]
                ratios=[[v.as_integer_ratio() for v in row] for row in d]
                den=max(q for row in ratios for p,q in row); costs=[[p*(den//q) for p,q in row] for row in ratios]
                best=None; optimal=[]; attempted=0; gate_feasible=0
                for perm in itertools.permutations(range(n)):
                    attempted+=1
                    if any(d[i][j]>case['gate_um'] for i,j in enumerate(perm)): continue
                    gate_feasible+=1; cost=sum(costs[i][j] for i,j in enumerate(perm))
                    if best is None or cost<best: best=cost; optimal=[perm]
                    elif cost==best: optimal.append(perm)
                assert len(optimal)==int(case['expected_frame_finite_count_analytic'])
                f=next(f for f in generated if f['stage']==k and f['frame']==t)
                with gzip.open(out/f['certificate_file'],'rt',encoding='utf-8') as z: cert=json.load(z)
                samecost=all(float.fromhex(hexv)==d[r-t*n][p-10000-t*n] for r,p,hexv,c in cert['allowed_costs'])
                assert samecost and cert['max_cardinality']==n
                assert fractions.Fraction(best,den)==fractions.Fraction(int(cert['canonical_exact_integer_sum']),int(cert['exact_cost_denominator']))
                equal=None
                if f['complete']:
                    memberperms={tuple(m[str(t*n+i)]-10000-t*n for i in range(n)) for m in f['members']}
                    equal=memberperms==set(optimal); assert equal
                results.append({'stage':k,'frame':t,'literal_permutations_checked':attempted,'eligible_max_cardinality_bijections':gate_feasible,
                     'literal_optimum_count':len(optimal),'literal_exact_minimum_cost':str(fractions.Fraction(best,den)),
                     'production_family_complete':f['complete'],'literal_member_set_equals_generated_finite_family':equal,
                     'independent_math_dist_equals_calculated_source_costs':samecost,
                     'cap_rejected_production_not_relabelled_complete':not f['complete']})
                opt[k,t]=optimal
        for k in range(2):
            left_images={perm[0] for perm in opt[k,0]}; edge_set=set(map(tuple,case['stages'][k]['edges']))
            counts=set(); patterns=set(); checked=0
            for image in left_images:
                for right in opt[k,1]:
                    v=tuple(int((10000+image,10000+n+right[j]) in edge_set) for j in range(n))
                    counts.add(sum(v)); patterns.add(v); checked+=1
            both=any(v[0] and v[1] for v in patterns); assert not both and counts=={1}
            possible=[any(v[j] for v in patterns) for j in range(n)]
            if case['kind']=='exact_degenerate': assert all(possible)
            allclaims.append({'stage':k,'literal_left_endpoint_projection_size':len(left_images),'literal_right_optimal_permutations':len(opt[k,1]),
                  'projected_stage_configurations_checked':checked,'joint_visible_count_values':sorted(counts),
                  'each_edge_separately_visible_possible':possible,
                  'claims_edge0_visible_and_edge1_visible_jointly_possible':both,
                  'proof':'Exhaustive projection of independent literal optimum permutations; left non-shared endpoints do not enter any star edge. Every prediction source has one outgoing stage edge and right-frame map is injective.'})
    emit(out/'literal_validation_profile.json',prof.result)
    emit(out/'literal_validation.json',{'status':'PASS_INDEPENDENT_LITERAL_PERMUTATION_CHECK','frame_checks':results,'shared_endpoint_claim_checks':allclaims,
         'does_not_substitute_for_cap_withheld_production_family':True,'not_independent_biological_replication':True})

def worker(phase,cid):
    out=ROOT/'results'/cid; out.mkdir(exist_ok=True); case=read(ROOT/'inputs'/f'{cid}.json')
    actions={'generation':generation,'joint_construction':joint_construction,'given_readout':given_readout,'literal_validation':literal_validation}
    actions[phase](case,out)
def run():
    freeze=read(ROOT/'INPUT_SOURCE_FREEZE.json')
    for row in freeze['files']:
        if sha(ROOT/row['path'])!=row['sha256']: raise ValueError('Frozen file changed: '+row['path'])
    if (ROOT/'RUN_START.json').exists(): raise FileExistsError('Already started; preserve every earlier result')
    emit(ROOT/'RUN_START.json',{'utc':utc(),'python':sys.executable,'python_version':sys.version,'platform':platform.platform(),
         'freeze_sha256':sha(ROOT/'INPUT_SOURCE_FREEZE.json'),'source_reuse_not_novel':True,'concurrent_workers':False,
         'research_labor_hours':None,'research_labor_hours_note':'NA; execution wall clock is not researcher labor'})
    case_rows=[]; profiles=[]; failures=[]
    for fixed in read(ROOT/'DESIGN_FREEZE.json')['fixed_cases']:
        cid=fixed['case_id']; out=ROOT/'results'/cid; out.mkdir()
        phases=['generation','joint_construction','literal_validation']
        for phase in phases:
            proc=subprocess.run([sys.executable,'-B','-X','utf8',str(ROOT/'run_stress.py'),'worker','--phase',phase,'--case',cid],capture_output=True,text=True,encoding='utf-8')
            emit(out/f'{phase}_process_receipt.json',{'phase':phase,'returncode':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr})
            if proc.returncode:
                failures.append({'case_id':cid,'phase':phase,'returncode':proc.returncode,'error':proc.stderr}); break
        if not (out/'joint_construction_status.json').exists(): continue
        js=read(out/'joint_construction_status.json')
        if js['status']=='COMPLETE_ACTUAL_JOINT_CONFIGURATIONS':
            phase='given_readout'
            proc=subprocess.run([sys.executable,'-B','-X','utf8',str(ROOT/'run_stress.py'),'worker','--phase',phase,'--case',cid],capture_output=True,text=True,encoding='utf-8')
            emit(out/f'{phase}_process_receipt.json',{'phase':phase,'returncode':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr})
            if proc.returncode: failures.append({'case_id':cid,'phase':phase,'returncode':proc.returncode,'error':proc.stderr})
        else:
            emit(out/'given_family_readout_profile.json',{'phase':'given_complete_joint_family_readout','runtime_seconds':None,
                 'phase_sampled_peak_working_set_bytes':None,'native_process_lifetime_peak_working_set_bytes':None,'reason':js['status']})
        gs=read(out/'generation_status.json'); fr=gs['frame_rows']; rp=out/'generic_joint_readout.json'
        readout=read(rp) if rp.exists() else None
        row={'case_id':cid,'kind':fixed['kind'],'n_per_frame':fixed['n'],'physical_frames':2,'saved_stages':2,
             'reference_nodes':gs['reference_nodes'],'matched_nodes_per_frame':fr[0]['matched_nodes'],
             'allowed_candidate_pairs_per_frame':fr[0]['allowed_candidate_pairs'],'candidate_density':fr[0]['candidate_density'],
             'minimum_noncanonical_same_cardinality_gap_um':fr[0]['minimum_noncanonical_forced_same_cardinality_gap_um'],
             'support_screen_product_per_frame':str(fr[0]['support_screen_product']),
             'actual_whole_frame_finite_map_count':fr[0]['finite_whole_map_count'],
             'analytic_expected_whole_frame_count':read(ROOT/fixed['path'])['expected_frame_finite_count_analytic'],
             'generation_status':gs['status'],'component_product':js.get('actual_component_product'),
             'analytic_expected_component_product':read(ROOT/fixed['path'])['expected_component_map_product_analytic'],
             'actual_joint_configurations':js.get('actual_joint_configurations'),'joint_status':js['status'],
             'given_family_readout_status':readout['status'] if readout else None,'scalar_fields_reported':len(readout['scalar_bounds']) if readout else 0,
             'output_coverage_complete_scalar_report':bool(readout),'input_bytes':fixed['input_bytes'],'biological_N':0}
        for phasefile in ('generation_profile.json','joint_construction_profile.json','given_family_readout_profile.json','literal_validation_profile.json'):
            if (out/phasefile).exists():
                p=read(out/phasefile); profiles.append({'case_id':cid,**p})
                label={'generation_profile.json':'generation','joint_construction_profile.json':'joint_construction','given_family_readout_profile.json':'given_family_readout','literal_validation_profile.json':'literal_validation'}[phasefile]
                row[label+'_runtime_seconds']=p.get('runtime_seconds')
                row[label+'_phase_sampled_peak_working_set_bytes']=p.get('phase_sampled_peak_working_set_bytes')
                row[label+'_native_lifetime_peak_working_set_bytes']=p.get('native_process_lifetime_peak_working_set_bytes')
        case_rows.append(row)
        print(json.dumps({'case':cid,'family':gs['status'],'joint':js['status'],'runtime_generation':row['generation_runtime_seconds']},ensure_ascii=False),flush=True)
    table(ROOT/'case_results.csv',case_rows); table(ROOT/'resource_profiles.csv',profiles); table(ROOT/'failures.csv',failures or [{'case_id':'NONE','phase':'NONE','returncode':0,'error':'No unexpected worker failures'}])
    allframes=[row for fixed in read(ROOT/'DESIGN_FREEZE.json')['fixed_cases'] if (ROOT/'results'/fixed['case_id']/'generation_status.json').exists() for row in read(ROOT/'results'/fixed['case_id']/'generation_status.json')['frame_rows']]
    table(ROOT/'all_frame_results.csv',allframes)
    emit(ROOT/'RUN_COMPLETE.json',{'utc':utc(),'attempted_cases':36,'case_summary_rows':len(case_rows),'unexpected_worker_failures':failures,
         'complete_frame_family_cases':sum(r['generation_status']=='COMPLETE_FINITE_FRAME_FAMILIES' for r in case_rows),
         'complete_scalar_report_cases':sum(r['output_coverage_complete_scalar_report'] for r in case_rows),
         'cap_withheld_cases':sum(not r['output_coverage_complete_scalar_report'] for r in case_rows),
         'biological_N':0,'research_labor_hours':None,'source_reuse_not_novel_algorithm':True,
         'scalar_endpoint_witnesses_only':True,'no_arbitrary_vector_or_integer_interior_claim':True,
         'sparse_original_domain_and_constructed_dense_domain_are_different':True,'public_location':None,'license':None})
    paths=sorted(p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    emit(ROOT/'OUTPUT_FREEZE.json',{'frozen_utc':utc(),'input_source_freeze_sha256':sha(ROOT/'INPUT_SOURCE_FREEZE.json'),
         'files':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p),'bytes':p.stat().st_size} for p in paths]})

def main():
    p=argparse.ArgumentParser(); p.add_argument('command',choices=('prepare','run','worker')); p.add_argument('--phase'); p.add_argument('--case'); a=p.parse_args()
    if a.command=='prepare': prepare()
    elif a.command=='run': run()
    else: worker(a.phase,a.case)
if __name__=='__main__': main()
