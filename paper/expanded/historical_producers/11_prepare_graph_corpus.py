"""Admit saved primitives into the fixed 1013 contract. No inference or source edits."""
from pathlib import Path
from collections import Counter
import csv,json,hashlib,re,sqlite3,time,sys,os
import numpy as np
import pandas as pd
import zarr
R=Path('D:/1013工作大修');O=R/'04_统一重分析';A=R/'01_输入清册';G=O/'graphs';T=O/'references'
G.mkdir(exist_ok=True);T.mkdir(exist_ok=True)
sys.dont_write_bytecode=True
sys.path.insert(0,str(R/'src/reference_backend/sources/executed'))
from stage_accounting import Graph
SCALE=np.array([1.625,.40625,.40625]);movie_re=re.compile(r'(?:44b6|6bba)_[0-9a-f]{8}')
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def read(p):return json.loads(p.read_text(encoding='utf8'))
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str),encoding='utf8')
def write_line(f,x):f.write(json.dumps(x,ensure_ascii=False,default=str)+'\n');f.flush()
def scalar_int(x,label):
    a=np.asarray(x)
    if a.dtype.kind not in 'iuf' or not np.isfinite(a).all():raise ValueError(label+' requires finite numeric integers')
    if a.dtype.kind=='f'and(np.any(np.abs(a)>=2**53)or not np.equal(a,np.floor(a)).all()):raise ValueError(label+' not an exact integer')
    if a.size and (np.min(a)<np.iinfo(np.int64).min or np.max(a)>np.iinfo(np.int64).max):raise ValueError(label+' outside int64')
    return a.astype(np.int64)
def normalize(ids,coords,edges,unit):
    ids=scalar_int(ids,'ids');edges=scalar_int(edges,'edges').reshape(-1,2);coords=np.asarray(coords,dtype=np.float64).copy()
    if coords.shape!=(len(ids),4):raise ValueError('Coordinates must be frame,z,y,x')
    if unit=='pixel':coords[:,1:]*=SCALE
    elif unit!='um':raise ValueError('Unsupported unit declaration')
    order=np.argsort(ids);ids=ids[order];coords=coords[order];coords[coords==0]=0.
    if len(edges):edges=edges[np.lexsort((edges[:,1],edges[:,0]))]
    graph=Graph(ids,coords,edges,'um')
    return graph
def identity(film,graph):
    h=hashlib.sha256();h.update((film+'|frame,z,y,x|um|id-pairs').encode())
    for v in [graph.ids.astype('<i8'),graph.coords.astype('<f8'),graph.edges.astype('<i8')]:h.update(str(v.shape).encode());h.update(v.tobytes())
    return h.hexdigest()
refs={};refroot=Path('D:/CELL数据暂存/cell（只读勿动）/gt_data/full/train')
for p in sorted(refroot.glob('*.geff')):
    target=T/(p.stem+'.npz')
    if target.exists():
        with np.load(target,allow_pickle=False)as d:refs[p.stem]={'nodes':len(d['ids']),'edges':len(d['edges']),'path':str(target.relative_to(O))}
        continue
    z=zarr.open_group(str(p),mode='r');g=normalize(z['nodes/ids'][:],np.column_stack([z['nodes/props/'+k+'/values'][:]for k in ['t','z','y','x']]),z['edges/ids'][:],'pixel')
    np.savez_compressed(target,ids=g.ids,coords=g.coords,edges=g.edges,unit=np.array('um'))
    refs[p.stem]={'nodes':len(g.ids),'edges':len(g.edges),'path':str(target.relative_to(O))}
dump(O/'REFERENCE_COHORT.json',{'movies':refs,'source_root':str(refroot),'conversion':SCALE.tolist(),'source_unit':'pixel','new_biological_N':0})

assets=[]
for line in (A/'SUBMISSION_ASSET_CENSUS.jsonl').read_text(encoding='utf8').splitlines():
    x=json.loads(line);assets.append({'asset_id':'F'+str(x['file_id']),'kind':'csv','root':x['root'],'path':x['path'],'original_locator':x['path'],'previous_schema_status':x['status']})
for x in rows(A/'ARCHIVE_SELECTED_RECORDS.csv'):
    if x['kind']=='prediction_submission_candidate'and x['recovered_path']:
        assets.append({'asset_id':'Z'+x['member_id'],'kind':'csv','root':'archive','path':x['recovered_path'],'original_locator':x['archive_locator']+'!'+x['member'],'previous_schema_status':'not_censused'})
