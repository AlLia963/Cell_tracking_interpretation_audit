"""Typed local-window accounting from actual registered mask views.

Two microscopy frames are distinct from the ordered processing views. Endpoint
frames are explicit MaskFrame fields, not decoded from IDs. Correspondence is
strict IoU>1/2 with disjoint reference supports; predictions may overlap.
No inference, receipt, fault label, or expected answer enters this function.
Input guards do not certify biological events or an independent matcher.
"""
import numpy as np
from ._upstream.mask_correspondence import MaskFrame
from ._upstream.stage_accounting import Graph, account_from_matches
from ._upstream.exact_disjoint_envelope import envelope, edge_envelope
from ._upstream.typed_pathways import annotate_typed_pathways

def _id(value, label):
    if isinstance(value,(bool,np.bool_)) or not isinstance(value,(int,np.integer)):
        raise ValueError(label+' requires integer IDs without float/bool coercion')
    value=int(value)
    if not -(2**63)<=value<2**63:raise ValueError(label+' exceeds signed int64')
    return value

def _pair(pair,label):
    if not isinstance(pair,(list,tuple,np.ndarray)) or (isinstance(pair,np.ndarray) and pair.ndim!=1) or len(pair)!=2:
        raise ValueError(label+' requires directed two-ID pairs')
    return tuple(_id(x,label) for x in pair)

def _pairs(values,label):
    if not isinstance(values,(list,tuple,set,frozenset,np.ndarray)) or (isinstance(values,np.ndarray) and values.ndim!=2):
        raise ValueError(label+' requires a pair collection')
    result=set()
    for pair in values:
        pair=_pair(pair,label)
        if pair in result:raise ValueError(label+' contains duplicate directed pairs')
        result.add(pair)
    return result

def _frames(frames,label):
    if not isinstance(frames,(list,tuple)) or len(frames)!=2:
        raise ValueError(label+' requires two explicit MaskFrames')
    for f in frames:
        if not isinstance(f,MaskFrame):raise ValueError(label+' requires MaskFrame objects')
        if not isinstance(f.ids,np.ndarray) or f.ids.ndim!=1 or f.ids.dtype.kind not in 'iu':
            raise ValueError('Unique typed integer instance IDs required')
        ids=[_id(x,'MaskFrame') for x in f.ids]
        if len(ids)!=len(set(ids)):raise ValueError('Duplicate MaskFrame IDs')
        if not isinstance(f.masks,np.ndarray) or f.masks.ndim!=3 or f.masks.dtype.kind!='b' or len(f.masks)!=len(ids):
            raise ValueError('Explicit NxHxW boolean instance support required')
        frame=_id(f.frame,'Frame index')
        if not -2**53<frame<2**53:raise ValueError('Frame outside exact float-integer range')
        if not isinstance(f.support_definition,str) or not f.support_definition.strip():
            raise ValueError('Declare support interpretation')
    if not frames[0].frame<frames[1].frame:raise ValueError('Frame order must be increasing')
    if set(map(int,frames[0].ids))&set(map(int,frames[1].ids)):
        raise ValueError('Node IDs must be unique across the two explicit frames')
    return frames

def _graph(frames, edges):
    ids=np.concatenate([f.ids for f in frames]);coords=[]
    if len(set(map(int,ids)))!=len(ids):
        raise ValueError('Node IDs must be unique across the two explicit frames')
    for f in frames:
        for mask in f.masks:
            xy=np.argwhere(mask).mean(axis=0) if mask.any() else [0.,0.]
            coords.append([f.frame,0.,float(xy[0]),float(xy[1])])
    if any(a not in ids or b not in ids for a,b in edges):
        raise ValueError('Every supplied edge requires existing endpoint IDs')
    return Graph(ids,np.asarray(coords).reshape(-1,4),
                 np.asarray(sorted(edges),dtype=np.int64).reshape(-1,2),'pixel')

def _check_view(view, refs):
    if not isinstance(view,dict) or set(view)!= {'previous','current','edges','division'}:
        raise ValueError('View requires previous/current MaskFrames and raw/division edge sets')
    frames=_frames([view['previous'],view['current']],'View')
    edges=_pairs(view['edges'],'Raw edges');division=_pairs(view['division'],'Division edges')
    if not division<=edges:raise ValueError('Division labels must be a subset of raw edges')
    for pred,ref in zip(frames,refs):
        if pred.frame!=ref.frame or pred.masks.shape[1:]!=ref.masks.shape[1:]:
            raise ValueError('Explicit matching frame and registered grid required')
    earlier=set(map(int,frames[0].ids));later=set(map(int,frames[1].ids))
    if any(a not in earlier or b not in later for a,b in edges):
        raise ValueError('All local edges must point from previous to current frame')
    return frames,edges,division

def _ordered_views(views):
    if not isinstance(views,(list,tuple)) or len(views)<2:
        raise ValueError('At least two ordered processing views required')
    return views

