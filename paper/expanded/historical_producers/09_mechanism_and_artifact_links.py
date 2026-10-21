from pathlib import Path
from collections import Counter,defaultdict
import ast,csv,json,re,hashlib,sqlite3,shutil,os
R=Path('D:/1013工作大修');O=R/'02_实验身份与谱系';db=sqlite3.connect(R/'01_输入清册/FILES.sqlite');db.row_factory=sqlite3.Row
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
def out(name,rs):
    with (O/name).open('w',encoding='utf-8-sig',newline='')as f:
        w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
nb=rows(O/'NOTEBOOK_IDENTITIES.csv');nbyid={x['file_id']:x for x in nb}
allfiles={str(Path(x['path'])).lower():dict(x)for x in db.execute('select id,path,category,bytes from files')}
submission_files=[(key,f)for key,f in allfiles.items()if f['category']=='prediction_submission']
aliases=[];dispositions=[]
prefix={'cell':Path('D:/CELL数据暂存/cell（只读勿动）'),'TRANSDATA':Path('D:/CELL数据暂存/TRANSDATA（只读勿动）'),'IWS':Path('D:/CELL数据暂存/IWS（只读勿动）')}
for n in nb:
    direct=[]
    for rel in n['original_registry_submissions'].split(';'):
        bits=rel.replace('\\','/').split('/')
        if bits and bits[0]in prefix:
            p=prefix[bits[0]].joinpath(*bits[1:]);hit=allfiles.get(str(p).lower())
            if hit:direct.append(hit);aliases.append({'notebook_file_id':n['file_id'],'artifact_file_id':hit['id'],'basis':'existing_registry_output_link','artifact':hit['path'],'execution_source_hash_match_not_asserted':True})
    parent=Path(n['path']).parent
    output_prefix=str(parent/'output').lower()+os.sep.lower()
    adjacent=[f for key,f in submission_files if key.startswith(output_prefix)]if parent!=prefix[n['root']]else[]
    for f in adjacent:
        if f['id']not in {x['id']for x in direct}:aliases.append({'notebook_file_id':n['file_id'],'artifact_file_id':f['id'],'basis':'same_notebook_directory_output_candidate','artifact':f['path'],'execution_source_hash_match_not_asserted':True})
    dispositions.append({'notebook_file_id':n['file_id'],'identity':n['identity'],'root':n['root'],'path':n['path'],'source_role':n['role'],
                         'existing_registry_output_links':len(direct),'adjacent_output_candidates':len(adjacent),'embedded_output_cells':n['cells_with_outputs'],
                         'mechanism_source_presence':n['mechanisms_present'],'disposition':'retained_result_source_candidate'if direct or adjacent else'code_or_runtime_ancestor_or_output_not_located',
                         'missing_or_ambiguous_execution_binding_retained':True})
out('NOTEBOOK_OUTPUT_LINKS.csv',aliases);out('ALL_NOTEBOOK_DISPOSITIONS.csv',dispositions)

signatures={};parse=[]
for n in nb:
    ident=n['identity']
    if ident in signatures:continue
    j=json.loads(Path(n['path']).read_text(encoding='utf-8-sig'));funcs=defaultdict(list);cfg=defaultdict(list)
    for ci,c in enumerate(j['cells']):
        if c['cell_type']!='code':continue
        src=''.join(c['source']);src='\n'.join('pass'if s.lstrip().startswith(('!','%'))else s for s in src.splitlines())
        try:tree=ast.parse(src)
        except SyntaxError:parse.append({'file_id':n['file_id'],'cell':ci,'scope':'non-Python/magic cell not used in AST comparison'});continue
        units=[('cell'+str(ci),tree)]
        for idx,node in enumerate(ast.walk(tree)):
            if isinstance(node,ast.Constant)and isinstance(node.value,str)and'def 'in node.value and len(node.value)>100:
                try:units.append((f'cell{ci}/embedded{idx}',ast.parse(node.value)))
                except SyntaxError:pass
        for scope,unit in units:
            for node in ast.walk(unit):
                if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    funcs[node.name].append(hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest())
                if isinstance(node,ast.keyword) and node.arg:
                    try:v=ast.literal_eval(node.value)
                    except (TypeError,ValueError):continue
                    if len(repr(v))<300:cfg['keyword:'+node.arg].append(repr(v))
                if isinstance(node,ast.AnnAssign) and node.value is not None:
                    try:v=ast.literal_eval(node.value)
                    except (TypeError,ValueError):continue
                    if len(repr(v))<300:cfg['annotated:'+ast.unparse(node.target)].append(repr(v))
                if isinstance(node,ast.Assign)and len(node.targets)==1:
                    key=ast.unparse(node.targets[0])
                    if 'environ['not in key and not re.fullmatch('[A-Z][A-Z0-9_]{2,}',key):continue
                    try:v=ast.literal_eval(node.value)
                    except (TypeError,ValueError):continue
                    if len(repr(v))<300:cfg[key].append(repr(v))
    signatures[ident]={'representative_file_id':n['file_id'],'functions':{k:sorted(set(v))for k,v in funcs.items()},'literal_occurrences':{k:sorted(set(v))for k,v in cfg.items()}}
