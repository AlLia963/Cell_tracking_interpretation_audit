from pathlib import Path
import csv,json,hashlib,shutil,subprocess,sys
R=Path(__file__).resolve().parents[1];D=R/'06_结果与交付';H=R/'05_补证与核验/四折负结果_历史证据';base=Path('D:/CELL数据暂存/IWS（只读勿动）/0929最后一次提交窗口');weight=base/'0929最后一次补充社区组/biohub v1284 head s075/v1284_head.pt';shutil.copy2(weight,H/'shipped_v1_head.pt')
gate=json.loads((H/'head_v2_gate.json').read_text(encoding='utf8'));inputs=[]
for fold in gate['folds']:
    film=fold['holdout'];source=Path('D:/CELL数据暂存/cell（只读勿动）/gt_data/full/train')/(film+'.geff');target=H/'reference_train'/(film+'.geff');shutil.copytree(source,target,dirs_exist_ok=True);inputs.append({'film':film,'reference':str(target.relative_to(H)),'capture':str(Path('capture')/film)})
(H/'HISTORICAL_TRAINING_INPUT_MAP.json').write_text(json.dumps({'shipped_v1_source':str(weight),'shipped_v1_local':'shipped_v1_head.pt','shipped_v1_sha256':hashlib.sha256((H/'shipped_v1_head.pt').read_bytes()).hexdigest(),'films':inputs,'original_train_script_absolute_paths_require_explicit_adapter_before_execution':True,'torch_training_environment_not_rebuilt_this_round':True},ensure_ascii=False,indent=2),encoding='utf8')
# Ensure exact-source final binding includes newly added scripts only; no repeat input hashes.
bind=D/'NEW_SOURCE_AND_INPUT_BINDINGS.json';b=json.loads(bind.read_text(encoding='utf8'));known={x['path']for x in b['files']};added=0
for p in (R/'src').rglob('*.py'):
    name=str(p.relative_to(R))
    if name not in known:b['files'].append({'path':name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()});added+=1
for item in b['files']:
    if item['path']==str(Path(__file__).relative_to(R)):
        item.update(bytes=Path(__file__).stat().st_size,sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
bind.write_text(json.dumps(b,ensure_ascii=False,indent=2),encoding='utf8')
# Source and deliverable checks, not a second all-input hash pass.
source_checks=[]
for item in b['files']:
    if item['path'].startswith('src'):
        p=R/item['path'];source_checks.append(hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'])
assert all(source_checks)
mapping=list(csv.DictReader((D/'文章证据映射.csv').open(encoding='utf-8-sig')));assert len(mapping)==14 and all(None not in x for x in mapping)
essential=[R/'README.txt',D/'阅读入口与第1至4步结果.txt',R/'03_研究范围与协议/贡献与范围重构决定.txt',D/'STEPS_1_TO_4_ACCEPTANCE.json',D/'ALL_ASSET_COHORT_RESULTS.csv',D/'FOCUSED_COHORT_CONTRASTS.json',R/'requirements.txt'];assert all(p.stat().st_size>0 for p in essential)
repo=Path('G:/kaggle论文化/论文工作区/BSPC_统一收束/04_审阅软件包/software');state=subprocess.check_output(['git','-C',str(repo),'status','--porcelain'],text=True);head=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip();assert not state
result={'status':'PASS','essential_deliverables':len(essential),'claim_evidence_rows':len(mapping),'source_binding_checks':len(source_checks),'source_bindings_added':added,'old_repository_clean':True,'old_repository_head':head,'new_workspace_only':True,'historical_head_shipped_weight_and_four_references_packaged':True,'no_new_training':True,'not_a_manuscript_or_submission_acceptance':True}
(D/'FINAL_DELIVERY_CHECK.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result,ensure_ascii=False))
