"""Pure graph-mechanism execution at native-restored boundary; no old runner import."""
import sys
sys.dont_write_bytecode=True
import ast,io,json,hashlib,traceback,copy,collections,csv
from pathlib import Path
import numpy as np
import zarr
from scipy.spatial import cKDTree
R=Path(__file__).resolve().parent
I=Path('legacy_inputs/IWS（只读勿动）');S=I/'SVM';S4=S/'SVM4';OLD=S/'research/target095';Q=S/'SVM5/research';GATE=Q/'event_gate'
from recount_sdy_sparse_v01 import score
GT=Path('legacy_inputs/cell（只读勿动）/gt_data/full/train')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def extract(path,names,extra=None):
    tree=ast.parse(path.read_text(encoding='utf-8-sig'))
    funcs=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in names]
    if {f.name for f in funcs}!=set(names):raise ValueError('Missing functions '+str(path))
    env={'np':np,'cKDTree':cKDTree,'defaultdict':collections.defaultdict,'copy':copy,'SPACING':np.array([1.625,.40625,.40625])}
    if extra:env.update(extra)
    exec(compile(ast.Module(body=funcs,type_ignores=[]),str(path),'exec'),env)
    return env
def load_npz(path,bindings):
    bindings[str(path)]=sha(path)
    with np.load(path,allow_pickle=False) as p:
        ids,coords,edges=[p[k].copy() for k in ['ids','coords','edges']]
    nodes={int(i):dict(node_id=int(i),t=int(c[0]),z=float(c[1]),y=float(c[2]),x=float(c[3])) for i,c in zip(ids,coords)}
    if len(nodes)!=len(ids):raise ValueError('duplicate input ids')
    return nodes,[dict(source_id=int(a),target_id=int(b)) for a,b in edges]
def load_geff(path,bindings):
    z=zarr.open_group(str(path),mode='r');ids=z['nodes/ids'][:];coords=np.column_stack([z[f'nodes/props/{k}/values'][:] for k in ['t','z','y','x']]);edges=z['edges/ids'][:]
    bindings[str(path)]={'decoded_arrays_sha256':hashlib.sha256(ids.tobytes()+coords.tobytes()+edges.tobytes()).hexdigest()}
    return {int(i):dict(node_id=int(i),t=int(c[0]),z=float(c[1]),y=float(c[2]),x=float(c[3])) for i,c in zip(ids,coords)},[dict(source_id=int(a),target_id=int(b)) for a,b in edges]
def one_geff(root,stem,bindings):
    paths=list(root.glob(f'*/unet_transformer/split_0/{stem}.geff'))
    if len(paths)!=1:raise ValueError(f'{root}: {stem} paths {len(paths)}')
    return load_geff(paths[0],bindings)
def restore(nodes,raw):
    nodes=copy.deepcopy(nodes)
    for i,n in raw.items():
        if i in nodes:nodes[i].update({k:n[k] for k in ['t','z','y','x']})
    return nodes
def edge_set(edges):return {(int(e['source_id']),int(e['target_id'])) for e in edges}
def save(path,nodes,edges):
    ids=np.array(sorted(nodes),dtype=np.int64);coords=np.array([[nodes[int(i)][k] for k in ['t','z','y','x']] for i in ids]);ee=np.array(sorted(edge_set(edges)),dtype=np.int64).reshape(-1,2)
    if len(ee)!=len(edges):raise ValueError('duplicate edges')
    np.savez_compressed(path,ids=ids,coords=coords,edges=ee,unit=np.array('pixel'))
