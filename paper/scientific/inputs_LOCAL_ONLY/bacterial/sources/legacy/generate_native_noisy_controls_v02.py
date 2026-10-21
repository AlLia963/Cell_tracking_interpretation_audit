"""Prediction-only executed fault fixture generation, no GT read or scoring."""
import sys
sys.dont_write_bytecode=True
import json,hashlib,copy
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;B=R/'external_end_to_end_feasibility_v0.1'
O=R/'native_noisy_controls_v0.2';O.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
protocol=R/'native_noisy_control_protocol_v0.1.md'
assert (R/'native_conditional_graph_audit_v0.2.md').exists()
arms=['unchanged','edge_delete','node_remove','support_zero','support_swap','delete_recover_delete','delete_recover','support_duplicate','prewindow_omission','absent_edge_noop']
bindings={'protocol_sha256':sha(protocol),'generator_sha256':sha(Path(__file__)),'construction_review_sha256':sha(R/'native_conditional_graph_audit_v0.2.md'),'graph_manifest_sha256':sha(B/'native_conditional_graph_v0.2/report.json'),'provenance_manifest_sha256':sha(B/'native_graph_provenance_v0.2/manifest.json'),'reference_read':False,'fault_truth_scope':'Executed computational overlay operations, not native model intervention effects'}
(O/'before_execution.json').write_text(json.dumps(bindings,indent=2))
reports=[]
for v in [f'{i:02d}' for i in range(1,30)]:
    sidepath=B/'native_graph_provenance_v0.2'/f'{v}_sidecar.json'
    side=json.loads(sidepath.read_text(encoding='utf-8'));gp=B/side['graph_path_relative_to_root'];assert sha(gp)==side['graph_sha256']
    graphs=json.loads(gp.read_text());ids=[];supports=[];statebindings=[]
    for f in [0,1]:
        record=side['records'][f];path=B/record['state_path_relative_to_root'];assert sha(path)==record['state_sha256']
        statebindings.append({'frame':f,'path':str(path),'sha256':sha(path)})
        with np.load(path,allow_pickle=False) as z:
            ids.extend(graphs[f]['stages']['D']['nodes']);supports.extend(z['return_masks'].copy())
    base={'ids':np.array(ids,dtype=np.int64),'masks':np.array(supports,dtype=bool),'edges':set(tuple(e[:2]) for e in graphs[1]['stages']['D']['edges']),'division':set(tuple(e[:2]) for e in graphs[1]['stages']['D']['edges'] if e[2]=='division')}
    targets=sorted(base['edges']);selected=targets[0] if targets else None
    current=sorted(n for n in ids if n>=100000);previous=sorted(n for n in ids if n<100000)
    partner=next((n for n in current if selected and n!=selected[1]),None)
    absent=next(((a,b) for a in previous for b in current if (a,b) not in base['edges']),None)
    records=[]
    for arm in arms:
        unavailable=None
        if selected is None and arm not in ['unchanged','absent_edge_noop']:unavailable='no predicted frame0-to1 edge'
        if arm in ['support_swap','support_duplicate'] and partner is None:unavailable='no second current candidate'
        if arm=='absent_edge_noop' and absent is None:unavailable='no absent pair in fixed domain'
        if unavailable:
            records.append({'arm':arm,'status':'unavailable','reason':unavailable});continue
        views=[copy.deepcopy(base) for _ in range(4)];receipts=[]
        for k,view in enumerate(views):
            active=(k>=1)
            if arm=='prewindow_omission':active=True
            if arm=='delete_recover_delete':active=k in [1,3]
            if arm=='delete_recover':active=k==1
            if arm in ['delete_recover_delete','delete_recover'] and k==2:
                # Execute restoration from the actually deleted previous view.
                view['edges']=views[k-1]['edges'].copy();view['division']=views[k-1]['division'].copy()
                assert selected not in view['edges']
                view['edges'].add(selected)
                if selected in base['division']:view['division'].add(selected)
                receipts.append({'stage':k,'operation':'edge_restore','executed':True,'changed':True,'selected':selected,'from_previous_stage':True})
                continue
            if not active or arm=='unchanged':continue
            before_ids=view['ids'].copy();before_masks=view['masks'].copy();before_edges=view['edges'].copy()
            if arm in ['edge_delete','delete_recover_delete','delete_recover','prewindow_omission']:
                view['edges'].discard(selected);view['division'].discard(selected)
            elif arm=='node_remove':
                keep=view['ids']!=selected[1];view['ids']=view['ids'][keep];view['masks']=view['masks'][keep]
                view['edges']={e for e in view['edges'] if selected[1] not in e};view['division']={e for e in view['division'] if selected[1] not in e}
            elif arm=='support_zero':view['masks'][view['ids']==selected[1]]=False
            elif arm in ['support_swap','support_duplicate']:
                a=int(np.flatnonzero(view['ids']==selected[1])[0]);b=int(np.flatnonzero(view['ids']==partner)[0])
                if arm=='support_swap':view['masks'][[a,b]]=view['masks'][[b,a]]
                else:view['masks'][b]=view['masks'][a]
            elif arm=='absent_edge_noop':view['edges'].discard(absent);view['division'].discard(absent)
            changed=not np.array_equal(before_ids,view['ids']) or not np.array_equal(before_masks,view['masks']) or before_edges!=view['edges']
            receipts.append({'stage':k,'operation':arm,'executed':True,'changed':changed,'selected':selected,'partner':partner if arm in ['support_swap','support_duplicate'] else None,'absent_pair':absent if arm=='absent_edge_noop' else None})
        arrays={}
        for k,view in enumerate(views):
            arrays[f'ids{k}']=view['ids'];arrays[f'masks{k}']=view['masks']
            arrays[f'edges{k}']=np.array(sorted(view['edges']),dtype=np.int64).reshape(-1,2)
            arrays[f'division{k}']=np.array(sorted(view['division']),dtype=np.int64).reshape(-1,2)
            assert all(a in view['ids'] and b in view['ids'] for a,b in view['edges'])
        p=O/f'{v}_{arm}.npz';np.savez_compressed(p,**arrays)
        records.append({'arm':arm,'status':'executed','fixture':p.name,'sha256':sha(p),'receipts':receipts})
    reports.append({'video':v,'selection':'first lexicographic D edge frame0-to1, before any GT correspondence','selected':selected,'partner':partner,'input_states':statebindings,'sidecar_sha256':sha(sidepath),'cases':records})
    print(v,sum(c['status']=='executed' for c in records),flush=True)
(O/'generator_receipts.json').write_text(json.dumps({'binding':bindings,'videos':reports,'execution_complete':True,'oracle_measurement':'not yet executed; receipts not valid measurement inputs'},indent=2))
