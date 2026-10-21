"""Real pixel G -> independently computed box -> actual next consumer, no GT."""
from pathlib import Path
import datetime, hashlib, json, traceback
import numpy as np
P=Path(__file__).resolve().parent;F=P.parent;O=P/'actual_v0.1'
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,v):
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,allow_nan=False)
def need(v,m):
    if not v:raise ValueError(m)
def arrays(p,want,pins):
    need(sha(p)==want,'Actual technical raw bytes '+str(p));pins[str(p)]=want
    with np.load(p,allow_pickle=False) as z:return {k:z[k].copy() for k in z.files}
def boxes(mask):
    need(mask.ndim==3 and mask.dtype==np.bool_,'Binary G carrier')
    n,h,w=mask.shape;out=[];bounds=[]
    for m in mask:
        y,x=np.nonzero(m)
        if not len(x):bounds.append(None);out.append([0.,0.,0.,0.]);continue
        x0,x1,y0,y1=map(np.float32,[x.min(),x.max(),y.min(),y.max()])
        bounds.append([int(x0),int(y0),int(x1),int(y1)])
        out.append([(x0+x1)/np.float32(2)/np.float32(w),
            (y0+y1)/np.float32(2)/np.float32(h),(x1-x0)/np.float32(w),(y1-y0)/np.float32(h)])
    return np.asarray(out,dtype=np.float32).reshape(n,4),bounds
def eq(a,b):return a.shape==b.shape and a.dtype==b.dtype and a.tobytes(order='C')==b.tobytes(order='C')
def dict_eq(a,b):return set(a)==set(b) and all(eq(a[k],b[k]) for k in a)

def main():
    O.mkdir(exist_ok=False);jp=F/'ROOT_COHORT06_NORMALIZATION_JOB_v0.1/JOB.json';job=load(jp)
    pins={str(jp):sha(jp),str(P/'PROTOCOL.md'):sha(P/'PROTOCOL.md'),str(Path(__file__)):sha(__file__)}
    maps={};specs={a:job['arm_inputs'][a] for a in ['WW','WA']}
    for a,s in specs.items():
        for k,w in [('technical_result_path','technical_result_sha256'),('consumed_receipt_path','consumed_receipt_sha256'),('manifest_path','manifest_sha256')]:
            need(sha(s[k])==s[w],'Current actual '+a+'/'+k);pins[s[k]]=s[w]
        m=load(s['consumed_receipt_path']);maps[a]=m if s['consumed_hash_mapping_key'] is None else m[s['consumed_hash_mapping_key']]
    taus=specs['WW']['tau_by_film'];need(taus==specs['WA']['tau_by_film'],'Same fixed schedule')
    selected=[f for f,t in sorted(taus.items()) if t is not None];need(len(selected)==14,'All14 trigger domain')
    write(O/'START.json',{'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'protocol_sha256':pins[str(P/'PROTOCOL.md')],
        'fixed14':selected,'no_GT':True,'retrospective_exploratory':True})
    rows=[]
    for film in selected:
        t=taus[film];d={};g={};bounds={};q={};capture={}
        for a,s in specs.items():
            root=Path(s['native_root'])/film/'direct_trace'
            get=lambda kind,frame:arrays(root/f'{frame:04d}_{kind}_00.npz',maps[a][str(root/f'{frame:04d}_{kind}_00.npz')],pins)
            d[a]=get('postprocess_M_G',t);g[a]=d[a]['root/G'];recomputed,bounds[a]=boxes(g[a])
            model=get('before_model',t+1);q[a]=model['root/targets/0/main/cur_target/track_query_boxes']
            need(eq(recomputed,q[a]),'Exact pixel-to-actual-query projection mismatch '+film+'/'+a)
            capture[a]={k:get(k,t+1) for k in ['consumer_stack','consumer_reference_points','raw_model_output']}
        need(eq(d['WW']['root/cells'],d['WA']['root/cells']) and eq(d['WW']['root/all_indices'],d['WA']['root/all_indices']),'Same pulse carrier IDs/order')
        need(eq(d['WW']['root/M'],d['WA']['root/M']),'Same M control')
        need(g['WW'].shape==g['WA'].shape,'Common grid')
        delta=np.logical_xor(g['WW'],g['WA']);rows_changed=[int(x) for x in np.flatnonzero(delta.any(axis=(1,2)))]
        ext_changed=[i for i,(a,b) in enumerate(zip(bounds['WW'],bounds['WA'])) if a!=b]
        row={'film':film,'tau':t,'pulse_rows':len(g['WW']),'row_indices_changed':rows_changed,
            'row_sum_XOR_pixels':int(delta.sum()),'row_extent_changes':ext_changed,
            'G_masks_equal':eq(g['WW'],g['WA']),'independent_boxes_match_actual_queries':True,
            'next_track_query_boxes_equal':eq(q['WW'],q['WA']),
            'actual_next_capture_array_equal':{k:dict_eq(capture['WW'][k],capture['WA'][k]) for k in capture['WW']},
            'W_pixel_extents':bounds['WW'],'A_pixel_extents':bounds['WA']}
        rows.append(row);write(O/(film+'_PROJECTION.json'),row)
        print('ACTUAL_G_PROJECTION',film,'xor',row['row_sum_XOR_pixels'],'extent',ext_changed,'Q_equal',row['next_track_query_boxes_equal'],'raw_equal',row['actual_next_capture_array_equal']['raw_model_output'],flush=True)
    result={'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'ACTUAL_ALL14_G_PIXEL_QUERY_PROJECTION_COMPLETE',
        'rows':rows,'triggers':14,'no_trigger_excluded_from_pulse_estimand':15,
        'changed_G_masks':sum(not r['G_masks_equal'] for r in rows),
        'unchanged_next_boxes':sum(r['next_track_query_boxes_equal'] for r in rows),
        'changed_next_boxes':sum(not r['next_track_query_boxes_equal'] for r in rows),
        'unchanged_next_raw_heads':sum(r['actual_next_capture_array_equal']['raw_model_output'] for r in rows),
        'input_sha256':pins,'no_GT':True,'new_biological_N':0,'SF_M1':'MAJOR_OPEN',
        'scope':'Independent true-pixel projection checked against actual next model and consumer captures. Single next-call scope, not final graph/accuracy, natural causality, full future history or utility; hypothesis proposed after first10 effect inspection.'}
    write(O/'RESULT.json',result)
if __name__=='__main__':
    try:main()
    except BaseException:
        if O.exists():write(O/'FAILED.json',{'status':'WITHHELD','traceback':traceback.format_exc(),'no_GT':True})
        raise
