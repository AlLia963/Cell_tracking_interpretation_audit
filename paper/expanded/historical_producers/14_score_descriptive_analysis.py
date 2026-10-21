from pathlib import Path
from collections import Counter
from itertools import combinations
import csv,json
import numpy as np
from scipy.stats import rankdata
R=Path('D:/1013工作大修');O=R/'04_统一重分析/score_history';O.mkdir(exist_ok=True)
raw=list(csv.DictReader((R/'01_输入清册/用户分数表_125条.csv').open(encoding='utf-8-sig')))
groups={}
for r in raw:
    key=tuple(r[k]for k in ['title_raw','status','account','relative_age_verbatim','tag','private_score','public_score'])
    groups.setdefault(key,[]).append(r)
unique=[rs[0]for rs in groups.values()];scored=[r for r in unique if r['private_score']and r['public_score']]
def describe(rows):
    if len(rows)<2:return {'records':len(rows)}
    x=np.array([float(r['public_score'])for r in rows]);y=np.array([float(r['private_score'])for r in rows]);counts=Counter();inversions=[]
    for i,j in combinations(range(len(rows)),2):
        dx=x[j]-x[i];dy=y[j]-y[i]
        if dx==0 or dy==0:counts['tied_on_at_least_one_board']+=1
        elif dx*dy<0:
            counts['opposite_order']+=1;inversions.append({'row_a':rows[i]['source_row'],'row_b':rows[j]['source_row'],'public_a':x[i],'public_b':x[j],'private_a':y[i],'private_b':y[j]})
        else:counts['same_order']+=1
    return {'records':len(rows),'pair_counts':dict(counts),'spearman_descriptive':float(np.corrcoef(rankdata(x),rankdata(y))[0,1]),'inversions':inversions,
            'no_inferential_p_value_or_independent_replication_claim':True}
blocks={'all_distinct_text_scored_records':describe(scored)}
for period in sorted({r['provisional_period']for r in scored}):blocks[period]=describe([r for r in scored if r['provisional_period']==period])
api=json.loads((R/'01_输入清册/KAGGLE_SUBMISSIONS_READONLY.json').read_text(encoding='utf8'))
report={'raw_author_rows':len(raw),'distinct_text_records':len(unique),'distinct_text_scored_records':len(scored),'text_repeat_groups':[[r['source_row']for r in rs]for rs in groups.values()if len(rs)>1],
 'raw_status_counts':dict(Counter(r['status']for r in raw)),'distinct_text_status_counts':dict(Counter(r['status']for r in unique)),
 'official_readonly_api':{'submissions':len(api['records']),'distinct_refs':len({r['ref']for r in api['records']}),'statuses':dict(Counter(r['status']for r in api['records'])),
   'public_scores_returned':sum('publicScore'in r for r in api['records']),'private_scores_returned':sum('privateScore'in r for r in api['records']),
   'earliest':min(r['date']for r in api['records']),'latest':max(r['date']for r in api['records'])},
 'blocks':blocks,'interpretation':'Observed aggregate-score ordering only. No causal module attribution, true run count, independent validation or prospective model selection. Author score text and API identity coverage differ.'}
(O/'RESULT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
flat=[]
for period,b in blocks.items():
    for row in b.get('inversions',[]):flat.append({'period':period,**row})
with (O/'ALL_OBSERVED_RANK_REVERSALS.csv').open('w',encoding='utf-8-sig',newline='')as f:
    w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
print(json.dumps({'records':len(scored),'global_pairs':blocks['all_distinct_text_scored_records']['pair_counts'],'spearman':blocks['all_distinct_text_scored_records']['spearman_descriptive'],'api_identity_records':len(api['records'])},ensure_ascii=False))
