from pathlib import Path
from collections import Counter
import sqlite3,json,csv,os,time
R=Path('D:/1013工作大修');db=sqlite3.connect(R/'01_输入清册/FILES.sqlite');base=Path('G:/kaggle论文化/论文工作区')
roots=[('later_science',base/'10_长期研究推进/2026-10-02_启动/article_strengthening_20261004_v1'),('stage_export',base/'08_Kaggle实验')]
skip={'__pycache__','.git','.venv','node_modules','.verification-venv','article_v1.0'}
counts=Counter();batch=[]
for label,root in roots:
    if db.execute('select count(*) from files where root=?',(label,)).fetchone()[0]:continue
    for directory,dirs,files in os.walk(root):
        dirs[:]=[d for d in dirs if d not in skip]
        for n in files:
            p=Path(directory)/n;s=p.stat();e=p.suffix.lower()
            cat='notebook' if e=='.ipynb'else'program' if e in ['.py','.ps1','.sh']else'prediction_submission' if n=='submission.csv'else'saved_array_or_graph' if e in ['.npz','.npy'] or '.geff/'in p.as_posix().lower()else'record_or_metadata' if e in ['.json','.jsonl','.log','.csv','.md','.txt','.yml','.yaml']else'other_asset'
            counts[label+'/'+cat]+=1;batch.append((label,p.relative_to(root).as_posix(),str(p),n,e,s.st_size,s.st_mtime_ns,cat))
            if len(batch)>=5000:db.executemany('insert into files(root,relative_path,path,name,extension,bytes,mtime_ns,category) values(?,?,?,?,?,?,?,?)',batch);db.commit();batch=[]
    print('ADDED',label,sum(v for k,v in counts.items()if k.startswith(label+'/')),flush=True)
if batch:db.executemany('insert into files(root,relative_path,path,name,extension,bytes,mtime_ns,category) values(?,?,?,?,?,?,?,?)',batch);db.commit()
def q(sql):return [dict(zip([x[0]for x in cur.description],row))for cur in [db.execute(sql)]for row in cur]
summary={'added_counts':dict(counts),'totals_by_root':q('select root,count(*) as files,sum(bytes) as bytes from files group by root'),
 'notebooks':q("select root,count(*)as n from files where extension='.ipynb' group by root"),
 'submission_files':q("select root,count(*)as n,sum(bytes)as bytes from files where category='prediction_submission' group by root"),
 'metadata_candidates':q("select name,count(*)as n from files where root in ('cell','TRANSDATA','IWS') and (name like '%manifest%' or name like '%receipt%' or name like '%kernel%' or name like '%summary%') and extension in ('.json','.txt') group by name order by n desc limit 45"),
 'discovery_scope':'Original three roots plus pre-strengthening history, strengthening scientific history excluding article_v1.0 delivery copies, and original stage-export runs; current52/30 validated routes retained separately.'}
(R/'01_输入清册/DISCOVERY_PROFILE.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(summary,ensure_ascii=False),flush=True)
