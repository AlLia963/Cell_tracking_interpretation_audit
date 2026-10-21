import numpy as np
import collections
from scipy.optimize import linear_sum_assignment
SCALE=np.array([1.625,.40625,.40625])

def score(g, truth):
    ids = np.array(sorted(g['nodes']), dtype=np.int64)
    coords = np.array([g['nodes'][int(i)] for i in ids])
    edges = g['edges']
    times = dict(zip(ids, coords[:, 0]))
    degree = collections.Counter((a for a, b in edges))
    if len(set(edges)) != len(edges):
        raise ValueError('duplicate edges require cleanup')
    if max(degree.values(), default=0) > 2:
        raise ValueError('degree cap active')
    for a, b in edges:
        if a not in times or b not in times or times[b] - times[a] != 1:
            raise ValueError('missing or nonadjacent endpoints')
    gi, gc, ge = truth
    mapping = {}
    for t in np.unique(gc[:, 0]):
        rr = np.flatnonzero(gc[:, 0] == t)
        pp = np.flatnonzero(coords[:, 0] == t)
        if not len(pp):
            continue
        distances = np.linalg.norm((gc[rr, None, 1:] - coords[None, pp, 1:]) * SCALE, axis=2)
        allowed = distances <= 7.0
        cost = np.where(allowed, distances, (min(len(rr), len(pp)) + 1) * 8.0)
        row, col = linear_sum_assignment(cost)
        mapping.update({int(ids[pp[b]]): int(gi[rr[a]]) for a, b in zip(row, col) if allowed[a, b]})
    outgoing = {a for a, b in ge}
    incoming = {b for a, b in ge}
    visible = set()
    fp = ignored = 0
    for a, b in edges:
        ma, mb = (mapping.get(a), mapping.get(b))
        if (ma, mb) in ge:
            visible.add((ma, mb))
        elif ma in outgoing or mb in incoming:
            fp += 1
        else:
            ignored += 1
    tp = len(visible)
    fn = len(ge) - tp
    return ({'TP': tp, 'FP': fp, 'FN': fn, 'ignored_predictions': ignored, 'predicted_nodes': len(ids), 'predicted_edges': len(edges), 'edge_jaccard': tp / (tp + fp + fn)}, visible)
