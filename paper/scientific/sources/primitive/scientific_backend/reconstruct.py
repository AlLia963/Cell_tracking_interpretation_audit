"""All raw NPZ -> exact flow certificates -> whole maps -> joint histories.

Only local explicit paths. Optimality is checked on exact binary-rational sums
of np.hypot.reduce calculated doubles, not real Euclidean distances. The old
canonical matcher is reused, and independently checked by residual-flow duals.
"""
import argparse, collections, csv, datetime, hashlib, heapq, itertools, json, math, os, platform, sys, time, traceback
from fractions import Fraction
from pathlib import Path
import numpy as np
import scipy
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'sources/executed'))
from stage_accounting import load_npz, match, account_from_matches

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def emit(p,x):
    with Path(p).open('x',encoding='utf-8',newline='\n') as f: json.dump(x,f,ensure_ascii=False,indent=2); f.write('\n')
def small_emit(p,x):
    with Path(p).open('x',encoding='utf-8',newline='\n') as f: json.dump(x,f,ensure_ascii=False,separators=(',',':')); f.write('\n')
def feature(h):
    v=list(map(int,h)); losses=[k for k in range(1,7) if v[k-1]==1 and v[k]==0]; gains=[k for k in range(1,7) if v[k-1]==0 and v[k]==1]; missing=v[-1]==0
    out={'final_missing':int(missing),'persistent_absence':int(not any(v)),'final_missing_with_loss':int(missing and bool(losses)),
      'changed_reference_identities':int(bool(losses or gains)),'first_last_loss_disagreements_final_missing':int(missing and bool(losses) and losses[0]!=losses[-1]),'final_last_loss_persistent':int(missing and not losses)}
    out.update({f'stage_visible_{k}':x for k,x in enumerate(v)})
    for k in range(1,7): out.update({f'gain_{k}':int(k in gains),f'loss_{k}':int(k in losses),f'final_last_loss_{k}':int(missing and bool(losses) and losses[-1]==k)})
    return out
def total_features(histories):
    out={k:0 for k in feature('0000000')}
    for h in histories:
        for k,v in feature(h).items(): out[k]+=v
    return out
def categories(strings):
    out=set()
    for h in strings:
        losses=[k for k in range(1,7) if h[k-1:k+1]=='10']
        out.add('final_present' if h[-1]=='1' else f'loss_stage_{losses[-1]}' if losses else 'persistent_absence')
    return sorted(out)

def residual(nr,npred,allowed,ci,base):
    S=nr+npred; T=S+1; arcs=[]; matchedp=set(base.values())
    for r in range(nr): arcs.append((r,S,0) if r in base else (S,r,0))
    for c in range(npred): arcs.append((T,nr+c,0) if c in matchedp else (nr+c,T,0))
    for r,c in zip(*np.nonzero(allowed)):
        r=int(r);c=int(c); cost=ci[r,c]
        arcs.append((nr+c,r,-cost) if base.get(r)==c else (r,nr+c,cost))
    return S,T,arcs
def potential(n,arcs):
    # Super-source with zero arcs to every vertex; exact Bellman-Ford difference
    # constraints. Feasible potentials certify no negative residual cycle.
    p=[0]*n
    for i in range(n):
        changed=False
        for u,v,c in arcs:
            if p[v]>p[u]+c: p[v]=p[u]+c; changed=True
        if not changed: return p,i+1
    raise ValueError('Canonical map has a negative exact-cost residual cycle; exact optimum withheld')
def reachable(n,arcs,S):
    adj=[[] for _ in range(n)]
    for u,v,c in arcs: adj[u].append(v)
    seen={S}; todo=[S]
    while todo:
        u=todo.pop()
        for v in adj[u]:
            if v not in seen: seen.add(v);todo.append(v)
    return seen
def dijkstra(n,adj,start):
    d=[None]*n; d[start]=0; prev=[None]*n; heap=[(0,start)]
    while heap:
        val,u=heapq.heappop(heap)
        if d[u]!=val: continue
        for v,c in adj[u]:
            nv=val+c
            if d[v] is None or nv<d[v]: d[v]=nv;prev[v]=u;heapq.heappush(heap,(nv,v))
    return d,prev

