import sys
sys.dont_write_bytecode=True
from pathlib import Path
import importlib.util,hashlib,json,copy,time,traceback
from collections import defaultdict,Counter
import numpy as np
import zarr
R=Path(__file__).resolve().parent;O=R/'common_carrier_cohort_v0.1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,j):
    with p.open('x',encoding='utf-8') as f:json.dump(j,f,indent=2)
def main():
    started=time.perf_counter();O.mkdir(exist_ok=False)
    sp=importlib.util.spec_from_file_location('topology',R/'replay_svm_topology_v02.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
    sourcepaths=[m.GATE/'event_consensus.py',m.GATE/'affirmative_veto.py',m.Q/'measurement_fusion/measurement_fusion.py',m.Q/'topology/endpoint_consistency.py']
    strict=m.extract(sourcepaths[0],['reciprocal_match','gate']);affirm=m.extract(sourcepaths[1],['reciprocal_match','gate']);blend=m.extract(sourcepaths[2],['blend'],{'reciprocal_match':strict['reciprocal_match']})['blend'];complete=m.extract(sourcepaths[3],['complete'])['complete']
    oldp=R/'SVM_topology_replay_v0.2/prediction_manifest.json';old=json.loads(oldp.read_text());films=[r for r in old['predictions'] if r['arm']=='native_consensus_B'];assert len(films)==16
    bindings={str(p):sha(p) for p in [*sourcepaths,oldp,Path(__file__),R/'common_carrier_protocol_v0.1.md',R/'replay_svm_topology_v02.py',R/'recount_sdy_sparse_v01.py']}
    arms=['unchanged','strict','affirmative','blend','endpoint','strict_blend'];predictions=[]
    for r in films:
        stem=r['stem'];split=r['split'];beforep=R/'SVM_topology_replay_v0.2'/f'{stem}_native_consensus_B_before.npz';assert sha(beforep)==r['before_sha256'];bn,be=m.load_npz(beforep,bindings)
        if split=='development':
            ep=m.OLD/'event_completion_active'/f'{stem}.npz';er,_=m.load_npz(m.OLD/'current_baseline'/stem/'raw.npz',bindings);br,bre=m.load_npz(m.S4/'validation'/stem/'raw.npz',bindings)
        else:
            ep=m.S4/'transfer_assets/event/validation_graphs/event_completion'/f'{stem}.npz';er,_=m.one_geff(m.S4/'transfer_assets/raw/tracking_repo/predictions',stem,bindings);br,bre=m.one_geff(m.S4/'private_validation/B/output/tracking_repo/predictions',stem,bindings)
        en,ee=m.load_npz(ep,bindings);en=m.restore(en,er);native_en={i:n for i,n in en.items() if i in er}
        oldedges=m.edge_set(be)
        for arm in arms:
            nodes=copy.deepcopy(bn);edges=copy.deepcopy(be);stats=defaultdict(int);details=[]
            if arm in ['strict','strict_blend']:
                edges,details=strict['gate'](nodes,edges,bre,en,ee,stats,observed=set(br),reference_observed=set(er))
            if arm=='affirmative':edges,details=affirm['gate'](nodes,edges,bre,en,ee,stats,observed=set(br),reference_observed=set(er))
            if arm in ['blend','strict_blend']:nodes=blend(nodes,set(br),native_en,stats)
            if arm=='endpoint':
                ids=np.array(sorted(nodes),dtype=np.int64);coords=np.array([[nodes[int(i)][k] for k in ['t','z','y','x']] for i in ids]);edgearray=np.array(sorted(m.edge_set(edges)),dtype=np.int64).reshape(-1,2)
                revised,st=complete(ids,coords,edgearray);stats.update(st);details=st['actions'];edges=[dict(source_id=int(a),target_id=int(b)) for a,b in revised]
            newedges=m.edge_set(edges);assert set(nodes)==set(bn) and all(nodes[i]['t']==bn[i]['t'] for i in bn)
            if arm not in ['blend','strict_blend']:assert all(nodes[i]==bn[i] for i in bn)
            if arm in ['unchanged','blend']:assert newedges==oldedges
            if arm=='endpoint':assert oldedges<=newedges
            if arm in ['strict','affirmative','strict_blend']:assert newedges<=oldedges and not (oldedges-newedges)&m.edge_set(bre)
            dest=O/f'{stem}_{arm}.npz';m.save(dest,nodes,edges)
            dup=None
            if arm=='strict':dup=(sha(dest)==r['after_sha256']);assert dup
            if arm=='strict_blend':
                previous=R/'SVM_measurement_boundary_v0.1'/f'{stem}_after.npz';dup=(sha(dest)==sha(previous));bindings[str(previous)]=sha(previous);assert dup
            predictions.append(dict(stem=stem,split=split,arm=arm,before_path=str(beforep),before_sha256=sha(beforep),output_path=str(dest),output_sha256=sha(dest),added_edges=sorted(newedges-oldedges),removed_edges=sorted(oldedges-newedges),changed_coordinates=sum(any(nodes[i][k]!=bn[i][k] for k in ['z','y','x']) for i in bn),stats=dict(stats),actions=details,prior_exact_output_duplicate=dup))
        print('FROZEN',stem,[(p['arm'],len(p['added_edges']),len(p['removed_edges']),p['changed_coordinates']) for p in predictions if p['stem']==stem],flush=True)
    assert len(predictions)==96
    write(O/'prediction_manifest.json',dict(predictions=predictions,input_bindings=bindings,reference_read=False,scope='Sixfixedarms/16samecarriers;duplicatesnotnewN'))
    results=[];gtbindings=[]
    for r in films:
        stem=r['stem'];g=zarr.open_group(str(m.GT/(stem+'.geff')),mode='r');ids=g['nodes/ids'][:];coords=np.column_stack([g[f'nodes/props/{k}/values'][:] for k in ['t','z','y','x']]);ge=g['edges/ids'][:];gtedges=set(map(tuple,ge.tolist()));gtbindings.append(dict(stem=stem,sha256=hashlib.sha256(ids.tobytes()+coords.tobytes()+ge.tobytes()).hexdigest()))
        scratch={};beforep=Path(next(p['before_path'] for p in predictions if p['stem']==stem));before_nodes,before_edges=m.load_npz(beforep,scratch);before,bv=m.score(m.scored_graph(before_nodes,before_edges),(ids,coords,gtedges))
        for pred in [p for p in predictions if p['stem']==stem]:
            nodes,edges=m.load_npz(Path(pred['output_path']),scratch);after,av=m.score(m.scored_graph(nodes,edges),(ids,coords,gtedges));dtp=after['TP']-before['TP'];dfp=after['FP']-before['FP'];good=dtp>0 or dfp<0;bad=dtp<0 or dfp>0;category='mixed' if good and bad else 'beneficial' if good else 'harmful' if bad else 'measured-null'
            results.append(dict(stem=stem,split=r['split'],arm=pred['arm'],before=before,after=after,gains=len(av-bv),losses=len(bv-av),gain_edges=sorted(av-bv),loss_edges=sorted(bv-av),descriptive_category=category,visibility_turnover=bool(av-bv and bv-av),no_output_change=not(pred['added_edges'] or pred['removed_edges'] or pred['changed_coordinates'])))
    summaries=[]
    for arm in arms:
        block=[r for r in results if r['arm']==arm];summaries.append(dict(arm=arm,gains=sum(r['gains'] for r in block),losses=sum(r['losses'] for r in block),TP_delta=sum(r['after']['TP']-r['before']['TP'] for r in block),FP_delta=sum(r['after']['FP']-r['before']['FP'] for r in block),categories=dict(Counter(r['descriptive_category'] for r in block)),no_output_change_films=sum(r['no_output_change'] for r in block)))
    write(O/'reference_results.json',dict(results=results,summaries=summaries,reference_bindings=gtbindings,runtime_seconds=time.perf_counter()-started,independent_audit='pending',selection_utility_tested=False))
    print('RESULT',summaries,flush=True)
if __name__=='__main__':
    try:main()
    except Exception:
        if O.exists():write(O/'failure.json',dict(traceback=traceback.format_exc()))
        raise
