from pathlib import Path
from functools import lru_cache
from collections import Counter
import sys,json,time,hashlib,argparse
import numpy as np
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import audit_engine as E
from linked_contrast import linked_contrast
p=argparse.ArgumentParser(description='Recalculate linked focused comparisons from declared saved graphs and complete frame families.')
p.add_argument('--corpus',type=Path,required=True,help='Normalized graphs and references')
p.add_argument('--audit-root',type=Path,help='Complete graph reports, visibility arrays and frame_cache; defaults to corpus')
p.add_argument('--contrasts',type=Path,required=True,help='Focused cohort JSON declaring film/before_graph/after_graph identities')
p.add_argument('--motion',type=Path,help='Optional eight-movie motion source/result JSON; only its graph-pair definitions enter the calculation')
p.add_argument('--output',type=Path,required=True,help='New absent output directory outside inputs')
a=p.parse_args();CORPUS=a.corpus.resolve();O=a.audit_root.resolve() if a.audit_root else CORPUS;D=a.output.resolve()
if any(D==q or q in D.parents for q in [CORPUS,O]):raise ValueError('Output must be outside input roots')
D.mkdir(parents=True,exist_ok=False)
old=json.loads(a.contrasts.read_text(encoding='utf-8-sig'));load=lru_cache(maxsize=2500)(E.read_json_gz)
if a.motion:
    motion=json.loads(a.motion.read_text(encoding='utf-8-sig'));rows=motion['records']
    if len(rows)!=8 or len({r['film'] for r in rows})!=8:raise ValueError('Expected eight distinct intervention movies')
    old.append({'design':'motion_replacement_disabled','common_movies':8,'motion_intervention':True,'per_movie':[{'film':r['film'],**r['product'],'identical_saved_graph':False} for r in rows],'totals':{'joint_bounds_sum_over_distinct_movies':{m:{s:sum(int(r['product'][m+'_'+s]) for r in rows) for s in ['minimum','maximum']} for m in ['before_TP','after_TP','gains','losses','net']}}})
bindings={'contrasts':{'path':str(a.contrasts.resolve()),'sha256':hashlib.sha256(a.contrasts.read_bytes()).hexdigest()},'corpus_root':str(CORPUS),'audit_root':str(O),'scope':'New linked readouts from declared graphs and supplied complete-family records; use a fresh graph-audit root for new primitive construction. Prior linked fields are not calculation inputs.'}
if a.motion:bindings['motion']={'path':str(a.motion.resolve()),'sha256':hashlib.sha256(a.motion.read_bytes()).hexdigest()}
(D/'INPUT_BINDINGS.json').write_text(json.dumps(bindings,indent=2),encoding='utf-8')
results=[];start=time.perf_counter();total=0
for comparison in old:
    records=[]
    for r in comparison['per_movie']:
        film=r['film'];gids=[r['before_graph'],r['after_graph']];graphs=[E.load_graph(CORPUS/'graphs'/(g+'.npz'))for g in gids];ref=E.load_graph(CORPUS/'references'/(film+'.npz'));ss=[load(O/'graph_reports'/(g+'.json.gz'))for g in gids];vs=[]
        for g in gids:
            with np.load(O/'visibility'/(g+'.npz'),allow_pickle=False)as z:vs.append({k:z[k].copy()for k in z.files})
        fs=[{int(t):load(O/'frame_cache'/loc)for t,loc in s['frame_locators'].items()}for s in ss]
        result=linked_contrast(graphs,ref,ss,vs,fs)
        if result['status']=='COMPLETE':
            for m in ['before_TP','after_TP','gains','losses','net']:
                assert int(r[m+'_minimum'])<=result['bounds'][m]['minimum']<=result['bounds'][m]['maximum']<=int(r[m+'_maximum'])
            if r['identical_saved_graph']:assert all(result['bounds'][m]=={'minimum':0,'maximum':0}for m in ['gains','losses','net'])
        out=('motion_linked/'+film+'.json.gz') if comparison.get('motion_intervention') else ('linked_records/'+comparison['design']+'/'+film+'.json.gz');E.save_json_gz(D/out,{'film':film,'before_graph':gids[0],'after_graph':gids[1],'before_frame_locators':ss[0]['frame_locators'],'after_frame_locators':ss[1]['frame_locators'],**result})
        record={**r,'linked_status':result['status'],'linked_bounds':result.get('bounds'),'linked_frames':len(result.get('linked_frames',[])),'linkage_status_counts':dict(Counter(x['status']for x in result['linkage'])),'linked_witness_record':out};records.append(record);total+=1
        if total%20==0:print('COMPARED',total,'seconds',round(time.perf_counter()-start,2),flush=True)
    complete=all(x['linked_status']=='COMPLETE'for x in records);aggregate={m:{s:sum(x['linked_bounds'][m][s]for x in records)for s in ['minimum','maximum']}for m in ['before_TP','after_TP','gains','losses','net']}if complete else None
    results.append({k:v for k,v in comparison.items()if k!='per_movie'}|{'per_movie':records,'linked_aggregate_bounds':aggregate,'linked_status_counts':dict(Counter(x['linked_status']for x in records))})
    (D/'LINKED_FOCUSED_CONTRASTS.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
summary={'status':'COMPLETE_EXECUTION','movie_comparisons':total,'comparisons':len(results),'seconds':time.perf_counter()-start,'source_sha256':hashlib.sha256((Path(E.__file__).parent/'linked_contrast.py').read_bytes()).hexdigest(),'engine_sha256':E.ENGINE_SHA,'declared_component_cap':1048576,'independent_contract_not_overwritten':True,'results':[{'design':x['design'],'common_movies':x['common_movies'],'product_net':x['totals']['joint_bounds_sum_over_distinct_movies']['net'],'linked_bounds':x['linked_aggregate_bounds'],'status_counts':x['linked_status_counts']}for x in results]}
(D/'LINKAGE_EXECUTION_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(summary,ensure_ascii=False),flush=True)
