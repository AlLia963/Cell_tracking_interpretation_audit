"""Audit a proposed pair-recovery statement on one saved coordinate graph.

All incident relations share the same complete frame maps. This is an untyped,
reference-relative report, not a tracker correction or biological confidence.
Place constructor/reconstruct.py and its relative source dependencies beside
this file; see the source-only constructed example in the software supplement.
"""
from pathlib import Path
from itertools import product
import argparse, collections, datetime, hashlib, importlib.util, json, math, sys
import numpy as np
import scipy

def pin(p):
    with p.open('rb')as f:h=hashlib.file_digest(f,'sha256').hexdigest()
    return {'path':str(p),'bytes':p.stat().st_size,'sha256':h}
def save(p,x):
    with p.open('x',encoding='utf-8')as f:json.dump(x,f,ensure_ascii=False,indent=2)

def main():
    if not __debug__:
        raise RuntimeError('CONSTRUCTOR_ASSERTIONS_DISABLED: run without -O and PYTHONOPTIMIZE')
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--reference',type=Path,required=True)
    a.add_argument('--prediction',type=Path,required=True)
    a.add_argument('--unit',choices=('pixel','um'),required=True)
    a.add_argument('--gate-um',type=float,required=True)
    a.add_argument('--path',type=int,nargs=3,required=True)
    a.add_argument('--proposed-value',type=int,choices=(0,1),required=True)
    a.add_argument('--frame-cap',type=int,default=1048576)
    a.add_argument('--query-cap',type=int,default=1048576)
    a.add_argument('--output',type=Path,required=True)
    args=a.parse_args()
    if not math.isfinite(args.gate_um) or args.gate_um <= 0:
        a.error('gate must be finite and positive')
    if args.frame_cap < 1 or args.query_cap < 1:
        a.error('caps must be positive')
    out=args.output.resolve()
    lib=Path(__file__).resolve().parent/'constructor/reconstruct.py'
    spec=importlib.util.spec_from_file_location('statement_constructor',lib)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    G=mod.load_npz.__globals__['Graph']
    def graph(p):
        with np.load(p,allow_pickle=False)as z:
            if 'unit' in z:
                stored=z['unit']
                if stored.shape!=() or stored.dtype.kind!='U' or stored.item() not in ('pixel','um'):
                    raise ValueError('Invalid NPZ unit metadata: scalar Unicode pixel or um required')
                if stored.item()!=args.unit:
                    raise ValueError('NPZ unit metadata conflicts with declared input unit')
            ids=z['ids'];coords=z['coords'].astype(np.float64,copy=True);edges=z['edges']
            assert coords.shape==(len(ids),4)and len(set(map(int,ids)))==len(ids)
            assert np.isfinite(coords).all()and np.equal(coords[:,0],coords[:,0].astype(int)).all()
            assert set(map(int,edges.ravel())).issubset(set(map(int,ids)))
            if args.unit=='pixel':coords[:,1:]*=np.array([1.625,.40625,.40625])
            return G(ids,coords,edges,'um')
    ref=graph(args.reference);pred=graph(args.prediction)
    out.mkdir(parents=True,exist_ok=False)
    evidence={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'reference':pin(args.reference.resolve()),'prediction':pin(args.prediction.resolve()),
        'constructor':pin(lib),'frontend':pin(Path(__file__).resolve()),'unit_in':args.unit,
        'unit_internal':'um','coordinate_conversion':'axis-wise pixel-to-um once' if args.unit=='pixel' else 'none; already um',
        'gate_um_inclusive':args.gate_um,'objective':'maximum cardinality then exact binary-rational sum of numpy.hypot.reduce float64 distances',
        'numpy':np.__version__,'scipy':scipy.__version__,'python':sys.version,
        'convention':'independent complete optimal maps across acquisition frames of one fixed snapshot',
        'query':'pair_recovery of both incident pairs under shared complete maps',
        'reference_path':args.path,'proposed_value':args.proposed_value,
        'frame_cap':args.frame_cap,'query_cap':args.query_cap,
        'cap_is_not_preflight_memory_or_runtime_bound':True,
        'no_type_or_biological_causality_inferred':True}
    save(out/'INPUT_AND_QUERY_CONTRACT.json',evidence)
    times=dict(zip(map(int,ref.ids),map(int,ref.coords[:,0])))
    rpair=set(map(tuple,ref.edges.tolist()));a,b,c=args.path
    assert len({a,b,c})==3 and times[a]<times[b]<times[c]
    assert (a,b)in rpair and(b,c)in rpair
    ppairs=set(map(tuple,pred.edges.tolist()));canonical=mod.match(pred,ref,args.gate_um)
    frame_maps=[];certs=[]
    for t in (times[a],times[b],times[c]):
        cert,finite,numeric,withheld=mod.frame_family(ref,pred,canonical,args.gate_um,t,args.frame_cap)
        if withheld:
            save(out/'REPORT.json',{'status':'WITHHELD_CONSTRUCTION','reason':withheld,'frame':t,'contract':evidence})
            return
        fixed={r:q for r,q in canonical.items()if times[r]==t};maps=[]
        for assignment in finite['assignments']if finite else [{}]:
            m=dict(fixed)
            for r,q in assignment.items():
                m.pop(int(r),None)
                if q is not None:m[int(r)]=int(q)
            maps.append(m)
        frame_maps.append(maps);certs.append(cert)
    save(out/'COMPLETE_FRAME_FAMILIES.json',{'frames':[times[x]for x in(a,b,c)],'certificates':certs,'whole_maps':frame_maps})
    qcount=np.prod([len(x)for x in frame_maps],dtype=object)
    if qcount>args.query_cap:
        save(out/'REPORT.json',{'status':'WITHHELD_QUERY_CAP','joint_configurations':qcount,'contract':evidence})
        return
    inc=[set(),set()];values=set();witnesses={};truth=[]
    for ix in product(*(range(len(m))for m in frame_maps)):
        m={r:q for maps,i in zip(frame_maps,ix)for r,q in maps[i].items()}
        first=int(a in m and b in m and(m[a],m[b])in ppairs)
        second=int(b in m and c in m and(m[b],m[c])in ppairs)
        value=first*second;values.add(value);inc[0].add(first);inc[1].add(second)
        truth.append({'whole_frame_map_indices':list(ix),'mapped_path':[m.get(x)for x in(a,b,c)],
                      'incident_visibility':[first,second],'pair_recovery':value})
        witnesses.setdefault(str(value),list(ix))
    relaxed=sorted({x*y for x,y in product(*inc)})
    admitted=args.proposed_value in values
    report={'status':'COMPLETE','query_name':'pair_recovery','proposed_value':args.proposed_value,
        'proposal_admitted':admitted,'proposal_status':'WITNESSED'if admitted else'REJECTED_UNATTAINABLE',
        'attainable_values':sorted(values),'independent_edge_relaxation_values':relaxed,
        'strict_relaxation_difference':set(relaxed)!=values,
        'whole_frame_witness_indices':witnesses,'complete_joint_truth_table':truth,
        'complete_frame_family_sizes':[len(x)for x in frame_maps],
        'evidence_graph_or_coordinates_changed_by_audit':False,
        'interpretation':'Admission concerns only the declared fixed-output correspondence contract; rejection does not certify a biological error.'}
    save(out/'REPORT.json',report)
    lines=['# Saved-graph path statement audit','',
        f'Proposed pair recovery: {args.proposed_value}. Decision: {report["proposal_status"]}.',
        f'Attainable values under complete shared maps: {report["attainable_values"]}.',
        f'Independent-edge relaxation: {relaxed}.','',
        'Input graphs and coordinates were retained. Complete frame families and map indices make every reported value replayable.',
        'This is a correspondence-sensitive untyped audit of one saved snapshot. It neither changes the tracker nor diagnoses biological causation.']
    (out/'ANALYST_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k]for k in('status','proposal_status','attainable_values','independent_edge_relaxation_values')}))

if __name__=='__main__':main()
