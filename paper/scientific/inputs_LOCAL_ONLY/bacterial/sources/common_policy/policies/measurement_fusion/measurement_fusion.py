from event_consensus import reciprocal_match


def blend(nodes,observed,reference_nodes,stats):
    mapping=reciprocal_match({i:n for i,n in nodes.items() if i in observed},reference_nodes)
    changed=0
    for i,j in mapping.items():
        old=[nodes[i][k] for k in ['z','y','x']]
        new=[.5*(nodes[i][k]+reference_nodes[j][k]) for k in ['z','y','x']]
        changed+=int(old!=new)
        for k,v in zip(['z','y','x'],new):nodes[i][k]=float(v)
    stats.update(measurement_matched_nodes=len(mapping),measurement_blended_nodes=changed,measurement_total_weight=1.)
    return nodes


def reconcile(nodes,edges,observed,reference_nodes,reference_edges,stats):
    blend(nodes,observed,reference_nodes,stats)
    return edges,[]
