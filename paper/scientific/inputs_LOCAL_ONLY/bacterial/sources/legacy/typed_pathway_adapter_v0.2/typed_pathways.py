"""Annotate typed-subgraph accounting using raw graph provenance.
No receipts, fault labels, producer duties or oracle values as inputs.
"""
import copy

def annotate_typed_pathways(records,views):
    result=copy.deepcopy(records)
    for record in result:
        if record['kind'] not in ['continuation','division']:
            raise ValueError('Explicit selected relation type required')
        for event in record['loss_pathways']:
            k=event['stage'];before=record['matched_pairs'][k-1];after=record['matched_pairs'][k]
            event['generic_relation_subset_pathway']=event['pathway']
            event['raw_pair_deleted']=None
            if before!=after or None in after:continue
            pair=tuple(after)
            if pair not in views[k-1]['edges']:raise ValueError('Previous visible raw pair missing')
            event['raw_pair_deleted']=pair not in views[k]['edges']
            if event['pathway']=='matched-pair-edge-deleted' and not event['raw_pair_deleted']:
                changed=(pair in views[k-1]['division'])!=(pair in views[k]['division'])
                if not changed:raise ValueError('Typed subset loss lacks raw edge deletion or relabeling')
                event['pathway']='matched-pair-relation-relabeled'
        ambiguous=record.get('ambiguous_visibility',False) or record.get('ambiguous_correspondence',False)
        record['pathway_uniqueness']='withheld-correspondence-ambiguity' if ambiguous else 'determined-under-supplied-correspondence'
        if ambiguous:
            for event in record['loss_pathways']:
                event['canonical_candidate_pathway']=event['pathway']
                event['canonical_raw_pair_deleted']=event['raw_pair_deleted']
                event['pathway']='withheld-correspondence-ambiguity'
                event['raw_pair_deleted']=None
        record['pathway_scope']='typed relation with raw graph provenance; observational not causal; ambiguous candidates withheld'
    return result
