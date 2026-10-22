from pathlib import Path
from collections import Counter
import argparse,csv,json,time,sys,hashlib,traceback,platform
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import audit_engine as E
ap=argparse.ArgumentParser(description='Construct complete families and graph queries from a declared normalized corpus.')
ap.add_argument('--corpus',type=Path,required=True,help='Folder containing GRAPH_INDEX.jsonl, graphs and references')
ap.add_argument('--output',type=Path,required=True,help='New absent directory for frame families and graph/query reports')
ap.add_argument('--limit',type=int,help='Optional bounded verification run; not a complete census')
args=ap.parse_args()
if args.limit is not None and args.limit<1:ap.error('--limit must be positive')
CORPUS=args.corpus.resolve();O=args.output.resolve()
if O==CORPUS or CORPUS in O.parents:raise ValueError('Output must be outside the input corpus')
O.mkdir(parents=True,exist_ok=False)
C=O/'frame_cache';S=O/'graph_reports';V=O/'visibility';Q=O/'query_reports'
for p in [C,S,V,Q]:p.mkdir(exist_ok=True)
rows=[json.loads(x)for x in(CORPUS/'GRAPH_INDEX.jsonl').read_text(encoding='utf8').splitlines()]
path=O/'GRAPH_AUDIT_SUMMARIES.jsonl';done={}
if path.exists():done={x['graph_id']:x for x in map(json.loads,path.read_text(encoding='utf8').splitlines())}
context={'engine_sha256':E.ENGINE_SHA,'constructor_sha256':E.BACKEND_SHA,'python':sys.version,'numpy':np.__version__,'platform':platform.platform(),'gate_um':E.GATE,'frame_cap':E.FRAME_CAP,'query_cap':E.QUERY_CAP,'ordinary_enumeration_cap':E.BASELINE_CAP,'scope':'retrospective saved untyped graph corpus; no new inference or biology','corpus_root':str(CORPUS),'graph_index_sha256':hashlib.sha256((CORPUS/'GRAPH_INDEX.jsonl').read_bytes()).hexdigest()}
cp=O/'AUDIT_EXECUTION_CONTEXT.json'
if cp.exists():
    old=json.loads(cp.read_text(encoding='utf8'))
    if old['engine_sha256']!=context['engine_sha256']or old['constructor_sha256']!=context['constructor_sha256']:raise ValueError('Audit implementation changed; preserve prior run and explicitly reconcile it')
else:cp.write_text(json.dumps(context,ensure_ascii=False,indent=2),encoding='utf8')
refs={};start=time.perf_counter();new=0
with path.open('a',encoding='utf8')as log,(O/'QUERY_EXCEPTIONS.jsonl').open('a',encoding='utf8')as unusual:
 for i,row in enumerate(rows):
    gid=row['graph_id'];film=row['film']
    if gid in done:continue
    t=time.perf_counter()
    try:
        if film not in refs:refs[film]=E.load_graph(CORPUS/'references'/(film+'.npz'))
        pred=E.load_graph(CORPUS/row['path']);summary,visibility,queries,exceptions=E.audit_graph(pred,refs[film],film,C)
        summary.update(graph_id=gid,film=film,normalized_graph_path=row['path'],engine_sha256=E.ENGINE_SHA)
        E.save_json_gz(S/(gid+'.json.gz'),summary);E.save_json_gz(Q/(gid+'.json.gz'),queries)
        np.savez_compressed(V/(gid+'.npz'),**visibility)
        for x in exceptions:unusual.write(json.dumps({'graph_id':gid,'film':film,**x},ensure_ascii=False)+'\n')
        unusual.flush()
        result={k:v for k,v in summary.items()if k not in ['canonical_map','frame_locators','frame_failures']}
        result.update(status='COMPLETE'if not summary['frame_failures']else'PARTIAL_WITHHELD',frame_failures=len(summary['frame_failures']),seconds=time.perf_counter()-t)
    except Exception as e:
        result={'graph_id':gid,'film':film,'status':'AUDIT_EXECUTION_FAILURE','error':type(e).__name__+': '+str(e),'traceback':traceback.format_exc(),'seconds':time.perf_counter()-t}
    log.write(json.dumps(result,ensure_ascii=False)+'\n');log.flush();done[gid]=result;new+=1
    if new<=3 or new%10==0:print('AUDIT',len(done),'/',len(rows),'new',new,'seconds',round(time.perf_counter()-start,1),'status',result['status'],'film',film,'ambiguous',result.get('ambiguous_relations'),'strict_path',result.get('path',{}).get('strict_relaxation_differences'),flush=True)
    if args.limit and new>=args.limit:break
valid=[x for x in done.values()if x['status']!='AUDIT_EXECUTION_FAILURE']
summary={'expected_unique_graphs':len(rows),'audited_graphs':len(done),'statuses':dict(Counter(x['status']for x in done.values())),
 'unique_films_audited':len({x['film']for x in done.values()}),'graph_reference_relation_queries':sum(x['reference_edges']for x in valid),
 'ambiguous_relation_reports':sum(x['ambiguous_relations']for x in valid),'nonunique_frame_reports_with_repeats':sum(x['nonunique_frames']for x in valid),
 'path_queries':sum(x['path']['queries']for x in valid),'path_ambiguous_reports':sum(x['path']['ambiguous_recovery']for x in valid),'path_strict_relaxation_reports':sum(x['path']['strict_relaxation_differences']for x in valid),
 'fork_queries':sum(x['fork']['queries']for x in valid),'fork_strict_relaxation_reports':sum(x['fork']['strict_relaxation_differences']for x in valid),
 'no_new_biological_N':True,'repeated_graph_queries_not_independent_discoveries':True,'process_seconds_this_invocation':time.perf_counter()-start}
(O/'GRAPH_AUDIT_PROGRESS.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(summary,ensure_ascii=False),flush=True)
