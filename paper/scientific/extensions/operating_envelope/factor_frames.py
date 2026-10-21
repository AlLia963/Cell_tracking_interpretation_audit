"""Certify finite-set factorization of complete frame families before queries.

Completeness of the supplied frame family is a separate adapter premise. This
module never repairs a missing map or interprets a finite family as a posterior.
"""
import itertools
import math


def factor_frame_blocks(blocks):
    result, proofs = [], []
    for original_index, block in enumerate(blocks):
        nodes = tuple(sorted(block['references']))
        family = {tuple(a[str(q)] for q in nodes) for a in block['assignments']}
        if not family or any(set(a) != set(map(str, nodes)) for a in block['assignments']):
            raise ValueError('Complete, nonempty and consistently keyed input family required')
        parent = {q: q for q in nodes}
        def root(q):
            while parent[q] != q:
                parent[q] = parent[parent[q]]; q = parent[q]
            return q
        def merge(values):
            values = list(values)
            if values:
                r = root(values[0])
                for q in values[1:]: parent[root(q)] = r
        candidate_owners = {}
        for q in nodes:
            for p in {a[str(q)] for a in block['assignments']} - {None}:
                candidate_owners.setdefault(p, []).append(q)
        for owners in candidate_owners.values(): merge(owners)
        def partition():
            groups = {}
            for q in nodes: groups.setdefault(root(q), []).append(q)
            return sorted([tuple(x) for x in groups.values()])
        def projection(ns):
            return {tuple(a[str(q)] for q in ns) for a in block['assignments']}
        groups = partition()
        raw_product = math.prod(len(projection(ns)) for ns in groups)
        fallback = raw_product != len(family)
        if fallback:
            merge(nodes); groups = partition()
        size = math.prod(len(projection(ns)) for ns in groups)
        if size != len(family): raise AssertionError('Finite-set product equality failed')
        indices = []
        for ns in groups:
            values = sorted(projection(ns), key=repr)
            indices.append(len(result))
            result.append(dict(block, references=list(ns), assignments=[dict(zip(map(str,ns),v)) for v in values],
                               id=len(result), original_frame_block_index=original_index))
        # Inclusion is automatic because these are projections of the full set;
        # equal finite cardinalities certify equality, not just a pairwise test.
        proofs.append({'original_frame_block_index': original_index, 'reference_ids':list(nodes),
                       'full_family_cardinality':len(family), 'premerge_projection_product':raw_product,
                       'nonfactorable_fallback_merge':fallback, 'factor_block_indices':indices,
                       'factor_cardinalities':[len(result[i]['assignments']) for i in indices],
                       'certified_product_cardinality':size, 'cartesian_product_equals_full_family':True})
    return result, proofs


def extend_history_witness(witness, split_blocks, components, original_blocks, stages, bases):
    maps = {s:dict(bases[s]) for s in stages}
    for c,ci in zip(components,witness['component_configuration_indices']):
        choices = c['configurations'][ci]
        for bi,ai in zip(c['block_indices'], choices):
            block = split_blocks[bi]
            for q,p in block['assignments'][ai].items():
                maps[block['stage']].pop(int(q),None)
                if p is not None: maps[block['stage']][int(q)] = p
    indices = []
    for block in original_blocks:
        nodes = block['references']
        signature = tuple(maps[block['stage']].get(q) for q in nodes)
        found = [i for i,a in enumerate(block['assignments']) if tuple(a[str(q)] for q in nodes)==signature]
        if not found: raise AssertionError('Reported witness fails actual whole-frame family membership')
        indices.append(found[0])
    return maps, indices
