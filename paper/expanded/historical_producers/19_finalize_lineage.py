from pathlib import Path
from collections import Counter,defaultdict
import csv,json,re,ast,shutil
R=Path(__file__).resolve().parents[1];A=R/'01_输入清册';D=R/'02_实验身份与谱系';O=R/'04_统一重分析'
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def out(name,rr):
    with(D/name).open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
notebooks=rows(D/'NOTEBOOK_IDENTITIES.csv');disp=rows(D/'ALL_NOTEBOOK_DISPOSITIONS.csv');ar=rows(A/'ARCHIVE_SELECTED_RECORDS.csv');new=[x for x in ar if x['extension']=='.ipynb'and x['status']=='RECOVERED_IN_NEW_WORKSPACE']
tree=ast.parse((R/'src/03_source_and_record_catalog.py').read_text(encoding='utf8'));mechanisms=next(ast.literal_eval(x.value)for x in tree.body if isinstance(x,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='mechanisms'for t in x.targets))
archive_details=[]
for x in new:
    j=json.loads(Path(x['recovered_path']).read_text(encoding='utf-8-sig'));code='\n'.join(''.join(c['source'])for c in j['cells']if c['cell_type']=='code');hits=[k for k,p in mechanisms.items()if re.search(p,code,re.I)];identity='sha256-prefix16:'+x['source_identity_prefix16'];fid='archive:'+x['member_id']
    disp.append(dict(zip(disp[0],['']*len(disp[0]))));disp[-1].update(notebook_file_id=fid,identity=identity,root='IWS_archive',path=x['recovered_path'],source_role='author_candidate',existing_registry_output_links=0,adjacent_output_candidates=0,embedded_output_cells=sum(bool(c.get('outputs'))for c in j['cells']),mechanism_source_presence=';'.join(hits),disposition='archived_earlier_code_variant; exact executed output not bound',missing_or_ambiguous_execution_binding_retained=True)
    archive_details.append({**x,'source_mechanisms_present_not_execution':hits,'code_cells':sum(c['cell_type']=='code'for c in j['cells']),'function_names':sorted(set(re.findall(r'def\s+(\w+)\(',code)))})
out('ALL_NOTEBOOK_DISPOSITIONS_WITH_ARCHIVES.csv',disp);dump(D/'NEW_ARCHIVED_NOTEBOOK_CODE_EVIDENCE.json',archive_details)
assets={x['asset_id']:x for x in map(json.loads,(O/'ASSET_ADMISSION.jsonl').read_text(encoding='utf8').splitlines())};links=rows(D/'NOTEBOOK_OUTPUT_LINKS.csv');cov=[]
for d in disp:
    ll=[x for x in links if x['notebook_file_id']==d['notebook_file_id']];matched=[assets['F'+x['artifact_file_id']]for x in ll if'F'+x['artifact_file_id']in assets];films={t['film']for a in matched for t in a.get('accepted',[])};gids={t['graph_id']for a in matched for t in a.get('accepted',[])}
    cov.append({'notebook_file_id':d['notebook_file_id'],'source_identity':d['identity'],'path':d['path'],'link_count':len(ll),'admitted_asset_count':len(matched),'movies':len(films),'unique_graphs':len(gids),'asset_ids':';'.join(a['asset_id']for a in matched),'evidence_status':'registry_or_adjacent_association; not content-bound historical execution'if matched else'code_only_or_runtime_ancestor_or_exact_output_unresolved'})
out('NOTEBOOK_TO_NEW_ANALYSIS_COVERAGE.csv',cov)
matrix=[]
for mechanism in mechanisms:
    members=[d for d in disp if mechanism in d['mechanism_source_presence'].split(';')];ids={d['identity']for d in members};fids={d['notebook_file_id']for d in members};cc=[c for c in cov if c['notebook_file_id']in fids];aa={a for c in cc for a in c['asset_ids'].split(';')if a};gg={t['graph_id']for a in aa for t in assets[a].get('accepted',[])};ff={t['film']for a in aa for t in assets[a].get('accepted',[])}
    matrix.append({'mechanism':mechanism,'code_identity_groups_with_presence':len(ids),'source_file_members':len(members),'linked_admitted_assets':len(aa),'linked_graphs':len(gg),'linked_movies':len(ff),'decision':'All admissible saved outputs included; source presence does not establish activation or isolate causal contribution','source_member_ids':';'.join(sorted(fids)),'source_evidence':'NOTEBOOK_CODE_EVIDENCE.json; SOURCE_FUNCTION_SIGNATURES.json; NEW_ARCHIVED_NOTEBOOK_CODE_EVIDENCE.json'})
out('MECHANISM_COVERAGE_MATRIX.csv',matrix)
# Each historical annotation remains traceable, with source-only assertions separated.
annotations=[]
for name in ['method_change_notes_cell.csv','method_change_notes_cell_skim.csv','method_change_notes.csv']:
    for i,row in enumerate(rows(A/name),2):
        key=row.get('key','');token=key.lower();matches=[d for d in disp if re.search(r'(?<![a-z0-9])'+re.escape(token)+r'(?![a-z0-9])',d['path'].lower())]if token else[]
        annotations.append({'source_table':name,'line':i,'historical_key':key,'historical_annotation_unverified':row.get('note',''),'evidence_text':row.get('evidence',''),'malformed_extra_columns_preserved':json.dumps(row.get(None,[]),ensure_ascii=False),'source_candidates':';'.join(d['notebook_file_id']for d in matches),'disposition':'mechanism history retained; output coverage follows all-assets admission, not best-score selection','historical_causal_wording_not_adopted':True})
out('ALL_HISTORICAL_MECHANISM_DISPOSITIONS.csv',annotations)
old=Path('G:/kaggle论文化/论文工作区/BSPC_统一收束/10_notebook与文码一致性核查');dest=R/'05_补证与核验/既有文码回查';dest.mkdir(exist_ok=True)
for name in ['CURRENT_NOTEBOOK_LINEAGE.csv','CLAIM_CODE_AUDIT.csv','CLAIM_CODE_AUDIT.json','NOTEBOOK_LINEAGE_FINDINGS.json','HISTORICAL_DELIVERY_COVERAGE.json','READ_ONLY_AUDIT_RECEIPT.json']:shutil.copy2(old/name,dest/name)
summary={'loose_notebook_files':419,'loose_content_identity_groups':351,'new_archive_identity_groups':len(new),'total_available_identity_groups':len({x['identity']for x in disp}),'file_dispositions_with_new_archives':len(disp),'notebook_file_associations_with_admitted_outputs':sum(x['admitted_asset_count']>0 for x in cov),'associated_source_identity_groups':len({x['source_identity']for x in cov if x['admitted_asset_count']>0}),'mechanism_annotations_retained':len(annotations),'source_output_association_edges':len(links),'exact_total_executions':'unresolved; 128 official submission identities and 82 runtime manifests are different, overlapping units','article_current_direct_author_notebook_outputs':3,'article_current_author_notebook_code_source':1,'no_retroactive_claim_article_uses_all_notebooks':True}
dump(D/'FINAL_LINEAGE_COUNTS.json',summary);print(json.dumps(summary,ensure_ascii=False))
