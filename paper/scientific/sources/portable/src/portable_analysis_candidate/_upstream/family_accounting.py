"""Reference-edge history sets from explicit feasible per-stage mappings.

No injection receipts, experiment names, causal labels, model internals, or
Kaggle notebook dependencies. Adapter must establish mapping-family completeness
and that correspondence choices have no additional cross-stage constraints.
Per-edge history sets do not certify coupled whole-graph aggregate intervals.
"""
import itertools
import numpy as np

def account_from_mapping_families(stages,reference,mapping_families,*,
                                 cross_stage_constraints,max_histories_per_edge=4096):
    """Return all possible histories under declared feasible mapping families.

    `cross_stage_constraints` must explicitly be 'none_in_correspondence_estimand'.
    This declaration applies to the supplied matching estimand; it is not a
    causal independence claim for pipeline states or interventions. Families
    contain complete one-to-one partial dictionaries, never independent endpoint
    candidate lists. Reference edges share endpoint choices within each mapping.
    Completeness/optimality of families remain the adapter's scientific duty.
    """
    if cross_stage_constraints!='none_in_correspondence_estimand':
        raise ValueError('Jointly constrained stage correspondences require a joint-family adapter')
    if len(stages)<2 or len(stages)!=len(mapping_families):
        raise ValueError('Ordered stage/family lengths invalid')
    if isinstance(max_histories_per_edge,bool) or not isinstance(max_histories_per_edge,int) or max_histories_per_edge<1:
        raise ValueError('Positive integral history cap required')
    reference_times=dict(zip(reference.ids.tolist(),reference.coords[:,0].tolist()))
    edge_sets=[];families=[]
    for stage,family in zip(stages,mapping_families):
        if stage.unit!=reference.unit:raise ValueError('Declared coordinate units differ')
        if not isinstance(family,(list,tuple)) or not family:raise ValueError('Nonempty explicit feasible-mapping family required')
        pred_times=dict(zip(stage.ids.tolist(),stage.coords[:,0].tolist()));checked=[]
        for mapping in family:
            if not isinstance(mapping,dict):raise ValueError('Mapping must be a partial dictionary')
            if len(set(mapping.values()))!=len(mapping):raise ValueError('Mapping is not one-to-one')
            for r,p in mapping.items():
                if isinstance(r,(bool,np.bool_)) or isinstance(p,(bool,np.bool_)) or not isinstance(r,(int,np.integer)) or not isinstance(p,(int,np.integer)):
                    raise ValueError('Integer endpoint identifiers required')
                if r not in reference_times or p not in pred_times or reference_times[r]!=pred_times[p]:
                    raise ValueError('Correspondence requires existing same-frame endpoints')
            checked.append(dict(mapping))
        families.append(checked);edge_sets.append(set(map(tuple,stage.edges.tolist())))
    records=[]
    for raw_a,raw_b in reference.edges:
        a,b=int(raw_a),int(raw_b);domains=[]
        for family,edge_set in zip(families,edge_sets):
            domains.append(sorted({int((mapping.get(a),mapping.get(b)) in edge_set)
                                   for mapping in family}))
        n=1
        for values in domains:n*=len(values)
        if n>max_histories_per_edge:
            records.append({'reference_edge':[a,b],'status':'WITHHELD_HISTORY_CAP',
                            'stage_visibility_domains':domains,'possible_history_count':n})
            continue
        strings=[];categories=set();persistent=set();final=set();first=set();last=set()
        for v in itertools.product(*domains):
            strings.append(''.join(map(str,v)));loss=[k for k in range(1,len(v)) if v[k-1]==1 and v[k]==0]
            f=not bool(v[-1]);p=not any(v);final.add(f);persistent.add(p);first.add(loss[0] if loss else None)
            if not f:categories.add('final_visible');last.add(None)
            elif not loss:categories.add('persistent_absence');last.add(None)
            else:categories.add('loss_stage_'+str(loss[-1]));last.add(loss[-1])
        records.append({'reference_edge':[a,b],'status':'ADMISSIBLE_HISTORY_SET',
                        'stage_visibility_domains':domains,'admissible_visibility_strings':sorted(strings),
                        'history_determinate':len(strings)==1,'final_missing_values':sorted(final),
                        'final_missing_determinate':len(final)==1,'persistent_absence_values':sorted(persistent),
                        'first_loss_possible_stages':sorted(first,key=lambda x:-1 if x is None else x),
                        'last_loss_if_final_missing_possible_stages':sorted(last,key=lambda x:-1 if x is None else x),
                        'final_history_categories':sorted(categories),'final_history_category_determinate':len(categories)==1,
                        'causal_responsibility':'not_established_by_reference_graph_record'})
    return {'scope':'Reference-relative per-edge admissible histories under supplied complete feasible mapping families',
            'cross_stage_correspondence_constraints':cross_stage_constraints,
            'mapping_family_sizes':[len(f) for f in families],'records':records,
            'joint_whole_graph_score_interval_certified':False,
            'family_completeness_and_optimality_certified_by_this_module':False,
            'biological_reference_truth_certified':False,'causal_independence_certified':False}
