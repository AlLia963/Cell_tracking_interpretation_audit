"""Check paired-input identities, reference denominators and coordinate grids."""
from pathlib import Path
from functools import lru_cache
import argparse,csv,json
import numpy as np

def run(comparisons,corpus,output):
    rows=list(csv.DictReader(Path(comparisons).open(encoding='utf-8-sig')));corpus=Path(corpus)
    @lru_cache(maxsize=8)
    def load(gid,kind='graphs'):
        with np.load(corpus/kind/(gid+'.npz'),allow_pickle=False) as z:return {k:z[k].copy() for k in z.files}
    result=[]
    for r in rows:
        ref=load(r['film'],'references');gs=[load(r[side+'_graph']) for side in ['before','after']]
        ix=[np.argsort(g['ids']) for g in gs]; aligned=[g['ids'][i] for g,i in zip(gs,ix)]
        same_ids=np.array_equal(*aligned)
        grid=[]
        for g in gs:
            px=g['coords'][:,1:]/np.array([1.625,.40625,.40625])
            grid.append({'dtype':str(g['coords'].dtype),'spatial_values':int(px.size),'on_integer_pixel_grid':int(np.equal(px,np.floor(px)).sum())})
        result.append({'design':r['design'],'film':r['film'],'reference_nodes':len(ref['ids']),'reference_relations':len(ref['edges']),'before_graph':r['before_graph'],'after_graph':r['after_graph'],'canonical_before_TP':int(r['canonical_before_TP']),'canonical_after_TP':int(r['canonical_after_TP']),'same_node_ids':same_ids,'same_coordinates_after_id_alignment':bool(same_ids and np.array_equal(gs[0]['coords'][ix[0]],gs[1]['coords'][ix[1]])),'same_edge_set':set(map(tuple,gs[0]['edges']))==set(map(tuple,gs[1]['edges'])),'coordinate_storage':grid})
    grouped=[]
    for design in sorted({r['design'] for r in result}):
        rr=[r for r in result if r['design']==design]
        grouped.append({'design':design,'movies':len(rr),'reference_nodes':sum(r['reference_nodes'] for r in rr),'reference_relations':sum(r['reference_relations'] for r in rr),'before_TP':sum(r['canonical_before_TP'] for r in rr),'after_TP':sum(r['canonical_after_TP'] for r in rr),**{k:sum(r[k] for r in rr) for k in ['same_node_ids','same_coordinates_after_id_alignment','same_edge_set']},'all_spatial_values_on_integer_pixel_grid':all(q['spatial_values']==q['on_integer_pixel_grid'] for r in rr for q in r['coordinate_storage'])})
    out={'groups':grouped,'per_movie':result,'grid_scope':'These focused CSV-derived inputs only; grid occupancy is checked after exact reversal of the declared scale. Not a claim about physical accuracy or all corpus formats.'}
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(out,indent=2),encoding='utf8');print(json.dumps(grouped,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--comparisons',required=True);p.add_argument('--corpus',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(**vars(a))
