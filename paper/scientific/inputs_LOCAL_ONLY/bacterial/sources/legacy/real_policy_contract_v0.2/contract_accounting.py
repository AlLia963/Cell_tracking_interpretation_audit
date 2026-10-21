"""Target and whole-output append checks under externally pinned source evidence.

Hash-pinned evidence is a caller trust root, not a signed biological certificate.
Policy inference from an observed absence is forbidden.
"""
import hashlib,json
from dataclasses import dataclass
from pathlib import Path
import numpy as np

def stamp(graph):
    order=np.argsort(graph.ids);ids=graph.ids[order].astype('<i8');coords=graph.coords[order].astype('<f8')
    edges=np.array(sorted(map(tuple,graph.edges.tolist())),dtype='<i8').reshape(-1,2)
    return hashlib.sha256(graph.unit.encode()+ids.tobytes()+coords.tobytes()+edges.tobytes()).hexdigest()
def pairs(values):
    if isinstance(values,(list,tuple)) and len(values)==0:return frozenset()
    a=np.asarray(values)
    if a.dtype.kind not in 'iu' or a.dtype.kind=='b' or a.ndim!=2 or a.shape[1]!=2:raise ValueError('Integer Nx2 pair array required')
    if a.dtype.kind=='u' and a.size and int(a.max())>np.iinfo(np.int64).max:raise ValueError('Pair ID outside int64')
    result=frozenset(map(tuple,a.astype(np.int64).tolist()))
    if len(result)!=len(a):raise ValueError('Duplicate contract pairs')
    return result
@dataclass(frozen=True)
class Authority:
    sha256:str
    entries:tuple
    def lookup(self,film):
        hits=[v for k,v in self.entries if k==film]
        if len(hits)!=1:return None
        return json.loads(hits[0])
def load_authority(path,expected_sha256):
    raw=Path(path).read_bytes();digest=hashlib.sha256(raw).hexdigest()
    if digest!=expected_sha256:raise ValueError('Authority artifact does not match pinned SHA256')
    doc=json.loads(raw)
    if doc.get('schema')!='pinned-append-authority-v1':raise ValueError('Unknown authority schema')
    records=doc['contracts'];names=[r['film'] for r in records]
    if len(names)!=len(set(names)):raise ValueError('Duplicate authority film')
    return Authority(digest,tuple((r['film'],json.dumps(r['contract'],sort_keys=True)) for r in records))
def withheld(reason):return dict(decision='withheld',reason=reason,output_contract_decision='withheld')
def canonical_nodes(g):
    i=np.argsort(g.ids);return g.ids[i],g.coords[i]
def check(before,after,candidate,contract,*,authority,film):
    pairset=pairs([candidate]);assert len(pairset)==1;pair=next(iter(pairset))
    if contract is None:return withheld('contract-not-established')
    if not isinstance(authority,Authority):return withheld('pinned-authority-not-supplied')
    expected=authority.lookup(film)
    if expected is None or contract!=expected:return withheld('contract-content-not-matched-to-authority')
    if contract.get('schema')!='certified-append-domain-v1':raise ValueError('Unknown contract schema')
    if contract.get('input_stamp')!=stamp(before):return withheld('input-contract-binding-mismatch')
    domain=pairs(contract['candidate_domain']);required=pairs(contract['required_additions'])
    if not required<=domain:raise ValueError('Duty outside audited domain')
    old=set(map(tuple,before.edges.tolist()));times=dict(zip(before.ids.tolist(),before.coords[:,0].tolist()))
    for a,b in domain:
        if a not in times or b not in times or times[b]-times[a]!=1 or (a,b) in old:raise ValueError('Invalid candidate in certified append domain')
        if sum(x==a for x,y in old)!=1 or any(y==b for x,y in old):raise ValueError('Candidate violates append prerequisites')
    if pair not in domain:return withheld('candidate-outside-audited-domain')
    bi,bc=canonical_nodes(before);ai,ac=canonical_nodes(after)
    if before.unit!=after.unit or not np.array_equal(bi,ai) or not np.array_equal(bc,ac):return withheld('output-domain-changed-outside-append-contract')
    output=set(map(tuple,after.edges.tolist()));missing_input=old-output;missing_required=required-output;unexpected=output-old-required
    overall='violated' if missing_input or missing_required or unexpected else 'satisfied'
    target='not-required-by-contract' if pair not in required else ('satisfied' if pair in output else 'violated')
    return dict(decision=target,reason='audited-policy-exclusion' if pair not in required else 'certified-append-output',output_contract_decision=overall,missing_input_edges=sorted(missing_input),missing_required_edges=sorted(missing_required),unexpected_added_edges=sorted(unexpected))
