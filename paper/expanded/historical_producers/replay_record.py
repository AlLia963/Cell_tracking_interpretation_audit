"""Portable targeted replay from packaged normalized inputs, not original paths."""
from pathlib import Path
import argparse,json
import numpy as np
import audit_engine as E
R=Path(__file__).resolve().parents[1];O=R/'04_统一重分析'
def replay_query(gid,kind,index,fresh=True):
    roster={x['graph_id']:x for x in map(json.loads,(O/'GRAPH_INDEX.jsonl').read_text(encoding='utf8').splitlines())};film=roster[gid]['film'];g=E.load_graph(O/roster[gid]['path']);r=E.load_graph(O/'references'/(film+'.npz'))
    saved=E.read_json_gz(O/'query_reports'/(gid+'.json.gz'))[kind][index];s=E.read_json_gz(O/'graph_reports'/(gid+'.json.gz'));times=dict(zip(map(int,r.ids),map(int,r.coords[:,0])));frames={}
    for t in saved['frames']:
        f=E.frame_result(E.framed(r,t),E.framed(g,t),t)if fresh else E.read_json_gz(O/'frame_cache'/s['frame_locators'][str(t)])
        old=E.read_json_gz(O/'frame_cache'/s['frame_locators'][str(t)])
        signature=lambda w:tuple(sorted(w.items()))
        assert {signature(w)for w in f['worlds']}=={signature(w)for w in old['worlds']}
        frames[t]=f
    out,inc=E.adjacency(g.edges);got=E.query(kind,saved['reference_nodes'],times,frames,out,inc)
    for k in ['status','r_values','s_values','independent_edge_values','strict_relaxation_difference']:assert got[k]==saved[k],k
    return {'status':'PASS','film':film,'graph':gid,'kind':kind,'query_index':index,'fresh_complete_family_construction':fresh,'result':got}
def replay_pair(record):
    p=Path(record)
    if not p.is_absolute():p=O/'paired'/p
    result=E.read_json_gz(p);film=result['film'];gids=[result['before_graph'],result['after_graph']];ref=E.load_graph(O/'references'/(film+'.npz'));graphs=[E.load_graph(O/'graphs'/(g+'.npz'))for g in gids];summaries=[E.read_json_gz(O/'graph_reports'/(g+'.json.gz'))for g in gids]
    if result['status'].startswith('WITHHELD'):
        vv=[]
        for g in gids:
            with np.load(O/'visibility'/(g+'.npz'),allow_pickle=False)as z:vv.append({k:z[k].copy()for k in z.files})
        fresh=E.coupled_contrast(*graphs,ref,*summaries,*vv,O/'frame_cache')
        assert fresh['status']==result['status']and fresh['bounds']is None and fresh['required']==result['required']
        return {'status':'PASS','actual_refusal':fresh}
    sets=[set(map(tuple,g.edges.tolist()))for g in graphs];checked=[]
    for name,w in result['whole_map_endpoint_witnesses'].items():
        maps=[{int(q):p for q,p in s['canonical_map'].items()}for s in summaries]
        for side,t,i in w['frame_map_choices']:
            f=E.read_json_gz(O/'frame_cache'/summaries[side]['frame_locators'][str(t)])
            for q in f['reference_ids']:maps[side].pop(q,None)
            maps[side].update(f['worlds'][i])
        b=np.array([(maps[0].get(int(a)),maps[0].get(int(c)))in sets[0]for a,c in ref.edges]);a=np.array([(maps[1].get(int(q)),maps[1].get(int(c)))in sets[1]for q,c in ref.edges])
        values={'before_TP':int(b.sum()),'after_TP':int(a.sum()),'gains':int((~b&a).sum()),'losses':int((b&~a).sum()),'net':int(a.sum())-int(b.sum())}
        assert values==w['values'];metric,side=name.rsplit('_',1);assert values[metric]==result['bounds'][metric][side];checked.append(name)
    return {'status':'PASS','film':film,'full_primitive_endpoint_replays':checked,'scalar_extrema_separate':True,'bounds':result['bounds']}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--graph');p.add_argument('--kind',choices=['path','fork'],default='path');p.add_argument('--query-index',type=int,default=0);p.add_argument('--pair-witness');p.add_argument('--output',required=True);a=p.parse_args()
    result=replay_pair(a.pair_witness)if a.pair_witness else replay_query(a.graph,a.kind,a.query_index)
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result,ensure_ascii=False))
