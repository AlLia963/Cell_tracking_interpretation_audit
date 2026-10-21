"""Check stored scalar witnesses literally, without the contrast evaluator.

Checks existence, family membership and declared equalities. Does not infer family
coverage or endpoint optimality from a witness. Use primitive reconstruction for
those properties; the full corpus retains its ordinary-family equality records.
"""
from pathlib import Path
import argparse,json,gzip
import numpy as np

METRICS = ('before_TP', 'after_TP', 'gains', 'losses', 'net')
ENDPOINTS = ('minimum', 'maximum')

def validate_endpoint_schema(record):
    """Require each named endpoint exactly once before inspecting any witness."""
    bounds = record.get('bounds')
    if not isinstance(bounds, dict) or set(bounds) != set(METRICS):
        raise ValueError('Exactly five scalar bounds required')
    for metric, endpoints in bounds.items():
        if not isinstance(endpoints, dict) or set(endpoints) != set(ENDPOINTS):
            raise ValueError('Exactly minimum and maximum bounds required')
        if any(type(v) is not int for v in endpoints.values()):
            raise ValueError('Scalar bounds must be exact integers')
        if endpoints['minimum'] > endpoints['maximum']:
            raise ValueError('Reversed scalar bounds')
        if metric != 'net' and endpoints['minimum'] < 0:
            raise ValueError('Negative relation count')
    witnesses = record.get('whole_map_endpoint_witnesses')
    expected = {m + '_' + e for m in METRICS for e in ENDPOINTS}
    if not isinstance(witnesses, dict) or set(witnesses) != expected:
        raise ValueError('Exactly ten named endpoint witnesses required')
    for witness in witnesses.values():
        if not isinstance(witness, dict):
            raise ValueError('Malformed endpoint witness')
        values = witness.get('values')
        if not isinstance(values, dict) or set(values) != set(METRICS):
            raise ValueError('Exactly five witness scalar values required')
        if any(type(v) is not int for v in values.values()):
            raise ValueError('Witness scalar values must be exact integers')
        if not isinstance(witness.get('frame_map_choices'), list):
            raise ValueError('Frame map choices must be a list')

def read(p):
    if str(p).endswith('.gz'):
        with gzip.open(p,'rt',encoding='utf8')as f:return json.load(f)
    return json.loads(Path(p).read_text(encoding='utf8'))
def relpath(p):return Path(str(p).replace('\\','/'))
def primitive_frames(g):
    ids=np.asarray(g['ids']);coords=np.asarray(g['coords']);edges=np.asarray(g['edges']);unit=np.asarray(g['unit'])
    if unit.shape!=() or unit.dtype.kind!='U' or str(unit.item())!='um':raise ValueError('Explicit um primitives required')
    if ids.dtype.kind not in 'iu' or ids.ndim!=1 or len(set(map(int,ids)))!=len(ids):raise ValueError('Invalid primitive identities')
    if coords.shape!=(len(ids),4) or not np.isfinite(coords).all() or not np.equal(coords[:,0],np.floor(coords[:,0])).all():raise ValueError('Invalid primitive frames/coordinates')
    if edges.dtype.kind not in 'iu' or edges.ndim!=2 or edges.shape[1]!=2:raise ValueError('Invalid primitive relations')
    times=dict(zip(map(int,ids),coords[:,0]))
    if any(int(a)not in times or int(b)not in times or times[int(a)]>=times[int(b)]for a,b in edges):raise ValueError('Invalid primitive relation endpoints')
    frames={}
    for q,c in zip(ids,coords):frames.setdefault(int(c[0]),{})[int(q)]=c[1:]
    return frames
