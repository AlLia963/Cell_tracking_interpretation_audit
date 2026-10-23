"""Execute the original graph-only processing cells with an explicit ranker root."""
from pathlib import Path
import hashlib,json,os
import tracksdata as td

def build_sim_env(ranker_root):
    here=Path(__file__).resolve().parent
    source=json.loads((here/'SOURCE.json').read_text(encoding='utf-8'))
    ranker_root=Path(ranker_root).resolve()
    if not (ranker_root/'model/local_association_ranker.pt').is_file():raise FileNotFoundError('Declared ranker checkpoint missing')
    # Prevent external environment settings from silently altering the experiment.
    for key in list(os.environ):
        if key.startswith('BIOHUB_'):del os.environ[key]
    os.environ['BIOHUB_LOCAL_RANKER_ROOT']=str(ranker_root)
    ns={'os':os,'Path':Path,'__name__':'v75_sim'}
    for row in source['cells']:
        path=here/row['file'];data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('Original processing cell identity mismatch')
        exec(compile(data,str(path),'exec'),ns)
    if ns.get('LOCAL_ASSOCIATION_RANKER') is None:raise RuntimeError('Ranker unavailable')
    return ns

def load_gt(path):
    g=td.graph.IndexedRXGraph.from_geff(str(path))
    if isinstance(g,tuple):g=g[0]
    na=g.node_attrs();ea=g.edge_attrs()
    nodes={int(r['node_id']):(float(r['t']),float(r['z']),float(r['y']),float(r['x'])) for r in na.iter_rows(named=True)}
    edges=[(int(r['source_id']),int(r['target_id'])) for r in ea.iter_rows(named=True)]
    n_est=float('nan')
    try:
        meta=json.loads((path/'zarr.json').read_text())
        n_est=float((meta.get('attributes',{}).get('geff',{}).get('extra',{}) or {}).get('estimated_number_of_nodes',float('nan')))
    except Exception:pass
    return nodes,edges,n_est
