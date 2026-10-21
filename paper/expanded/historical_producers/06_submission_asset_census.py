"""Read all retained submission tables; record schema/film coverage, not performance."""
from pathlib import Path
from collections import Counter
import csv,json,sqlite3,time
import pandas as pd
R=Path('D:/1013工作大修');O=R/'01_输入清册';db=sqlite3.connect(O/'FILES.sqlite');db.row_factory=sqlite3.Row
target=O/'SUBMISSION_ASSET_CENSUS.jsonl';done={}
if target.exists():
    for line in target.read_text(encoding='utf8').splitlines():
        j=json.loads(line);done[j['file_id']]=j
refs={p.stem for p in Path('D:/CELL数据暂存/cell（只读勿动）/gt_data/full/train').glob('*.geff')}
files=list(db.execute("select * from files where category='prediction_submission' and root in ('cell','TRANSDATA','IWS') order by id"))
with target.open('a',encoding='utf8')as log:
 for idx,f in enumerate(files):
    if f['id']in done:continue
    p=Path(f['path']);row={'file_id':f['id'],'root':f['root'],'path':str(p),'bytes':f['bytes']}
    try:
        header=pd.read_csv(p,nrows=0);row['columns']=list(header)
        required={'dataset','row_type','node_id','t','z','y','x','source_id','target_id'}
        if not required<=set(header):row.update(status='UNSUPPORTED_SUBMISSION_SCHEMA',missing_columns=sorted(required-set(header)))
        else:
            counts=Counter();total=0
            for chunk in pd.read_csv(p,usecols=['dataset','row_type'],chunksize=250000):
                total+=len(chunk)
                for (film,kind),n in chunk.groupby(['dataset','row_type'],dropna=False).size().items():counts[str(film),str(kind)]+=int(n)
            films=sorted({film for film,kind in counts});row.update(status='SCHEMA_CENSUSED_NOT_YET_SCIENTIFICALLY_ADMITTED',rows=total,films=films,
                film_row_counts=[{'film':film,'row_type':kind,'rows':n}for (film,kind),n in sorted(counts.items())],
                films_with_local_reference=[x for x in films if x in refs],films_without_local_reference=[x for x in films if x not in refs])
    except Exception as e:row.update(status='READ_FAILURE',error=type(e).__name__+': '+str(e)[:300])
    log.write(json.dumps(row,ensure_ascii=False)+'\n');log.flush();done[f['id']]=row
    if (idx+1)%15==0:print('CENSUS',idx+1,'/',len(files),flush=True)
rows=[done[f['id']]for f in files]
summary={'files':len(rows),'statuses':dict(Counter(x['status']for x in rows)),
 'distinct_film_names':sorted({f for x in rows for f in x.get('films',[])}),
 'local_reference_films':sorted({f for x in rows for f in x.get('films_with_local_reference',[])}),
 'files_with_reference_coverage':sum(bool(x.get('films_with_local_reference'))for x in rows),
 'source_files_not_modified':True,'no_matching_or_performance_measurement_executed':True}
(O/'SUBMISSION_CENSUS_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(summary,ensure_ascii=False),flush=True)
