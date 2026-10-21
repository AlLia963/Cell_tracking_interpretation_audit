from pathlib import Path
from collections import Counter
import ast,csv,json,sqlite3,zipfile,shutil
import numpy as np
R=Path('D:/1013工作大修');O=R/'01_输入清册';db=sqlite3.connect(O/'FILES.sqlite');db.row_factory=sqlite3.Row
old=list(csv.DictReader((O/'NPZ_READ_EXCEPTIONS.csv').open(encoding='utf-8-sig')))
shutil.copy2(O/'NPZ_READ_EXCEPTIONS.csv',O/'NPZ_INSPECTION_INITIAL_ERRORS.csv')
graphs=[];headers=[];remain=[]
for i,r in enumerate(old):
    if 'AttributeError'not in r['error']:remain.append(r);continue
    f=db.execute('select * from files where id=?',(r['file_id'],)).fetchone();p=Path(f['path'])
    with zipfile.ZipFile(p)as z:
        names={n[:-4]for n in z.namelist()if n.endswith('.npy')};keys=('ids','coords','edges')if'ids'in names else('node_ids','coords','edges');shape={}
        for k in keys:
            with z.open(k+'.npy')as s:
                v=np.lib.format.read_magic(s);n=int.from_bytes(s.read(2 if v==(1,0) else 4),'little');h=ast.literal_eval(s.read(n).decode('utf8'if v==(3,0)else'latin1'))
                shape[k]={'shape':list(h['shape']),'dtype':str(np.dtype(h['descr']))}
        graphs.append({'file_id':f['id'],'root':f['root'],'path':str(p),'relative_path':f['relative_path'],'bytes':f['bytes'],'id_key':keys[0],'coordinates_key':keys[1],'edges_key':keys[2],
                       'nodes_shape':str(shape[keys[0]]['shape']),'coords_shape':str(shape[keys[1]]['shape']),'edges_shape':str(shape[keys[2]]['shape']),
                       'coordinate_dtype':shape[keys[1]]['dtype'],'has_unit_metadata':'unit'in names,'unit_not_yet_admitted':True,'edge_identity_semantics_not_yet_admitted':True})
        headers.append({'file_id':f['id'],'path':str(p),'keys':';'.join(sorted(names)),'graph_schema_candidate':True})
    if (i+1)%200==0:print('REPAIRED_HEADER_READER',i+1,flush=True)
for name,rs in [('GRAPH_NPZ_CANDIDATES.csv',graphs),('NPZ_READ_EXCEPTIONS.csv',remain)]:
    with (O/name).open('w',encoding='utf-8-sig',newline='')as f:
        w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
with (O/'NPZ_HEADER_INVENTORY.csv').open('a',encoding='utf8',newline='')as f:
    w=csv.DictWriter(f,fieldnames=list(headers[0]));w.writerows(headers)
summary=json.loads((O/'GRAPH_DISCOVERY_SUMMARY.json').read_text(encoding='utf8'))
summary.update(npz_headers_inspected=summary['npz_headers_inspected']+len(headers),graph_array_candidates=len(graphs),by_root=dict(Counter(g['root']for g in graphs)),header_errors=remain,
               initial_inspector_numpy_private_api_errors=len(graphs),inspector_errors_repaired_without_rerunning_successful_header_reads=True)
(O/'GRAPH_DISCOVERY_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in summary.items()if k not in ['top_schemas']},ensure_ascii=False))
