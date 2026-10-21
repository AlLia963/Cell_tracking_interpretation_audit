"""Replay one path-value witness against bound source graphs.

Successful replay certifies this value for the indexed supplied maps. It does
not independently prove optimality or coverage of the entire mapping family.
"""
from pathlib import Path
import argparse, hashlib, json
import numpy as np

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def replay(directory,indices,claimed_value,reference=None,prediction=None):
    directory=Path(directory).resolve()
    binding=json.loads((directory/'REPORT_BINDING.json').read_text(encoding='utf8'))
    if binding.get('schema')!='bound-path-audit/1.2':raise ValueError('Unsupported binding')
    if set(binding['files']) != {'INPUT_AND_QUERY_CONTRACT.json','REPORT.json','COMPLETE_FRAME_FAMILIES.json'}:
        raise ValueError('Incomplete binding file set')
    for name,expected in binding['files'].items():
        if name not in ('INPUT_AND_QUERY_CONTRACT.json','REPORT.json','COMPLETE_FRAME_FAMILIES.json') or sha(directory/name)!=expected:
            raise ValueError('Bound artifact hash mismatch')
    contract=json.loads((directory/'INPUT_AND_QUERY_CONTRACT.json').read_text(encoding='utf8'))
    report=json.loads((directory/'REPORT.json').read_text(encoding='utf8'))
    if report['status']!='COMPLETE':raise ValueError('No complete report to replay')
    ff=json.loads((directory/'COMPLETE_FRAME_FAMILIES.json').read_text(encoding='utf8'))
    families=ff['whole_maps']
    if len(indices)!=len(families) or any(type(i) is not int or i<0 or i>=len(f) for i,f in zip(indices,families)):
        raise ValueError('Whole-map witness index outside supplied family')
    graphs={}
    for kind in ('reference','prediction'):
        pin=contract[kind];p=Path((reference if kind=='reference' else prediction) or pin['path'])
        if sha(p)!=pin['sha256']:raise ValueError('Input graph hash mismatch')
        with np.load(p,allow_pickle=False) as z:graphs[kind]={k:z[k].copy() for k in ('ids','coords','edges')}
    rt=dict(zip(map(int,graphs['reference']['ids']),graphs['reference']['coords'][:,0]))
    pt=dict(zip(map(int,graphs['prediction']['ids']),graphs['prediction']['coords'][:,0]))
    maps=[]
    for frame,fam,i in zip(ff['frames'],families,indices):
        m={int(r):int(p) for r,p in fam[i].items()}
        if len(set(m.values()))!=len(m) or any(r not in rt or p not in pt or rt[r]!=frame or pt[p]!=frame for r,p in m.items()):
            raise ValueError('Witness map violates endpoint/frame/injectivity domain')
        maps.append(m)
    merged={r:p for m in maps for r,p in m.items()};a,b,c=contract['reference_path']
    pairs=set(map(tuple,graphs['prediction']['edges'].tolist()))
    bits=[int(x in merged and y in merged and (merged[x],merged[y]) in pairs) for x,y in ((a,b),(b,c))]
    actual=bits[0]*bits[1]
    if type(claimed_value) is not int or claimed_value not in (0,1) or actual!=claimed_value:
        raise ValueError('Claimed value differs from graph replay')
    return {'status':'WITNESS_REPLAY_PASS','whole_frame_map_indices':indices,'incident_visibility':bits,'pair_recovery':actual,
            'bound_family_sha256':binding['files']['COMPLETE_FRAME_FAMILIES.json'],
            'family_completeness_independently_certified_by_replay':False,
            'optimality_independently_certified_by_replay':False}
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--report',type=Path,required=True)
    ap.add_argument('--indices',nargs=3,type=int,required=True);ap.add_argument('--value',type=int,choices=(0,1),required=True)
    ap.add_argument('--reference',type=Path);ap.add_argument('--prediction',type=Path)
    ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    result=replay(a.report,a.indices,a.value,a.reference,a.prediction)
    with a.output.open('x',encoding='utf8') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))
if __name__=='__main__':main()
