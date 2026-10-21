"""Local saved-graph queries, with no microscopy paths or matching algorithm.

Executed scope: binary forks and three-node paths in the seven saved views of
the fixed original corpus. View length is supplied by the caller's stage_order.
This core does not certify input-family completeness or biological annotation.
"""
import itertools
import math


def local_graph_query_value(kind, mapped_nodes, outgoing, incoming):
    """Return R, T and the two incident-edge bits in one directed graph.

    mapped_nodes order is mother, child1, child2 for binary_fork; upstream,
    middle, downstream for three_node_path. None denotes supported unmatched.
    outgoing/incoming must describe the full saved predicted graph.
    """
    a, b, c = mapped_nodes
    if kind == 'binary_fork':
        edge_bits = (int(a is not None and b is not None and b in outgoing.get(a, ())),
                     int(a is not None and c is not None and c in outgoing.get(a, ())))
        r = int(all(edge_bits))
        t = int(r and outgoing.get(a, set()) == {b, c}
                and incoming.get(b, set()) == {a} and incoming.get(c, set()) == {a})
    elif kind == 'three_node_path':
        edge_bits = (int(a is not None and b is not None and b in outgoing.get(a, ())),
                     int(b is not None and c is not None and c in outgoing.get(b, ())))
        r = int(all(edge_bits))
        t = int(r and outgoing.get(a, set()) == {b} and outgoing.get(b, set()) == {c}
                and incoming.get(b, set()) == {a} and incoming.get(c, set()) == {b})
    else:
        raise ValueError('Unsupported local graph query kind: ' + str(kind))
    return r, t, edge_bits


def history_projection(kind, nodes, stage_order, mapped_lookup, adjacency):
    r, t, e0, e1 = [], [], [], []
    for stage in stage_order:
        value = local_graph_query_value(kind, [mapped_lookup(stage, q) for q in nodes],
                                        adjacency[stage][0], adjacency[stage][1])
        r.append(str(value[0])); t.append(str(value[1]))
        e0.append(str(value[2][0])); e1.append(str(value[2][1]))
    return ''.join(r), ''.join(t), ''.join(e0), ''.join(e1)


def relevant_component_join(components, relevant_ids, cap):
    """Enumerate relevant *complete feasible* component domains under a cap.

    Caller must establish Cartesian feasibility factorization, domain
    completeness and extension by fixed feasible irrelevant components first.
    This function alone establishes none of those facts.
    """
    ids = list(relevant_ids)
    product = math.prod(len(components[c]['configurations']) for c in ids)
    if product > cap:
        return product, None
    return product, itertools.product(*(range(len(components[c]['configurations'])) for c in ids))


def final_category(history):
    if not history or any(x not in '01' for x in history):
        raise ValueError('Nonempty binary history required')
    if history[-1] == '1':
        return 'final_present'
    losses = [k for k in range(1, len(history)) if history[k-1:k+1] == '10']
    return 'loss_stage_' + str(losses[-1]) if losses else 'persistent_absence'


def independent_edge_relaxation(edge0_histories, edge1_histories):
    """A conservative AND projection; paired edge witnesses may be incompatible."""
    witnesses = {}
    for left, right in itertools.product(sorted(edge0_histories), sorted(edge1_histories)):
        if len(left) != len(right):
            raise ValueError('Incident-edge view lengths disagree')
        h = ''.join(str(int(a == b == '1')) for a, b in zip(left, right))
        witnesses.setdefault(h, [left, right])
    return witnesses
