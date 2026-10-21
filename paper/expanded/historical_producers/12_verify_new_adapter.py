from pathlib import Path
import json,sys
import numpy as np
import audit_engine as E
R=Path('D:/1013工作大修');O=R/'05_补证与核验/新适配器验证';O.mkdir(exist_ok=True)
checks=[]
def graph(ids,xyz,edges):return E.Graph(np.array(ids,np.int64),np.array(xyz,float).reshape(-1,4),np.array(edges,np.int64).reshape(-1,2),'um')
def check(name,ok,detail):
    checks.append({'name':name,'pass':bool(ok),'detail':detail})
    if not ok:raise AssertionError(name)
ref=graph([1,2,3],[[0,0,0,0],[1,0,0,0],[2,0,0,0]],[(1,2),(2,3)])
pred=graph([10,20,21,30],[[0,0,0,0],[1,0,0,-1],[1,0,0,1],[2,0,0,0]],[(10,20),(21,30)])
s,v,q,x=E.audit_graph(pred,ref,'constructed_split',O/'split/cache')
check('shared_middle_blocks_joint_recovery',q['path'][0]['r_values']==[0]and q['path'][0]['independent_edge_values']==[0,1],q['path'][0])
check('raw_ordinary_full_families_equal',s['ordinary_equal_frames']==3,{'equal_frames':s['ordinary_equal_frames']})
old=E.FRAME_CAP;E.FRAME_CAP=1
cap=E.frame_result(E.framed(ref,1),E.framed(pred,1),1);E.FRAME_CAP=old
check('genuine_constructor_cap_refusal',cap['status']=='WITHHELD_CONSTRUCTION',{'status':cap['status'],'reason':cap.get('reason')})
ref2=graph([1,2,3,4],[[0,0,0,0],[0,0,0,0],[1,0,0,0],[1,0,0,20]],[(1,3),(2,4)])
pred2=graph([10,30,40],[[0,0,0,0],[1,0,0,0],[1,0,0,20]],[(10,30),(10,40)])
empty=graph(pred2.ids,pred2.coords,[])
sa,va,qa,xa=E.audit_graph(pred2,ref2,'constructed_competition',O/'aggregate/cache')
sb,vb,qb,xb=E.audit_graph(empty,ref2,'constructed_competition',O/'aggregate/cache')
coupled=E.coupled_contrast(empty,pred2,ref2,sb,sa,vb,va,O/'aggregate/cache')
check('shared_assignment_changes_scalar_envelope',int(va['minimum'].sum())==0 and int(va['maximum'].sum())==2 and coupled['bounds']['gains']=={'minimum':1,'maximum':1},coupled)
same=E.coupled_contrast(pred2,pred2,ref2,sa,sa,va,va,O/'aggregate/cache')
check('independent_reevaluation_can_exchange_identity_without_graph_change',same['bounds']['net']=={'minimum':0,'maximum':0}and same['bounds']['gains']=={'minimum':0,'maximum':1},same)
check('endpoint_vectors_not_combined',all(w['values']['gains']==w['values']['losses']for w in same['whole_map_endpoint_witnesses'].values()),'Separate extrema witnesses retain gain=loss here; arbitrary endpoint vectors are not asserted')
bad=graph([1,2],[[0,0,0,0],[0,0,0,2]],[]);pp=graph([10,20],[[0,0,0,0],[0,0,0,3]],[])
original=E.backend.match
try:
    E.backend.match=lambda *args:{1:20,2:10}
    fixed=E.frame_result(bad,pp,0)
finally:E.backend.match=original
check('exact_ordinary_seed_recovers_invalid_floating_proposal',fixed['status']=='COMPLETE'and fixed['seed_fallback']is not None and fixed['worlds']==[{1:10,2:20}],{'fallback':fixed['seed_fallback'],'worlds':fixed['worlds']})
for name,ids,co,ed in [('duplicate_ids',[1,1],[[0,0,0,0],[1,0,0,0]],[]),('nonfinite',[1],[[0,float('nan'),0,0]],[])]:
    failed=False
    try:graph(ids,co,ed)
    except ValueError:failed=True
    check('reject_'+name,failed,'Actual Graph input validation called')
# New adapter on the existing real D47 primitives, only its three requested frames.
oldroot=Path('G:/kaggle论文化/论文工作区/BSPC_统一收束/04_审阅软件包/controlled_companion_LOCAL_ONLY')
contract=json.loads((oldroot/'current_verification_stage4/task/INPUT_AND_QUERY_CONTRACT.json').read_text(encoding='utf8'))
def original_npz(p):
    with np.load(p,allow_pickle=False)as z:
        co=z['coords'].astype(float)
        if contract['unit_in']=='pixel':co[:,1:]*=[1.625,.40625,.40625]
        return E.Graph(z['ids'],co,z['edges'],'um')
rr=original_npz(oldroot/'03_最小D47/LOCAL_ONLY_INPUTS/reference.npz');gg=original_npz(oldroot/'03_最小D47/LOCAL_ONLY_INPUTS/prediction.npz')
nodes=[156000000073,157000000073,158000000073];times=dict(zip(map(int,rr.ids),map(int,rr.coords[:,0])))
ff={t:E.frame_result(E.framed(rr,t),E.framed(gg,t),t)for t in sorted({times[q]for q in nodes})}
oo,ii=E.adjacency(gg.edges);real=E.query('path',nodes,times,ff,oo,ii)
check('real_D47_new_adapter',real['r_values']==[0]and real['independent_edge_values']==[0,1]and[len(f['worlds'])for f in ff.values()]==[1,2,1],real)
report={'status':'PASS','checks':checks,'scope':'New adapter logic and integration; no original cohort, model inference or cost rerun','original_source_untouched':True}
(O/'RESULT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'status':'PASS','checks':len(checks),'real_family_sizes':[len(f['worlds'])for f in ff.values()]},ensure_ascii=False))
