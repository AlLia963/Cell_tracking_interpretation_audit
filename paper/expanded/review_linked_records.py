"""Literal checks of all 216 stored comparison endpoint witnesses."""
from pathlib import Path
from functools import lru_cache
import argparse,json
import numpy as np
import verify_endpoints as V
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--corpus',type=Path,required=True);p.add_argument('--records',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
if a.output.exists():raise FileExistsError('Use a new output file')
load=lru_cache(maxsize=3000)(V.read);V.read=load
@lru_cache(maxsize=100)
def npz(p):
    with np.load(p,allow_pickle=False)as z:return {k:z[k].copy()for k in z.files}
records=[]
for path in sorted(a.records.glob('linked_records/*/*.json.gz'))+sorted(a.records.glob('motion_linked/*.json.gz')):
    r=load(path);gids=[r['before_graph'],r['after_graph']];c=V.verify(r,npz(a.corpus/'references'/(r['film']+'.npz')),[npz(a.corpus/'graphs'/(g+'.npz'))for g in gids],[load(a.corpus/'graph_reports'/(g+'.json.gz'))for g in gids],a.corpus/'frame_cache');records.append({'record':str(path.relative_to(a.records)),**c})
if len(records)!=216:raise ValueError('Expected complete declared 208 plus 8 comparison set')
out={'status':'ALL_LINKED_ENDPOINTS_PASS','comparisons':len(records),'witnesses':sum(r['witnesses']for r in records),'scope':'Existence, stored-family membership and equality checks; not primitive-family completeness or extremality by replay alone','records':records}
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2),encoding='utf8');print(out['status'])
