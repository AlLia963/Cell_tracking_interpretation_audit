"""Recompute next-call projection and historical SVM/SDY negative results."""
from pathlib import Path
import argparse
import collections
import csv
import hashlib
import importlib.util
import json
import sys
import numpy as np
import zarr


def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,x):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,indent=2)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def module(p,name):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['projection','historical-negative']);p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();c=read(a.config);root=Path(c['extra_input_root']);rt=Path(c['runtime_root']);a.output.mkdir(parents=True,exist_ok=False)
    for r in read(root/('EXTRA_INPUT_MANIFEST_v2.json' if (root/'EXTRA_INPUT_MANIFEST_v2.json').exists() else 'EXTRA_INPUT_MANIFEST.json'))['files']:
        if sha(root/r['path'])!=r['sha256']:raise ValueError('Extra scientific input changed: '+r['path'])
    if a.mode=='projection':
        m=module(rt/'historical_sources/projection/analyze.py','pixel_projection');rows=[]
        def arrays(row):
            with np.load(root/row['path'],allow_pickle=False) as z:return {k:z[k].copy() for k in z.files}
        for case in read(root/'PROJECTION_INPUTS.json')['cases']:
            data={arm:{k:arrays(v) for k,v in block.items()} for arm,block in case['arms'].items()};bounds={};q={}
            for arm,d in data.items():
                box,bounds[arm]=m.boxes(d['postprocess_M_G']['root/G']);q[arm]=d['before_model']['root/targets/0/main/cur_target/track_query_boxes'];assert m.eq(box,q[arm])
            w=data['WW']['postprocess_M_G'];v=data['WA']['postprocess_M_G'];assert m.eq(w['root/cells'],v['root/cells']) and m.eq(w['root/all_indices'],v['root/all_indices']) and m.eq(w['root/M'],v['root/M']);delta=np.logical_xor(w['root/G'],v['root/G'])
            rows.append({'film':case['film'],'tau':case['tau'],'pulse_rows':len(w['root/G']),'row_indices_changed':np.flatnonzero(delta.any(axis=(1,2))).tolist(),'row_sum_XOR_pixels':int(delta.sum()),'row_extent_changes':[i for i,(x,y) in enumerate(zip(bounds['WW'],bounds['WA'])) if x!=y],'G_masks_equal':m.eq(w['root/G'],v['root/G']),'independent_boxes_match_actual_queries':True,'next_track_query_boxes_equal':m.eq(q['WW'],q['WA']),'actual_next_capture_array_equal':{k:m.dict_eq(data['WW'][k],data['WA'][k]) for k in ['consumer_stack','consumer_reference_points','raw_model_output']},'W_pixel_extents':bounds['WW'],'A_pixel_extents':bounds['WA']})
        result={'rows':rows,'triggers':len(rows),'changed_G_masks':sum(not r['G_masks_equal'] for r in rows),'changed_next_boxes':sum(not r['next_track_query_boxes_equal'] for r in rows),'unchanged_next_raw_heads':sum(r['actual_next_capture_array_equal']['raw_model_output'] for r in rows),'new_model_forward':False,'no_GT':True};write(a.output/'RESULT.json',result);assert rows==read(root/'expected/PROJECTION_report.json')['rows']
        write(a.output/'COMPARISON.json',{'all14_full_rows_equal':True})
    else:
        backend=module(rt/'historical_sources/legacy_negative/stage_accounting.py','legacy_exact_accounting');scorer=module(rt/'inputs_LOCAL_ONLY/bacterial/sources/common_policy/recount_sdy_sparse_v01.py','sdy_scorer');contract=read(root/'HISTORICAL_INPUTS.json');references={}
        for film,rel in contract['references'].items():
            z=zarr.open_group(str(root/rel),mode='r');references[film]=(z['nodes/ids'][:],np.column_stack([z[f'nodes/props/{k}/values'][:] for k in ['t','z','y','x']]),set(map(tuple,z['edges/ids'][:].tolist())))
        def graph(pin):
            with np.load(root/pin['path'],allow_pickle=False) as z:ids,coords,edges=[z[k].copy() for k in ['ids','coords','edges']]
            coords=coords.astype(float);coords[:,1:]*=[1.625,.40625,.40625];return backend.Graph(ids,coords,edges)
        pairs=[]
        for row in contract['cohorts']:
            before,after=graph(row['before']),graph(row['after']);ids,coords,edges=references[row['film']];coords=coords.astype(float);coords[:,1:]*=[1.625,.40625,.40625];truth=backend.Graph(ids,coords,np.array(sorted(edges)));hist=backend.account([before,after],truth);bv=np.array([r['visibility'][0] for r in hist],bool);av=np.array([r['visibility'][1] for r in hist],bool);pairs.append({'film':row['film'],'mechanism':row['mechanism'],'split':row['split'],'reference_edges':len(edges),'changed_coordinate_nodes':int(np.any(before.coords!=after.coords,axis=1).sum()),'gains':int((~bv&av).sum()),'losses':int((bv&~av).sum()),'control_FN':int((~bv).sum()),'intervention_FN':int((~av).sum())})
        groups=[]
        for mechanism in ['free_endpoint','lineage_junction','track_variance']:
            for split in ['development','transfer']:
                block=[r for r in pairs if r['mechanism']==mechanism and r['split']==split];groups.append({'mechanism':mechanism,'split':split,'films':len(block),**{k:sum(r[k] for r in block) for k in ['reference_edges','changed_coordinate_nodes','gains','losses','control_FN','intervention_FN']}})
        tags=['zero','head','head_pool','head_traj','head_pool_traj'];graphs={t:scorer.readgraph(root/'sdy'/(t+'.csv')) for t in tags};scores=[];visible={}
        for tag,films in graphs.items():
            for film,g in films.items():
                counts,vs=scorer.score(g,references[film]);visible[tag,film]=vs;scores.append({'arm':tag,'film':film,'counts':counts})
        contrasts=[]
        for b,d in [('zero','head'),('head','head_pool'),('head','head_traj'),('head_pool','head_pool_traj')]:
            for film in sorted(graphs[b]):contrasts.append({'before':b,'after':d,'film':film,'gains':len(visible[d,film]-visible[b,film]),'losses':len(visible[b,film]-visible[d,film])})
        write(a.output/'RESULT.json',{'SVM_pairs':pairs,'SVM_groups':groups,'SDY_scores':scores,'SDY_contrasts':contrasts,'scope':'Saved-output negative-result recount; not estimator or model retraining'})
        prior=list(csv.DictReader((root/'expected/SVM_pairs.csv').open(encoding='utf-8-sig')))
        assert len(prior)==len(pairs)==48
        for previous,current in zip(prior,pairs):
            assert previous['stem']==current['film'] and all(str(current[k])==previous[k] for k in current if k!='film')
        assert groups==read(root/'expected/SVM_report.json')['groups'];old=read(root/'expected/SDY_report.json');assert sorted(scores,key=lambda r:(r['arm'],r['film']))==sorted([{k:r[k] for k in ['arm','film','counts']} for r in old['rows']],key=lambda r:(r['arm'],r['film']))
        assert contrasts==[{k:r[k] for k in ['before','after','film','gains','losses']} for r in old['contrasts']]
        write(a.output/'COMPARISON.json',{'all48_SVM_pairs_groups_and20_SDY_scores_equal':True})


if __name__=='__main__':main()
