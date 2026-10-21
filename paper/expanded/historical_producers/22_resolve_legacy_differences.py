"""Replay only the 19 discrepant legacy metric records; no inference or training."""
from pathlib import Path
from collections import defaultdict
import csv,json,ast
import numpy as np
import zarr
from scipy.optimize import linear_sum_assignment
import audit_engine as E
R=Path(__file__).resolve().parents[1];O=R/'04_统一重分析';D=R/'05_补证与核验/历史计数对照'
rows=json.loads((D/'RESULT.json').read_text(encoding='utf8'))['differing_records'];nb=next(x for x in csv.DictReader((R/'02_实验身份与谱系/NOTEBOOK_IDENTITIES.csv').open(encoding='utf-8-sig'))if x['file_id']=='18601');j=json.loads(Path(nb['path']).read_text(encoding='utf-8-sig'));cell=''.join(j['cells'][19]['source']);tree=ast.parse(cell);selected=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in ['match_nodes','_edge_counts']];assert len(selected)==2
code=ast.unparse(ast.Module(body=selected,type_ignores=[]));(D/'extracted_legacy_matching_and_counting.py').write_text('# Extracted unchanged functions from notebook file 18601, code cell 19.\n'+code,encoding='utf8');env={'np':np,'defaultdict':defaultdict,'linear_sum_assignment':linear_sum_assignment,'DEFAULT_SCALE':(1.625,.40625,.40625),'DEFAULT_MAX_DISTANCE':7.0};exec(compile(code,'legacy_metric_functions','exec'),env)
scale=np.array([1.625,.40625,.40625]);results=[]
for r in rows:
    film=r['film'];g=E.load_graph(O/'graphs'/(r['graph_id']+'.npz'));ref=E.load_graph(O/'references'/(film+'.npz'));z=zarr.open_group(str(Path('D:/CELL数据暂存/cell（只读勿动）/gt_data/full/train')/(film+'.geff')),mode='r');ri=z['nodes/ids'][:];rc=np.column_stack([z['nodes/props/'+k+'/values'][:]for k in ['t','z','y','x']]);prednodes={int(i):(int(c[0]),*(c[1:]/scale))for i,c in zip(g.ids,g.coords)};refnodes={int(i):tuple(c)for i,c in zip(ri,rc)}
    mapping=env['match_nodes'](prednodes,refnodes);counts=env['_edge_counts']([tuple(map(int,e))for e in g.edges],mapping,[tuple(map(int,e))for e in ref.edges],{i:int(c[0])for i,c in prednodes.items()});old=tuple(r['old_'+k]for k in ['TP','FP','FN']);summary=E.read_json_gz(O/'graph_reports'/(r['graph_id']+'.json.gz'));inv={v:k for k,v in mapping.items()};outside=[];different=[]
    for ts,loc in summary['frame_locators'].items():
        f=E.read_json_gz(O/'frame_cache'/loc);m={q:inv[q]for q in f['reference_ids']if q in inv}
        if m!=f['canonical']:different.append(int(ts))
        if m not in f['worlds']:outside.append(int(ts))
    results.append({'asset_id':r['asset_id'],'film':film,'historical_counts':old,'legacy_function_replay_counts':counts,'historical_counts_reproduced':old==counts,'new_hypot_canonical_counts':[r['new_canonical_'+k]for k in ['TP','FP','FN']],'legacy_mapping_different_from_new_canonical_frames':different,'legacy_mapping_outside_new_exact_hypot_family_frames':outside,'input_graph_fixed':True})
status={'checked_discrepancies':len(results),'historical_three_counts_reproduced':sum(x['historical_counts_reproduced']for x in results),'results':results,'source_notebook':nb['path'],'source_cell':19,'cause_supported':'Legacy norm distance, unnormalised rectangular pred-to-GT assignment and tie handling differ from new hypot exact objective and canonical ordering. Source functions replayed without notebook runtime.'}
(D/'RESOLVED_DIFFERENCES.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf8');print('Resolved legacy metric records',status['historical_three_counts_reproduced'],'/',len(results))