dump(O/'SOURCE_FUNCTION_SIGNATURES.json',signatures);dump(O/'SOURCE_PARSE_SCOPES.json',parse)
pairs=[('v5.1','v5.2'),('v5.2','v5.2.1'),('v5.3','v5.4'),('v5.6','v5.7'),('v5.7','v5.8'),('v6.0','v7.0'),('v7.0','v7.1'),('v7.1','v7.2'),('v7.2','v7.3'),('v7.3','v7.4'),('v7.3','v7.5'),('v7.5','v7.6'),('v7.6','v7.7'),('v7.7','v7.8'),('v8.0','v8.1'),('v8.1','v8.2'),('v8.2','v8.3'),('v8.2','v9.0'),('v9.0','v9.1'),('v9.1','v9.2'),('v9.3','v9.4')]
def choose(ver,cv=False):
    tail=ver+('_CV'if cv else'')+'.ipynb'
    found=[n for n in nb if n['root']=='cell'and n['name'].lower().endswith('_'+tail.lower())]
    return sorted(found,key=lambda x:(len(x['relative_path']),x['relative_path']))[0]if found else None
diffs=[]
for a,b in pairs:
 for cv in [False,True]:
    x,y=choose(a,cv),choose(b,cv)
    if not x or not y:continue
    u,v=signatures[x['identity']],signatures[y['identity']]
    changed=[k for k in set(u['functions'])|set(v['functions'])if u['functions'].get(k)!=v['functions'].get(k)]
    configs=[{'key':k,'before':u['literal_occurrences'].get(k),'after':v['literal_occurrences'].get(k)}for k in sorted(set(u['literal_occurrences'])|set(v['literal_occurrences']))if u['literal_occurrences'].get(k)!=v['literal_occurrences'].get(k)]
    diffs.append({'before':a,'after':b,'CV_not_submitted':cv,'before_file_id':x['file_id'],'after_file_id':y['file_id'],'changed_function_definitions':sorted(changed),'literal_differences':configs,
                  'scope':'Static implementation comparison; named sequence is a comparison design, not proof of single-factor intervention or exact historical parentage'})
dump(O/'EARLY_IMPLEMENTATION_COMPARISONS.json',diffs)
# Existing author-confirmed mainline mapping is stronger than matching a vague tag.
maps=rows(R/'01_输入清册/cell_official_scores_mysubmissions.csv');scores=rows(O/'SCORE_RUN_SOURCE_CROSSWALK.csv')
for s in scores:
    hit=[m for m in maps if m['name']==s['name']and m['version']==s['version_label']and m['author']==s['account']and m['status']==s['status']]
    ids={n['file_id']for m in hit for n in nb if Path(n['name']).stem==m['mapped_stem']}
    s['author_confirmed_mainline_map_file_ids']=';'.join(sorted(ids,key=int))
    s['author_confirmed_mainline_map_scope']='Historical author confirmation; CV/measure variants are not leaderboard submissions'if hit else''
out('SCORE_RUN_SOURCE_CROSSWALK.csv',scores)
# The supplied handoff's 41 steps are historical records, not 41 new independent experiments.
handoff=(R/'01_输入清册/前置对话_完整工作路线参考.md').read_text(encoding='utf8')
part=handoff[handoff.index('### 01. 启动计划'):handoff.index('## 完整论文评阅轮次')]
routes=[]
for m in re.finditer(r'^### (\d{2})\. (.+)\n([\s\S]*?)(?=^### |\Z)',part,re.M):
    routes.append({'historical_step':m.group(1),'title':m.group(2),'historical_record':m.group(3).strip(),'disposition':'retain existing bounded evidence; current52/30 map is a subset; no unchanged rerun','new_execution_claim':False})
dump(O/'HISTORICAL_41_STEP_COVERAGE.json',routes)
assert len(routes)==41
summary={'notebook_dispositions':len(dispositions),'notebook_output_associations':len(aliases),'source_identities_compared':len(signatures),'early_code_pairs':len(diffs),
         'historical_route_records':len(routes),'mainline_author_mapping_rows':sum(bool(s['author_confirmed_mainline_map_scope'])for s in scores),
         'scientific_causal_inference_from_names_or_code_presence':False}
dump(O/'MECHANISM_LINK_SUMMARY.json',summary);print(json.dumps(summary,ensure_ascii=False))
