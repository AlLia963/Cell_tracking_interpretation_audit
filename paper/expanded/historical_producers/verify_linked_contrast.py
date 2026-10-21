from pathlib import Path
from itertools import product
import json,sys,copy
import numpy as np
R=Path('D:/1013工作大修');sys.path.insert(0,str(R/'src'));import audit_engine as E
from linked_contrast import linked_contrast,signature
D=Path(__file__).resolve().parent;cache=D/'constructed_linkage/cache';checks=[]
def graph(ids,coords,edges):return E.Graph(np.array(ids,np.int64),np.array(coords,float),np.array(edges,np.int64).reshape(-1,2),'um')
ref=graph([1,2,3],[[0,0,0,0],[1,0,0,0],[2,0,0,0]],[(1,2),(2,3)])
g=graph([10,20,21,30],[[0,0,0,0],[1,0,0,-1],[1,0,0,1],[2,0,0,0]],[(10,20),(21,30)])
h=graph(g.ids,g.coords,[(10,20),(20,30)])
def inputs(a,b):
    rr=[E.audit_graph(x,ref,'linkage_constructed',cache)for x in[a,b]];ss=[x[0]for x in rr];vs=[x[1]for x in rr];fs=[{int(t):E.read_json_gz(cache/loc)for t,loc in s['frame_locators'].items()}for s in ss];return ss,vs,fs
def brute(gs,fs,linked):
    variables=[(side,t)for side in range(2)for t in sorted(fs[side])];values=[];pairs=[set(map(tuple,x.edges.tolist()))for x in gs]
    for inds in product(*(range(len(fs[s][t]['worlds']))for s,t in variables)):
        chosen={v:fs[v[0]][v[1]]['worlds'][i]for v,i in zip(variables,inds)}
        if any(signature(chosen[0,t])!=signature(chosen[1,t])for t in linked):continue
        maps=[{q:p for(s,t),w in chosen.items()if s==side for q,p in w.items()}for side in range(2)];before=[(maps[0].get(int(a)),maps[0].get(int(b)))in pairs[0]for a,b in ref.edges];after=[(maps[1].get(int(a)),maps[1].get(int(b)))in pairs[1]for a,b in ref.edges];values.append({'before_TP':sum(before),'after_TP':sum(after),'gains':sum(not a and b for a,b in zip(before,after)),'losses':sum(a and not b for a,b in zip(before,after)),'net':sum(after)-sum(before)})
    return {m:{'minimum':min(v[m]for v in values),'maximum':max(v[m]for v in values)}for m in values[0]}
for label,other in [('identical_graph',g),('same_geometry_different_edges',h)]:
    ss,vs,fs=inputs(g,other);a=linked_contrast([g,other],ref,ss,vs,fs);b=linked_contrast([g,other],ref,ss,vs,fs,enable_links=False);old=E.coupled_contrast(g,other,ref,*ss,*vs,cache)
    assert a['bounds']==brute([g,other],fs,a['linked_frames']);assert b['bounds']==old['bounds']==brute([g,other],fs,[])
    if label=='identical_graph':assert all(a['bounds'][m]=={'minimum':0,'maximum':0}for m in ['gains','losses','net'])and b['bounds']['gains']['maximum']>0
    checks.append({'name':label,'status':'PASS','linked':a['bounds'],'independent':b['bounds'],'plain_global_enumeration_equal':True})
    if label=='identical_graph':
        refuse=linked_contrast([g,other],ref,ss,vs,fs,cap=1);assert refuse['status']=='WITHHELD_COMPONENT_CAP'and refuse['bounds']is None;checks.append({'name':'real_cap_branch','status':'PASS','record':refuse})
        bad=copy.deepcopy(fs);bad[1][1]['worlds']=bad[1][1]['worlds'][:1];r=linked_contrast([g,other],ref,ss,vs,bad);assert r['status']=='WITHHELD_DOMAIN_INCONSISTENCY';checks.append({'name':'identical_geometry_but_incomplete_domain_rejected','status':'PASS'})
changed=g.coords.copy();changed[2,3]=2.;other=graph(g.ids,changed,g.edges);ss,vs,fs=inputs(g,other);r=linked_contrast([g,other],ref,ss,vs,fs);assert 1 not in r['linked_frames'];assert r['bounds']==brute([g,other],fs,r['linked_frames']);checks.append({'name':'changed_coordinates_not_linked','status':'PASS'})
other=graph(g.ids+100,g.coords,g.edges+100);ss,vs,fs=inputs(g,other);r=linked_contrast([g,other],ref,ss,vs,fs);assert not r['linked_frames'];checks.append({'name':'different_ID_namespace_not_linked','status':'PASS'})
(D/'LINKAGE_IMPLEMENTATION_CHECKS.json').write_text(json.dumps({'status':'PASS','checks':checks},ensure_ascii=False,indent=2),encoding='utf8');print('PASS',len(checks),'linkage checks')