for i,x in enumerate(read(A/'NONZIP_ARCHIVE_INTAKE.json')['selected']):
    if x['recovered_path']and x['member'].endswith('.csv'):
        assets.append({'asset_id':'R'+str(i),'kind':'csv','root':'archive','path':x['recovered_path'],'original_locator':x['archive']+'!'+x['member'],'previous_schema_status':'not_censused'})
for x in rows(A/'GRAPH_NPZ_CANDIDATES.csv'):
    if x['root']=='stage_export':continue # retained existing complete-route evidence, not repeated here
    assets.append({'asset_id':'F'+x['file_id'],'kind':'npz','root':x['root'],'path':x['path'],'original_locator':x['path'],'previous_schema_status':'explicit_ids_header'})
for x in rows(A/'NPZ_HEADER_INVENTORY.csv'):
    if x['keys']=='coords;edges':assets.append({'asset_id':'F'+x['file_id'],'kind':'npz_implicit','root':'cell'if'cell（'in x['path']else'IWS','path':x['path'],'original_locator':x['path'],'previous_schema_status':'implicit_id_candidate'})
for i,x in enumerate(rows(A/'GEFF_CONTAINERS.csv')):
    if x['reference_candidate']=='True':continue
    assets.append({'asset_id':'G'+str(i),'kind':'geff','root':x['root'],'path':x['path'],'original_locator':x['path'],'previous_schema_status':'container_only'})
dump(O/'FROZEN_ASSET_ROSTER.json',{'assets':assets,'count':len(assets),'by_kind':dict(Counter(x['kind']for x in assets)),
      'selection':'All structurally identified assets; no score or outcome filter','stage_exports':'existing evidence retained separately'})
completed={};known={};aliases=[]
if (O/'ASSET_ADMISSION.jsonl').exists():
    completed={x['asset_id']:x for x in map(json.loads,(O/'ASSET_ADMISSION.jsonl').read_text(encoding='utf8').splitlines())}
