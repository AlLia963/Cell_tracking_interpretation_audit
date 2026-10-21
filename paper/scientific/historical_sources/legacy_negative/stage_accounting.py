"""Graph-only measurement framework. No injection logs or causal oracle inputs.

Coordinates: (time,z,y,x), spatial coordinates already in micrometres.
The loader must explicitly convert pixel coordinates before constructing Graph.
"""
from dataclasses import dataclass
import numpy as np
from scipy.optimize import linear_sum_assignment


@dataclass
class Graph:
    ids: np.ndarray
    coords: np.ndarray
    edges: np.ndarray

    def __post_init__(self):
        self.ids = np.asarray(self.ids, dtype=np.int64)
        self.coords = np.asarray(self.coords, dtype=float).reshape(-1, 4)
        self.edges = np.asarray(self.edges, dtype=np.int64).reshape(-1, 2)
        if len(self.ids) != len(self.coords) or len(set(self.ids)) != len(self.ids):
            raise ValueError('IDs must be unique and align with coordinates')
        if not np.isfinite(self.coords).all():
            raise ValueError('Nonfinite coordinates')
        if not np.equal(self.coords[:, 0], np.floor(self.coords[:, 0])).all():
            raise ValueError('Time must be integral')
        times = dict(zip(self.ids, self.coords[:, 0]))
        if any(a not in times or b not in times or times[a] >= times[b]
               for a, b in self.edges):
            raise ValueError('Edges require existing endpoints and increasing time')


def match(pred, reference, radius=7.0):
    """Maximum-cardinality gated matching, then minimum total distance.

    Canonical ID ordering makes input permutation irrelevant but does not claim
    scientifically unique solutions for tied distances. Dense assignment is
    suitable for the pilot, not yet benchmarked on full-resolution movies.
    """
    if radius <= 0 or not np.isfinite(radius):
        raise ValueError('Invalid radius')
    assignment = {}
    for t in np.unique(reference.coords[:, 0]):
        ri = np.flatnonzero(reference.coords[:, 0] == t)
        pi = np.flatnonzero(pred.coords[:, 0] == t)
        ri = ri[np.argsort(reference.ids[ri])]
        pi = pi[np.argsort(pred.ids[pi])]
        if not len(pi):
            continue
        distance = np.linalg.norm(reference.coords[ri, None, 1:] -
                                  pred.coords[None, pi, 1:], axis=2)
        forbidden = (min(len(ri), len(pi)) + 1) * (radius + 1)
        cost = np.where(distance <= radius, distance, forbidden)
        rows, cols = linear_sum_assignment(cost)
        for r, c in zip(rows, cols):
            if distance[r, c] <= radius:
                assignment[int(reference.ids[ri[r]])] = int(pred.ids[pi[c]])
    return assignment


def account(stages, reference, radius=7.0):
    if len(stages) < 2:
        raise ValueError('At least two ordered exports required')
    matches = [match(s, reference, radius) for s in stages]
    edge_sets = [set(map(tuple, s.edges.tolist())) for s in stages]
    records = []
    for a, b in reference.edges:
        pairs = [(m.get(int(a)), m.get(int(b))) for m in matches]
        visible = [int(None not in pair and pair in es)
                   for pair, es in zip(pairs, edge_sets)]
        losses = [k for k in range(1, len(stages))
                  if visible[k - 1] and not visible[k]]
        gains = [k for k in range(1, len(stages))
                 if not visible[k - 1] and visible[k]]
        pathways = []
        for k in losses:
            prev, curr = pairs[k - 1], pairs[k]
            if None in curr:
                removed = not set(prev).issubset(set(stages[k].ids.tolist()))
                path = 'matched-endpoint-removed' if removed else 'endpoint-unmatched'
            elif prev != curr:
                path = 'matched-identifiers-reassigned'
            else:
                path = 'matched-pair-edge-deleted'
            pathways.append({'stage': k, 'pathway': path})
        records.append({'reference_edge': [int(a), int(b)],
                        'visibility': visible, 'matched_pairs': pairs,
                        'loss_stages': losses, 'gain_stages': gains,
                        'first_observed_loss': losses[0] if losses else None,
                        'persistent_absence': not any(visible),
                        'final_missing': not bool(visible[-1]),
                        'loss_pathways': pathways,
                        'causal_responsibility': 'not-established-by-graph-record'})
    return records
