"""Audit explicitly certified append duties; never infer a policy from final FN.

Contract authority must be supplied by an independently reconstructed producer
decision ledger. This checker validates graph binding, not the biological truth
or the authenticity of arbitrary user-supplied certificates.
"""
import hashlib
import numpy as np

def stamp(graph):
    order=np.argsort(graph.ids); ids=graph.ids[order].astype('<i8');coords=graph.coords[order].astype('<f8')
    edges=np.array(sorted(map(tuple,graph.edges.tolist())),dtype='<i8').reshape(-1,2)
    return hashlib.sha256(graph.unit.encode()+ids.tobytes()+coords.tobytes()+edges.tobytes()).hexdigest()

def pairs(values):
    a=np.asarray(values)
    if a.dtype.kind not in 'iu' or a.dtype.kind=='b' or a.ndim!=2 or a.shape[1]!=2:raise ValueError('Integer pair array required')
    if a.dtype.kind=='u' and a.size and int(a.max())>np.iinfo(np.int64).max:raise ValueError('Pair ID outside int64')
    result=set(map(tuple,a.astype(np.int64).tolist()))
    if len(result)!=len(a):raise ValueError('Duplicate contract pairs')
    return result

def check(before, after, candidate, contract):
    target=pairs(np.asarray([candidate]))
    if len(target)!=1:raise ValueError('One candidate required')
    pair=next(iter(target))
    if contract is None:return dict(decision='withheld',reason='contract-not-established')
    if contract.get('schema')!='certified-append-domain-v1' or not contract.get('authority_sha256'):raise ValueError('Explicit contract authority required')
    if contract.get('input_stamp')!=stamp(before):return dict(decision='withheld',reason='input-contract-binding-mismatch')
    domain=pairs(contract['candidate_domain']);required=pairs(contract['required_additions'])
    if not required<=domain:raise ValueError('Duty outside audited candidate domain')
    if pair not in domain:return dict(decision='withheld',reason='candidate-outside-audited-domain')
    times=dict(zip(before.ids.tolist(),before.coords[:,0].tolist()));old=set(map(tuple,before.edges.tolist()))
    for a,b in required:
        if a not in times or b not in times or times[b]-times[a]!=1 or (a,b) in old:raise ValueError('Invalid certified append action')
        if sum(x==a for x,y in old)!=1 or any(y==b for x,y in old):raise ValueError('Certified action violates append prerequisites')
    if set(before.ids)!=set(after.ids) or not np.array_equal(before.ids,after.ids) or not np.array_equal(before.coords,after.coords):
        return dict(decision='withheld',reason='output-domain-changed-outside-append-contract')
    if pair not in required:return dict(decision='not-required-by-contract',reason='audited-policy-exclusion')
    emitted=pair in set(map(tuple,after.edges.tolist()))
    return dict(decision='satisfied' if emitted else 'violated',reason='certified-append-output')
