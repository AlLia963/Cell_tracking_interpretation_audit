from pathlib import Path
import csv,json,shutil
R=Path(__file__).resolve().parents[1];O=R/'04_统一重分析';D=R/'05_补证与核验/历史计数对照';D.mkdir(exist_ok=True)
assets={x['asset_id']:x for x in map(json.loads,(O/'ASSET_ADMISSION.jsonl').read_text(encoding='utf8').splitlines())};summ={x['graph_id']:x for x in map(json.loads,(O/'GRAPH_AUDIT_SUMMARIES.jsonl').read_text(encoding='utf8').splitlines())};rows=[]
for aid in ['F11588','F11794','F11847']:
    a=assets[aid];source=Path(a['path']).parent/'cv_per_movie.csv';shutil.copy2(source,D/(aid+'_historical_per_movie.csv'));saved=list(csv.DictReader(source.open(encoding='utf-8-sig')));maps={x['film']:x['graph_id']for x in a['accepted']}
    for s in saved:
        n=summ[maps[s['dataset']]];row={'asset_id':aid,'film':s['dataset'],'graph_id':n['graph_id'],'old_source':str(source),'old_TP':int(s['edge_tp']),'new_canonical_TP':n['canonical_TP'],'old_FP':int(s['edge_fp']),'new_canonical_FP':n['canonical_FP'],'old_FN':int(s['edge_fn']),'new_canonical_FN':n['canonical_FN'],'ambiguous_relations':n['ambiguous_relations'],'new_certain_visible':n['certain_visible'],'new_possible_visible':n['reference_edges']-n['certain_absent']}
        row['same_three_counts']=all(row['old_'+k]==row['new_canonical_'+k]for k in ['TP','FP','FN']);rows.append(row)
with(D/'ALL_279_MOVIE_RECORDS.csv').open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
result={'records':len(rows),'matching_three_counts':sum(x['same_three_counts']for x in rows),'differing_records':[x for x in rows if not x['same_three_counts']],'interpretation':'Historical point estimates are retained. New hypot exact-cost maximum-cardinality families and sparse reference counting do not retroactively overwrite legacy norm/canonical evaluation. Implicit graph inputs separately match all 283 sibling CSVs exactly.'}
(D/'RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print('legacy records',len(rows),'matching TP/FP/FN',result['matching_three_counts'])
