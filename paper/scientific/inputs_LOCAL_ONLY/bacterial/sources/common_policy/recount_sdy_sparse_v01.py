"""Recount every saved SDY arm; never execute archival desktop-writing code."""
import sys
sys.dont_write_bytecode=True
import csv,json,hashlib,collections
from pathlib import Path
import numpy as np
import zarr
from scipy.optimize import linear_sum_assignment
R=Path(__file__).resolve().parent
P=Path('legacy_inputs/IWS（只读勿动）/0929最后一次提交窗口/SDY/05_experiments/E5_head_v2')
GT=Path('legacy_inputs/cell（只读勿动）/gt_data/full/train')
SCALE=np.array([1.625,.40625,.40625])
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def integer(value):
    n=int(value)
    if str(n)!=value.strip():raise ValueError('noncanonical integer: '+value)
    return n
def readgraph(path):
    data={}
    with path.open(encoding='utf-8-sig',newline='') as file:
        for row in csv.DictReader(file):
            ds=row['dataset'];g=data.setdefault(ds,{'nodes':{},'edges':[]})
            if row['row_type']=='node':
                ident=integer(row['node_id']);t=integer(row['t'])
                if ident in g['nodes']:raise ValueError('duplicate node')
                coords=[t,*[float(row[k]) for k in ['z','y','x']]]
                if not np.isfinite(coords).all():raise ValueError('nonfinite coordinates')
                g['nodes'][ident]=coords
            elif row['row_type']=='edge':g['edges'].append((integer(row['source_id']),integer(row['target_id'])))
            else:raise ValueError('unknown row type')
    return data
def score(g,truth):
    ids=np.array(sorted(g['nodes']),dtype=np.int64);coords=np.array([g['nodes'][int(i)] for i in ids])
    edges=g['edges'];times=dict(zip(ids,coords[:,0]));degree=collections.Counter(a for a,b in edges)
    if len(set(edges))!=len(edges):raise ValueError('duplicate edges require cleanup')
    if max(degree.values(),default=0)>2:raise ValueError('degree cap active')
    for a,b in edges:
        if a not in times or b not in times or times[b]-times[a]!=1:raise ValueError('missing or nonadjacent endpoints')
    gi,gc,ge=truth;mapping={}
    for t in np.unique(gc[:,0]):
        rr=np.flatnonzero(gc[:,0]==t);pp=np.flatnonzero(coords[:,0]==t)
        if not len(pp):continue
        distances=np.linalg.norm((gc[rr,None,1:]-coords[None,pp,1:])*SCALE,axis=2)
        allowed=distances<=7.;cost=np.where(allowed,distances,(min(len(rr),len(pp))+1)*8.)
        row,col=linear_sum_assignment(cost)
        mapping.update({int(ids[pp[b]]):int(gi[rr[a]]) for a,b in zip(row,col) if allowed[a,b]})
    outgoing={a for a,b in ge};incoming={b for a,b in ge};visible=set();fp=ignored=0
    for a,b in edges:
        ma,mb=mapping.get(a),mapping.get(b)
        if (ma,mb) in ge:visible.add((ma,mb))
        elif ma in outgoing or mb in incoming:fp+=1
        else:ignored+=1
    tp=len(visible);fn=len(ge)-tp
    return {'TP':tp,'FP':fp,'FN':fn,'ignored_predictions':ignored,'predicted_nodes':len(ids),'predicted_edges':len(edges),'edge_jaccard':tp/(tp+fp+fn)},visible
def main():
    out=R/'SDY_sparse_recount_v0.1';out.mkdir(exist_ok=False)
    tags=['zero','head','head_pool','head_traj','head_pool_traj']
    bindings={str(Path(__file__)):sha(Path(__file__)),str(R/'SDY_sparse_recount_protocol_v0.1.md'):sha(R/'SDY_sparse_recount_protocol_v0.1.md')}
    for tag in tags:bindings[str(P/(tag+'_pp')/'submission.csv')]=sha(P/(tag+'_pp')/'submission.csv')
    (out/'before_execution.json').write_text(json.dumps(bindings,indent=2))
    graphs={tag:readgraph(P/(tag+'_pp')/'submission.csv') for tag in tags}
    films=sorted(graphs['zero']);assert len(films)==4 and all(sorted(g)==films for g in graphs.values())
    saved=json.loads((P/'arms_result.json').read_text(encoding='utf-8'));saved['head_pool_traj']=json.loads((P/'head_pool_traj_result.json').read_text(encoding='utf-8'))
    rows=[];visible={};references=[]
    for film in films:
        path=GT/(film+'.geff');group=zarr.open_group(str(path),mode='r')
        gi=group['nodes/ids'][:];gc=np.column_stack([group[f'nodes/props/{k}/values'][:] for k in ['t','z','y','x']]);ge=set(map(tuple,group['edges/ids'][:].tolist()))
        references.append({'film':film,'reference_nodes':len(gi),'reference_edges':len(ge),'reference_arrays_sha256':hashlib.sha256(gi.tobytes()+gc.tobytes()+np.array(sorted(ge),dtype=np.int64).tobytes()).hexdigest()})
        for tag in tags:
            try:
                counts,vs=score(graphs[tag][film],(gi,gc,ge));visible[tag,film]=vs
                historical=next(r for r in saved[tag]['rows'] if r['dataset']==film)
                differences={k:counts[k]-historical['edge_'+k.lower()] for k in ['TP','FP','FN']}
                rows.append({'arm':tag,'film':film,'status':'recounted','counts':counts,'historical_count_differences':differences})
            except ValueError as error:rows.append({'arm':tag,'film':film,'status':'withheld-cleanup-contract','reason':str(error)})
        print(film,'done',flush=True)
    contrasts=[]
    for before,after in [('zero','head'),('head','head_pool'),('head','head_traj'),('head_pool','head_pool_traj')]:
        for film in films:
            bg,ag=graphs[before][film],graphs[after][film]
            preserve=bg['nodes'].keys()==ag['nodes'].keys() and set(bg['edges'])==set(ag['edges']) and all(bg['nodes'][i][0]==ag['nodes'][i][0] for i in bg['nodes'].keys()&ag['nodes'].keys())
            record={'before':before,'after':after,'film':film,'IDs_frames_edges_preserved':preserve,'eligible_pure_coordinate_saved_contrast':before=='head_pool' and after=='head_pool_traj' and preserve}
            if (before,film) in visible and (after,film) in visible:
                gains=visible[after,film]-visible[before,film];losses=visible[before,film]-visible[after,film]
                record.update(gains=len(gains),losses=len(losses),gain_reference_edges=sorted(gains),loss_reference_edges=sorted(losses))
            contrasts.append(record)
    report={'binding':bindings,'references':references,'rows':rows,'contrasts':contrasts,'scope':'Retrospective local sparse edge recount; not predictor/scorer-service replication, not division/composite metric, not independent biological validation.'}
    (out/'report.json').write_text(json.dumps(report,indent=2))
    print('rows',len(rows),'withheld',sum(r['status']!='recounted' for r in rows),'historical differences',sum(any(r.get('historical_count_differences',{}).values()) for r in rows),flush=True)
if __name__=='__main__':main()
