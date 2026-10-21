from pathlib import Path
import json,csv
import replay_record as V
R=Path(__file__).resolve().parents[1];O=R/'04_统一重分析';D=R/'05_补证与核验/新增结果针对性复核';D.mkdir(exist_ok=True);results=[]
cases=json.loads((R/'06_结果与交付/EARLY_REAL_SHARED_CORRESPONDENCE_CASES.json').read_text(encoding='utf8'))
for case in cases:
    q=case['query'];results.append(V.replay_query(q['graph_id'],q['kind'],q['query_index']))
pairs=list(csv.DictReader((O/'paired/ALL_WITHIN_MOVIE_PAIRS.csv').open(encoding='utf-8-sig')));chosen=[];seen=set()
for row in pairs:
    if row['strict_coupling_narrowing']=='True'and row['film']not in seen:
        chosen.append(row);seen.add(row['film'])
        if len(chosen)==8:break
chosen += [r for r in pairs if not r['status'].startswith('COMPLETE')]
for row in chosen:results.append({'source_witness':row['witness_record'],**V.replay_pair(row['witness_record'])})
assert len(cases)==2 and len(chosen)==9 and all(r['status']=='PASS'for r in results)
(D/'RESULT.json').write_text(json.dumps({'status':'PASS','checks':results,'fresh_real_query_families':len(cases),'full_primitive_pair_endpoint_replays':8,'real_pair_refusal_recomputed':1,'scope':'Targeted checks plus exhaustive in-engine checks, not a new independent reviewer'},ensure_ascii=False,indent=2),encoding='utf8')
print('PASS',len(results),'targeted records')
