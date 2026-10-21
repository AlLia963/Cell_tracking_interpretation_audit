from pathlib import Path
import csv,json,subprocess,hashlib,gzip
R=Path('D:/1013工作大修');O=R/'01_输入清册';report=json.loads((O/'ARCHIVE_INTAKE_SUMMARY.json').read_text(encoding='utf8'))
pins={x['identity'].split(':')[-1]for x in csv.DictReader((R/'02_实验身份与谱系/NOTEBOOK_IDENTITIES.csv').open(encoding='utf-8-sig'))}
pins|={x['source_identity_prefix16']for x in csv.DictReader((O/'ARCHIVE_SELECTED_RECORDS.csv').open(encoding='utf-8-sig'))if x['source_identity_prefix16']}
results=[];selected=[]
for ai,a in enumerate(report['remaining_nonzip_archives']):
    path=a['path'];p=Path(path)
    if p.suffix=='.gz'and not p.name.endswith('.tar.gz'):
        with gzip.open(p,'rt',encoding='utf8',errors='replace')as f:header=f.readline().strip()
        results.append({'archive':path,'status':'GZIP_TABLE_HEADER_READ','header':header,'scope':'candidate evidence table, not a final prediction graph'});continue
    proc=subprocess.run(['C:/Windows/System32/tar.exe','-tf',path],capture_output=True)
    try:s=proc.stdout.decode('utf8')
    except UnicodeDecodeError:s=proc.stdout.decode('gb18030',errors='replace')
    entries=s.splitlines();results.append({'archive':path,'status':'INDEXED'if proc.returncode==0 else'INDEX_FAILURE','members':entries,'returncode':proc.returncode})
    if proc.returncode:continue
    for mi,member in enumerate(entries):
        name=Path(member.replace('\\','/')).name
        if not(name.endswith('.ipynb')or(name.endswith('.csv')and'submission'in name.lower())):continue
        data=subprocess.run(['C:/Windows/System32/tar.exe','-xOf',path,member],capture_output=True)
        if data.returncode:selected.append({'archive':path,'member':member,'status':'READ_FAILURE','recovered_path':''});continue
        sha=hashlib.sha256(data.stdout).hexdigest()if name.endswith('.ipynb')else''
        if sha and sha[:16]in pins:selected.append({'archive':path,'member':member,'status':'IDENTITY_ALREADY_CATALOGUED','identity_prefix16':sha[:16],'recovered_path':''});continue
        target=O/'压缩包恢复'/f'nonzip{ai}_{mi}_{name}';target.write_bytes(data.stdout)
        selected.append({'archive':path,'member':member,'status':'RECOVERED','identity_prefix16':sha[:16]if sha else'','recovered_path':str(target)})
        if sha:pins.add(sha[:16])
(O/'NONZIP_ARCHIVE_INTAKE.json').write_text(json.dumps({'archives':results,'selected':selected,'originals_untouched':True},ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'archives':len(results),'selected':len(selected),'recovered':sum(bool(x['recovered_path'])for x in selected),'failures':sum(x['status']=='INDEX_FAILURE'for x in results)},ensure_ascii=False))