if (O/'GRAPH_INDEX.jsonl').exists():known={x['graph_id']:x for x in map(json.loads,(O/'GRAPH_INDEX.jsonl').read_text(encoding='utf8').splitlines())}
def make_graph(ids,coords,edges,unit='pixel'):return normalize(ids,coords,edges,unit)
start=time.perf_counter()
with (O/'ASSET_ADMISSION.jsonl').open('a',encoding='utf8')as admissions,(O/'GRAPH_INDEX.jsonl').open('a',encoding='utf8')as index,(O/'GRAPH_ALIASES.jsonl').open('a',encoding='utf8')as aliaslog:
 def admit(film,ids,coords,edges,asset,unit='pixel',semantics='explicit node-ID pairs'):
    if film not in refs:raise ValueError('NO_SELECTED_REFERENCE:'+str(film))
    g=make_graph(ids,coords,edges,unit);gid=identity(film,g)
    source=asset['original_locator'].replace('\\','/')
    role='candidate_or_upstream_graph'if any(s in source.lower()for s in ['/pre_ilp','/raw.npz','/tracking_repo/predictions/'])else'final_or_replayed_saved_graph'
    if gid not in known:
        np.savez_compressed(G/(gid+'.npz'),ids=g.ids,coords=g.coords,edges=g.edges,unit=np.array('um'))
        out=Counter(map(int,g.edges[:,0]));inc=Counter(map(int,g.edges[:,1]));times=dict(zip(map(int,g.ids),g.coords[:,0]))
        row={'graph_id':gid,'film':film,'nodes':len(g.ids),'edges':len(g.edges),'frames':len(np.unique(g.coords[:,0])),
             'frame_min':int(g.coords[:,0].min())if len(g.ids)else None,'frame_max':int(g.coords[:,0].max())if len(g.ids)else None,
             'max_outdegree':max(out.values(),default=0),'max_indegree':max(inc.values(),default=0),
             'nonadjacent_edges':sum(times[int(b)]-times[int(a)]!=1 for a,b in g.edges),'first_asset':asset['asset_id'],
             'path':'graphs/'+gid+'.npz','unit':'um','normalization':'ID and pair sorting; source coordinates scaled once; no node/edge cleanup; weights/type flags not used by untyped queries'}
        known[gid]=row;write_line(index,row)
    write_line(aliaslog,{'asset_id':asset['asset_id'],'graph_id':gid,'film':film,'source_unit_declared':unit,'edge_identity_semantics':semantics,'view_role':role,'original_locator':asset['original_locator']})
    return gid
 for i,a in enumerate(assets):
    if a['asset_id']in completed:continue
    p=Path(a['path']);record={**a,'accepted':[],'rejected':[],'status':'INSPECTED'}
    try:
        if a['kind']=='csv':
            header=list(pd.read_csv(p,nrows=0));required=['dataset','row_type','node_id','t','z','y','x','source_id','target_id']
            if not set(required)<=set(header):raise ValueError('NOT_A_PREDICTION_TABLE:'+','.join(sorted(set(required)-set(header))))
            df=pd.read_csv(p,usecols=required)
            for film,block in df.groupby('dataset',sort=True,dropna=False):
                try:
                    if not set(block.row_type)<= {'node','edge'}:raise ValueError('Unknown row type')
                    ns=block[block.row_type=='node'];es=block[block.row_type=='edge']
                    gid=admit(str(film),ns.node_id.to_numpy(),ns[['t','z','y','x']].to_numpy(),es[['source_id','target_id']].to_numpy(),a)
                    record['accepted'].append({'film':str(film),'graph_id':gid})
                except Exception as e:record['rejected'].append({'film':str(film),'error':type(e).__name__+': '+str(e)})
            del df
        elif a['kind'].startswith('npz'):
            films=movie_re.findall(a['original_locator']);film=films[-1]if films else None
            with np.load(p,allow_pickle=False)as d:
                co=d['coords'];ed=d['edges'];unit='pixel'
                if'unit'in d:
                    u=d['unit']
                    if u.shape!=()or u.dtype.kind!='U' or u.item()!='pixel':raise ValueError('UNIT_CONTRACT_CONFLICT: source writer declares pixel')
                if a['kind']=='npz_implicit':
                    if co.ndim!=2 or co.shape[1]!=4:raise ValueError('IMPLICIT_ID_CACHE_LACKS_FULL_FRAME_ZYX_GRAPH')
                    ids=np.arange(len(co),dtype=np.int64);semantics='row IDs under CV writer; cross-check against sibling CSV where retained'
                else:ids=d['ids'];semantics='explicit node-ID pairs'
                gid=admit(film,ids,co,ed,a,unit,semantics);record['accepted'].append({'film':film,'graph_id':gid})
        else:
            film=p.stem
            z=zarr.open_group(str(p),mode='r');ids=z['nodes/ids'][:];co=np.column_stack([z['nodes/props/'+k+'/values'][:]for k in ['t','z','y','x']]);ed=z['edges/ids'][:]
            gid=admit(film,ids,co,ed,a);record['accepted'].append({'film':film,'graph_id':gid})
        if record['rejected']:record['status']='PARTIAL_ADMISSION'if record['accepted']else'WITHHELD_STRUCTURAL_OR_SCOPE'
        else:record['status']='ADMITTED_SAVED_GRAPH_PRIMITIVES'
    except Exception as e:record.update(status='WITHHELD_STRUCTURAL_OR_SCOPE',error=type(e).__name__+': '+str(e)[:500])
    write_line(admissions,record);completed[a['asset_id']]=record
    if (i+1)%20==0:print('PREPARE',i+1,'/',len(assets),'unique_graphs',len(known),'last',record['status'],flush=True)
summary={'assets':len(assets),'processed':len(completed),'statuses':dict(Counter(x['status']for x in completed.values())),'unique_untyped_graph_primitives':len(known),
 'distinct_reference_films':len({x['film']for x in known.values()}),'accepted_asset_movie_records':sum(len(x['accepted'])for x in completed.values()),
 'rejected_asset_movie_records':sum(len(x['rejected'])for x in completed.values()),'seconds_this_process':time.perf_counter()-start,
 'no_prediction_or_reference_array_changed_in_originals':True,'graph_dedup_is_not_independent_experiment_count':True}
dump(O/'PREPARATION_SUMMARY.json',summary);print(json.dumps(summary,ensure_ascii=False),flush=True)
