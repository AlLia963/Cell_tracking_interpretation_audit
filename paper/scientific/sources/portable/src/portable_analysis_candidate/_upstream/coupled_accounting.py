"""Exact additive history bounds over explicit feasible correspondence families.

This module uses supplied whole maps, graph incidence and finite-set factorization,
not a tracker, posterior distribution, source fault receipt or expected result.
Completeness/optimality of the family remains the adapter's responsibility.
The supported correspondence estimand has no additional cross-stage constraints.
"""
import itertools
from numbers import Integral
from .family_accounting import account_from_mapping_families


def coupled_aggregate_bounds(stages, reference, mapping_families, feature_function, *,
                             cross_stage_constraints, max_assignments_per_component=65536):
    """Compute separate attainable scalar bounds; not an attainable joint vector.

    feature_function(history_tuple) must return the same nonempty dictionary of
    integral additive contributions for every history. Whole families are validated
    by the per-edge interface. Components split only when their projected family
    sets provably have a Cartesian product equal to the supplied whole family.
    If a component exceeds the cap, global bounds are withheld, never truncated.
    """
    if isinstance(max_assignments_per_component, bool) or not isinstance(max_assignments_per_component, int) or max_assignments_per_component < 1:
        raise ValueError('Positive integral enumeration cap required')
    validation = account_from_mapping_families(
        stages, reference, mapping_families,
        cross_stage_constraints=cross_stage_constraints, max_histories_per_edge=1)
    edges = [tuple(map(int, edge)) for edge in reference.edges.tolist()]
    if not edges:
        raise ValueError('Empty edge domain requires an explicitly defined feature identity')
    ids = tuple(map(int, reference.ids.tolist()))
    pairs = [set(map(tuple, stage.edges.tolist())) for stage in stages]
    base_maps = [dict(family[0]) for family in mapping_families]
    varying_by_stage = [{r for r in ids if len({m.get(r) for m in family}) > 1}
                        for family in mapping_families]
    variables = set().union(*varying_by_stage)
    parent = {r: r for r in variables}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def merge(items):
        items = list(items)
        if not items:
            return
        root = find(items[0])
        for value in items[1:]:
            parent[find(value)] = root

    for a, b in edges:
        if a in variables and b in variables:
            merge([a, b])

    def groups():
        output = {}
        for r in sorted(variables):
            output.setdefault(find(r), []).append(r)
        return sorted([tuple(values) for values in output.values()])

    def project(family, nodes):
        return {tuple(mapping.get(r) for r in nodes) for mapping in family}

    # A finite family is a subset of the Cartesian product of its projections.
    # Equality of cardinalities proves exact factorization, with no probability
    # assumption. Correlated components are merged and retested.
    while True:
        partition = groups()
        merged = False
        for family, varying in zip(mapping_families, varying_by_stage):
            full = project(family, tuple(sorted(variables)))
            size = 1
            for nodes in partition:
                size *= len(project(family, nodes))
            if size != len(full):
                before = len(groups())
                merge(sorted(varying))
                if len(groups()) >= before:
                    raise ValueError('Projection factorization could not be certified')
                merged = True
                break
        if not merged:
            break

    partition = groups()
    component_by_node = {r: i for i, nodes in enumerate(partition) for r in nodes}
    variable_edges = [[] for _ in partition]
    fixed_edges = []
    for edge in edges:
        incident = {component_by_node[r] for r in edge if r in variables}
        if not incident:
            fixed_edges.append(edge)
        elif len(incident) == 1:
            variable_edges[incident.pop()].append(edge)
        else:
            raise AssertionError('Reference edge crosses components after incidence union')

    def history(edge, maps):
        a, b = edge
        return tuple(int((m.get(a), m.get(b)) in edge_set)
                     for m, edge_set in zip(maps, pairs))

    names = tuple(sorted(feature_function(history(edges[0], base_maps))))
    if not names:
        raise ValueError('Feature dictionary is empty')

    def contributions(edge_list, maps):
        total = {name: 0 for name in names}
        for edge in edge_list:
            values = feature_function(history(edge, maps))
            if tuple(sorted(values)) != names or any(isinstance(v, bool) or not isinstance(v, Integral) for v in values.values()):
                raise ValueError('Features require stable names and integral additive contributions')
            for name, value in values.items():
                total[name] += int(value)
        return total

    constant = contributions(fixed_edges, base_maps)
    lower, upper = dict(constant), dict(constant)
    component_results = []
    minimum_choices, maximum_choices = [], []
    for nodes, incident_edges in zip(partition, variable_edges):
        domains = [sorted(project(family, nodes), key=repr) for family in mapping_families]
        count = 1
        for domain in domains:
            count *= len(domain)
        if count > max_assignments_per_component:
            return {'status': 'WITHHELD_COMPONENT_ENUMERATION_CAP',
                    'unresolved_component_nodes': list(nodes), 'assignments_required': count,
                    'cap': max_assignments_per_component, 'scalar_bounds': None,
                    'no_truncated_bounds_reported': True,
                    'joint_whole_graph_scalar_bounds_certified': False,
                    'family_completeness_certified_by_module': False}
        minima, maxima = None, None
        min_choices, max_choices = {}, {}
        for choices in itertools.product(*domains):
            maps = [dict(mapping) for mapping in base_maps]
            for mapping, values in zip(maps, choices):
                for node, value in zip(nodes, values):
                    if value is None:
                        mapping.pop(node, None)
                    else:
                        mapping[node] = value
            values = contributions(incident_edges, maps)
            if minima is None:
                minima, maxima = dict(values), dict(values)
                min_choices = {name: choices for name in names}
                max_choices = {name: choices for name in names}
            else:
                for name in names:
                    if values[name] < minima[name]:
                        minima[name] = values[name]
                        min_choices[name] = choices
                    if values[name] > maxima[name]:
                        maxima[name] = values[name]
                        max_choices[name] = choices
        for name in names:
            lower[name] += minima[name]
            upper[name] += maxima[name]
        component_results.append({'reference_nodes': list(nodes), 'incident_reference_edges': [list(e) for e in incident_edges],
                                  'stage_projection_sizes': [len(d) for d in domains],
                                  'assignments_enumerated': count, 'minimum': minima, 'maximum': maxima})
        minimum_choices.append(min_choices)
        maximum_choices.append(max_choices)
    canonical = contributions(edges, base_maps)
    # Each assembled component extremizer must extend to an ACTUAL supplied
    # whole map in every stage. Return its index, not only an extremum value.
    family_index = [{tuple(m.get(r) for r in ids): i for i, m in enumerate(family)}
                    for family in mapping_families]
    witnesses = {}
    for name in names:
        witnesses[name] = {}
        for side, chosen, expected in [('minimum', minimum_choices, lower[name]),
                                       ('maximum', maximum_choices, upper[name])]:
            maps = [dict(m) for m in base_maps]
            for nodes, component_choice in zip(partition, chosen):
                for mapping, values in zip(maps, component_choice[name]):
                    for node, value in zip(nodes, values):
                        if value is None:
                            mapping.pop(node, None)
                        else:
                            mapping[node] = value
            indices = [index[tuple(m.get(r) for r in ids)]
                       for index, m in zip(family_index, maps)]
            whole_maps = [family[i] for family, i in zip(mapping_families, indices)]
            realized = contributions(edges, whole_maps)[name]
            if realized != expected:
                raise AssertionError('Assembled whole-map endpoint witness does not reproduce scalar')
            witnesses[name][side] = {'whole_map_index_per_stage': indices,
                                     'reproduced_scalar': realized,
                                     'all_maps_are_members_of_supplied_families': True}
    return {'status': 'EXACT_ADDITIVE_SCALAR_BOUNDS_OVER_SUPPLIED_FAMILIES',
            'scalar_bounds': {name: {'minimum': lower[name], 'maximum': upper[name],
                                    'canonical': canonical[name],
                                    'minimum_witness': witnesses[name]['minimum'],
                                    'maximum_witness': witnesses[name]['maximum']} for name in names},
            'reference_edges': len(edges), 'fixed_reference_edges': len(fixed_edges),
            'components': component_results,
            'whole_stage_family_sizes': validation['mapping_family_sizes'],
            'factorization_certified_by_finite_set_cardinality': True,
            'joint_whole_graph_scalar_bounds_certified': True,
            'whole_map_endpoint_witness_indices_emitted_and_replayed': True,
            'joint_extrema_vector_certified': False,
            'family_completeness_certified_by_module': False,
            'biological_reference_truth_certified': False,
            'causal_independence_certified': False}
