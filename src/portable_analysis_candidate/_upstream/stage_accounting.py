"""Graph-only measurement framework. No injection logs or causal oracle inputs.

Coordinates: (time,z,y,x), spatial coordinates in the explicitly declared unit (um or pixel).
The loader must explicitly convert pixel coordinates before constructing Graph.
"""
from dataclasses import dataclass
import numpy as np
from scipy.optimize import linear_sum_assignment


def integral_array(values, name, dimensions, trailing=None):
    array = np.asarray(values)
    if array.dtype.kind not in 'iu' or array.dtype.kind == 'b':
        raise ValueError(f'{name} must have an integer dtype; no float/bool coercion')
    if array.ndim != dimensions or (trailing is not None and array.shape[-1] != trailing):
        raise ValueError(f'{name} has invalid shape')
    if array.dtype.kind == 'u' and array.size and int(array.max()) > np.iinfo(np.int64).max:
        raise ValueError(f'{name} exceeds signed int64')
    return array.astype(np.int64, copy=True)


@dataclass
class Graph:
    ids: np.ndarray
    coords: np.ndarray
    edges: np.ndarray
    unit: str

    def __post_init__(self):
        if self.unit not in ('um', 'pixel'):
            raise ValueError('Explicit supported coordinate unit required')
        self.ids = integral_array(self.ids, 'ids', 1)
        self.edges = integral_array(self.edges, 'edges', 2, 2)
        raw = np.asarray(self.coords)
        if raw.dtype.kind not in 'iuf' or raw.ndim != 2 or raw.shape[1] != 4:
            raise ValueError('coords must be a numeric Nx4 array: frame,z,y,x')
        if np.any(raw[:,0]>=2**53) or np.any(raw[:,0]<=-2**53):
            raise ValueError('Frame outside exact float-integer range; use an integer-frame adapter')
        self.coords = raw.astype(float, copy=True)
        if len(self.ids) != len(self.coords) or len(set(self.ids)) != len(self.ids):
            raise ValueError('IDs must be unique and align with coordinates')
        if not np.isfinite(self.coords).all():
            raise ValueError('Nonfinite coordinates')
        if not np.equal(self.coords[:, 0], np.floor(self.coords[:, 0])).all():
            raise ValueError('Frame index must be integral')
        if len(set(map(tuple, self.edges))) != len(self.edges):
            raise ValueError('Duplicate edges would change metric denominators')
        times = dict(zip(self.ids, self.coords[:, 0]))
        if any(a not in times or b not in times or times[a] >= times[b] for a,b in self.edges):
            raise ValueError('Edges require existing endpoints and increasing time')


def load_npz(path, *, declared_unit=None):
    """Require archive unit or explicit adapter declaration; reject disagreement.

    A declaration supplies missing metadata, never scales coordinates. Caller
    must document provenance of the unit and any conversion before this loader.
    """
    with np.load(path, allow_pickle=False) as data:
        unit = None
        if 'unit' in data:
            value = data['unit']
            if value.shape != () or value.dtype.kind != 'U':
                raise ValueError('unit metadata must be scalar Unicode')
            unit = str(value.item())
        if unit is None:
            if declared_unit is None:
                raise ValueError('Archive has no unit: explicit adapter declaration required')
            unit = declared_unit
        elif declared_unit is not None and declared_unit != unit:
            raise ValueError('Unit metadata and adapter declaration disagree')
        return Graph(data['ids'], data['coords'], data['edges'], unit)


def match(pred, reference, radius):
    """Maximum-cardinality gated matching, then minimum total distance.

    Canonical ID ordering makes input permutation irrelevant but does not claim
    scientifically unique solutions for tied distances. Dense assignment is
    suitable for the pilot, not yet benchmarked on full-resolution movies.
    """
    if pred.unit != reference.unit:
        raise ValueError("Matching coordinate units differ")
    if isinstance(radius,(bool,np.bool_)) or not isinstance(radius,(int,float,np.integer,np.floating)) or radius <= 0 or not np.isfinite(radius):
        raise ValueError('Invalid radius')
    assignment = {}
    for t in np.unique(reference.coords[:, 0]):
        ri = np.flatnonzero(reference.coords[:, 0] == t)
        pi = np.flatnonzero(pred.coords[:, 0] == t)
        ri = ri[np.argsort(reference.ids[ri])]
        pi = pi[np.argsort(pred.ids[pi])]
        if not len(pi):
            continue
        try:
            with np.errstate(over='raise',invalid='raise'):
                delta = reference.coords[ri,None,1:] - pred.coords[None,pi,1:]
                distance = np.hypot.reduce(delta,axis=2)
        except FloatingPointError as error:
            raise ValueError('Spatial distance outside representable numeric range') from error
        # Normalize allowed costs to [0,1], avoiding radius-dependent overflow.
        forbidden = float(min(len(ri),len(pi))+2)
        cost = np.full(distance.shape,forbidden)
        allowed = distance<=radius
        if allowed.any():
            values=distance[allowed]
            normalizer=float(values.max()) or 1.0
            normalized=values/normalizer
            if np.any((values>0)&(normalized==0)):
                raise ValueError('Distance normalization loses distinct positive costs; unsupported numeric range')
            cost[allowed]=normalized
        rows, cols = linear_sum_assignment(cost)
        for r, c in zip(rows, cols):
            if distance[r, c] <= radius:
                assignment[int(reference.ids[ri[r]])] = int(pred.ids[pi[c]])
    return assignment


def account(stages, reference, radius):
    return account_from_matches(stages, reference, [match(stage,reference,radius) for stage in stages])


def account_from_matches(stages, reference, matches):
    """Visibility accounting from explicitly supplied object correspondence.

    Adapter must separately validate its estimand and matching algorithm. This
    interface validates identity/frame/one-to-one schema, not scientific truth.
    """
    if len(stages)<2 or len(matches)!=len(stages):
        raise ValueError('Ordered stage/matching lengths invalid')
    ref_time=dict(zip(reference.ids,reference.coords[:,0]))
    for stage,mapping in zip(stages,matches):
        if stage.unit!=reference.unit:
            raise ValueError('Graph bookkeeping units differ')
        pred_time=dict(zip(stage.ids,stage.coords[:,0]))
        if not isinstance(mapping,dict):
            raise ValueError('Correspondence must be a partial dict')
        for r,p in mapping.items():
            if isinstance(r,(bool,np.bool_)) or isinstance(p,(bool,np.bool_)) or not isinstance(r,(int,np.integer)) or not isinstance(p,(int,np.integer)):
                raise ValueError('Correspondence identifiers require integer types')
            if r not in ref_time or p not in pred_time or ref_time[r]!=pred_time[p]:
                raise ValueError('Correspondence requires existing same-frame endpoints')
        if len(set(mapping.values()))!=len(mapping):
            raise ValueError('Correspondence must be one-to-one')
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

