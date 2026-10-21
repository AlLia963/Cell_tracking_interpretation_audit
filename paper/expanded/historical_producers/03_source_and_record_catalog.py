from pathlib import Path
from collections import defaultdict,Counter
import ast,csv,hashlib,json,re,sqlite3
R=Path('D:/1013工作大修');O=R/'02_实验身份与谱系';db=sqlite3.connect(R/'01_输入清册/FILES.sqlite');db.row_factory=sqlite3.Row
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str),encoding='utf8')
def csvout(name,rows):
    if not rows:
        (O/name).write_text('file_id,path,parse_status\n',encoding='utf-8-sig');return
    with (O/name).open('w',encoding='utf-8-sig',newline='')as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
reg=list(csv.DictReader((R/'01_输入清册/旧330条notebook清册.csv').open(encoding='utf-8-sig')))
registry={}
for x in reg:
    rel=x['RelDir'].replace('\\','/')
    if rel.lower()==x['Copy'].lower():rel=''
    if rel.lower().startswith(x['Copy'].lower()+'/'):rel=rel[len(x['Copy'])+1:]
    registry[(x['Copy'],('/'.join([v for v in [rel,x['Notebook']]if v])).lower())]=x
mechanisms={
 'detection_prior':r'deepcenter|detector|det_threshold|heatmap|unet3d|center_prior',
 'multi_source_augmentation':r'secondary_|dual_seed|feature.*tta|bidirectional|harmonic|dctta|ensemble',
 'association_constraint':r'ilp_|linear_sum_assignment|motion_relink|edge_candidate|reciprocal|arbitrat|association',
 'gap_endpoint_repair':r'gap_close|gap_clos|endpoint|readmit|missing.*frame|repair',
 'division_event':r'division|mother|daughter|fork|branch|event_consensus',
 'coordinate_trajectory':r'linefit|trajectory|registration|shared_motion|coordinate|smooth|variance|axis_',
 'execution_contract':r'time_budget|budget_seconds|timeout|fallback|round_coords|submission|MAX.*SECONDS|memory'}
notebooks=[];details=[];errors=[]
for f in db.execute("select * from files where category='notebook' and root in ('cell','TRANSDATA','IWS') order by root,relative_path"):
    p=Path(f['path']);old=registry.get((f['root'],f['relative_path'].lower()))
    try:j=json.loads(p.read_text(encoding='utf-8-sig'))
    except Exception as e:errors.append({'path':str(p),'error':repr(e)});continue
    codes=[(i,''.join(c.get('source',[])))for i,c in enumerate(j.get('cells',[]))if c.get('cell_type')=='code']
    source='\n'.join(x for i,x in codes);functions=[];configs=[];parents=[];hits={}
    for mi,pat in mechanisms.items():
        values=[]
        for ci,s in codes:
            for li,line in enumerate(s.splitlines(),1):
                if re.search(pat,line,re.I):values.append({'cell_index':ci,'line':li,'excerpt':line.strip()[:220]})
        if values:hits[mi]=values[:12]
    for ci,s in codes:
        functions += [{'cell':ci,'name':m.group(1)}for m in re.finditer(r'^\s*def\s+(\w+)\s*\(',s,re.M)]
        parents += re.findall(r'[\w./\\ -]+\.ipynb',s)
        cleaned='\n'.join('pass' if l.lstrip().startswith(('!','%'))else l for l in s.splitlines())
        try:tree=ast.parse(cleaned)
        except SyntaxError:continue
        for n in ast.walk(tree):
            if not isinstance(n,ast.Assign)or len(n.targets)!=1:continue
            target=ast.unparse(n.targets[0])
            if not ('environ['in target or re.fullmatch(r'[A-Z][A-Z0-9_]{2,}',target)):continue
            try:value=ast.literal_eval(n.value)
            except (ValueError,TypeError):continue
            if len(repr(value))>300:continue
            configs.append({'cell':ci,'line':n.lineno,'target':target,'value':value,'execution_not_inferred_from_presence':True})
    identity=('old-sha16:'+old['SHA16'])if old else'new-file-sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
    role=old['Class']if old else ('community_or_reference_candidate' if any(x in str(p).lower()for x in ['community','社区','02_base','community_top'])else'author_candidate')
    row={'file_id':f['id'],'root':f['root'],'relative_path':f['relative_path'],'path':str(p),'name':p.name,'identity':identity,
      'identity_basis':'existing_registry_not_rehashed'if old else'previously_unindexed_file_hashed_once','role':role,
      'code_cells':len(codes),'cells_with_outputs':sum(bool(c.get('outputs'))for c in j['cells']if c.get('cell_type')=='code'),
      'mechanisms_present':';'.join(hits),'original_registry_has_output':old['HasOutput']if old else'',
      'original_registry_submissions':old['SubRel']if old else'','source_only_role_not_actual_execution':True}
    notebooks.append(row);details.append({'file_id':f['id'],'source_mechanism_evidence':hits,'functions':functions,'literal_configuration':configs,'notebook_path_mentions':sorted(set(parents)),'metadata':{k:v for k,v in j.get('metadata',{}).items()if k in ['kernelspec','language_info','kaggle']}})
