"""Copy bounded evidence into the new controlled workspace; never run archival jobs."""
from pathlib import Path
import shutil,json,hashlib,sqlite3,importlib.util
import numpy as np
import zarr
R=Path(__file__).resolve().parents[1];D=R/'05_补证与核验';I=Path('D:/CELL数据暂存/IWS（只读勿动）');S=I/'SVM';OLD=Path('G:/kaggle论文化/论文工作区');U=OLD/'BSPC_统一收束';manifest=[]
def copy(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);manifest.append({'source':str(src),'destination':str(dst.relative_to(R)),'bytes':dst.stat().st_size,'sha256':hashlib.sha256(dst.read_bytes()).hexdigest()})
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
# Original pure endpoint function, with a newly discriminating constructed control.
src=U/'04_审阅软件包/software/paper/scientific/inputs_LOCAL_ONLY/bacterial/sources/common_policy/policies/topology/endpoint_consistency.py';ep=D/'端点搜索域核验/endpoint_consistency.py';copy(src,ep)
spec=importlib.util.spec_from_file_location('endpoint_original',ep);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
ids=np.arange(1,9);coords=np.array([[0,0,0,0],[1,0,0,1],[2,0,0,2],[3,0,0,3.5],[4,0,0,4.5],[5,0,0,5.5],[2,0,0,50],[3,0,0,3]],float);coords[:,3]/=.40625
edges=np.array([[1,2],[2,3],[4,5],[5,6],[7,8]],np.int64)
blocked,bs=mod.complete(ids,coords,edges);positive,ps=mod.complete(ids[:6],coords[:6],edges[:4])
assert (3,4)not in set(map(tuple,blocked))and(3,4)in set(map(tuple,positive))
np.savez_compressed(ep.parent/'CONTROL_INPUTS.npz',ids=ids,coords=coords,edges=edges)
save(ep.parent/'RESULT.json',{'status':'PASS','blocked_actions':bs,'without_ineligible_nearest_node':ps,'expected_claim':'Nearest over all next-frame nodes, then endpoint eligibility; nearest eligible endpoint is a different algorithm','constructed_not_biological_experiment':True})
# Preserve four failed folds and the exact historical training/capture implementation.
hs=I/'0929最后一次提交窗口/SDY/05_experiments/E5_head_v2';hd=D/'四折负结果_历史证据'
for p in hs.iterdir():
    if p.is_file()and p.suffix in ['.py','.json','.pt']:copy(p,hd/p.name)
for p in (hs/'capture').rglob('*.npz'):copy(p,hd/'capture'/p.relative_to(hs/'capture'))
gate=json.loads((hd/'head_v2_gate.json').read_text(encoding='utf8'));assert len(gate['folds'])==4 and gate['wins_vs_v1']==0
save(hd/'核验.json',{'historical_gate_read':True,'folds':len(gate['folds']),'v2_wins_vs_v1':sum(x['v2_mean_um']<x['shipped_v1_mean_um']for x in gate['folds']),'ensemble_wins_vs_v1':sum(x['v2_ens_mean_um']<x['shipped_v1_mean_um']for x in gate['folds']),'training_rerun_this_round':False,'capture_files':len(list((hd/'capture').rglob('*.npz'))),'training_metric':'displacement error, not relation recovery or leaderboard score'})
# Earlier sixteen-movie local smoother replay: all declared raw/repaired/expected arrays.
hist=OLD/'10_长期研究推进/2026-10-02_启动';vd=D/'16片局部重放_历史证据';source=S/'SVM5/research/heterogeneity';s4=S/'SVM4'
copy(hist/'09_历史执行脚本/01_实验分析与软件构建/replay_variance_estimator.py',vd/'archival_runner.py')
copy(hist/'03_方法框架与专项分析/intervention_registry_v0.1/variance_replay_v0.1/replay_report.json',vd/'historical_report.json')
deps=[source/'heterogeneous_estimator.py']+[s4/x for x in ['trajectory_estimator.py','axis_trajectory.py','coupled_trajectory.py','shared_motion_estimator.py']]
for p in deps:copy(p,vd/'sources'/p.name)
records=json.loads((source/'validation/manifest.json').read_text(encoding='utf8'))['films'];inputs=[]
for record in records:
    film,split=record['stem'],record['split'];base=vd/'inputs'/film;base.mkdir(parents=True,exist_ok=True)
    if split=='development':
        raw=S/'research/target095/current_baseline'/film/'raw.npz';repaired=S/'research/target095/event_completion_active'/(film+'.npz')
        with np.load(raw,allow_pickle=False)as z:ids0,coords0=z['ids'],z['coords']
    else:
        repaired=s4/'transfer_assets/event/validation_graphs/event_completion'/(film+'.npz');matches=list((s4/'transfer_assets/raw/tracking_repo/predictions').glob('*/unet_transformer/split_0/'+film+'.geff'));assert len(matches)==1;raw=matches[0];g=zarr.open_group(str(raw),mode='r');ids0=g['nodes/ids'][:];coords0=np.column_stack([g['nodes/props/'+k+'/values'][:]for k in ['t','z','y','x']])
    np.savez_compressed(base/'native_coordinates.npz',ids=ids0,coords=coords0)
    copy(repaired,base/'repaired_graph.npz');copy(source/'validation'/(film+'.npz'),base/'expected.npz')
    inputs.append({'film':film,'split':split,'native_source':str(raw),'repaired_source':str(repaired),'input_folder':str(base.relative_to(vd)),'coordinate_unit':'full_resolution_pixels'})
save(vd/'INPUTS.json',inputs)
old=json.loads((vd/'historical_report.json').read_text(encoding='utf8'));expected={Path(p).name:h for p,h in old['dependency_hashes'].items()};checks={p.name:hashlib.sha256(p.read_bytes()).hexdigest()==expected[p.name]for p in deps};assert all(checks.values())
save(vd/'核验.json',{'historical_films':len(old['films']),'historical_all_arrays_exact':old['all_arrays_exact'],'all_declared_inputs_packaged':len(inputs)==16,'five_dependencies_match_historical_hashes':checks,'historical_scope':old['scope'],'new_training_or_full_pipeline_inference':False})
# Sampling contract and real source, no resampling.
plan=S/'research/target095/kaggle_event_validator/output/validation_plan.json';copy(plan,D/'迁移样本选择/validation_plan.json')
selection=S/'research/target095/kaggle_event_validator/build_private_validator.py'
if selection.exists():copy(selection,D/'迁移样本选择/build_private_validator.py')
copy(U/'04_审阅软件包/software/LICENSE',R/'src/reference_backend/LICENSE')
save(D/'TARGETED_EVIDENCE_FILES.json',manifest)
print(json.dumps({'copied_files':len(manifest),'copied_MB':sum(x['bytes']for x in manifest)/1e6,'endpoint_control':'PASS','negative_folds':4,'variance_inputs':len(inputs),'five_dependency_hashes_match':all(checks.values())},ensure_ascii=False))
