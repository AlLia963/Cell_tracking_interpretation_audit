import sys,json,hashlib,copy,traceback
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
sys.dont_write_bytecode=True
D=Path(__file__).resolve().parent;A=D.parent;B=A/'clean_runtime_COPY_v0.1'
ARMS=('unchanged','edge_delete','node_remove','support_zero','support_swap','delete_recover_delete','delete_recover','support_duplicate','prewindow_omission','absent_edge_noop','type_relabel')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v):
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2)
O=D/'fixtures_v0.2';O.mkdir(exist_ok=False);pins={};receipts=[]
try:
    resource=B/'external_natural/RESOURCE_MANIFEST.json';cfg=read(resource);pins[str(resource)]=sha(resource)
    selection=[];raw=[]
    for spec in cfg['films']:
        film=spec['film'];gp=resource.parent/spec['graph_relative'];sp=resource.parent/spec['sidecar_relative']
        assert sha(gp)==spec['graph_sha256'] and sha(sp)==spec['sidecar_sha256']
        graphs=read(gp);states=read(sp)['records'];pins[str(gp)]=sha(gp);pins[str(sp)]=sha(sp)
        assert len(graphs)==len(states)==spec['frames']
        eligible=[g for g in graphs if g['frame']>0 and any(e[2]=='division' for e in g['stages']['D']['edges'])]
        if not eligible:selection.append(dict(film=film,status='no_predicted_division'));continue
        g=eligible[0];f=g['frame'];pairs=sorted((int(x),int(y)) for x,y,k in g['stages']['D']['edges'] if k=='division')
        selection.append(dict(film=film,status='selected_prediction_only',current_frame=f,pairs=[list(p) for p in pairs]))
        raw.append((spec,graphs,states,f,pairs))
    write(O/'SELECTION_BEFORE_REFERENCE.json',dict(UTC=datetime.now(timezone.utc).isoformat(),selection=selection,input_pins=pins,protocol_sha256=sha(D/'PROTOCOL.md'),generator_sha256=sha(__file__),reference_opened=False,scope='Previously accepted baseline natural graphs;not pulse fourcell outputs'))
    for spec,graphs,states,f,pairs in raw:
        film=spec['film'];masks=[];ids=[];offset=(f-1)*100000
        for t in (f-1,f):
            p=Path(spec['support_paths_resolve_under'])/states[t]['state_path_relative_to_root']
            assert sha(p)==states[t]['state_sha256'];pins[str(p)]=sha(p)
            with np.load(p,allow_pickle=False) as a:m=a['return_masks'].astype(bool)
            ii=np.array(graphs[t]['stages']['D']['nodes'],dtype=np.int64)-offset
            assert len(ii)==len(m);masks.append(m);ids.append(ii)
        base={'ids':np.concatenate(ids),'masks':np.concatenate(masks),'edges':{(int(x)-offset,int(y)-offset) for x,y,k in graphs[f]['stages']['D']['edges']},'division':{(int(x)-offset,int(y)-offset) for x,y,k in graphs[f]['stages']['D']['edges'] if k=='division'}}
        assert len(set(map(int,base['ids'])))==len(base['ids']) and all(x in base['ids'] and y in base['ids'] for x,y in base['edges'])
        for pair_index,(x,y) in enumerate(pairs):
            target=(x-offset,y-offset);partners=sorted(int(i) for i in ids[1] if i!=target[1]);absent=next(((int(i),int(j)) for i in sorted(ids[0]) for j in sorted(ids[1]) if (int(i),int(j)) not in base['edges']),None)
            if not partners or absent is None:
                receipts.append(dict(film=film,current_frame=f,target=list(target),status='unavailable_partner_or_absent_pair'));continue
            partner=partners[0];target_row=int(np.flatnonzero(base['ids']==target[1])[0]);partner_row=int(np.flatnonzero(base['ids']==partner)[0]);cases=[]
            for arm in ARMS:
                views=[copy.deepcopy(base) for _ in range(4)]
                for k,v in enumerate(views):
                    remove=(arm in ('edge_delete','prewindow_omission') and (k>=1 or arm=='prewindow_omission')) or (arm=='delete_recover_delete' and k in (1,3)) or (arm=='delete_recover' and k==1)
                    if remove:v['edges'].discard(target);v['division'].discard(target)
                    if k>=1:
                        if arm=='node_remove':
                            keep=v['ids']!=target[1];v['ids']=v['ids'][keep];v['masks']=v['masks'][keep];v['edges']={e for e in v['edges'] if target[1] not in e};v['division']={e for e in v['division'] if target[1] not in e}
                        elif arm=='support_zero':v['masks'][target_row]=False
                        elif arm=='support_swap':v['masks'][[target_row,partner_row]]=v['masks'][[partner_row,target_row]]
                        elif arm=='support_duplicate':v['masks'][partner_row]=v['masks'][target_row]
                        elif arm=='absent_edge_noop':v['edges'].discard(absent);v['division'].discard(absent)
                        elif arm=='type_relabel':v['division'].discard(target)
                path=O/f'{film}_{pair_index:02d}_{arm}.npz';arrays={}
                for k,v in enumerate(views):
                    arrays[f'ids{k}']=v['ids'];arrays[f'masks{k}']=v['masks'];arrays[f'edges{k}']=np.array(sorted(v['edges']),dtype=np.int64).reshape(-1,2);arrays[f'division{k}']=np.array(sorted(v['division']),dtype=np.int64).reshape(-1,2)
                np.savez_compressed(path,**arrays);cases.append(dict(arm=arm,fixture=path.name,sha256=sha(path)))
            receipts.append(dict(film=film,current_frame=f,target=list(target),partner=partner,absent_pair=list(absent),status='fixtures_complete',cases=cases))
    write(O/'GENERATOR_COMPLETE_BEFORE_REFERENCE.json',dict(UTC=datetime.now(timezone.utc).isoformat(),receipts=receipts,source_pins=pins,protocol_sha256=sha(D/'PROTOCOL.md'),generator_sha256=sha(__file__),selected_movies=sum(x['status']=='selected_prediction_only' for x in selection),selected_pairs=sum(len(x.get('pairs',[])) for x in selection),fixture_count=sum(len(r.get('cases',[])) for r in receipts),reference_opened=False,new_biological_N=0))
    print(json.dumps(dict(selected_movies=sum(x['status']=='selected_prediction_only' for x in selection),selected_pairs=sum(len(x.get('pairs',[])) for x in selection),fixture_count=sum(len(r.get('cases',[])) for r in receipts),reference_opened=False)))
except BaseException:
    write(O/'GENERATOR_FAILURE.json',dict(exception=traceback.format_exc(),reference_opened=False));raise
