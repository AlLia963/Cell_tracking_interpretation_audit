"""Summarize observed fixed outputs without inflating independent units."""
from pathlib import Path
from collections import Counter,defaultdict
import csv,json,gzip
import numpy as np
import audit_engine as E
R=Path(__file__).resolve().parents[1];O=R/'04_统一重分析';D=R/'06_结果与交付';D.mkdir(exist_ok=True)
def jl(p):return [json.loads(x)for x in p.read_text(encoding='utf8').splitlines()]
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
assets=jl(O/'ASSET_ADMISSION.jsonl');aliases=jl(O/'GRAPH_ALIASES.jsonl');index=jl(O/'GRAPH_INDEX.jsonl');byid={x['graph_id']:x for x in index};byasset={x['asset_id']:x for x in assets};summaries=jl(O/'GRAPH_AUDIT_SUMMARIES.jsonl');exceptions=jl(O/'QUERY_EXCEPTIONS.jsonl')
links=defaultdict(list)
for a in aliases:links[a['graph_id']].append(a)
groups={'all_saved_graphs':set(byid)}
for kind in ['csv','npz','npz_implicit','geff']:
    groups[kind]={a['graph_id']for a in aliases if byasset[a['asset_id']]['kind']==kind}
groups['early_cell_csv']={a['graph_id']for a in aliases if byasset[a['asset_id']]['kind']=='csv' and byasset[a['asset_id']]['root']=='cell'}
effect={}
for name,gids in groups.items():
    strict=[x for x in exceptions if x['graph_id']in gids and x.get('strict_relaxation_difference')]
    record={'graphs':len(gids),'movies':len({byid[g]['film']for g in gids}),'strict_reports':len(strict)}
    for k in ['path','fork']:
        qs=[x for x in strict if x['kind']==k];record[k]={'reports':len(qs),'distinct_movie_query_identities':len({(x['film'],tuple(x['reference_nodes']))for x in qs}),'affected_movies':len({x['film']for x in qs})}
    record['distinct_movie_query_identities']=len({(x['film'],x['kind'],tuple(x['reference_nodes']))for x in strict});record['affected_movies']=len({x['film']for x in strict});effect[name]=record
save(D/'NATURAL_EFFECT_DENOMINATORS.json',effect)
framecounts=Counter();fallback=[];locators=set();fallback_seen=set()
for row in summaries:
    assert row['ordinary_equal_frames']==row['reference_frames'] and row['ordinary_withheld_frames']==0 and row['status']=='COMPLETE'
    s=E.read_json_gz(O/'graph_reports'/(row['graph_id']+'.json.gz'));locators.update(s['frame_locators'].values())
    if row['ordinary_seed_fallback_frames']:
        for locator in s['frame_locators'].values():
            if locator in fallback_seen:continue
            f=E.read_json_gz(O/'frame_cache'/locator)
            if f.get('seed_fallback'):fallback_seen.add(locator);fallback.append({'film':f['film'],'frame':f['frame'],'cache':'frame_cache/'+locator,**f['seed_fallback']})
frames=len(locators);framecounts.update({'producer:COMPLETE':frames,'ordinary:EXACT_COMPLETE_FAMILY_EQUAL':frames})
save(D/'COMPLETE_FAMILY_CHECKS.json',{'unique_geometry_frames':frames,'counts':dict(framecounts),'fallback_frames':fallback,'fallback_count':len(fallback),'fallback_shares_seed_not_independent_producer_construction':True,'count_basis':'Deduplicated referenced frame locators; each graph already checks ordinary_equal_frames == reference_frames and zero withholds. Unreferenced cache files excluded.'})
# All 283 implicit-ID inputs are checked against their saved CSV sibling.
csv_assets=[a for a in assets if a['kind']=='csv'and a.get('accepted')];parity=[]
for a in assets:
    if a['kind']!='npz_implicit'or not a.get('accepted'):continue
    folder=Path(a['path']).parent.parent;match=[b for b in csv_assets if Path(b['path']).parent==folder]
    for item in a['accepted']:
        for b in match:
            target=next((x for x in b['accepted']if x['film']==item['film']),None)
            if target:
                g=E.load_graph(O/byid[item['graph_id']]['path']);h=E.load_graph(O/byid[target['graph_id']]['path'])
                parity.append({'npz_asset':a['asset_id'],'csv_asset':b['asset_id'],'film':item['film'],'same_normalized_graph':item['graph_id']==target['graph_id'],'ids_equal':np.array_equal(g.ids,h.ids),'coords_equal':np.array_equal(g.coords,h.coords),'edges_equal':np.array_equal(g.edges,h.edges)})
save(D/'IMPLICIT_NODE_ID_PARITY.json',{'records':parity,'checked':len(parity),'all_equal':all(x['same_normalized_graph']for x in parity)})
# Real early witnesses, one path and one fork. This is a case export, not case selection for counts.
cases=[]
for kind in ['path','fork']:
    candidates=[q for q in exceptions if q['kind']==kind and q.get('strict_relaxation_difference')and q['graph_id']in groups['early_cell_csv']]
    if not candidates:continue
    q=sorted(candidates,key=lambda x:(x['film'],x['graph_id'],x['reference_nodes']))[0];gid=q['graph_id'];s=E.read_json_gz(O/'graph_reports'/(gid+'.json.gz'));g=E.load_graph(O/byid[gid]['path']);ref=E.load_graph(O/'references'/(q['film']+'.npz'));frames={t:E.read_json_gz(O/'frame_cache'/s['frame_locators'][str(t)])for t in q['frames']}
    mapped=set(p for f in frames.values()for w in f['worlds']for n,p in w.items()if n in q['reference_nodes']);neighbours={int(p)for e in g.edges if any(int(v)in mapped for v in e)for p in e}|mapped
    cases.append({'query':q,'source_aliases':links[gid],'reference_coordinates':{str(int(n)):c.tolist()for n,c in zip(ref.ids,ref.coords)if n in q['reference_nodes']},'predicted_coordinates':{str(int(n)):c.tolist()for n,c in zip(g.ids,g.coords)if int(n)in neighbours},'actual_predicted_relations':[e.tolist()for e in g.edges if any(int(v)in mapped for v in e)],'projected_whole_frame_alternatives':{str(t):[{str(n):w.get(n)for n in q['reference_nodes']if n in f['reference_ids']}for w in f['worlds']]for t,f in frames.items()},'whole_family_evidence':{str(t):s['frame_locators'][str(t)]for t in q['frames']},'unit':'um'})
save(D/'EARLY_REAL_SHARED_CORRESPONDENCE_CASES.json',cases)
rejected=[a for a in assets if a['status']!='ADMITTED_SAVED_GRAPH_PRIMITIVES'];save(D/'INPUT_WITHHOLDS_COMPLETE.json',rejected)
save(D/'CORPUS_SYNTHESIS.json',{'asset_statuses':dict(Counter(a['status']for a in assets)),'scientific_readout_not_leaderboard_score':True,'natural_effects':effect,'implicit_parity_checked':len(parity),'implicit_parity_all_equal':all(x['same_normalized_graph']for x in parity),'family_checks':dict(framecounts),'unique_geometry_frames':frames,'seed_fallbacks':len(fallback)})
print(json.dumps({'effect':effect,'parity_checks':len(parity),'parity_equal':all(x['same_normalized_graph']for x in parity),'framecounts':dict(framecounts),'fallback_count':len(fallback)},ensure_ascii=False),flush=True)
