"""Only veto a B-added fork when E has a definite matching single-child topology."""
import copy
from collections import defaultdict
import numpy as np
from scipy.spatial import cKDTree

SPACING=np.array([1.625,.40625,.40625])

def reciprocal_match(nodes,reference,radius=3.0):
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

def gate(nodes,edges,raw_edges,reference_nodes,reference_edges,stats,observed=None,reference_observed=None):
    if observed is None or reference_observed is None:
        raise ValueError('Affirmative veto requires explicit native-observation provenance')
    matching_nodes={i:n for i,n in nodes.items() if i in observed}
    matching_reference={i:n for i,n in reference_nodes.items() if i in reference_observed}
    mapping=reciprocal_match(matching_nodes,matching_reference)
    raw={(int(e['source_id']),int(e['target_id'])) for e in raw_edges}
    out=defaultdict(list);ref=defaultdict(set)
    for e in edges:out[int(e['source_id'])].append(int(e['target_id']))
    for e in reference_edges:ref[int(e['source_id'])].add(int(e['target_id']))
    removed=set();details=[]
    for source,children in out.items():
        if len(children)!=2:continue
        native=[child for child in children if (source,child) in raw]
        reason='uncertain_native_continuation'
        rejected=False
        if len(native)==1:
            if any(i not in mapping for i in [source,*children]):reason='uncertain_mapping'
            else:
                source_ref=mapping[source];continuation_ref=mapping[native[0]]
                targets_ref=ref.get(source_ref,set())
                rejected=len(targets_ref)==1 and continuation_ref in targets_ref
                reason='confirmed_single_child_conflict' if rejected else 'no_confirmed_conflict'
                if rejected:removed.add((source,next(c for c in children if c!=native[0])))
        details.append(dict(source=source,targets=children,reference_parent=mapping.get(source),
                            reference_children=[mapping.get(c) for c in children],decision='suppress' if rejected else 'keep',reason=reason))
    stats['event_consensus_forks']=len(details)
    stats['event_consensus_suppressed']=len(removed)
    stats['event_consensus_matched_nodes']=len(mapping)
    stats['affirmative_veto_forks']=len(details)
    stats['affirmative_veto_suppressed']=len(removed)
    return [e for e in edges if (int(e['source_id']),int(e['target_id'])) not in removed],details

def install(ns,reference_loader,smoother):
    """Same production interface as strict consensus; only the gate changes."""
    old_filter=ns['filter_output_graph'];old_smooth=ns['linefit_smooth_output_graph'];state={}
    def filtered(nodes,edges,*args,**kwargs):
        assert not state,'Nested event veto processing is unsupported'
        dataset=kwargs.get('dataset',args[0] if args else None)
        if not dataset:raise ValueError('Event veto needs the current dataset name')
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