def verify(record,reference,graphs,summaries,cache,expected_contract='identical-input'):
    if expected_contract not in ['independent','identical-input']:raise ValueError('Unknown comparison contract')
    if record['status']!='COMPLETE':
        if record['status']not in ['WITHHELD_DOMAIN_INCONSISTENCY','WITHHELD_FRAME','WITHHELD_COMPONENT_CAP']:raise ValueError('Unknown report status')
        if record.get('bounds') is not None:raise ValueError('Withheld record exposes bounds')
        return {'status':'WITHHELD_RETAINED','witnesses':0}
    if 'contract'in record and record['contract']!=expected_contract:raise ValueError('Report differs from declared comparison contract')
    validate_endpoint_schema(record)
    rf=primitive_frames(reference);pf=[primitive_frames(g)for g in graphs]
    locs=[s['frame_locators']for s in summaries]
    families=[{int(t):read(cache/relpath(loc))for t,loc in ls.items()}for ls in locs]
    if any(set(fs)!=set(rf)for fs in families):raise ValueError('Family frames differ from primitive reference')
    required_links=[]
    if expected_contract=='identical-input':
        for t in rf:
            aa=[np.flatnonzero(g['coords'][:,0]==t)for g in graphs]
            aa=[ix[np.argsort(g['ids'][ix])]for g,ix in zip(graphs,aa)]
            if np.array_equal(graphs[0]['ids'][aa[0]],graphs[1]['ids'][aa[1]]) and np.array_equal(graphs[0]['coords'][aa[0]],graphs[1]['coords'][aa[1]]):required_links.append(t)
    links=record.get('linked_frames',[])
    if any(type(t)is not int for t in links) or len(set(links))!=len(links):raise ValueError('Malformed linked-frame identities')
    if sorted(links)!=sorted(required_links):raise ValueError('Declared links differ from actual matching-input contract')
    checked=0
    for name,w in record['whole_map_endpoint_witnesses'].items():
        chosen={}
        for item in w['frame_map_choices']:
            if not isinstance(item,list) or len(item)!=3 or any(type(v)is not int for v in item):raise ValueError('Malformed frame map choice')
            s,t,ix=item
            if s not in [0,1] or t not in families[s] or (s,t)in chosen:raise ValueError('Duplicate or unknown frame map choice')
            if not 0<=ix<len(families[s][t]['worlds']):raise ValueError('Invalid family member index')
            chosen[s,t]=ix
        maps=[]
        for side in range(2):
            m={}
            for t,f in families[side].items():
                ix=chosen.get((side,t),f['canonical_index'])
                if not 0<=ix<len(f['worlds']):raise ValueError('Invalid family member index')
                stored=f['worlds'][ix]
                if any(str(int(q))!=q or type(v)is not int for q,v in stored.items()):raise ValueError('Witness identities must be exact integer IDs')
                world={int(q):v for q,v in stored.items()}
                if len(set(world.values()))!=len(world):raise ValueError('Noninjective family member')
                if set(map(int,f['reference_ids']))!=set(rf[t]):raise ValueError('Family reference domain differs from primitives')
                for q,v in world.items():
                    if q not in rf[t] or v not in pf[side].get(t,{}):raise ValueError('Witness endpoint absent or in wrong primitive frame')
                    if float(np.hypot.reduce(rf[t][q]-pf[side][t][v]))>7:raise ValueError('Witness pair outside declared gate')
                if set(m).intersection(world):raise ValueError('Reference identity covered in multiple frame maps')
                m.update(world)
            if len(set(m.values()))!=len(m):raise ValueError('Noninjective assembled whole map')
            maps.append(m)
        for t in links:
            for q in families[0][t]['reference_ids']:
                if maps[0].get(int(q))!=maps[1].get(int(q)):raise ValueError('Declared equality violated')
        pairs=[set(map(tuple,g['edges'].tolist()))for g in graphs]
        bits=[[((m.get(int(a)),m.get(int(b)))in pair)for a,b in reference['edges']]for m,pair in zip(maps,pairs)]
        b,a=bits;v={'before_TP':sum(b),'after_TP':sum(a),'gains':sum(y and not x for x,y in zip(b,a)),'losses':sum(x and not y for x,y in zip(b,a)),'net':sum(a)-sum(b)}
        if v!=w['values']:raise ValueError('Whole-map scalar readout mismatch')
        metric,endpoint=name.rsplit('_',1)
        if v[metric]!=record['bounds'][metric][endpoint]:raise ValueError('Endpoint mismatch')
        checked+=1
    if checked!=10:raise ValueError('Ten separate endpoint witnesses required')
    return {'status':'WITNESS_EXISTENCE_AND_LINKS_PASS','witnesses':checked,'family_completeness_claimed_by_this_check':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--task',required=True);p.add_argument('--reference',required=True);p.add_argument('--before',required=True);p.add_argument('--after',required=True)
    a=p.parse_args();task=Path(a.task).resolve();r=read(task/'REPORT.json');ps=[Path(x)for x in [a.reference,a.before,a.after]]
    import hashlib
    declaration=read(task/'COMPARISON_CONTRACT.json')
    if any(r.get(k)!=declaration.get(k)for k in ['contract','primitive_inputs','input_contract']):raise ValueError('Report/declared input contract mismatch')
    contract=declaration['input_contract']
    required={'unit':'um','inclusive_gate_um':7,'objective':'maximum cardinality then exact sum of calculated float64 hypot distances','types':'untyped directed relations'}
    if any(contract.get(k)!=v for k,v in required.items()) or type(contract.get('component_cap'))is not int or contract['component_cap']<1:raise ValueError('Unsupported primitive evaluation contract')
    bindings=r.get('artifact_bindings',{})
    if not all(k in bindings for k in ['COMPARISON_CONTRACT.json','graph_0.json.gz','graph_1.json.gz']):raise ValueError('Missing task artifact bindings')
    for name,digest in bindings.items():
        path=(task/relpath(name)).resolve()
        if not path.is_relative_to(task):raise ValueError('Artifact path escapes task')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Bound task artifact changed')
    for label,path in zip(['reference','before','after'],ps):
        if hashlib.sha256(path.read_bytes()).hexdigest()!=r['primitive_inputs'][label]['sha256']:raise ValueError('Input binding mismatch')
    gs=[]
    for path in ps:
        with np.load(path,allow_pickle=False)as z:gs.append({k:z[k].copy()for k in z.files})
    summaries=[read(task/('graph_'+str(i)+'.json.gz'))for i in range(2)]
    for s in summaries:
        for loc in s['frame_locators'].values():
            name='frame_cache/'+str(loc).replace('\\','/')
            if name not in bindings:raise ValueError('Unbound frame family')
    out=verify(r,gs[0],gs[1:],summaries,task/'frame_cache',expected_contract=declaration['contract'])
    (task/'WITNESS_CHECK.json').write_text(json.dumps(out,indent=2),encoding='utf8');print(out['status'])
