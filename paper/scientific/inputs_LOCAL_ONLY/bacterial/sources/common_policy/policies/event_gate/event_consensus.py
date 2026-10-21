"""Input-only event consistency: bilateral detector branches need reference support."""
import copy
from collections import defaultdict
import numpy as np
from scipy.spatial import cKDTree

SPACING=np.array([1.625,0.40625,0.40625])

def reciprocal_match(nodes, reference, radius=3.0):
    by_t=defaultdict(list);ref_t=defaultdict(list);matched={}
    for i,n in nodes.items():by_t[int(n['t'])].append(i)
    for i,n in reference.items():ref_t[int(n['t'])].append(i)
    for t,ids in by_t.items():
        ref=ref_t[t]
        if not ref:continue
        x=np.array([[nodes[i][k] for k in ['z','y','x']] for i in ids])*SPACING
        y=np.array([[reference[i][k] for k in ['z','y','x']] for i in ref])*SPACING
        dist,ii=cKDTree(y).query(x,k=min(2,len(ref)))
        back,bb=cKDTree(x).query(y,k=min(2,len(ids)))
        if len(ref)==1:dist=dist[:,None];ii=ii[:,None]
        if len(ids)==1:back=back[:,None];bb=bb[:,None]
        for a,i in enumerate(ids):
            b=int(ii[a,0])
            if dist[a,0]>radius or int(bb[b,0])!=a:continue
            if (dist.shape[1]>1 and np.isclose(dist[a,0],dist[a,1])) or (back.shape[1]>1 and np.isclose(back[b,0],back[b,1])):continue
            matched[i]=ref[b]
    return matched

def gate(nodes, edges, raw_edges, reference_nodes, reference_edges, stats,
         observed=None,reference_observed=None):
    """Preserve native observations and one-to-one topology; suppress unsupported added forks.

    E and B node IDs belong to different graphs; reciprocal spatial matching is mandatory.
    Ambiguous or absent matching does not grant a branch consensus. The continuation is
    retained by original native-edge identity; a fork with no identifiable native edge
    is left unchanged rather than inventing an arbitrary continuation.
    """
    # Production must not treat repair-generated points as independent evidence.
    # Explicit observation sets also make the result invariant to synthetic-node
    # interpolation/smoothing order. None preserves the first frozen replay API.
    matching_nodes=nodes if observed is None else {i:n for i,n in nodes.items() if i in observed}
    matching_reference=reference_nodes if reference_observed is None else {i:n for i,n in reference_nodes.items() if i in reference_observed}
    mapping=reciprocal_match(matching_nodes,matching_reference)
    raw={(int(e['source_id']),int(e['target_id'])) for e in raw_edges}
    out=defaultdict(list);ref=defaultdict(set)
    for e in edges:out[int(e['source_id'])].append(int(e['target_id']))
    for e in reference_edges:ref[int(e['source_id'])].add(int(e['target_id']))
    removed=set();detail=[]
    for s,targets in out.items():
        if len(targets)!=2:continue
        native=[t for t in targets if (s,t) in raw]
        if len(native)!=1:
            detail.append(dict(source=s,targets=targets,decision='unresolved_native'))
            continue
        rs=mapping.get(s);rt={mapping.get(t) for t in targets}
        supported=rs is not None and None not in rt and rt==ref.get(rs,set())
        if not supported:removed.add((s,next(t for t in targets if t!=native[0])))
        detail.append(dict(source=s,targets=targets,reference_parent=rs,reference_children=sorted(t for t in rt if t is not None),decision='keep' if supported else 'suppress'))
    stats['event_consensus_forks']=len(detail)
    stats['event_consensus_suppressed']=len(removed)
    stats['event_consensus_matched_nodes']=len(mapping)
    return [e for e in edges if (int(e['source_id']),int(e['target_id'])) not in removed],detail


