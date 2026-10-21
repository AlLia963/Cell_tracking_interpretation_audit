from pathlib import Path
from collections import Counter,defaultdict
import csv,json,re,sqlite3
R=Path('D:/1013工作大修');O=R/'02_实验身份与谱系'
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def csvout(p,rs):
    with p.open('w',encoding='utf-8-sig',newline='')as f:
        w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
def norm(s):return re.sub('[^a-z0-9]+','',s.lower())
nb=rows(O/'NOTEBOOK_IDENTITIES.csv');kernels=rows(O/'KERNEL_IDENTITIES.csv');old=rows(R/'01_输入清册/kaggle_submissions_parsed.csv');new=rows(R/'01_输入清册/用户分数表_125条.csv')
by_path={str(Path(x['path'])).lower():x for x in nb};candidates=[]
for x in nb:candidates.append((norm(Path(x['name']).stem),x,'notebook_filename'))
for k in kernels:
    p=str(Path(k['path']).parent/k['code_file']).lower();n=by_path.get(p)
    if n:candidates.append((norm(k['title']),n,'kernel_metadata_title'))
out=[];links=[]
generic={'biohubcelltracking','submissioncsv','notebook3b14dda268'}
for r in new:
    name=norm(r['name']);hits=[];mode='unresolved_source_identity'
    if name not in generic:
        exact=[(n,why)for key,n,why in candidates if key==name]
        if exact:hits=exact;mode='exact_title_or_filename_candidate'
        elif len(name)>=18:
            hits=[(n,why)for key,n,why in candidates if (key.startswith(name)or name.startswith(key))and min(len(name),len(key))>=18]
            if hits:mode='truncated_title_candidate'
    if not hits and r['tag']:
        tokens=re.findall(r'v\d+(?:\.\d+)+(?:\s*R[12])?|vk\d+',r['tag'],re.I)
        for tok in tokens:
            pattern=r'(?<![a-z0-9])'+re.escape(tok.split()[0])+r'(?![.\d])'
            hits += [(n,'author_tag_matches_filename')for n in nb if re.search(pattern,n['name'],re.I)]
        if hits:mode='author_tag_source_candidate'
    unique={n['file_id']:(n,why)for n,why in hits};identities=sorted({n['identity']for n,why in unique.values()})
    oldhits=[x for x in old if norm(x['name'])==name and x['version']==r['version_label'] and x['author']==r['account'] and x['status']==r['status']]
    for n,why in unique.values():links.append({'score_row':r['source_row'],'notebook_file_id':n['file_id'],'notebook_identity':n['identity'],'basis':why,'path':n['path'],'is_verified_execution_to_submission_binding':False})
    out.append({**r,'old_103_table_matching_rows':len(oldhits),'old_public_scores':';'.join(sorted({x['score']for x in oldhits if x['score']})),
      'source_link_status':mode,'candidate_notebook_files':len(unique),'candidate_source_identities':len(identities),'candidate_file_ids':';'.join(unique),
      'exact_execution_id':'not_in_author_score_text','exact_submission_id':'not_in_author_score_text',
      'current_use':'historical_score_evidence; source candidates require execution/output binding'})
csvout(O/'SCORE_RUN_SOURCE_CROSSWALK.csv',out);csvout(O/'SCORE_SOURCE_CANDIDATE_EDGES.csv',links)
# Every original score/lineage record remains separately addressable; no overwrite by rounded markers.
coverage=[]
for fn in ['kaggle_submissions_parsed.csv','cell_lineage_versions.csv','master_experiment_table.csv']:
    for i,x in enumerate(rows(R/'01_输入清册'/fn),1):
        text=' '.join(str(v)for v in x.values());named=x.get('name',x.get('Stem',x.get('Variant','')))
        matches=[r['source_row']for r in new if norm(r['name'])==norm(named)]
        stems=[n['file_id']for n in nb if norm(Path(n['name']).stem)==norm(named)]
        coverage.append({'source_table':fn,'row':i,'record_name':named,'new_score_rows':';'.join(matches),'notebook_file_ids':';'.join(stems),
                         'status':'crosslinked_by_exact_name'if matches or stems else'preserved_context_or_unresolved_alias','original_record_json':json.dumps(x,ensure_ascii=False)})
csvout(O/'OLD_LEDGER_COVERAGE.csv',coverage)
summary={'raw_score_rows':len(out),'source_link_status':dict(Counter(x['source_link_status']for x in out)),
 'rows_with_source_candidates':sum(x['candidate_notebook_files']>0 for x in out),'rows_with_exact_old_record_keys':sum(x['old_103_table_matching_rows']>0 for x in out),
 'old_ledger_rows_preserved':len(coverage),'missing_submission_ids':len(out),'identical_text_candidates_not_deleted':True,
 'candidate_links_not_promoted_to_verified_execution':True}
(O/'SCORE_CROSSWALK_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(summary,ensure_ascii=False))
