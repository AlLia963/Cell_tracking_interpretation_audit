"""Relocatable adapter for the historical cached-coordinate replay, not image inference."""
from pathlib import Path
from collections import defaultdict
import sys,copy,json,argparse
import numpy as np
R=Path(__file__).resolve().parents[1];D=R/'05_补证与核验/16片局部重放_历史证据'
sys.dont_write_bytecode=True;sys.path.insert(0,str(D/'sources'));import heterogeneous_estimator as estimator
p=argparse.ArgumentParser();p.add_argument('--film',required=True);p.add_argument('--output',required=True);a=p.parse_args();base=D/'inputs'/a.film
with np.load(base/'repaired_graph.npz',allow_pickle=False)as z:ids,coords,edges=[z[k].copy()for k in ['ids','coords','edges']]
with np.load(base/'native_coordinates.npz',allow_pickle=False)as z:ni,nc=z['ids'].copy(),z['coords'].copy()
nodes={int(i):dict(node_id=int(i),t=int(c[0]),z=float(c[1]),y=float(c[2]),x=float(c[3]))for i,c in zip(ids,coords)};frozen=copy.deepcopy(nodes)
for i,c in zip(ni,nc):
    if int(i)in nodes:nodes[int(i)].update(t=int(c[0]),z=float(c[1]),y=float(c[2]),x=float(c[3]))
stats=defaultdict(int);result=estimator.smooth(nodes,[dict(source_id=int(u),target_id=int(v))for u,v in edges],stats,set(map(int,ni)),lambda *args:copy.deepcopy(frozen));oi=np.array(sorted(result),np.int64);oc=np.maximum(0,np.round(np.array([[result[int(i)][k]for k in ['t','z','y','x']]for i in oi])))
with np.load(base/'expected.npz',allow_pickle=False)as z:checks={'ids':np.array_equal(oi,z['ids']),'coords':np.array_equal(oc,z['coords']),'edges':np.array_equal(edges,z['edges'])}
assert all(checks.values());dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps({'status':'PASS','film':a.film,'exact_arrays':checks,'scope':'native cached coordinates and repaired graph to local smoother; no image inference','stats':dict(stats)},indent=2),encoding='utf8');print(checks)