def account_typed_mask_window(views, references, reference_edges):
    """Return records and complete ID options under the declared mask rule.

    `reference_edges` maps directed pairs to continuation/division. Certain/
    possible typed visibility is computed for each edge at each processing
    view. This does not certify arbitrary joint whole-graph extrema or a
    coupled history distribution. Pathways are observational, not causal.
    """
    views=_ordered_views(views);references=_frames(references,'Reference')
    if not isinstance(reference_edges,dict):raise ValueError('Typed reference edges require a dict')
    if any(k not in ('continuation','division') for k in reference_edges.values()):
        raise ValueError('Explicit continuation/division labels required')
    reference_edges={_pair(e,'Reference edges'):kind for e,kind in reference_edges.items()}
    earlier=set(map(int,references[0].ids));later=set(map(int,references[1].ids))
    if any(a not in earlier or b not in later for a,b in reference_edges):
        raise ValueError('Reference edges require previous-to-current endpoint IDs')
    checked=[_check_view(v,references) for v in views]
    domains=[]
    for frames,_,_ in checked:
        domains.append({**envelope(frames[0],references[0]),**envelope(frames[1],references[1])})
    records=[]
    rawviews=[{'edges':edges,'division':division} for _,edges,division in checked]
    for kind in ('continuation','division'):
        selected={e for e,k in reference_edges.items() if k==kind}
        edge_sets=[division if kind=='division' else edges-division for _,edges,division in checked]
        gs=[_graph(frames,edges) for (frames,_,_),edges in zip(checked,edge_sets)]
        reference=_graph(references,selected)
        canonical=[{r:opts[0] for r,opts in d.items() if opts} for d in domains]
        accounted=account_from_matches(gs,reference,canonical)
        for rec in accounted:
            a,b=rec['reference_edge']
            bounds=[edge_envelope(d[a],d[b],es) for d,es in zip(domains,edge_sets)]
            rec.update(kind=kind,bounds=bounds,
                ambiguous_visibility=any(lo!=hi for lo,hi in bounds),
                ambiguous_correspondence=any(len(d[a])>1 or len(d[b])>1 for d in domains))
            rec['unique_boundary']=('withheld-ambiguity' if rec['ambiguous_visibility'] else
                rec['loss_stages'][-1] if rec['final_missing'] and rec['loss_stages'] else None)
            records.append(rec)
    return annotate_typed_pathways(records,rawviews),domains

def _domains(domains,checked,edge):
    if not isinstance(domains,(list,tuple)) or len(domains)!=len(checked):
        raise ValueError('Exactly one ordered ID domain per processing view required')
    result=[];keyset=None
    for d,(frames,_,_) in zip(domains,checked):
        if not isinstance(d,dict):raise ValueError('Each ID domain requires a dict')
        normalized={};slots=[set(map(int,f.ids)) for f in frames]
        for key,options in d.items():
            key=_id(key,'Domain reference')
            if not isinstance(options,(list,tuple,np.ndarray)) or (isinstance(options,np.ndarray) and options.ndim!=1):
                raise ValueError('Domain options require an ID sequence; empty means unmatched')
            candidates=tuple(None if x is None else _id(x,'Domain candidate') for x in options)
            if len(set(candidates))!=len(candidates):raise ValueError('Duplicate domain candidates')
            slot=slots[0] if key==edge[0] else slots[1] if key==edge[1] else slots[0]|slots[1]
            if any(x is not None and x not in slot for x in candidates):
                raise ValueError('Domain candidates require existing IDs in the corresponding frame')
            normalized[key]=candidates
        keys=set(normalized)
        if not set(edge)<=keys or (keyset is not None and keys!=keyset):
            raise ValueError('Complete consistent domain keys and queried endpoints required')
        keyset=keys;result.append(normalized)
    return result

def adjacent_difference_baseline(views,domains,edge,kind):
    """Same-information adjacent differencing, not an independent matcher.

    Ordered views/domains must be equally complete, with typed IDs and same-frame
    candidates for queried endpoints. Empty domains/None options mean absence.
    Supplied domains are not independently re-matched or certified optimal.
    Migration of the previously accepted comparator; its equivalence is
    admissible. The last loss is conditional on final absence.
    """
    if kind not in ('continuation','division'):raise ValueError('Explicit relation type required')
    views=_ordered_views(views);edge=_pair(edge,'Reference edge')
    if edge[0]==edge[1]:raise ValueError('Reference edge endpoints must be distinct across frames')
    if not isinstance(views[0],dict) or not {'previous','current'}<=set(views[0]):
        raise ValueError('View requires explicit MaskFrame pair')
    refs=_frames([views[0]['previous'],views[0]['current']],'Baseline frame')
    checked=[_check_view(v,refs) for v in views]
    domains=_domains(domains,checked,edge)
    history=[]
    for (_,raw,div),d in zip(checked,domains):
        edges=div if kind=='division' else raw-div
        vals=[(a,b) in edges for a in d[edge[0]] for b in d[edge[1]]]
        if vals and any(vals)!=all(vals):return 'withheld-ambiguity'
        history.append(int(bool(vals) and all(vals)))
    if history[-1]:return None
    last=None
    for k in range(1,len(history)):
        if history[k-1] and not history[k]:last=k
    return last
