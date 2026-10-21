"""Discover saved graph schemas from archive headers, not graph measurements."""
from pathlib import Path
from collections import Counter,defaultdict
import ast,csv,json,sqlite3,zipfile,struct
import numpy as np
R=Path('D:/1013工作大修');O=R/'01_输入清册';db=sqlite3.connect(O/'FILES.sqlite');db.row_factory=sqlite3.Row
def csvout(name,rows):
    if not rows:return
    with (O/name).open('w',encoding='utf-8-sig',newline='')as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
headers=[];graphs=[];errors=[];schemas=Counter();geffs={}
for f in db.execute("select * from files where root in ('cell','TRANSDATA','IWS','stage_export') and (extension='.npz' or path like '%.geff%') order by id"):
    path=Path(f['path'])
    if '.geff'in f['path'].lower():
        raw=f['path'];ix=raw.lower().index('.geff')+5;gp=raw[:ix]
        if gp not in geffs:geffs[gp]={'root':f['root'],'path':gp,'film':Path(gp).stem,'files':0,'bytes':0,'reference_candidate':('gt_data'in raw or '/ground_truth/'in raw.replace('\\','/'))}
        geffs[gp]['files']+=1;geffs[gp]['bytes']+=f['bytes']
    if f['extension']!='.npz':continue
    try:
        with zipfile.ZipFile(path)as z:
            names={n[:-4]for n in z.namelist()if n.endswith('.npy')};schema=';'.join(sorted(names));schemas[schema]+=1
            keys=None
            for ids,coords,edges in [('ids','coords','edges'),('node_ids','coords','edges')]:
                if {ids,coords,edges}<=names:keys=(ids,coords,edges);break
            if keys:
                shape={}
                for k in keys:
                    with z.open(k+'.npy')as stream:
                        version=np.lib.format.read_magic(stream)
                        width=2 if version==(1,0) else 4
                        size=int.from_bytes(stream.read(width),'little')
                        data=ast.literal_eval(stream.read(size).decode('utf8'if version==(3,0)else'latin1'))
                        shape[k]={'shape':list(data['shape']),'dtype':str(np.dtype(data['descr']))}
                graphs.append({'file_id':f['id'],'root':f['root'],'path':str(path),'relative_path':f['relative_path'],'bytes':f['bytes'],'id_key':keys[0],'coordinates_key':keys[1],'edges_key':keys[2],
                               'nodes_shape':str(shape[keys[0]]['shape']),'coords_shape':str(shape[keys[1]]['shape']),'edges_shape':str(shape[keys[2]]['shape']),
                               'coordinate_dtype':shape[keys[1]]['dtype'],'has_unit_metadata':'unit'in names,'unit_not_yet_admitted':True,'edge_identity_semantics_not_yet_admitted':True})
            headers.append({'file_id':f['id'],'path':str(path),'keys':schema,'graph_schema_candidate':bool(keys)})
    except Exception as e:errors.append({'file_id':f['id'],'path':str(path),'error':repr(e)})
csvout('NPZ_HEADER_INVENTORY.csv',headers);csvout('GRAPH_NPZ_CANDIDATES.csv',graphs);csvout('GEFF_CONTAINERS.csv',list(geffs.values()));csvout('NPZ_READ_EXCEPTIONS.csv',errors)
summary={'npz_headers_inspected':len(headers),'graph_array_candidates':len(graphs),'by_root':dict(Counter(g['root']for g in graphs)),
         'geff_containers':len(geffs),'reference_candidate_geffs':sum(g['reference_candidate']for g in geffs.values()),'header_errors':errors,
         'top_schemas':schemas.most_common(35),'coordinates_edges_units_not_inferred_from_shape':True}
(O/'GRAPH_DISCOVERY_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in summary.items()if k!='header_errors'},ensure_ascii=False))
