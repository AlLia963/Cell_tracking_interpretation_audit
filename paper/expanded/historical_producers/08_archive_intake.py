"""Index ZIP contents and recover selected source/output records into new workspace."""
from pathlib import Path,PurePosixPath
from collections import Counter
import csv,hashlib,json,sqlite3,zipfile,io,os
R=Path('D:/1013工作大修');O=R/'01_输入清册';dest=O/'压缩包恢复';dest.mkdir(exist_ok=True)
db=sqlite3.connect(O/'FILES.sqlite');db.row_factory=sqlite3.Row
nbpins={x['identity'].split(':')[-1]for x in csv.DictReader((R/'02_实验身份与谱系/NOTEBOOK_IDENTITIES.csv').open(encoding='utf-8-sig'))}
members=[];selected=[];errors=[];summ=[];counter=0
def scan(z,source,archive_id,depth=0):
    global counter
    for info in z.infolist():
        if info.is_dir():continue
        counter+=1;raw=info.filename.replace('\\','/');name=PurePosixPath(raw).name;ext=Path(name).suffix.lower()
        row={'member_id':counter,'archive_file_id':archive_id,'archive_locator':source,'member':raw,'bytes':info.file_size,'CRC32':f'{info.CRC:08x}','extension':ext}
        members.append(row)
        wanted=(ext=='.ipynb' or (ext=='.csv'and 'submission'in name.lower()) or name in ['kernel-metadata.json','push_receipt.txt','cv_summary.json','cv_per_movie.csv'])
        if wanted:
            payload=z.read(info);kind='notebook'if ext=='.ipynb'else'prediction_submission_candidate'if ext=='.csv'and'submission'in name.lower()else'run_metadata'
            identity=hashlib.sha256(payload).hexdigest()if kind=='notebook'else''
            if identity and identity[:16]in nbpins:
                selected.append({**row,'kind':kind,'source_identity_prefix16':identity[:16],'status':'IDENTITY_ALREADY_IN_419_FILE_CATALOG','recovered_path':''});continue
            safe=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',name)[:140]
            p=dest/(str(counter)+'_'+safe);p.write_bytes(payload)
            selected.append({**row,'kind':kind,'source_identity_prefix16':identity[:16]if identity else'','status':'RECOVERED_IN_NEW_WORKSPACE','recovered_path':str(p)})
            if identity:nbpins.add(identity[:16])
        elif ext=='.zip'and depth==0 and info.file_size<=100_000_000:
            try:
                with zipfile.ZipFile(io.BytesIO(z.read(info)))as inner:scan(inner,source+'!'+raw,archive_id,depth+1)
            except Exception as e:errors.append({'archive':source+'!'+raw,'error':type(e).__name__})
import re
for f in db.execute("select * from files where root in ('cell','TRANSDATA','IWS') and extension='.zip' and path not like '%.venv%' order by id"):
    before=counter
    try:
        with zipfile.ZipFile(f['path'])as z:scan(z,f['path'],f['id'])
        summ.append({'archive':f['path'],'status':'INDEXED','members_including_nested':counter-before})
    except Exception as e:errors.append({'archive':f['path'],'error':type(e).__name__});summ.append({'archive':f['path'],'status':'UNREADABLE','members_including_nested':counter-before})
def out(name,rs):
    if not rs:return
    with (O/name).open('w',encoding='utf-8-sig',newline='')as f:
        w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
out('ARCHIVE_MEMBERS.csv',members);out('ARCHIVE_SELECTED_RECORDS.csv',selected)
report={'archives':summ,'members_indexed':len(members),'selected_records':len(selected),'selection_status':dict(Counter(x['status']for x in selected)),
        'recovered_by_kind':dict(Counter(x['kind']for x in selected if x['recovered_path'])),'errors':errors,'original_archives_untouched':True,'no_programs_executed':True,
        'remaining_nonzip_archives':[dict(x)for x in db.execute("select path,extension,bytes from files where root in ('cell','TRANSDATA','IWS') and extension in ('.rar','.7z','.tar','.gz') and path not like '%.venv%'")]}
(O/'ARCHIVE_INTAKE_SUMMARY.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in report.items()if k not in ['archives','remaining_nonzip_archives']},ensure_ascii=False),flush=True)
