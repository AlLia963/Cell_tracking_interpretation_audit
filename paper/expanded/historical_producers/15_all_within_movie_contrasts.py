"""All unordered distinct saved-graph comparisons, stratified by reference movie.

Direction is lexical graph identity, never inferred chronology. This coverage
matrix is not a causal intervention experiment or an independent-sample count.
"""
from pathlib import Path
from collections import defaultdict,Counter
from itertools import combinations,product
from functools import lru_cache
from types import SimpleNamespace
import csv,json,time,hashlib,sys,argparse
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import audit_engine as E
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--corpus',type=Path,required=True,help='Normalized primitive corpus containing GRAPH_INDEX.jsonl, graphs and references')
ap.add_argument('--audit-root',type=Path,help='Completed graph-audit output; defaults to the retained corpus')
ap.add_argument('--output',type=Path,required=True,help='New absent directory for pair records and witnesses')
ap.add_argument('--limit',type=int,help='Optional bounded verification run; not a complete pair census')
args=ap.parse_args()
if args.limit is not None and args.limit<1:ap.error('--limit must be positive')
CORPUS=args.corpus.resolve();O=args.audit_root.resolve() if args.audit_root else CORPUS;D=args.output.resolve()
if any(D==p or p in D.parents for p in [CORPUS,O]):raise ValueError('Output must be outside primitive and audit inputs')
D.mkdir(parents=True,exist_ok=False);cache=O/'frame_cache'
roster=[json.loads(x)for x in(CORPUS/'GRAPH_INDEX.jsonl').read_text(encoding='utf8').splitlines()]
completed=[json.loads(x)for x in(O/'GRAPH_AUDIT_SUMMARIES.jsonl').read_text(encoding='utf8').splitlines()]
if len(completed)!=len(roster):raise RuntimeError('Complete graph census must finish first')
byid={x['graph_id']:x for x in roster};byfilm=defaultdict(list)
for x in roster:byfilm[x['film']].append(x['graph_id'])
summaries={};visibility={};refs={}
for i,x in enumerate(roster):
    gid=x['graph_id'];summaries[gid]=E.read_json_gz(O/'graph_reports'/(gid+'.json.gz'))
    with np.load(O/'visibility'/(gid+'.npz'),allow_pickle=False)as z:visibility[gid]={k:z[k].copy()for k in z.files}
    if x['film']not in refs:refs[x['film']]=E.load_graph(CORPUS/'references'/(x['film']+'.npz'))
raw_read=E.read_json_gz
E.read_json_gz=lru_cache(maxsize=4096)(raw_read)
@lru_cache(maxsize=1024)
def projection(gid):
    """Keep only actual pairs that can affect uncertain reference relations.

    Invariant relations contribute certified constants. No graph neighbourhood,
    FP, type or tracking-performance statement uses this reduced representation.
    """
    v=visibility[gid];s=summaries[gid];ref=refs[byid[gid]['film']];uncertain=np.flatnonzero((v['minimum']==0)&(v['maximum']==1))
    if not len(uncertain):return SimpleNamespace(edges=np.empty((0,2),np.int64))
    full=E.load_graph(CORPUS/byid[gid]['path']);pairs=set(map(tuple,full.edges.tolist()));times=dict(zip(map(int,ref.ids),map(int,ref.coords[:,0])));keep=set()
    for i in uncertain:
        a,b=map(int,ref.edges[i]);fa=E.read_json_gz(cache/s['frame_locators'][str(times[a])]);fb=E.read_json_gz(cache/s['frame_locators'][str(times[b])])
        aa={w.get(a)for w in fa['worlds']};bb={w.get(b)for w in fb['worlds']}
        possible={(u,v)for u,v in product(aa,bb)if(u,v)in pairs};keep|=possible
        if not possible or len(possible)==len(aa)*len(bb):raise AssertionError('Projected ambiguous relation domain disagrees with full census')
    return SimpleNamespace(edges=np.array(sorted(keep),np.int64).reshape(-1,2))
metrics=['before_TP','after_TP','gains','losses','net'];header=['film','before_graph','after_graph','canonical_before_TP','canonical_after_TP','canonical_gains','canonical_losses','canonical_net','same_TP_with_identity_turnover','same_canonical_visibility','status']+[m+'_'+s for m in metrics for s in ['minimum','maximum']]+['independent_gain_min','independent_gain_max','independent_loss_min','independent_loss_max','strict_coupling_narrowing','witness_record']
processed=set();counts=Counter();total=0;strict_examples=[];verified=[]
target=D/'ALL_WITHIN_MOVIE_PAIRS.csv'
if target.exists():
    for r in csv.DictReader(target.open(encoding='utf-8-sig')):
        processed.add((r['film'],r['before_graph'],r['after_graph']));counts[r['status']]+=1
    total=len(processed)
