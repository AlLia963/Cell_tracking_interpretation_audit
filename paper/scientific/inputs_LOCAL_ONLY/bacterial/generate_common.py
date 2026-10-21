"""Execute all six pinned policies on the original fixed B/E carriers, locally."""
from pathlib import Path
import argparse, collections, copy, json, shutil, sys
import numpy as np
from run_archive import HERE,read,write,sha,require,module,source_bindings

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input-root',type=Path,required=True);ap.add_argument('--iws-root',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();source_bindings();root=a.input_root.resolve();out=a.output.resolve();require(not out.exists(),'Fresh output');out.mkdir(parents=True);shutil.copy2(__file__,out/'EXECUTED_ADAPTER.py');dest=out/'generated';dest.mkdir()
    src=HERE/'sources/common_policy';sys.path.insert(0,str(src));m=module(src/'replay_svm_topology_v02.py');s=a.iws_root/'SVM';m.update(R=root,S=s,S4=s/'SVM4',OLD=s/'research/target095',Q=s/'SVM5/research',GATE=s/'SVM5/research/event_gate')
    policies=src/'policies';strict=m['extract'](policies/'event_gate/event_consensus.py',['reciprocal_match','gate']);affirm=m['extract'](policies/'event_gate/affirmative_veto.py',['reciprocal_match','gate']);blend=m['extract'](policies/'measurement_fusion/measurement_fusion.py',['blend'],{'reciprocal_match':strict['reciprocal_match']})['blend'];complete=m['extract'](policies/'topology/endpoint_consistency.py',['complete'])['complete']
    pm=read(root/'SVM_topology_replay_v0.2/prediction_manifest.json');films=[r for r in pm['predictions'] if r['arm']=='native_consensus_B'];require(len(films)==16,'All16 carriers');pins={str(p):sha(p) for p in policies.rglob('*.py')};records=[]
    arms=['unchanged','strict','affirmative','blend','endpoint','strict_blend']
    for row in films:
        film=row['stem'];split=row['split'];p=root/'SVM_topology_replay_v0.2'/f'{film}_native_consensus_B_before.npz';require(sha(p)==row['before_sha256'],'Frozen B carrier');bn,be=m['load_npz'](p,pins)
        if split=='development':
            ep=m['OLD']/'event_completion_active'/f'{film}.npz';er,_=m['load_npz'](m['OLD']/'current_baseline'/film/'raw.npz',pins);br,bre=m['load_npz'](m['S4']/'validation'/film/'raw.npz',pins)
        else:
            ep=m['S4']/'transfer_assets/event/validation_graphs/event_completion'/f'{film}.npz';er,_=m['one_geff'](m['S4']/'transfer_assets/raw/tracking_repo/predictions',film,pins);br,bre=m['one_geff'](m['S4']/'private_validation/B/output/tracking_repo/predictions',film,pins)
        en,ee=m['load_npz'](ep,pins);en=m['restore'](en,er);native_en={i:n for i,n in en.items() if i in er};old=m['edge_set'](be)
        for arm in arms:
            nodes=copy.deepcopy(bn);edges=copy.deepcopy(be);stats=collections.defaultdict(int);details=[]
            if arm in ['strict','strict_blend']:edges,details=strict['gate'](nodes,edges,bre,en,ee,stats,observed=set(br),reference_observed=set(er))
            if arm=='affirmative':edges,details=affirm['gate'](nodes,edges,bre,en,ee,stats,observed=set(br),reference_observed=set(er))
            if arm in ['blend','strict_blend']:nodes=blend(nodes,set(br),native_en,stats)
            if arm=='endpoint':
                ids=np.array(sorted(nodes),np.int64);coords=np.array([[nodes[int(i)][k] for k in ['t','z','y','x']] for i in ids]);edgearray=np.array(sorted(m['edge_set'](edges)),np.int64).reshape(-1,2);revised,st=complete(ids,coords,edgearray);stats.update(st);details=st['actions'];edges=[dict(source_id=int(x),target_id=int(y)) for x,y in revised]
            new=m['edge_set'](edges);require(set(nodes)==set(bn) and all(nodes[i]['t']==bn[i]['t'] for i in bn),'Same nodes/times')
            if arm not in ['blend','strict_blend']:require(all(nodes[i]==bn[i] for i in bn),'Fixed coordinates')
            if arm in ['unchanged','blend']:require(new==old,'Fixed topology')
            if arm=='endpoint':require(old<=new,'Append only')
            if arm in ['strict','affirmative','strict_blend']:require(new<=old and not (old-new)&m['edge_set'](bre),'Native edges protected')
            q=dest/f'{film}_{arm}.npz';m['save'](q,nodes,edges);records.append({'film':film,'split':split,'arm':arm,'output_sha256':sha(q),'added_edges':sorted(new-old),'removed_edges':sorted(old-new),'changed_coordinates':sum(any(nodes[i][k]!=bn[i][k] for k in ['z','y','x']) for i in bn),'stats':dict(stats),'actions':details})
        print('GENERATED_COMMON6',film,flush=True)
    write(out/'PREDICTIONS_BEFORE_REFERENCE.json',{'records':records,'input_bindings':pins,'reference_read':False,'operation':'new policy replay on fixed saved carriers; no model inference'})
    write(out/'GENERATOR_OUTPUT_FREEZE.json',{'generated':{p.name:sha(p) for p in dest.iterdir()},'generator_sha256':sha(__file__)})
    # Historical answers are opened only after every fresh prediction is frozen.
    comparisons=[]
    for row in records:
        p=dest/f"{row['film']}_{row['arm']}.npz";q=HERE/'inputs_LOCAL_ONLY/common_carrier96'/p.name
        with np.load(p,allow_pickle=False) as x,np.load(q,allow_pickle=False) as y:
            exact=set(x.files)==set(y.files) and all(np.array_equal(x[k],y[k]) for k in x.files)
        comparisons.append({'film':row['film'],'arm':row['arm'],'all_array_members_exact':exact,'bytes_exact':sha(p)==sha(q)})
    write(out/'COMPARISON_AFTER_PREDICTION_FREEZE.json',{'all96_array_members_exact':all(r['all_array_members_exact'] for r in comparisons),'rows':comparisons});require(all(r['all_array_members_exact'] for r in comparisons),'Regenerated policy arrays mismatch; preserve all results')
    write(out/'RESULT.json',{'policy_outputs':len(records),'carriers':16,'all96_array_members_exact':True,'source_code':{str(Path(p).relative_to(HERE)):sha(p) for p in [__file__,src/'replay_svm_topology_v02.py',*policies.rglob('*.py')]},'new_biological_N':0,'upstream_model_regenerated':False})
if __name__=='__main__':main()
