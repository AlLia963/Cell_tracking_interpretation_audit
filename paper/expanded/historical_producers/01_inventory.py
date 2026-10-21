"""Read-only metadata inventory for the authorized revision; no archive execution."""
from pathlib import Path
from collections import Counter
import csv,json,os,shutil,sqlite3,time
R=Path('D:/1013工作大修')
OLD=Path('G:/kaggle论文化/论文工作区/BSPC_统一收束')
for d in ['00_范围与进度','01_输入清册','02_实验身份与谱系','03_研究范围与协议','04_统一重分析','05_补证与核验','06_结果与交付','src','logs']:(R/d).mkdir(exist_ok=True)
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
imports=[(OLD/'10_notebook与文码一致性核查/清点规划/工作清点与证据扩展计划.txt','00_范围与进度/授权依据_计划.txt'),
         (OLD/'10_notebook与文码一致性核查/清点规划/用户提供_kaggle分数表_20261013.txt','01_输入清册/用户分数表.txt'),
         (OLD/'10_notebook与文码一致性核查/清点规划/分数表逐条记录.csv','01_输入清册/用户分数表_125条.csv'),
         (OLD/'10_notebook与文码一致性核查/READ_ONLY_ORIGINAL_NOTEBOOK_FILES.csv','01_输入清册/已知419份notebook.csv'),
         (Path('G:/kaggle论文化/整理到此处/00_清册/notebook_registry.csv'),'01_输入清册/旧330条notebook清册.csv')]
for n in ['kaggle_submissions_parsed.csv','kaggle_submissions_dated.csv','cell_lineage_versions.csv','master_experiment_table.csv']:
    imports.append((OLD.parent/'B_研究证据主表'/n,'01_输入清册/'+n))
for p,q in imports:
    target=R/q
    if not target.exists():shutil.copy2(p,target)
dump(R/'00_范围与进度/STATE.json',{'date':'2026-10-13','authorized_steps':[1,2,3,4],'not_authorized_this_turn':'Step5 manuscript/figure reconstruction and submission','current_step':1,'source_roots_read_only':True,'old_candidate_untouched':True,'repository_untouched':True})
db=R/'01_输入清册/FILES.sqlite'
if db.exists():raise RuntimeError('Existing inventory must be reused, not silently regenerated')
con=sqlite3.connect(db)
con.execute('create table files(id integer primary key, root text, relative_path text, path text, name text, extension text, bytes integer, mtime_ns integer, category text)')
roots=[('cell',Path('D:/CELL数据暂存/cell（只读勿动）')),('TRANSDATA',Path('D:/CELL数据暂存/TRANSDATA（只读勿动）')),('IWS',Path('D:/CELL数据暂存/IWS（只读勿动）'))]
# Scientific local-run history is indexed separately; duplicated manuscript delivery trees are not new runs.
roots.append(('local_history',OLD.parent/'10_长期研究推进/2026-10-02_启动'))
skip={'__pycache__','.git','.venv','node_modules','.verification-venv'}
skip_history={'article_strengthening_20261004_v1'}
counts=Counter();errors=[];batch=[];started=time.perf_counter()
def category(p):
    n=p.name.lower();e=p.suffix.lower()
    if e=='.ipynb':return 'notebook'
    if e in ['.py','.ps1','.sh']:return 'program'
    if n=='submission.csv' or (e=='.csv' and 'submission' in n):return 'prediction_submission'
    if e in ['.npz','.npy','.geff'] or '.geff/' in p.as_posix().lower():return 'saved_array_or_graph'
    if e in ['.json','.jsonl','.log','.txt','.md','.csv','.yaml','.yml','.toml']:return 'record_or_metadata'
    if e in ['.pth','.pt','.ckpt']:return 'checkpoint'
    return 'other_asset'
for label,root in roots:
    print('SCAN',label,flush=True)
    for base,dirs,files in os.walk(root):
        dirs[:]=[d for d in dirs if d not in skip and not (label=='local_history' and Path(base)==root and d in skip_history)]
        for n in files:
            p=Path(base)/n
            try:s=p.stat()
            except OSError as err:errors.append({'path':str(p),'error':str(err)});continue
            cat=category(p);batch.append((label,p.relative_to(root).as_posix(),str(p),n,p.suffix.lower(),s.st_size,s.st_mtime_ns,cat));counts[label+'/'+cat]+=1
            if len(batch)>=5000:
                con.executemany('insert into files(root,relative_path,path,name,extension,bytes,mtime_ns,category) values(?,?,?,?,?,?,?,?)',batch);con.commit();batch=[]
    print('SCANNED',label,sum(v for k,v in counts.items()if k.startswith(label+'/')),flush=True)
if batch:con.executemany('insert into files(root,relative_path,path,name,extension,bytes,mtime_ns,category) values(?,?,?,?,?,?,?,?)',batch)
con.execute('create index idx_ext on files(extension)');con.execute('create index idx_name on files(name)');con.execute('create index idx_root on files(root)');con.commit()
selected=list(con.execute("select id,root,relative_path,path,bytes,category from files where category in ('notebook','prediction_submission') order by root,relative_path"))
with (R/'01_输入清册/NOTEBOOK_AND_SUBMISSION_FILES.csv').open('w',encoding='utf-8-sig',newline='')as f:
    w=csv.writer(f);w.writerow(['file_id','root','relative_path','path','bytes','category']);w.writerows(selected)
summary={'counts':dict(counts),'files':sum(counts.values()),'bytes':con.execute('select sum(bytes) from files').fetchone()[0],
         'errors':errors,'seconds':time.perf_counter()-started,'source_file_bytes_not_hashed':True,
         'local_history_excluded_delivery_copy_tree':list(skip_history),'metadata_inventory_is_not_run_count':True}
dump(R/'01_输入清册/FILE_INVENTORY_SUMMARY.json',summary)
print(json.dumps(summary,ensure_ascii=False),flush=True)