def frame_family(ref,state,canonical,gate,frame,cap):
    if not __debug__:
        raise RuntimeError('CONSTRUCTOR_ASSERTIONS_DISABLED: run without -O and PYTHONOPTIMIZE')
    ri=np.flatnonzero(ref.coords[:,0]==frame); pi=np.flatnonzero(state.coords[:,0]==frame)
    ri=ri[np.argsort(ref.ids[ri])];pi=pi[np.argsort(state.ids[pi])]
    rids=list(map(int,ref.ids[ri]));pids=list(map(int,state.ids[pi]));nr=len(ri);npred=len(pi)
    delta=ref.coords[ri,None,1:]-state.coords[None,pi,1:]
    dist=np.hypot.reduce(delta,axis=2);allowed=dist<=gate
    rix={x:i for i,x in enumerate(rids)};pix={x:i for i,x in enumerate(pids)}
    base={rix[q]:pix[p] for q,p in canonical.items() if q in rix}
    ratios={(int(r),int(c)):float(dist[r,c]).as_integer_ratio() for r,c in zip(*np.nonzero(allowed))}
    denominator=max([d for a,d in ratios.values()],default=1)
    ci={key:a*(denominator//d) for key,(a,d) in ratios.items()}
    S,T,arcs=residual(nr,npred,allowed,ci,base); n=T+1
    reach=reachable(n,arcs,S)
    if T in reach: raise ValueError('Canonical cardinality is not maximum')
    cover=[['reference',rids[r]] for r in range(nr) if r not in reach]+[['prediction',pids[c]] for c in range(npred) if nr+c in reach]
    assert len(cover)==len(base)
    pot,rounds=potential(n,arcs);adj=[[] for _ in range(n)]
    for u,v,c in arcs:
        rc=c+pot[u]-pot[v];assert rc>=0;adj[u].append((v,rc))
    source_d,_=dijkstra(n,adj,S); cache={}
    exact_base=sum(ci[r,c] for r,c in base.items());fsbase=math.fsum(float(dist[r,c]) for r,c in base.items())
    # A global conservative screen: every numerically admitted map has exact
    # gap <= 66 eps * max(1,K*gate), allowing fsum roundoff on both sides.
    screen=Fraction.from_float(66*np.finfo(float).eps*max(1,len(base)*gate))
    screen_int=math.ceil(screen*denominator)
    supports={r:[] for r in range(nr)};forced=[]
    for r in range(nr):
        for c in map(int,np.flatnonzero(allowed[r])):
            if base.get(r)==c: gap=0
            else:
                if c not in cache: cache[c]=dijkstra(n,adj,nr+c)
                back=cache[c][0][r]
                gap=None if back is None else ci[r,c]+pot[r]-pot[nr+c]+back
            keep=gap is not None and gap<=screen_int
            forced.append([rids[r],pids[c],None if gap is None else str(Fraction(gap,denominator)),bool(keep)])
            if keep: supports[r].append(c)
        if r not in base: gap=0
        else: gap=None if source_d[r] is None else pot[r]-pot[S]+source_d[r]
        keep=gap is not None and gap<=screen_int
        forced.append([rids[r],None,None if gap is None else str(Fraction(gap,denominator)),bool(keep)])
        if keep: supports[r].append(None)
        assert supports[r]
    variable=[r for r in range(nr) if len(supports[r])>1]
    combinations=math.prod(len(supports[r]) for r in variable)
    certificate={'frame':int(frame),'reference_ids':rids,'prediction_ids':pids,'canonical_pairs':[[rids[r],pids[c]] for r,c in sorted(base.items())],
      'max_cardinality':len(base),'minimum_vertex_cover':cover,'exact_cost_denominator':str(denominator),'canonical_exact_integer_sum':str(exact_base),
      'canonical_native_fsum_um':fsbase,'residual_potentials_order':'reference_ids,prediction_ids,source,sink','residual_potentials':[str(v) for v in pot],
      'potential_relaxation_rounds':rounds,'allowed_costs_columns':['reference_id','prediction_id','float_hex','scaled_exact_integer_cost'],
      'allowed_costs':[[rids[r],pids[c],float(dist[r,c]).hex(),str(ci[r,c])] for r,c in sorted(ci)],
      'forced_option_columns':['reference_id','prediction_id_or_null','minimum_exact_same_cardinality_gap_or_null_unreachable','conservative_screen_admitted'],
      'forced_options':forced,'support_screen_exact_um':str(screen),'support_options':[[rids[r],[None if c is None else pids[c] for c in supports[r]]] for r in range(nr)],
      'screened_combinations':combinations,'certificate_kind':'exact_integer_residual_dual_and_equal_cardinality_vertex_cover'}
    if combinations>cap: return certificate,None,None,{'status':'WITHHELD_WHOLE_FRAME_CAP','required':combinations,'cap':cap,'scalar_bounds':None}
    finite=[];numeric=[];checks=[]
    for choices in itertools.product(*(supports[r] for r in variable)):
        mapping=dict(base)
        for r,c in zip(variable,choices):
            mapping.pop(r,None)
            if c is not None: mapping[r]=c
        injective=len(set(mapping.values()))==len(mapping);cardinal=len(mapping)==len(base)
        if not injective or not cardinal:
            checks.append({'choices':[None if c is None else pids[c] for c in choices],'one_to_one':injective,'maximum_cardinality':cardinal,'finite_admitted':False,'numerical_admitted':False});continue
        exact=sum(ci[r,c] for r,c in mapping.items()); gap=exact-exact_base
        assert gap>=0
        fsum=math.fsum(float(dist[r,c]) for r,c in mapping.items());fgap=fsum-fsbase;tol=64*np.finfo(float).eps*max(1,abs(fsum),abs(fsbase))
        nf=bool(abs(fgap)<=tol);ef=gap==0
        replacement={str(rids[r]):None if mapping.get(r) is None else pids[mapping[r]] for r in variable}
        if ef: finite.append(replacement)
        if nf: numeric.append(replacement)
        checks.append({'choices':[None if c is None else pids[c] for c in choices],'one_to_one':True,'maximum_cardinality':True,'native_fsum_um':fsum,'native_fsum_gap_um':fgap,
          'exact_calculated_double_sum_gap':str(Fraction(gap,denominator)),'numeric_threshold_um':float(tol),'finite_admitted':ef,'numerical_admitted':nf})
    assert finite and numeric
    def block(assignments,rule):
        return {'frame':int(frame),'references':[rids[r] for r in variable],'assignments':assignments,'rule':rule} if variable else None
    certificate['whole_map_checks']=checks
    certificate['finite_support_options']=[[rids[r],sorted({a.get(str(rids[r]),canonical.get(rids[r])) for a in finite},key=repr)] for r in variable]
    certificate['numerical_support_options']=[[rids[r],sorted({a.get(str(rids[r]),canonical.get(rids[r])) for a in numeric},key=repr)] for r in variable]
    return certificate,block(finite,'exact_calculated_double_minimum'),block(numeric,'64epsilon_numerical_tolerance'),None

def links_from_geometry(data,blocks):
    variables={};links=[];rejected=[]
    for b in blocks:
        for q in b['references']: variables[b['film'],b['stage'],q]=sorted({a[str(q)] for a in b['assignments']},key=repr)
    for film,q in sorted({(f,q) for f,k,q in variables}):
        ref,states,maps=data[film];refc={int(i):tuple(map(float,c)) for i,c in zip(ref.ids,ref.coords)}
        coords=[{int(i):tuple(map(float,c)) for i,c in zip(s.ids,s.coords)} for s in states]
        for k in range(6):
            left=variables.get((film,k,q),[maps[k].get(q)]);right=variables.get((film,k+1,q),[maps[k+1].get(q)])
            same_domain=left==right;geometry=same_domain and all(p is None or coords[k][p]==coords[k+1][p] for p in left)
            row={'film':film,'reference_id':q,'from_stage':k,'to_stage':k+1,'reference_coordinate':list(refc[q]),'left_domain':left,'right_domain':right,
              'left_candidate_coordinates':{str(p):list(coords[k][p]) for p in left if p is not None},'right_candidate_coordinates':{str(p):list(coords[k+1][p]) for p in right if p is not None}}
            if geometry and (film,k,q) in variables and (film,k+1,q) in variables: links.append(row)
            elif not geometry: row['reason']='candidate_domain_changed' if not same_domain else 'candidate_geometry_changed';rejected.append(row)
    return {'links':links,'rejected':rejected,'negative_control':'PASS_ACTUAL_INCOMPATIBLE_BOUNDARY_REJECTED' if rejected else 'NOT_AVAILABLE','reference_geometry_shared_fixed_input':True}

def joint_readout(data,records,blocks,links,cap):
    # The union includes frame-level correlated maps, shared variable reference
    # endpoints, reference-edge incidence and every geometry equality link.
    remaining=set(range(len(blocks)));groups=[]
    while remaining:
        inds={min(remaining)};remaining-=inds;film=blocks[min(inds)]['film'];changed=True
        while changed:
            changed=False;nodes={q for i in inds for q in blocks[i]['references']}
            touching={q for r in records if r['film']==film and nodes.intersection(r['reference_edge']) for q in r['reference_edge']}
            for i in sorted(remaining):
                if blocks[i]['film']==film and touching.intersection(blocks[i]['references']):inds.add(i);remaining.remove(i);changed=True
        groups.append(sorted(inds))
    components=[];fullsets={};affected=set();witnesses=[]
    for ci,inds in enumerate(groups):
        film=blocks[inds[0]]['film'];ref,states,maps=data[film];nodes={q for i in inds for q in blocks[i]['references']}
        local=[r for r in records if r['film']==film and nodes.intersection(r['reference_edge'])];keys=[(film,*r['reference_edge']) for r in local]
        count=math.prod(len(blocks[i]['assignments']) for i in inds)
        if count>cap: return {'status':'WITHHELD_COMPONENT_ENUMERATION_CAP','required':count,'component':ci,'cap':cap,'scalar_bounds':None},None,None
        pairs=[set(map(tuple,s.edges.tolist())) for s in states]; configs=[];choices_saved=[];mins=None;maxs=None;minimum_witness={};maximum_witness={};sets=[set() for _ in local]
        applicable=[row for row in links if row['film']==film and row['reference_id'] in nodes]
        for values in itertools.product(*(blocks[i]['assignments'] for i in inds)):
            choice={(blocks[i]['stage'],int(q)):p for i,assignment in zip(inds,values) for q,p in assignment.items()}
            if any(choice.get((l['from_stage'],l['reference_id']),maps[l['from_stage']].get(l['reference_id']))!=choice.get((l['to_stage'],l['reference_id']),maps[l['to_stage']].get(l['reference_id'])) for l in applicable):continue
            hs=[]
            for r,seen in zip(local,sets):
                a,b=r['reference_edge'];h=''.join(str(int((choice.get((k,a),maps[k].get(a)),choice.get((k,b),maps[k].get(b))) in pairs[k])) for k in range(7));hs.append(h);seen.add(h)
            stats=total_features(hs);idx=len(configs);configs.append(hs);choices_saved.append([[k,q,p] for (k,q),p in sorted(choice.items())])
            if mins is None: mins=dict(stats);maxs=dict(stats);minimum_witness={k:idx for k in stats};maximum_witness=dict(minimum_witness)
            else:
                for k,v in stats.items():
                    if v<mins[k]:mins[k]=v;minimum_witness[k]=idx
                    if v>maxs[k]:maxs[k]=v;maximum_witness[k]=idx
        if not configs: raise ValueError('Geometry constraint has no feasible whole configuration')
        for key,seen in zip(keys,sets):fullsets[key]=sorted(seen);affected.add(key)
        components.append({'reference_edge_ids':[list(x) for x in keys],'configurations':configs})
        witnesses.append({'component':ci,'film':film,'block_indices':inds,'references':sorted(nodes),'raw_product_configurations_before_links':count,'feasible_configurations':len(configs),'mapping_choices':choices_saved,
          'minimum':mins,'maximum':maxs,'minimum_witness_config_index':minimum_witness,'maximum_witness_config_index':maximum_witness})
    fixed=[{'reference_edge_id':[r['film'],*r['reference_edge']],'history':r['history']} for r in records if (r['film'],*r['reference_edge']) not in affected]
    doc={'reference_edge_ids':[[r['film'],*r['reference_edge']] for r in records],'stage_count':7,'fixed_histories':fixed,'components':components,
      'completeness_asserted_by_caller':True,'product_factorization_asserted_by_caller':True,'joint_family_rule':'Raw gated frame maps certified by integer residual dual and max-cardinality cover; exhaustive whole-map admission; components union frame dependence and reference incidence; explicit optional unchanged-geometry equality links.'}
    fixedstats=total_features(x['history'] for x in fixed);canonical=total_features(r['history'] for r in records)
    bounds={k:{'canonical':canonical[k],'minimum':fixedstats[k]+sum(w['minimum'][k] for w in witnesses),'maximum':fixedstats[k]+sum(w['maximum'][k] for w in witnesses)} for k in canonical}
    hist=[{'film':r['film'],'reference_edge':r['reference_edge'],'canonical_history':r['history'],'admissible_visibility_strings':fullsets.get((r['film'],*r['reference_edge']),[r['history']]),
      'categories':categories(fullsets.get((r['film'],*r['reference_edge']),[r['history']]))} for r in records]
    status={'status':'RAW_TO_CERTIFIED_WHOLE_MAP_TO_JOINT_READOUT_COMPLETE','reference_edges':len(records),'scalar_fields':len(bounds),'component_configurations':[w['feasible_configurations'] for w in witnesses],
      'component_raw_product_counts':[w['raw_product_configurations_before_links'] for w in witnesses],'ambiguous_history_edges':sum(len(r['admissible_visibility_strings'])>1 for r in hist),
      'whole_graph_joint_assignments_represented':math.prod(w['feasible_configurations'] for w in witnesses),'fixed_edges':len(fixed),'all31_scalar_bounds':bounds,
      'factorization_certificate':'All map variables in each frame are in a single block; components union shared reference nodes and incident reference edges. Disjoint components have disjoint frame blocks and constraints and partition affected edge identities. Thus their full map choices form an exact Cartesian product.',
      'new_biological_N':0,'clean_machine':False,'simultaneous_extrema_vector_certified':False}
    return status,doc,{'histories':hist,'witnesses':witnesses,'bounds':bounds}

def run(a):
    out=a.output.resolve();inputs=a.input_root.resolve();beg=time.perf_counter()
    if out.exists() and not a.resume: raise FileExistsError(out)
    out.mkdir(parents=True,exist_ok=a.resume)
    emit(out/'RUN_START.json',{'UTC':now(),'argv':sys.argv,'PID':os.getpid(),'python':sys.executable,'python_version':sys.version,'numpy':np.__version__,'scipy':scipy.__version__,'platform':platform.platform(),'same_host_new_path':True}) if not (out/'RUN_START.json').exists() else None
    for gate in a.gates:
        gd=out/f'gate_{gate:02d}';gd.mkdir(exist_ok=a.resume);data={};records=[];finiteblocks=[];numericblocks=[];caps=[]
        films=sorted(p for p in inputs.iterdir() if p.is_dir() and (p/'reference.npz').exists());assert len(films)==8
        for film in films:
            fp=gd/(film.name+'.json');ref=load_npz(film/'reference.npz');states=[load_npz(film/f'stage_{k}.npz') for k in range(7)]
            assert ref.unit=='um' and all(s.unit=='um' for s in states)
            maps=[match(s,ref,float(gate)) for s in states];data[film.name]=(ref,states,maps)
            if fp.exists():
                payload=json.loads(fp.read_text(encoding='utf-8'));assert payload['input_sha256']=={p.name:sha(p) for p in [film/'reference.npz']+[film/f'stage_{k}.npz' for k in range(7)]}
            else:
                frames=[];fb=[];nb=[]
                for k,s in enumerate(states):
                    for t in np.unique(ref.coords[:,0]):
                        cert,f,n,c=frame_family(ref,s,maps[k],float(gate),t,a.frame_cap);cert.update({'film':film.name,'stage':k,'gate_um':gate});frames.append(cert)
                        if f:f.update({'film':film.name,'stage':k});fb.append(f)
                        if n:n.update({'film':film.name,'stage':k});nb.append(n)
                        if c:caps.append({'film':film.name,'stage':k,'frame':int(t),**c})
                payload={'film':film.name,'gate_um':gate,'input_sha256':{p.name:sha(p) for p in [film/'reference.npz']+[film/f'stage_{k}.npz' for k in range(7)]},'frame_certificates':frames,
                  'canonical_maps':[[[q,p] for q,p in sorted(m.items())] for m in maps],'finite_blocks':fb,'numerical_blocks':nb,'withheld':caps}
                small_emit(fp,payload)
            finiteblocks.extend(payload['finite_blocks']);numericblocks.extend(payload['numerical_blocks']);caps.extend(payload.get('withheld',[]))
            rows=account_from_matches(states,ref,maps)
            records.extend({'film':film.name,'reference_edge':r['reference_edge'],'history':''.join(map(str,r['visibility'])),'matched_pairs':r['matched_pairs']} for r in rows)
            print(json.dumps({'UTC':now(),'checkpoint':str(fp),'gate':gate,'film':film.name,'certified_frames':len(payload['frame_certificates']),'finite_blocks':len(payload['finite_blocks']),'numerical_blocks':len(payload['numerical_blocks'])}),flush=True)
        assert len(records)==5751
        if caps: emit(gd/'WITHHELD.json',{'withheld':caps,'scalar_bounds':None});continue
        emit(gd/'CANONICAL_HISTORIES.json',records) if not (gd/'CANONICAL_HISTORIES.json').exists() else None
        for name,blocks in [('finite',finiteblocks),('numerical',numericblocks)]:
            cd=gd/name
            if (cd/'RESULT.json').exists():continue
            cd.mkdir(exist_ok=True);small_emit(cd/'WHOLE_FRAME_FAMILIES.json',blocks)
            ls=links_from_geometry(data,blocks);emit(cd/'GEOMETRY_LINKS_AND_REJECTIONS.json',ls)
            variants=[('unconstrained',[])]+([('geometry_constrained',ls['links'])] if gate==7 and name=='finite' else [])
            for variant,links in variants:
                vd=cd/variant;vd.mkdir(exist_ok=True);res,doc,derived=joint_readout(data,records,blocks,links,a.component_cap)
                emit(vd/'RESULT.json',res)
                if doc:
                    small_emit(vd/'JOINT_INPUT.LOCAL_ONLY.json',doc);small_emit(vd/'ALL5751_HISTORY_SETS.json',derived['histories']);emit(vd/'ALL31_SCALAR_BOUNDS.json',derived['bounds']);small_emit(vd/'COMPLETE_MAPPING_CONFIGURATION_WITNESSES.json',derived['witnesses'])
            emit(cd/'RESULT.json',{'status':'COMPLETE_FAMILY_BRANCH','gate':gate,'contract':name,'whole_frame_blocks':len(blocks),'whole_frame_assignments':sum(len(b['assignments']) for b in blocks)})
    pins={str(p.relative_to(HERE)).replace('\\','/'):sha(p) for p in sorted(HERE.rglob('*.py')) if 'runtime/venv' not in str(p).replace('\\','/')}
    inputs_manifest={str(p.relative_to(inputs)).replace('\\','/'):sha(p) for p in sorted(inputs.glob('*/*.npz'))}
    emit(out/'EXECUTED_SOURCE_AND_RAW_BINDINGS.json',{'source_hashes':pins,'raw_hashes':inputs_manifest,'source_manifest_sha256':sha(HERE/'SCIENTIFIC_INPUT_AND_SOURCE_MANIFEST.json')})
    # No prior accepted family/cost outputs are opened by this program.
    freeze={str(p.relative_to(out)).replace('\\','/'):sha(p) for p in sorted(out.rglob('*')) if p.is_file()}
    emit(out/'PRECOMPARISON_OUTPUT_FREEZE.json',{'UTC':now(),'prior_family_or_cost_answers_opened_by_program':False,'outputs':freeze,'elapsed_seconds':time.perf_counter()-beg})
    print(json.dumps({'status':'COMPUTATION_FROZEN','files':len(freeze),'seconds':time.perf_counter()-beg}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--gates',type=int,nargs='+',default=[7,6,8]);p.add_argument('--frame-cap',type=int,default=1048576);p.add_argument('--component-cap',type=int,default=1048576);p.add_argument('--resume',action='store_true');a=p.parse_args()
    if any(g not in (6,7,8) for g in a.gates):p.error('Supported gates: 6,7,8')
    try: run(a)
    except BaseException:
        if a.output.exists():
            fail=a.output/(f'FAILURE_{os.getpid()}_{int(time.time())}.json');emit(fail,{'UTC':now(),'argv':sys.argv,'PID':os.getpid(),'error':traceback.format_exc(),'status':'ACTUAL_FAILURE_RETAINED'})
        raise