csvout('NOTEBOOK_IDENTITIES.csv',notebooks);dump(O/'NOTEBOOK_CODE_EVIDENCE.json',details)
assert len(notebooks)==419
# Retain metadata documents as evidence records; they are not counted as independent completed runs.
records=[];kernel=[];runtime=[];record_errors=[]
names={'kernel-metadata.json','push_receipt.txt','runtime_manifest.json','SNAPSHOT_MANIFEST.json','ARTIFACT_MANIFEST.json','svm4_manifest.json','svm2_manifest.json','svm5_manifest.json','sdy_manifest.json','build_manifest.json','release_manifest.json','validation_plan.json','plan.json','receipt.json','read_receipt.json'}
for f in db.execute("select * from files where root in ('cell','TRANSDATA','IWS') and extension in ('.json','.txt') order by id"):
    if f['name']not in names and not any(t in f['name'].lower()for t in ['manifest','receipt','run_complete','run_start']):continue
    if f['bytes']>10_000_000:continue
    p=Path(f['path'])
    try:j=json.loads(p.read_text(encoding='utf-8-sig'))
    except Exception as e:record_errors.append({'file_id':f['id'],'path':str(p),'parse_status':type(e).__name__});continue
    if not isinstance(j,dict):continue
    selected={k:j[k]for k in j if k.lower()in ['id','title','code_file','kernel_type','kernelid','versionnumber','ref','status','operation','scope','parent','parent_sha256','source','source_kernel','notebook','notebook_sha256','qualification','new_biological_n','returncode','variant','training_overlap','selection']}
    records.append({'file_id':f['id'],'root':f['root'],'path':str(p),'name':f['name'],'top_level_keys':list(j),'identity_and_scope':selected})
    if f['name']=='kernel-metadata.json':kernel.append({'file_id':f['id'],'path':str(p),'kernel_id':j.get('id',''),'title':j.get('title',''),'code_file':j.get('code_file',''),'kernel_type':j.get('kernel_type',''),'local_code_exists':(p.parent/str(j.get('code_file',''))).is_file()})
    if f['name']=='runtime_manifest.json':runtime.append({'file_id':f['id'],'path':str(p),'parent':j.get('parent',''),'parent_sha256':j.get('parent_sha256',''),'qualification':j.get('qualification',''),'manifest_alone_does_not_prove_completion':True})
dump(O/'ORIGINAL_EXECUTION_METADATA.json',records);csvout('KERNEL_IDENTITIES.csv',kernel);csvout('LOCAL_RUNTIME_PARENT_RECORDS.csv',runtime)
csvout('METADATA_PARSE_EXCEPTIONS.csv',record_errors)
summ={'notebook_file_copies':len(notebooks),'identity_groups_within_available_pins':len({n['identity']for n in notebooks}),
 'old_registry_reused':sum(n['identity_basis']=='existing_registry_not_rehashed'for n in notebooks),'newly_identified_file_copies':sum(n['identity_basis']!='existing_registry_not_rehashed'for n in notebooks),
 'notebooks_with_embedded_outputs':sum(n['cells_with_outputs']>0 for n in notebooks),'mechanism_presence_by_files':dict(Counter(m for n in notebooks for m in n['mechanisms_present'].split(';'))),
 'kernel_metadata_files':len(kernel),'distinct_kernel_slugs':len({k['kernel_id']for k in kernel if k['kernel_id']}),'runtime_parent_records':len(runtime),'metadata_records':len(records),'parse_exceptions':len(record_errors),
 'notebook_parse_errors':errors,'identity_groups_are_not_independent_experiments':True,'code_presence_does_not_prove_enabled_execution':True}
dump(O/'SOURCE_CATALOG_SUMMARY.json',summ);print(json.dumps(summ,ensure_ascii=False))
