from pathlib import Path
from collections import defaultdict
from fractions import Fraction
from datetime import datetime, timezone
import ast,json,hashlib,zipfile,io,csv
import numpy as np
import tifffile

P=Path(__file__).resolve().parent;A=P.parent
B=A/'reproduction_LOCAL_ONLY_v0.1'/'external_full'
S=A/'closest_prior_lineage_definitions_v0.1'
O=P/'actual_v0.1';ARMS=('baseline','max_area','all_components')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,d):
    with p.open('x',encoding='utf-8') as f:json.dump(d,f,ensure_ascii=False,indent=2)
def require(x,m):
    if not x:raise RuntimeError(m)
def funcs(path,names,namespace):
    tree=ast.parse(path.read_text(encoding='utf-8'))
    found=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    require({n.name for n in found}==names,'Source function missing')
    exec(compile(ast.Module(body=found,type_ignores=[]),str(path),'exec'),namespace)
def tracks(data,frames):
    rows=[tuple(map(int,l.split())) for l in data.decode('utf-8-sig').splitlines() if l.strip()]
    require(all(len(x)==4 for x in rows),'Track width')
    table={i:(s,e,p) for i,s,e,p in rows};require(len(table)==len(rows),'Duplicate track')
    for i,(s,e,p) in table.items():
        require(i>0 and 0<=s<=e<frames and p>=0,'Track domain')
        if p:require(p in table and table[p][1]==s-1,'Parent timing')
    return np.asarray(rows,dtype=np.int64).reshape(-1,4),table
def independent_events(ref,pred,maps,tolerance):
    def children(table):
        result=defaultdict(list)
        for i,(_,_,p) in table.items():
            if p:result[p].append(i)
        return {p:sorted(ids) for p,ids in result.items() if len(ids)>1}
    rc=children(ref);pc=children(pred);pairs=[]
    for r,rd in sorted(rc.items()):
        re=ref[r][1]
        for p,pd in sorted(pc.items()):
            pe=pred[p][1]
            if len(rd)!=len(pd) or abs(re-pe)>tolerance:continue
            mother_time=min(re,pe)
            if maps[mother_time].get(r)!=p:continue
            daughters=[];valid=True
            for daughter in rd:
                candidates=[]
                for child in pd:
                    rs=ref[daughter][0];ps=pred[child][0]
                    if abs(rs-ps)>tolerance:continue
                    if maps[max(rs,ps)].get(daughter)==child:candidates.append(child)
                if len(candidates)!=1:valid=False;break
                daughters.append(candidates[0])
            if valid and len(set(daughters))==len(rd):
                pairs.append({'reference_mother':r,'prediction_mother':p,'mother_end_shift':pe-re,
                     'reference_daughters':rd,'prediction_daughters_corresponding':daughters,
                     'daughter_start_shifts':[pred[child][0]-ref[daughter][0] for daughter,child in zip(rd,daughters)]})
    # Required for interpretable F1; do not invent an assignment tie-break.
    require(len({x['reference_mother'] for x in pairs})==len(pairs),'Reference event reused')
    require(len({x['prediction_mother'] for x in pairs})==len(pairs),'Prediction event reused')
    tp=len(pairs);fp=len(pc)-tp;fn=len(rc)-tp
    return (tp,fp,fn),pairs,len(rc),len(pc)