def scored_graph(nodes,edges):return {'nodes':{i:[n[k] for k in ['t','z','y','x']] for i,n in nodes.items()},'edges':list(edge_set(edges))}
def main():
    out=R/'SVM_topology_replay_v0.2';out.mkdir(exist_ok=False)
    files=[Path(__file__),R/'SVM_topology_replay_protocol_v0.1.md',R/'recount_sdy_sparse_v01.py',GATE/'event_consensus_native_frozen.py',GATE/'event_consensus.py',GATE/'persistent_divergence.py',Q/'continuation/crossview_continuation.py',S4/'coupled_trajectory.py',S4/'trajectory_estimator.py',S4/'check_axis_trajectory.py',OLD/'kaggle_event_validator/output/validation_plan.json']
    bindings={str(p):sha(p) for p in files}
    (out/'before_execution.json').write_text(json.dumps(bindings,indent=2))
    ce=extract(GATE/'event_consensus_native_frozen.py',['reciprocal_match','gate'])
    ci=extract(GATE/'event_consensus.py',['reciprocal_match','gate'])
    pg=extract(GATE/'persistent_divergence.py',['gate'])
    drift=extract(S4/'coupled_trajectory.py',['common_drift'])
    continuation=extract(Q/'continuation/crossview_continuation.py',['reconcile'],{'reciprocal_match':ci['reciprocal_match'],'common_drift':drift['common_drift']})
    for fname,path in [('native_consensus',GATE/'native_consensus/prediction_manifest.json'),('persistence',GATE/'persistence/prediction_manifest.json')]:
        m=json.loads(path.read_text(encoding='utf-8'));source=GATE/('event_consensus_native_frozen.py' if fname=='native_consensus' else 'persistent_divergence.py')
        raw_sha=sha(source);lf_sha=hashlib.sha256(source.read_bytes().replace(bytes([13,10]),bytes([10]))).hexdigest()
        if m['module_sha256'] not in [raw_sha,lf_sha]:raise ValueError('Frozen module mismatch even after explicit CRLF normalization: '+fname)
        bindings['module_binding_'+fname]={'archived_manifest_hash':m['module_sha256'],'current_bytes_sha256':raw_sha,'LF_bytes_sha256':lf_sha,'comparison':'byte-exact' if m['module_sha256']==raw_sha else 'explicit-CRLF-to-LF-only;execution-AST-unchanged'}
        bindings[str(path)]=sha(path)
    dev=[p.stem for p in sorted((OLD/'event_completion_active').glob('*.npz'))]
    transfer=json.loads((OLD/'kaggle_event_validator/output/validation_plan.json').read_text(encoding='utf-8'))['new_stems']
    assert len(dev)==len(transfer)==8 and not set(dev)&set(transfer)
    predictions=[];memory={}
    for split,stems in [('development',dev),('transfer',transfer)]:
        for stem in stems:
            ep=OLD/'event_completion_active'/f'{stem}.npz' if split=='development' else S4/'transfer_assets/event/validation_graphs/event_completion'/f'{stem}.npz'
            en,ee=load_npz(ep,bindings)
            if split=='development':
                er,ere=load_npz(OLD/'current_baseline'/stem/'raw.npz',bindings);bp=S4/'combination_validation'/f'{stem}.npz';br,bre=load_npz(S4/'validation'/stem/'raw.npz',bindings)
            else:
                er,ere=one_geff(S4/'transfer_assets/raw/tracking_repo/predictions',stem,bindings)
                bbase=S4/'private_validation/B/output';bp=bbase/'validated_graphs'/f'{stem}.npz';br,bre=one_geff(bbase/'tracking_repo/predictions',stem,bindings)
            bn,be=load_npz(bp,bindings);en=restore(en,er);bn=restore(bn,br)
            trials=[]
            stats=collections.defaultdict(int);after,details=ce['gate'](bn,be,bre,en,ee,stats,observed=set(br),reference_observed=set(er))
            trials.append(('native_consensus_B',bn,be,after,details,dict(stats),GATE/'native_consensus'/f'{stem}.npz',edge_set(bre)))
            for arm,nodes,edges,raw in [('E',en,ee,ere),('B',bn,be,bre)]:
                stats=collections.defaultdict(int);after,details=pg['gate'](nodes,edges,raw,set(er if arm=='E' else br),stats)
                trials.append(('persistent_divergence_'+arm,nodes,edges,after,details,dict(stats),GATE/'persistence'/f'{stem}_{arm}.npz',edge_set(raw)))
            # Reproduce historical continuation's unrestricted-B matching input;
            # E membership is limited to observed rows exactly as its original runner.
            native_en={i:n for i,n in en.items() if i in er};stats=collections.defaultdict(int)
            gate_edges,_=ci['gate'](bn,be,bre,native_en,ee,stats)
            after,details=continuation['reconcile'](bn,gate_edges,set(br),native_en,ee,stats)
            trials.append(('continuation',bn,gate_edges,after,details,dict(stats),Q/'continuation/validation'/f'{stem}.npz',None))
            for arm,nodes,before,after,details,stats,archived,protected in trials:
                ab=out/f'{stem}_{arm}_before.npz';aa=out/f'{stem}_{arm}_after.npz';save(ab,nodes,before);save(aa,nodes,after)
                _,stored_edges=load_npz(archived,bindings)
                if edge_set(stored_edges)!=edge_set(after):raise ValueError(f'{stem} {arm}: historical edge set mismatch')
                removed=edge_set(before)-edge_set(after);added=edge_set(after)-edge_set(before)
                if arm!='continuation' and added:raise ValueError('Deletion gate added edge')
                if protected is not None and removed&protected:raise ValueError('Gate removed a native input edge')
                row={'stem':stem,'split':split,'arm':arm,'added_edges':len(added),'removed_edges':len(removed),'stats':stats,'actions':details,'stored_edges_exact':True,'coordinates_held_fixed':True,'before_sha256':sha(ab),'after_sha256':sha(aa),'archived_sha256':sha(archived),'scope':'New fixed-coordinate gate contrast; historical final topology parity only, no downstream smoother execution.'}
                predictions.append(row);memory[stem,arm]=(nodes,before,after)
            print('FROZEN',split,stem,[(a,len(edge_set(b)-edge_set(c))) for a,n,b,c,d,s,p,k in trials],flush=True)
    assert len(predictions)==64
    (out/'prediction_manifest.json').write_text(json.dumps({'input_bindings':bindings,'predictions':predictions,'reference_read':False},indent=2))
    # References are opened only after every source prediction is saved.
    results=[];reference_bindings=[]
    for split,stems in [('development',dev),('transfer',transfer)]:
        for stem in stems:
            group=zarr.open_group(str(GT/(stem+'.geff')),mode='r');gi=group['nodes/ids'][:];gc=np.column_stack([group[f'nodes/props/{k}/values'][:] for k in ['t','z','y','x']]);ge=set(map(tuple,group['edges/ids'][:].tolist()))
            reference_bindings.append({'stem':stem,'reference_nodes':len(gi),'reference_edges':len(ge),'decoded_arrays_sha256':hashlib.sha256(gi.tobytes()+gc.tobytes()+np.array(sorted(ge),dtype=np.int64).tobytes()).hexdigest()})
            for row in [p for p in predictions if p['stem']==stem]:
                nodes,before,after=memory[stem,row['arm']]
                bc,bv=score(scored_graph(nodes,before),(gi,gc,ge));ac,av=score(scored_graph(nodes,after),(gi,gc,ge))
                results.append({'stem':stem,'split':split,'arm':row['arm'],'before':bc,'after':ac,'gains':len(av-bv),'losses':len(bv-av),'gain_reference_edges':sorted(av-bv),'loss_reference_edges':sorted(bv-av)})
    groups=[]
    for arm in sorted({r['arm'] for r in results}):
        for split in ['development','transfer']:
            block=[r for r in results if r['arm']==arm and r['split']==split]
            summary={'arm':arm,'split':split,'film_n':len(block),'gains':sum(r['gains'] for r in block),'losses':sum(r['losses'] for r in block)}
            for s in ['before','after']:summary[s]={k:sum(r[s][k] for r in block) for k in ['TP','FP','FN','ignored_predictions']}
            groups.append(summary)
    (out/'reference_results.json').write_text(json.dumps({'results':results,'groups':groups,'reference_bindings':reference_bindings,'scope':'Descriptive sparse-reference results at newly fixed native-restored coordinate boundary; not historical final composite score, not biological truth certification.'},indent=2))
    print(json.dumps(groups,indent=2),flush=True)
    return out
if __name__=='__main__':
    try:main()
    except Exception as error:
        p=R/'SVM_topology_replay_v0.2'
        if p.exists() and not (p/'failure.json').exists():(p/'failure.json').write_text(json.dumps({'type':type(error).__name__,'error':str(error),'traceback':traceback.format_exc()},indent=2))
        raise

