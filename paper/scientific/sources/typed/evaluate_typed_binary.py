"""Literal typed-coordinate binary-lineage demonstration, not a production solver.

Constructed input types are supplied by the controlled graph. No microscope,
mask, physical uncertainty, production float parity or general lineage guarantee
is established. Original experiment inputs and historical software are untouched.
"""
import argparse
import hashlib
import itertools
import json
import math
import time
from fractions import Fraction
from pathlib import Path

TYPES={'continuation','division_daughter'}
def nodes(rows):
    if type(rows) is not list: raise ValueError('Node array required')
    out={}
    for row in rows:
        if type(row) is not dict or set(row)!={'id','frame','xy'}:raise ValueError('Node schema')
        if type(row['id']) is not int or type(row['frame']) is not int or row['id'] in out:raise ValueError('Unique integer ID/frame domain')
        if type(row['xy']) is not list or len(row['xy'])!=2:raise ValueError('Two coordinates')
        for x in row['xy']:
            if type(x) not in (int,float):raise ValueError('Finite numeric coordinates')
            try: valid=math.isfinite(x)
            except (OverflowError,ValueError,TypeError):valid=False
            if not valid:raise ValueError('Finite coordinate domain')
        out[row['id']]=row
    return out
def graph(rows, ns):
    if type(rows) is not list:raise ValueError('Typed edge array')
    out={}; incoming={}; outgoing={}
    for e in rows:
        if type(e) is not dict or set(e)!={'source','target','type'}:raise ValueError('Typed edge schema')
        a,b,t=e['source'],e['target'],e['type']
        if type(a) is not int or type(b) is not int or a not in ns or b not in ns or t not in TYPES:raise ValueError('Typed endpoint/type domain')
        if (a,b) in out or ns[b]['frame']!=ns[a]['frame']+1:raise ValueError('Unique adjacent directed pair')
        if b in incoming:raise ValueError('Binary lineage may not merge')
        out[(a,b)]=t; incoming[b]=a; outgoing.setdefault(a,[]).append(t)
    for ts in outgoing.values():
        if ts!=['continuation'] and (len(ts)!=2 or set(ts)!={'division_daughter'}):
            raise ValueError('Continuation singly or exactly two division daughters required')
    return out
def fmaps(rs,ps,gate,cap):
    options=[]
    for r in rs:
        q=[(None,Fraction(0))]
        for p in ps:
            d=math.dist(r['xy'],p['xy'])
            if not math.isfinite(d):raise ValueError('Finite calculated distance required')
            if d<=gate:q.append((p['id'],Fraction.from_float(d)))
        options.append(q)
    screen=math.prod(map(len,options))
    if screen>cap:return None,{'status':'WITHHELD_FRAME_SCREEN_CAP','screen_upper_bound':screen,'cap':cap}
    bestk=-1;bestcost=None;best=[];examined=0;injective=0
    for c in itertools.product(*options):
        examined+=1; values=[v for v,_ in c if v is not None]
        if len(values)!=len(set(values)):continue
        injective+=1;k=len(values);cost=sum((d for v,d in c if v is not None),Fraction(0))
        m={r['id']:v for r,(v,d) in zip(rs,c)}
        if k>bestk or k==bestk and cost<bestcost:bestk,bestcost,best=k,cost,[m]
        elif k==bestk and cost==bestcost:best.append(m)
    return best,{'status':'COMPLETE_LITERAL_PARTIAL_INJECTION_ENUMERATION','screen_upper_bound':screen,
                 'examined_products':examined,'injective_maps':injective,'maximum_cardinality':bestk,
                 'minimum_calculated_cost_fraction':[bestcost.numerator,bestcost.denominator],'optimal_maps':best}
def projections(bits, edges, mother):
    daughter=[i for i,(a,b,t) in enumerate(edges) if a==mother and t=='division_daughter']
    inc=[i for i,(a,b,t) in enumerate(edges) if b==mother and t=='continuation']
    assert len(daughter)==2 and len(inc)==1
    features={}
    for s in range(2):
        count=sum(int(bits[i][s]) for i in daughter)
        event=int(count==2); context=int(event and bits[inc[0]][s]=='1')
        features.update({f'typed_daughter_count_{s}':count,f'complete_binary_event_{s}':event,f'incoming_and_complete_event_{s}':context})
    features['event_transition']=int(features['complete_binary_event_0']!=features['complete_binary_event_1'])
    features['context_transition']=int(features['incoming_and_complete_event_0']!=features['incoming_and_complete_event_1'])
    return features
def envelope(rows,key):
    fields=sorted(rows[0][key]); out={}
    for f in fields:
        vals=sorted({r[key][f] for r in rows})
        out[f]={'values':vals,'minimum':vals[0],'maximum':vals[-1],
                'minimum_witness_index':next(i for i,r in enumerate(rows) if r[key][f]==vals[0]),
                'maximum_witness_index':next(i for i,r in enumerate(rows) if r[key][f]==vals[-1])}
    return out
