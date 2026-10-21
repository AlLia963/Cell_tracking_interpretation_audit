"""Time the already implemented stronger gated-component baseline on D47 only."""
from measure_adoption_cost import *
OUT=HERE/'component_cost_v02'
OUT.mkdir(exist_ok=False) if len(sys.argv)==1 else None
P=REPO/'paper/scientific/extensions/natural/literal_constrained_baseline_v03.py'
def run(i):
    out=OUT/f'component_run_{i:02}';out.mkdir(exist_ok=False)
    contract=json.loads((OLD/'INPUT_AND_QUERY_CONTRACT.json').read_text(encoding='utf8'))
    constructor=module('existing_for_G',SOURCE);G=constructor.load_npz.__globals__['Graph']
    ref=load(Path(contract['reference']['path']),G);pred=load(Path(contract['prediction']['path']),G)
    baseline=module('ordinary_component_baseline',P)
    t=time.perf_counter();c=time.process_time();families=[];details=[]
    for f in (50,51,52):
        canonical,b,cert=baseline.build_frame(ref,pred,f,7.,1048576)
        maps=[]
        for a in b['assignments'] if b else [{}]:
            m=dict(canonical)
            for r,p in a.items():
                m.pop(int(r),None)
                if p is not None:m[int(r)]=int(p)
            maps.append(m)
        families.append(maps);details.append(cert)
    construction=time.perf_counter()-t;cpu=time.process_time()-c
    t=time.perf_counter();pairs=set(map(tuple,pred.edges.tolist()));pair_index=time.perf_counter()-t
    t=time.perf_counter();truth=query(families,contract['reference_path'],pairs);q=time.perf_counter()-t
    record={'run':i,'construction_three_frames_seconds':construction,'construction_cpu_seconds':cpu,'query_seconds':q,'whole_film_pair_index_seconds':pair_index,'memory':memory(),'family_sizes':list(map(len,families)),'truth':truth,'protocol_sha256':sha(HERE/'PROTOCOL.md'),'source_sha256':sha(P)}
    dump(out/'RESULT_BEFORE_COMPARISON.json',record)
    expected=json.loads((HERE/'run_01/FAMILY_EVIDENCE.json').read_text(encoding='utf8'))
    for cert,actual,supplied in zip(expected['certificates'],families,expected['whole_maps']):
        refs=cert['reference_ids'];supplied=[{int(r):p for r,p in m.items()} for m in supplied]
        assert {signature(m,refs) for m in actual}=={signature(m,refs) for m in supplied}
    dump(out/'COMPARISON.json',{'all_three_whole_families_equal':True,'attainable_values':[0],'loaded_existing_stronger_baseline_not_new_algorithm':True})
def entry():
    if len(sys.argv)>1:run(int(sys.argv[1]));return
    records=[]
    for i in (1,2,3):
        r=subprocess.run([sys.executable,str(Path(__file__).resolve()),str(i)],capture_output=True,text=True)
        dump(OUT/f'COMPONENT_PROCESS_{i:02}.json',{'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
        if r.returncode:raise RuntimeError(r.stderr)
        records.append(json.loads((OUT/f'component_run_{i:02}/RESULT_BEFORE_COMPARISON.json').read_text(encoding='utf8')))
    summary={k:{'min':min(r[k] for r in records),'median':sorted(r[k] for r in records)[1],'max':max(r[k] for r in records)} for k in ('construction_three_frames_seconds','whole_film_pair_index_seconds','query_seconds')}
    dump(OUT/'STRONG_COMPONENT_BASELINE_COST.json',{'status':'COMPLETE','seconds':summary,'peak_working_set_MiB':[r['memory']['peak_working_set_bytes']/1048576 for r in records],'all_whole_families_equal':True,'not_speed_superiority_test':True})
    print(json.dumps(summary))
if __name__=='__main__':entry()
