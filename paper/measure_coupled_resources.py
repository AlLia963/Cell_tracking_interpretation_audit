"""Only new resource instrumentation; consumes already frozen D43 inputs."""
from pathlib import Path
import argparse, ctypes, datetime, hashlib, importlib.util, json, platform, statistics, subprocess, sys, time
from ctypes import wintypes
C=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--inputs',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--case');p.add_argument('--convention');p.add_argument('--route');p.add_argument('--repeat',type=int)
a=p.parse_args();OUTPUT=a.output.resolve()
SRC=C/'paper/scientific/extensions/operating_envelope'
INPUT=a.inputs.resolve()
sys.path.insert(0,str(SRC))
import run_operating_envelope as implementation
old=implementation.old
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf8') as f:json.dump(x,f,ensure_ascii=False,indent=2)
def memory():
    class PMC(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[(x,ctypes.c_size_t) for x in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
    p=PMC();p.cb=ctypes.sizeof(p);k=ctypes.WinDLL('kernel32');k.GetCurrentProcess.restype=wintypes.HANDLE
    ps=ctypes.WinDLL('psapi');ps.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(PMC),wintypes.DWORD]
    if not ps.GetProcessMemoryInfo(k.GetCurrentProcess(),ctypes.byref(p),p.cb):raise ctypes.WinError()
    return {'cumulative_peak_working_set_bytes':p.PeakWorkingSetSize,'current_working_set_bytes':p.WorkingSetSize}
def child(case,convention,route,repeat):
    out=OUTPUT/f'{case}/{convention}/{route}/{repeat}'
    out.mkdir(parents=True,exist_ok=False);phases={}
    def phase(name,fn):
        t=time.perf_counter();cpu=time.process_time();v=fn()
        phases[name]={'seconds':time.perf_counter()-t,'cpu_seconds':time.process_time()-cpu,**memory()};return v
    manifest=json.loads((INPUT/'INPUT_COHORT_FROZEN_BEFORE_QUERY.json').read_text(encoding='utf8'))
    entry=next(x for x in manifest['cases'] if x['name']==case)
    raw=[INPUT/f['path'] for f in entry['files']]
    for p,pin in zip(raw,entry['files']):assert sha(p)==pin['sha256']
    gs=phase('load',lambda:[old.load_npz(p) for p in raw]);ref,states=gs[0],gs[1:];stages=[f'V{i}' for i in range(len(states))]
    def construct():
        bases={};blocks=[];certs=[]
        for s,g in zip(stages,states):
            base=old.match(g,ref,2);bases[s]=base
            for frame in (0,1,2):
                cert,b,_,fail=old.frame_family(ref,g,base,2,frame,65536)
                if fail:raise RuntimeError(fail)
                certs.append(dict(cert,stage=s))
                if b is not None:blocks.append(dict(b,stage=s,id=len(blocks)))
        return bases,blocks,certs
    bases,blocks,certs=phase('matching_and_complete_frame_construction',construct)
    if route=='certified_projection':used,proofs=phase('exact_projection_factorization',lambda:implementation.factor_frame_blocks(blocks))
    else:used,proofs=blocks,[]
    adj=phase('graph_adjacency',lambda:{s:old.adjacency(g) for s,g in zip(stages,states)})
    queries,_=old.census(case,ref)
    links,_=phase('derive_unchanged_evidence_links',lambda:old.derive_links(blocks,bases,states,stages))
    linkset=links if convention=='unchanged_geometry_equality' else []
    cs,owner,cf=phase('dependency_components',lambda:old.components(used,linkset,bases,1024))
    results=phase('all_declared_path_queries',lambda:[old.project_query(q,stages,bases,used,cs,owner,adj,convention,1024,cf) for q in queries])
    def replay():
        count=0
        for row in results:
            if row['status']!='COMPLETE':continue
            for key,idx in [('pair_recovery',0),('structural_consistency',1)]:
                for history,witness in row[key]['history_witnesses'].items():
                    maps,wi=implementation.extend_history_witness(witness,used,cs,blocks,stages,bases)
                    observed=implementation.independent_history(row['nodes'],stages,maps,adj)
                    if observed[idx]!=history:raise AssertionError('Witness value differs')
                    count+=1
        return count
    replay_count=phase('whole_map_extension_and_graph_replay',replay)
    phase('serialize_actual_evidence',lambda:dump(out/'QUERY_EVIDENCE.json',{'results':results,'certificates':certs,'factor_proofs':proofs}))
    measured={'case':case,'convention':convention,'route':route,'repeat':repeat,'phases':phases,'complete':sum(x['status']=='COMPLETE' for x in results),'withheld':sum(x['status']!='COMPLETE' for x in results),'statuses':sorted(set(x['status'] for x in results)),'queries':len(queries),'witnesses_replayed':replay_count,'max_raw_family':max(len(b['assignments']) for b in blocks),'max_used_projection':max(len(b['assignments']) for b in used),'max_complete_query_combinations':max((x['relevant_combinations'] for x in results if x['status']=='COMPLETE'),default=None),'component_refusals':cf,'caps':{'frame':65536,'component':1024,'query':1024},'memory':memory(),'python':sys.version,'platform':platform.platform(),'source_pins':{str(p.relative_to(C)):sha(p) for p in (SRC/'run_operating_envelope.py',SRC/'factor_frames.py',Path(old.__file__))},'input_pins':[{'path':str(p),'sha256':sha(p)} for p in raw]}
    dump(out/'MEASURED_BEFORE_HISTORICAL_COMPARISON.json',measured)
    # Historical scientific answers only read after our result freeze.
    previous=json.loads((INPUT/case/(convention+'.json')).read_text(encoding='utf8'))['new' if route=='certified_projection' else 'old']
    if results!=previous:raise AssertionError('Scientific query results changed during instrumentation')
    dump(out/'HISTORICAL_COMPARISON.json',{'all_query_records_equal':True,'previous_sha256':sha(INPUT/case/(convention+'.json'))})
    print(json.dumps({'case':case,'route':route,'complete':measured['complete'],'withheld':measured['withheld']}))
def main():
    if a.case:child(a.case,a.convention,a.route,a.repeat);return
    rows=[];root=OUTPUT;root.mkdir(exist_ok=False)
    for case in ('n32_k2_v2','n64_k4_v3','n128_k8_v5'):
        for conv in ('per_view_product','unchanged_geometry_equality'):
            for route in ('whole_frame','certified_projection'):
                rec=[]
                for repeat in (1,2,3):
                    t=time.perf_counter();p=subprocess.run([sys.executable,'-X','utf8',str(Path(__file__).resolve()),'--inputs',str(INPUT),'--output',str(OUTPUT),'--case',case,'--convention',conv,'--route',route,'--repeat',str(repeat)],capture_output=True,text=True,encoding='utf8')
                    dump(root/f'{case}/{conv}/{route}/PROCESS_{repeat}.json',{'returncode':p.returncode,'whole_process_seconds':time.perf_counter()-t,'stdout':p.stdout,'stderr':p.stderr})
                    if p.returncode:raise RuntimeError(p.stderr)
                    rec.append(json.loads((root/f'{case}/{conv}/{route}/{repeat}/MEASURED_BEFORE_HISTORICAL_COMPARISON.json').read_text(encoding='utf8')))
                row={k:rec[0][k] for k in ('case','convention','route','complete','withheld','queries','statuses','max_raw_family','max_used_projection','max_complete_query_combinations','caps')}
                row['phase_median_ms']={k:statistics.median(r['phases'][k]['seconds'] for r in rec)*1000 for k in rec[0]['phases']}
                row['process_peak_MiB_range']=[min(r['memory']['cumulative_peak_working_set_bytes'] for r in rec)/1048576,max(r['memory']['cumulative_peak_working_set_bytes'] for r in rec)/1048576]
                rows.append(row);print(json.dumps(row),flush=True)
    dump(root/'SUMMARY.json',{'status':'COMPLETE_NEW_RESOURCE_INSTRUMENTATION_EXISTING_FROZEN_INPUTS','rows':rows,'protocol_sha256':sha(C/'paper/PROTOCOL_RESOURCES_v1.2.md'),'instrumentation_sha256':sha(Path(__file__)),'no_new_biological_N':True,'not_speed_advantage_over_strong_factored_baseline':True,'peak_is_process_high_water_not_phase_specific':True})
if __name__=='__main__':main()