def run(data,convention,frame_cap,joint_cap):
    t0=time.perf_counter()
    if set(data)!={'description','units','gate','reference_nodes','reference_edges','focal_mother','stages'}:raise ValueError('Exact demonstration schema')
    if not all(type(data[k]) is str and data[k].strip() for k in ('description','units')):raise ValueError('Description and units')
    gate=data['gate']
    if type(gate) not in (int,float) or not math.isfinite(gate) or gate<0:raise ValueError('Finite nonnegative gate')
    ref=nodes(data['reference_nodes']); rg=graph(data['reference_edges'],ref)
    mother=data['focal_mother']; es=sorted((a,b,t) for (a,b),t in rg.items())
    if type(mother) is not int or mother not in ref:raise ValueError('Focal mother domain')
    projections(['00']*len(es),es,mother) # verifies exact focal incoming/two-daughter query domain
    if type(data['stages']) is not list or len(data['stages'])!=2:raise ValueError('Exactly two processing views')
    validated=[];frames=sorted({n['frame'] for n in ref.values()})
    for stage in data['stages']:
        if type(stage) is not dict or set(stage)!={'nodes','edges'}:raise ValueError('Stage domain')
        ns=nodes(stage['nodes']); gg=graph(stage['edges'],ns)
        if {n['frame'] for n in ns.values()}-set(frames):raise ValueError('No additional frames in this bounded adapter')
        for r in ref.values():
            for p in ns.values():
                if r['frame']==p['frame'] and not math.isfinite(math.dist(r['xy'],p['xy'])):raise ValueError('Finite distance preflight')
        validated.append((ns,gg))
    if convention=='same_map_identical_snapshots' and data['stages'][0]!=data['stages'][1]:raise ValueError('This small equality convention requires identical complete snapshots')
    preflight=time.perf_counter()-t0
    stage_maps=[];certs=[];tc=time.perf_counter()
    for s,(ns,gg) in enumerate(validated):
        all_frames=[]
        for f in frames:
            ms,cert=fmaps([ref[i] for i in sorted(ref) if ref[i]['frame']==f],
                          [ns[i] for i in sorted(ns) if ns[i]['frame']==f],gate,frame_cap)
            certs.append({'stage':s,'frame':f,**cert})
            if ms is None:return {'status':'WITHHELD_FRAME_SCREEN_CAP','frame_certificates':certs,'readout':None,'no_truncated_report':True}
            all_frames.append(ms)
        stage_maps.append([{i:p for part in parts for i,p in part.items()} for parts in itertools.product(*all_frames)])
    count=math.prod(map(len,stage_maps)) if convention=='per_view_product' else len(stage_maps[0])
    if count>joint_cap:return {'status':'WITHHELD_JOINT_ENUMERATION_CAP','whole_map_count':count,'joint_cap':joint_cap,'frame_certificates':certs,'readout':None,'no_truncated_report':True}
    construction=time.perf_counter()-tc;tp=time.perf_counter();rows=[]
    assignments=itertools.product(*stage_maps) if convention=='per_view_product' else ((m,m) for m in stage_maps[0])
    for maps in assignments:
        raw=[];typed=[]
        for a,b,t in es:
            rb=[];tb=[]
            for m,(ns,gg) in zip(maps,validated):
                pair=(m[a],m[b]); present=pair[0] is not None and pair[1] is not None and pair in gg
                rb.append(str(int(present)));tb.append(str(int(present and gg[pair]==t)))
            raw.append(''.join(rb));typed.append(''.join(tb))
        rows.append({'stage_maps':maps,'raw_histories':raw,'typed_histories':typed,'features':projections(typed,es,mother)})
    assert len(rows)==count
    domains=[sorted({r['typed_histories'][i] for r in rows}) for i in range(len(es))]
    relaxed=[{'typed_histories':list(c),'features':projections(c,es,mother)} for c in itertools.product(*domains)]
    report={'status':'COMPLETE_CONSTRUCTED_TYPED_BINARY_REPORT','convention':convention,
            'reference_edges':[{'source':a,'target':b,'type':t} for a,b,t in es],
            'frame_certificates':certs,'whole_maps_per_view':stage_maps,'whole_map_count':len(rows),
            'whole_map_reports':rows,'typed_history_domains':domains,
            'canonical_conditional_report':rows[0],'separate_scalar_reports':envelope(rows,'features'),
            'marginal_relaxation':{'configuration_count':len(relaxed),'scalar_reports':envelope(relaxed,'features'),'readouts':relaxed,
                'scope':'conservative Cartesian relaxation of marginal histories; not a valid full-map existence certificate'},
            'time_seconds':{'preflight':preflight,'construction':construction,'projection_and_marginal_relaxation':time.perf_counter()-tp},
            'scope':'Four constructed binary cases; explicit input types, literal complete maps. Not existing production/general mask adapter certification, new biological N, physical calibration, intervention utility or peer-review acceptance.'}
    # Separate witnesses certify only their own scalar, not arbitrary vectors.
    for f,v in report['separate_scalar_reports'].items():
        for end in ('minimum','maximum'):assert rows[v[end+'_witness_index']]['features'][f]==v[end]
    return report
def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--convention',choices=['per_view_product','same_map_identical_snapshots'],default='per_view_product')
    p.add_argument('--frame-cap',type=int,default=64);p.add_argument('--joint-cap',type=int,default=64);a=p.parse_args()
    if a.output.exists() or min(a.frame_cap,a.joint_cap)<1:raise ValueError('New output path and positive caps')
    b=a.input.read_bytes();d=json.loads(b.decode('utf-8'))
    r=run(d,a.convention,a.frame_cap,a.joint_cap)
    r.update({'input_path':str(a.input),'input_sha256':hashlib.sha256(b).hexdigest(),
              'producer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    a.output.mkdir(parents=True)
    (a.output/'RESULT.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'input':a.input.name,'output':str(a.output),'status':r['status']},ensure_ascii=False))
if __name__=='__main__':main()
