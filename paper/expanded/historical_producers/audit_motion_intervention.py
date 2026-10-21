"""Join an actual frozen-raw-input intervention to existing graph evidence."""
from pathlib import Path
from collections import Counter
import sys,json,csv,shutil
import numpy as np
R=Path('D:/1013工作大修');D=Path(__file__).resolve().parent;O=R/'04_统一重分析';S=Path('D:/CELL数据暂存/IWS（只读勿动）/SVM/research/target095');sys.path.insert(0,str(R/'src'))
import audit_engine as E
from linked_contrast import linked_contrast
from orientation import reverse_pair_record
old=json.loads((S/'current_baseline/runtime_manifest.json').read_text(encoding='utf8'));new=json.loads((S/'motion_ablation/runtime/runtime_manifest.json').read_text(encoding='utf8'))
assert old['parent_sha256']==new['parent_sha256'] and old['predictor_original_sha256']==new['predictor_original_sha256'] and old['weights']==new['weights']
config_differences={k:[old['postprocess_config'].get(k),new['postprocess_config'].get(k)]for k in set(old['postprocess_config'])|set(new['postprocess_config'])if old['postprocess_config'].get(k)!=new['postprocess_config'].get(k)}
env_differences={k:[old['environment'].get(k),new['environment'].get(k)]for k in set(old['environment'])|set(new['environment'])if old['environment'].get(k)!=new['environment'].get(k)}
assert not config_differences;assert set(env_differences)<= {'SVM2_EVIDENCE_DIR'}
assets=[json.loads(x)for x in(O/'ASSET_ADMISSION.jsonl').read_text(encoding='utf8').splitlines()];by_path={str(Path(x['path'])).lower():x for x in assets};pairs={(r['film'],r['before_graph'],r['after_graph']):r for r in csv.DictReader((O/'paired/ALL_WITHIN_MOVIE_PAIRS.csv').open(encoding='utf-8-sig'))}
films=sorted(p.stem for p in(S/'motion_ablation').glob('*.json')if p.stem.startswith(('44b6_','6bba_')));assert len(films)==8
# Declared before this script evaluates any new constrained readout.
protocol={'inputs':'All eight saved motion_ablation outputs and their current_baseline/final.npz; raw graph and unchanged retained image/weight context are historical execution inputs','contract':'Reuse original product contrast; add the same LINKAGE_PROTOCOL exact identical matching-input rule','required_films':films,'cap':1048576,'pass':'All pairs mapped to existing normalized graph reports; complete all permitted bounds and full-map replays or retain explicit refusal','do_not_select_by_outcome':True,'no_new_tracker_inference':True}
(D/'MOTION_COMPARISON_PROTOCOL.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2),encoding='utf8')
saved=D/'motion_source_records';saved.mkdir(exist_ok=True)
for p in [S/'ablate_motion_replacement.py',S/'run_current_baseline.py',S/'current_root_runtime.py']:
    shutil.copy2(p,saved/p.name)
shutil.copy2(S/'current_baseline/runtime_manifest.json',saved/'baseline_runtime_manifest.json');shutil.copy2(S/'motion_ablation/runtime/runtime_manifest.json',saved/'intervention_pre_override_manifest.json')
records=[]
for film in films:
    historical=json.loads((S/'motion_ablation'/(film+'.json')).read_text(encoding='utf8'));baseline=json.loads((S/'current_baseline'/film/'report.json').read_text(encoding='utf8'));assert historical['baseline']==baseline['final_score'];assert historical['stats']['motion_relink_edges']==0 and historical['stats']['motion_relink_replaced_raw_edges']==0
    shutil.copy2(S/'motion_ablation'/(film+'.json'),saved/(film+'_historical.json'))
    aa=[by_path[str(S/'current_baseline'/film/'final.npz').lower()],by_path[str(S/'motion_ablation'/(film+'.npz')).lower()]];gids=[next(x['graph_id']for x in a['accepted']if x['film']==film)for a in aa];a,b=gids
    assert a!=b
    x,y=sorted(gids);p=dict(pairs[(film,x,y)]);p=reverse_pair_record(p)if a==y else p
    graphs=[E.load_graph(O/'graphs'/(g+'.npz'))for g in gids];ref=E.load_graph(O/'references'/(film+'.npz'));ss=[E.read_json_gz(O/'graph_reports'/(g+'.json.gz'))for g in gids];vs=[]
    for g in gids:
        with np.load(O/'visibility'/(g+'.npz'),allow_pickle=False)as z:vs.append({k:z[k].copy()for k in z.files})
    fs=[{int(t):E.read_json_gz(O/'frame_cache'/loc)for t,loc in s['frame_locators'].items()}for s in ss];linked=linked_contrast(graphs,ref,ss,vs,fs)
    if linked['status']=='COMPLETE':
        for m in ['before_TP','after_TP','gains','losses','net']:assert int(p[m+'_minimum'])<=linked['bounds'][m]['minimum']<=linked['bounds'][m]['maximum']<=int(p[m+'_maximum'])
    dest='motion_linked/'+film+'.json.gz';E.save_json_gz(D/dest,{'film':film,'before_graph':a,'after_graph':b,'before_frame_locators':ss[0]['frame_locators'],'after_frame_locators':ss[1]['frame_locators'],**linked})
    records.append({'film':film,'before_asset':aa[0]['asset_id'],'after_asset':aa[1]['asset_id'],'raw_source':str(S/'current_baseline'/film/'raw.npz'),'raw_source_exists':(S/'current_baseline'/film/'raw.npz').exists(),'legacy_before':historical['baseline'],'legacy_after':historical['revised'],'baseline_action_counter':baseline['stats'].get('motion_relink_replaced_raw_edges'),'intervention_action_counter':historical['stats']['motion_relink_replaced_raw_edges'],'product':p,'linked_status':linked['status'],'linked_bounds':linked.get('bounds'),'linked_witness_record':dest,'new_canonical_FP_before':ss[0]['canonical_FP'],'new_canonical_FP_after':ss[1]['canonical_FP']})
legacy={k:sum(r['legacy_after'][k]-r['legacy_before'][k]for r in records)for k in ['edge_tp','edge_fp','edge_fn']};counts={k:sum(int(r['product'][k])for r in records)for k in ['canonical_gains','canonical_losses','canonical_net']}
complete=all(r['linked_status']=='COMPLETE'for r in records);bounds={m:{s:sum(r['linked_bounds'][m][s]for r in records)for s in ['minimum','maximum']}for m in ['before_TP','after_TP','gains','losses','net']}if complete else None
result={'status':'COMPLETE_SOURCE_AND_OUTPUT_JOIN','film_count':8,'parent_sha256':old['parent_sha256'],'unchanged_historical_weights_and_predictor':True,'configuration_before_override_equal':True,'manifest_precedes_override':'load_runtime writes manifest before ablate_motion_replacement.py sets OUTPUT_MOTION_RELINK=False; actual statistics confirm zero motion actions','environment_differences':env_differences,'historical_pipeline_uses_image_and_weight_context':True,'scientific_scope':'Conditional local component intervention on reused raw graphs and fixed retained processing context. No held-out generalization or competition score claim.','legacy_delta':legacy,'new_canonical':counts,'linked_bounds':bounds,'records':records}
(D/'MOTION_INTERVENTION_RESULTS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in result.items()if k not in ['records','environment_differences']},ensure_ascii=False))