start=time.perf_counter()
with target.open('a',encoding='utf-8-sig'if not target.exists()else'utf8',newline='')as f:
    writer=csv.DictWriter(f,fieldnames=header)
    if not processed:writer.writeheader()
    for film,gids in sorted(byfilm.items()):
        if args.limit is not None and total>=args.limit:break
        for a,b in combinations(sorted(gids),2):
            if args.limit is not None and total>=args.limit:break
            if(film,a,b)in processed:continue
            va,vb=visibility[a],visibility[b];ca,cb=va['canonical'],vb['canonical'];gain=int(((ca==0)&(cb==1)).sum());loss=int(((ca==1)&(cb==0)).sum())
            row={'film':film,'before_graph':a,'after_graph':b,'canonical_before_TP':int(ca.sum()),'canonical_after_TP':int(cb.sum()),'canonical_gains':gain,'canonical_losses':loss,'canonical_net':gain-loss,
                 'same_TP_with_identity_turnover':gain==loss and gain>0,'same_canonical_visibility':gain==loss==0,'strict_coupling_narrowing':False,'witness_record':''}
            if np.any(va['minimum']<0)or np.any(vb['minimum']<0):result={'status':'WITHHELD_FRAME','bounds':None}
            else:
                row.update(independent_gain_min=int(((va['maximum']==0)&(vb['minimum']==1)).sum()),independent_gain_max=int(((va['minimum']==0)&(vb['maximum']==1)).sum()),
                           independent_loss_min=int(((va['minimum']==1)&(vb['maximum']==0)).sum()),independent_loss_max=int(((va['maximum']==1)&(vb['minimum']==0)).sum()))
                if np.array_equal(va['minimum'],va['maximum'])and np.array_equal(vb['minimum'],vb['maximum']):
                    values={'before_TP':int(ca.sum()),'after_TP':int(cb.sum()),'gains':gain,'losses':loss,'net':gain-loss}
                    result={'status':'COMPLETE_INVARIANT_EDGE_READOUTS','bounds':{k:{'minimum':v,'maximum':v}for k,v in values.items()}}
                    row['witness_record']='Canonical maps in both graph reports; every relation readout is invariant'
                else:
                    result=E.coupled_contrast(projection(a),projection(b),refs[film],summaries[a],summaries[b],va,vb,cache)
                    pid=hashlib.sha256((film+a+b).encode()).hexdigest();name='witnesses/'+pid[:2]+'/'+pid+'.json.gz'
                    E.save_json_gz(D/name,{'film':film,'before_graph':a,'after_graph':b,**result});row['witness_record']=name
                    if len(verified)<10 and result['status']=='COMPLETE':
                        full=E.coupled_contrast(E.load_graph(CORPUS/byid[a]['path']),E.load_graph(CORPUS/byid[b]['path']),refs[film],summaries[a],summaries[b],va,vb,cache)
                        if full['bounds']!=result['bounds']:raise AssertionError('Reduced relation-pair representation changed exact bounds')
                        verified.append({'film':film,'before':a,'after':b,'all_five_bounds_equal_to_full_graph':True})
                if result.get('bounds'):
                    for m in metrics:
                        for side in ['minimum','maximum']:row[m+'_'+side]=result['bounds'][m][side]
                    row['strict_coupling_narrowing']=any(row[m+'_'+s]!=row['independent_'+{'gains':'gain','losses':'loss'}[m]+'_'+('min'if s=='minimum'else'max')]for m in ['gains','losses']for s in ['minimum','maximum'])
                    if row['strict_coupling_narrowing']and len(strict_examples)<50:strict_examples.append(dict(row))
            row['status']=result['status'];writer.writerow(row);total+=1;counts[result['status']]+=1
            if total%1000==0:f.flush();print('PAIRS',total,'seconds',round(time.perf_counter()-start,1),flush=True)
        f.flush()
summary={'pair_records':total,'expected_pairs':sum(len(g)*(len(g)-1)//2 for g in byfilm.values()),'status_counts':dict(counts),'projection_checks':verified,
         'corpus_root':str(CORPUS),'audit_root':str(O),'bounded_run':args.limit is not None,'direction':'Lexical normalized graph identity; not chronological change','pair_count_not_independent_experiments':True,'strict_examples':strict_examples,'elapsed_seconds_this_process':time.perf_counter()-start}
with (D/'SUMMARY.json').open('w',encoding='utf8')as f:json.dump(summary,f,ensure_ascii=False,indent=2)
print(json.dumps({k:v for k,v in summary.items()if k not in ['strict_examples','projection_checks']},ensure_ascii=False),flush=True)