def install_precomputed(ns,reference_provider):
    """Install after D trajectory estimator, before the production writer.

    reference_provider(dataset) must return a dict with `raw_nodes`, `nodes`,
    `edges` for the E front-end graph after the same E repair/short-track stages.
    Its final coordinates are irrelevant: matching uses native E coordinates and
    final E membership. Native IDs must stay within each individual graph.
    The provider should read precomputed per-film references, not recursively
    call this wrapped namespace. No graph or labels from another movie may enter.

    The E references can be materialized in a separate postprocess pass using the
    unmodified E filter. Its coordinates may be smoothed; native coordinates are
    restored here. Each graph is loaded on demand, so memory is per-film bounded.
    """
    old_filter=ns['filter_output_graph'];old_smooth=ns['linefit_smooth_output_graph'];state={}
    def filtered(nodes,edges,*args,**kwargs):
        assert not state,'Nested event consensus processing is unsupported'
        dataset=kwargs.get('dataset',args[0] if args else None)
        if not dataset:raise ValueError('Event consensus needs the current dataset name')
        reference=reference_provider(dataset)
        raw=reference['raw_nodes'];final=reference['nodes']
        state.update(observed=set(nodes),raw_edges=copy.deepcopy(edges),reference_nodes={i:raw[i] for i in final if i in raw},
                     reference_observed=set(raw),reference_edges=reference['edges'])
        try:return old_filter(nodes,edges,*args,**kwargs)
        finally:state.clear()
    def smooth(nodes,edges,stats):
        assert state,'Native observations must be captured before event repair'
        revised,detail=gate(nodes,edges,state['raw_edges'],state['reference_nodes'],state['reference_edges'],stats,
                            observed=state['observed'],reference_observed=state['reference_observed'])
        edges[:]=revised
        return old_smooth(nodes,edges,stats)
    ns['filter_output_graph']=filtered;ns['linefit_smooth_output_graph']=smooth
    return ns


def install(ns,reference_loader,smoother):
    """Complete two-graph postprocess, installed on E before a trajectory wrapper.

    `reference_loader(dataset) -> (native_E_nodes, native_E_edges)` loads one
    same-input E GEFF. `smoother(nodes,edges,stats,observed,original)` is D or an
    independently validated successor. The original E repairs run for E and B.
    E needs only final topology/membership, so its unused smoothing is skipped.
    B gate runs after repairs/short-track filtering, before the passed smoother.
    No E node IDs are copied into the B graph. Only B returns to the CSV writer.
    """
    old_filter=ns['filter_output_graph'];old_smooth=ns['linefit_smooth_output_graph'];state={}
    def filtered(nodes,edges,*args,**kwargs):
        assert not state,'Nested event consensus processing is unsupported'
        dataset=kwargs.get('dataset',args[0] if args else None)
        if not dataset:raise ValueError('Event consensus needs the current dataset name')
        reference_nodes,reference_edges=reference_loader(dataset)
        reference_raw=copy.deepcopy(reference_nodes)
        state.update(phase='reference',observed=set(nodes),raw_edges=copy.deepcopy(edges))
        try:
            ref_final,ref_edges,ref_stats=old_filter(copy.deepcopy(reference_nodes),copy.deepcopy(reference_edges),*args,**kwargs)
            state.update(phase='candidate',reference_nodes={i:reference_raw[i] for i in ref_final if i in reference_raw},
                         reference_observed=set(reference_raw),reference_edges=ref_edges)
            result=old_filter(nodes,edges,*args,**kwargs)
            result[2]['event_consensus_reference_nodes']=len(ref_final)
            result[2]['event_consensus_reference_edges']=len(ref_edges)
            return result
        finally:state.clear()
    def smooth(nodes,edges,stats):
        assert state,'Native observations must be captured before event repair'
        if state['phase']=='reference':return nodes
        revised,detail=gate(nodes,edges,state['raw_edges'],state['reference_nodes'],state['reference_edges'],stats,
                            observed=state['observed'],reference_observed=state['reference_observed'])
        edges[:]=revised
        return smoother(nodes,edges,stats,state['observed'],old_smooth)
    ns['filter_output_graph']=filtered;ns['linefit_smooth_output_graph']=smooth
    return ns
