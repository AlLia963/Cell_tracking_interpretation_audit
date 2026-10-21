"""Fixed, conservative topology completion after final coordinate estimation."""
from collections import defaultdict
import numpy as np
from scipy.spatial import cKDTree

SPACING = np.array([1.625, .40625, .40625])


def complete(ids, coords, edges):
    ids = np.asarray(ids); coords = np.asarray(coords); edges = np.asarray(edges)
    pos = {int(i): np.asarray(c[1:], dtype=float)*SPACING for i, c in zip(ids, coords)}
    times = {int(i): int(c[0]) for i, c in zip(ids, coords)}
    pre, suc, frames = defaultdict(list), defaultdict(list), defaultdict(list)
    for i in ids: frames[times[int(i)]].append(int(i))
    for a,b in edges:
        a,b=int(a),int(b)
        assert times[b] == times[a]+1
        pre[b].append(a); suc[a].append(b)
    assert all(len(v)<=1 for v in pre.values())
    trees = {t:cKDTree(np.array([pos[i] for i in ns])) for t,ns in frames.items()}
    # Least-squares three-point continuation at t=3 from observations t=0,1,2.
    def prediction(i, direction):
        chain=[i]; neighbours=pre if direction==1 else suc
        reverse=suc if direction==1 else pre
        for _ in range(2):
            n=neighbours.get(chain[-1],[])
            if len(n)!=1 or len(reverse.get(n[0],[]))!=1: return None
            chain.append(n[0])
        p=np.array([pos[j] for j in chain[::-1]])
        return (-2*p[0]+p[1]+4*p[2])/3.
    forwards={i:prediction(i,1) for i in pos if not suc.get(i)}
    backwards={i:prediction(i,-1) for i in pos if not pre.get(i)}
    forwards={i:p for i,p in forwards.items() if p is not None}
    backwards={i:p for i,p in backwards.items() if p is not None}
    def nearest(t,p):
        if t not in trees: return None, float('inf')
        ds,ii=trees[t].query(p,k=2)
        if abs(ds[0]-ds[1])<1e-10: return None, float(ds[0])
        return frames[t][int(ii[0])],float(ds[0])
    actions=[]
    for a,p in sorted(forwards.items()):
        b,fd=nearest(times[a]+1,p)
        if b not in backwards or fd>3.:continue
        back,bd=nearest(times[a],backwards[b])
        if back!=a or bd>3.:continue
        distance=float(np.linalg.norm(pos[b]-pos[a]))
        if distance>6.:continue
        actions.append(dict(source_id=a,target_id=b,forward_error_um=fd,backward_error_um=bd,distance_um=distance))
    extras=np.asarray([[a['source_id'],a['target_id']] for a in actions],dtype=edges.dtype).reshape(-1,2)
    result=np.concatenate([edges,extras],axis=0)
    assert len(set(map(tuple,result)))==len(result)
    return result,dict(actions=actions,eligible_source_ends=len(forwards),eligible_target_starts=len(backwards))