def main():
    O.mkdir(exist_ok=False)
    cfg=read(B/'RESOURCE_MANIFEST.json');ns={'np':np}
    require(sha(S/'bc.py')=='cab0b299382ca6d1c041a7a142261f1c1813f5c03bbf27758576cd3a8581c56d','Primary source pin')
    funcs(S/'bc.py',{'get_ids_that_ends_with_split','calculate_f1_score','is_matching','raw_division_metrics','bc'},ns)
    scorer=B/'reproduce_external_from_labels.py';matchns={'np':np};funcs(scorer,{'actual_matches'},matchns)
    pins={str(P/'PROTOCOL.md'):sha(P/'PROTOCOL.md'),str(P/'analyze.py'):sha(P/'analyze.py'),
          str(B/'RESOURCE_MANIFEST.json'):sha(B/'RESOURCE_MANIFEST.json'),str(S/'bc.py'):sha(S/'bc.py'),str(scorer):sha(scorer)}
    roots={x['arm']:x for x in cfg['arms']};manifests={}
    for arm in ARMS:
        path=B/roots[arm]['manifest_relative'];require(sha(path)==roots[arm]['manifest_sha256'],'Manifest pin')
        pins[str(path)]=sha(path)
        manifests[arm]={x['video']:x for x in read(path)['all_video_reports']}
        require(set(manifests[arm])=={f'{i:02d}' for i in range(1,30)},'Complete29 domain')
    write(O/'START.json',{'UTC':datetime.now(timezone.utc).isoformat(),'input_manifest_pins_before_outcomes':pins,
           'archive':cfg['archive_path'],'previously_admitted_archive_sha256':cfg['archive_sha256'],
           'GT_scope':'Existing previously admitted three-policy test29; NOT fourarm','retrospective':True})
    results=[];consumed={};gtconsumed={}
    with zipfile.ZipFile(cfg['archive_path']) as z:
        for i in range(1,30):
            film=f'{i:02d}';frames=manifests['baseline'][film]['input_frames']
            ref_name=f'CTC/test/{film}_GT/TRA/man_track.txt';rb=z.read(ref_name)
            gtconsumed[ref_name]=hashlib.sha256(rb).hexdigest();ref_arr,ref_table=tracks(rb,frames)
            images=[]
            for t in range(frames):
                name=f'CTC/test/{film}_GT/TRA/man_track{t:03d}.tif';raw=z.read(name)
                gtconsumed[name]=hashlib.sha256(raw).hexdigest();images.append(tifffile.imread(io.BytesIO(raw)))
            movie=[]
            for arm in ARMS:
                report=manifests[arm][film];require(report['input_frames']==frames,'Common frame domain')
                root=Path(roots[arm]['native_root'])/film
                path=root/'res_track.txt';data=path.read_bytes();h=hashlib.sha256(data).hexdigest()
                require(h==report['output_hashes'][path.name],'Track pin');consumed[str(path)]=h
                pred_arr,pred_table=tracks(data,frames)
                maps=[];mr=[];mp=[]
                for t,ref in enumerate(images):
                    path=root/f'mask{t:03d}.tif';data=path.read_bytes();h=hashlib.sha256(data).hexdigest()
                    require(h==report['output_hashes'][path.name],'Mask pin');consumed[str(path)]=h
                    pred=tifffile.imread(io.BytesIO(data))
                    forward,_=matchns['actual_matches'](ref,pred,t)
                    mapping={k[1]:v[1] for k,v in forward.items()}
                    require(len(set(mapping.values()))==len(mapping),'Nonunique correspondence')
                    maps.append(mapping);mr.append(list(mapping));mp.append([mapping[r] for r in mapping])
                records=[]
                for tolerance in [0,1]:
                    count,pairs,nref,npred=independent_events(ref_table,pred_table,maps,tolerance)
                    original=tuple(map(int,ns['raw_division_metrics'](pred_arr,ref_arr,mr,mp,tolerance)))
                    require(count==original,'Event counting route mismatch '+film+arm+str(tolerance))
                    tp,fp,fn=count
                    exact=Fraction(2*tp,2*tp+fp+fn) if tp+fn else None
                    original_f1=ns['bc'](*original)
                    require((exact is None)==(original_f1 is None),'Undefined mismatch')
                    if exact is not None:require(abs(float(exact)-original_f1)<1e-12,'F1 route mismatch')
                    row={'film':film,'arm':arm,'tolerance_frames':tolerance,'reference_events':nref,'prediction_events':npred,
                         'division_TP':tp,'division_FP':fp,'division_FN':fn,'F1':float(exact) if exact is not None else None,
                         'F1_exact':str(exact),'matched_pairs':pairs,'per_frame_correspondence':[sorted(m.items()) for m in maps]}
                    records.append(row);results.append(row)
                require({x['reference_mother'] for x in records[0]['matched_pairs']}<={x['reference_mother'] for x in records[1]['matched_pairs']},'Tolerance lost exact events')
                movie.extend(records)
            write(O/(film+'_EVENTS.json'),movie)
            print('ACTUAL_DIVISION_TIMING',film,[(x['arm'],x['tolerance_frames'],x['division_TP']) for x in movie],flush=True)
    require(all(sha(Path(p))==h for p,h in pins.items()),'Source/manifest changed during execution')
    write(O/'CONSUMED_BINDINGS.json',{'prediction_files':consumed,'reference_member_content_sha256':gtconsumed})
    summaries={}
    for arm in ARMS:
        summaries[arm]={}
        for tolerance in [0,1]:
            rows=[x for x in results if x['arm']==arm and x['tolerance_frames']==tolerance]
            require(len(rows)==29,'Not all29 measured')
            tp=sum(x['division_TP'] for x in rows);fp=sum(x['division_FP'] for x in rows);fn=sum(x['division_FN'] for x in rows)
            macro=sum((Fraction(x['F1_exact']) for x in rows),Fraction(0))/29
            summaries[arm][str(tolerance)]={'reference_events':tp+fn,'prediction_events':tp+fp,'TP':tp,'FP':fp,'FN':fn,
               'micro_F1':float(Fraction(2*tp,2*tp+fp+fn)),'micro_F1_exact':str(Fraction(2*tp,2*tp+fp+fn)),
               'macro_F1':float(macro),'macro_F1_exact':str(macro),'movie_count':29}
    with (O/'PER_MOVIE.csv').open('x',encoding='utf-8',newline='') as f:
        keys=['film','arm','tolerance_frames','reference_events','prediction_events','division_TP','division_FP','division_FN','F1','F1_exact']
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows({k:x[k] for k in keys} for x in results)
    result={'UTC':datetime.now(timezone.utc).isoformat(),'status':'ACTUAL_EXISTING29_THREE_POLICY_DIVISION_TIMING_SENSITIVITY_COMPLETE',
       'all174_primary_event_and_independent_map_routes_agree':True,'one_to_one_event_use_verified':True,
       'per_arm':summaries,'mask_correspondence':'Strict integer IoU>0.5; same previously verified complete-policy audit matching',
       'scope':'Existing29 retrospective endpoint sensitivity. Definition-aligned branch conditions with stated IoU correspondence, not official CTC BC certification, new inference/N/utility or fourarm GT admission.',
       'new_N':0,'fourarm_admission':False,'SF_M1':'MAJOR_OPEN'}
    write(O/'RESULT.json',result);print(json.dumps(result,ensure_ascii=False),flush=True)

try:main()
except Exception as exc:
    if O.exists() and not (O/'FAILED.json').exists():write(O/'FAILED.json',{'UTC':datetime.now(timezone.utc).isoformat(),'error':repr(exc),'status':'FAILED_RESULTS_WITHHELD'})
    raise
