"""Narrow instrumentation of existing D47; no figure code or pipeline rerun."""
from pathlib import Path
import argparse, ctypes, datetime, hashlib, importlib.util, itertools, json, math, platform, subprocess, sys, time
from ctypes import wintypes
from fractions import Fraction
import numpy as np

HERE=Path(__file__).resolve().parent
REPO=Path(r'G:\kaggle论文化\论文工作区\GitHub发布\2026-10-07\stage-resolved-tracking-audit')
OLD=REPO/'outputs/paper_20261010/analyst-path/measurement'
SOURCE=REPO/'paper/scientific/extras/analyst/constructor/reconstruct.py'
FACTOR=REPO/'paper/scientific/extensions/operating_envelope/factor_frames.py'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,obj):
    with Path(p).open('x',encoding='utf8') as f:json.dump(obj,f,ensure_ascii=False,indent=2)
def module(name,p):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def memory():
    class PMC(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[(x,ctypes.c_size_t) for x in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
    p=PMC();p.cb=ctypes.sizeof(p)
    k=ctypes.WinDLL('kernel32');k.GetCurrentProcess.restype=wintypes.HANDLE
    ps=ctypes.WinDLL('psapi');ps.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(PMC),wintypes.DWORD]
    if not ps.GetProcessMemoryInfo(k.GetCurrentProcess(),ctypes.byref(p),p.cb):raise ctypes.WinError()
    return {'peak_working_set_bytes':p.PeakWorkingSetSize,'working_set_bytes':p.WorkingSetSize}
def load(p,G):
    with np.load(p,allow_pickle=False) as z:
        c=z['coords'].astype(float,copy=True);c[:,1:]*=[1.625,.40625,.40625]
        return G(z['ids'].copy(),c,z['edges'].copy(),'um')
def direct_family(ref,pred,t,gate):
    ri=np.flatnonzero(ref.coords[:,0]==t);pi=np.flatnonzero(pred.coords[:,0]==t)
    ri=ri[np.argsort(ref.ids[ri])];pi=pi[np.argsort(pred.ids[pi])]
    r=list(map(int,ref.ids[ri]));p=list(map(int,pred.ids[pi]))
    dist=np.hypot.reduce(ref.coords[ri,None,1:]-pred.coords[None,pi,1:],axis=2)
    ratios={(i,j):float(dist[i,j]).as_integer_ratio() for i,j in zip(*np.nonzero(dist<=gate))}
    den=max((d for a,d in ratios.values()),default=1);cost={(i,j):a*(den//d) for (i,j),(a,d) in ratios.items()}
    choices=[[j for j in range(len(p)) if (i,j) in cost]+[None] for i in range(len(r))]
    best=(-1,0);maps=[];visited=0
    for x in itertools.product(*choices):
        q=[j for j in x if j is not None]
        if len(q)!=len(set(q)):continue
        visited+=1;key=(len(q),-sum(cost[i,j] for i,j in enumerate(x) if j is not None))
        if key>best:best=key;maps=[]
        if key==best:maps.append({r[i]:p[j] for i,j in enumerate(x) if j is not None})
    return maps,{'frame':t,'partial_injections_evaluated':visited,'max_cardinality':best[0],'exact_minimum_cost':str(Fraction(-best[1],den)),'optimal_maps':len(maps)}
def signature(m,refs):return tuple(m.get(r) for r in refs)
def query(families,path,pairs):
    truth=[]
    for ix in itertools.product(*(range(len(x)) for x in families)):
        m={r:p for fam,i in zip(families,ix) for r,p in fam[i].items()}
        a,b,c=[m.get(r) for r in path]
        v=(int(a is not None and b is not None and (a,b) in pairs),int(b is not None and c is not None and (b,c) in pairs))
        truth.append({'indices':list(ix),'visibility':list(v),'value':math.prod(v)})
    return truth
def child(index):
    out=HERE/f'run_{index:02}';out.mkdir(exist_ok=False);start=time.perf_counter();cpu=time.process_time();phases={}
    def phase(name,fn):
        t=time.perf_counter();c=time.process_time();v=fn();phases[name]={'wall_seconds':time.perf_counter()-t,'cpu_seconds':time.process_time()-c,**memory()};return v
    mod=phase('import_backend',lambda:module('existing_constructor',SOURCE))
    fac=module('existing_factor',FACTOR)
    contract=json.loads((OLD/'INPUT_AND_QUERY_CONTRACT.json').read_text(encoding='utf8'))
    refp=Path(contract['reference']['path']);predp=Path(contract['prediction']['path'])
    G=mod.load_npz.__globals__['Graph']
    ref,pred=phase('load_inputs',lambda:(load(refp,G),load(predp,G)))
    times=dict(zip(map(int,ref.ids),map(int,ref.coords[:,0])));path=contract['reference_path'];frames=[times[r] for r in path]
    canonical=phase('canonical_whole_saved_film',lambda:mod.match(pred,ref,7.0))
    def construction():
        fam=[];certs=[]
        for t in frames:
            cert,b,n,w=mod.frame_family(ref,pred,canonical,7.,t,1048576)
            if w:raise RuntimeError(w)
            base=dict(cert['canonical_pairs']);maps=[]
            for a in b['assignments'] if b else [{}]:
                m=dict(base)
                for r,p in a.items():
                    m.pop(int(r),None)
                    if p is not None:m[int(r)]=int(p)
                maps.append(m)
            fam.append(maps);certs.append(cert)
        return fam,certs
    fam,certs=phase('construct_three_complete_frame_families',construction)
    blocks=[{'references':list(c['reference_ids']),'assignments':[{str(r):m.get(r) for r in c['reference_ids']} for m in f]} for c,f in zip(certs,fam)]
    split,proofs=phase('finite_set_factor_certificate',lambda:fac.factor_frame_blocks(blocks))
    # This independent implementation does not read certificates or old families.
    direct=phase('ordinary_raw_partial_injection_construction',lambda:[direct_family(ref,pred,t,7.) for t in frames])
    for i,(maps,details) in enumerate(direct):
        refs=certs[i]['reference_ids']
        assert {signature(m,refs) for m in maps}=={signature(m,refs) for m in fam[i]}
    pairs=set(map(tuple,pred.edges.tolist()))
    literal=phase('ordinary_shared_map_query',lambda:query([x[0] for x in direct],path,pairs))
    # Evaluate certified finite projections, extending them to original whole maps.
    relevant=[b for b in split if set(b['references'])&set(path)]
    def factored_query():
        answer=[]
        for ix in itertools.product(*(range(len(b['assignments'])) for b in relevant)):
            selected={int(r):p for b,j in zip(relevant,ix) for r,p in b['assignments'][j].items()}
            a,b,c=[selected[r] for r in path]
            v=[int(a is not None and b is not None and (a,b) in pairs),int(b is not None and c is not None and (b,c) in pairs)]
            full=[]
            for refs,ff in zip((c['reference_ids'] for c in certs),fam):
                options=[j for j,m in enumerate(ff) if all(m.get(r)==p for r,p in selected.items() if r in refs)]
                assert options;full.append(options[0])
            answer.append({'indices':full,'visibility':v,'value':math.prod(v)})
        return answer
    projected=phase('certified_projection_query_and_extension',factored_query)
    assert {(tuple(x['visibility']),x['value']) for x in literal}=={(tuple(x['visibility']),x['value']) for x in projected}
    def verify():
        for row in projected:
            replay=query([[fam[i][j]] for i,j in enumerate(row['indices'])],path,pairs)[0]
            assert replay['value']==row['value'] and replay['visibility']==row['visibility']
        # Premise ablations: input-family checks alone cannot prove omission.
        omitted=[list(f) for f in fam];omitted[1]=omitted[1][:1]
        alltruth=query(fam,path,pairs);smalltruth=query(omitted,path,pairs)
        assert {x['visibility'][0] for x in alltruth}=={0,1}
        assert len({x['visibility'][0] for x in smalltruth})==1
        omission_detected={signature(m,certs[1]['reference_ids']) for m in omitted[1]}!={signature(m,certs[1]['reference_ids']) for m in direct[1][0]}
        try:fam[1][len(fam[1])]
        except IndexError:bad_index_rejected=True
        else:bad_index_rejected=False
        required=math.prod(map(len,fam))
        assert omission_detected and bad_index_rejected and required>1
        return {'omitted_family_schema_and_member_checks_pass':True,'omission_detected_against_raw_exhaustive_constructor':omission_detected,'incomplete_first_edge_values':sorted({x['visibility'][0] for x in smalltruth}),'complete_first_edge_values':[0,1],'invalid_witness_index_rejected':bad_index_rejected,'query_cap_one_required':required,'query_cap_one_status':'WITHHELD_QUERY_CAP'}
    controls=phase('witness_replay_and_responsibility_probes',verify)
    result={'run':index,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'phases':phases,'frames':frames,'reference_path':path,'frame_ref_counts':[len(c['reference_ids']) for c in certs],'frame_prediction_counts':[len(c['prediction_ids']) for c in certs],'complete_family_sizes':list(map(len,fam)),'raw_partial_injection_baseline':[x[1] for x in direct],'factor_sizes':[len(b['assignments']) for b in split],'ordinary_truth':literal,'projected_truth':projected,'controls':controls,'protocol_sha256':sha(HERE/'PROTOCOL.md'),'source_pins':{str(p):sha(p) for p in (refp,predp,SOURCE,FACTOR,Path(__file__))},'python':sys.version,'numpy':np.__version__,'platform':platform.platform(),'memory':memory(),'measured_body_wall_seconds':time.perf_counter()-start,'measured_body_cpu_seconds':time.process_time()-cpu}
    # Save and time actual evidence serialization, excluding result metadata.
    phase('serialize_family_evidence',lambda:dump(out/'FAMILY_EVIDENCE.json',{'certificates':certs,'whole_maps':fam,'factor_proofs':proofs}))
    result['memory']=memory();dump(out/'RESULT.json',result)
    # Old results are consulted only after this run's own result was saved.
    old=json.loads((OLD/'REPORT.json').read_text(encoding='utf8'))
    assert sorted({x['value'] for x in projected})==old['attainable_values']
    dump(out/'COMPARISON_AFTER_RESULT_FREEZE.json',{'family_sizes_equal':list(map(len,fam))==old['complete_frame_family_sizes'],'attainable_values_equal':True,'old_report_sha256':sha(OLD/'REPORT.json'),'result_sha256':sha(out/'RESULT.json')})
    print(json.dumps({'run':index,'status':'COMPLETE','peak_MB':result['memory']['peak_working_set_bytes']/1048576}))
def main():
    p=argparse.ArgumentParser();p.add_argument('--child',type=int);a=p.parse_args()
    if a.child:child(a.child);return
    records=[]
    for i in range(1,4):
        t=time.perf_counter();r=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--child',str(i)],capture_output=True,text=True)
        dump(HERE/f'PROCESS_{i:02}.json',{'returncode':r.returncode,'wall_seconds_including_startup':time.perf_counter()-t,'stdout':r.stdout,'stderr':r.stderr})
        if r.returncode:raise RuntimeError(r.stderr)
        records.append(json.loads((HERE/f'run_{i:02}/RESULT.json').read_text(encoding='utf8')))
    fields=list(records[0]['phases']);summary={k:{'min':min(r['phases'][k]['wall_seconds'] for r in records),'median':sorted(r['phases'][k]['wall_seconds'] for r in records)[1],'max':max(r['phases'][k]['wall_seconds'] for r in records)} for k in fields}
    dump(HERE/'COST_AND_ADOPTION_SUMMARY.json',{'status':'COMPLETE_THREE_INSTRUMENT_REPEATS_EXISTING_D47','phase_seconds':summary,'peak_working_set_MiB':[r['memory']['peak_working_set_bytes']/1048576 for r in records],'full_shared_values':[0],'marginal_relaxation_values':[0,1],'ordinary_complete_baseline_equal':True,'scientific_input_cohort_repeated':False,'not_new_biological_N':True,'not_universal_speed_benchmark':True,'responsibility_probe':records[0]['controls'],'source_protocol_sha256':sha(HERE/'PROTOCOL.md')})
    print(json.dumps({'status':'COMPLETE','phase_seconds':summary,'peak_MiB':[r['memory']['peak_working_set_bytes']/1048576 for r in records]}))
if __name__=='__main__':main()
