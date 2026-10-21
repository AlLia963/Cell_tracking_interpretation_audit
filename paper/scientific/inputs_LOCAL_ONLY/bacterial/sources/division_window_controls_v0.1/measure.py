import sys,json,hashlib,zipfile,io,itertools,traceback,time
from pathlib import Path
from fractions import Fraction
from datetime import datetime,timezone
from collections import Counter
import numpy as np,cv2
sys.dont_write_bytecode=True
D=Path(__file__).resolve().parent;B=D.parent/'clean_runtime_COPY_v0.1'
sys.path.insert(0,str(B))
from run_native_noisy_validation_v03 import measure,frames,MaskFrame,independent_diff_baseline
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,v):
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2)
def literal_domains(pred,ref):
    ps=[set(np.flatnonzero(m)) for m in pred.masks]; rs=[set(np.flatnonzero(m)) for m in ref.masks]; eligible_pred={};out={}
    for i,r in enumerate(rs):
        best=Fraction(1,2);best_ids=[]
        for j,p in enumerate(ps):
            u=len(r|p);q=Fraction(len(r&p),u) if u else Fraction(0)
            if q>Fraction(1,2):
                assert j not in eligible_pred or eligible_pred[j]==i;eligible_pred[j]=i
                if q>best:best=q;best_ids=[int(pred.ids[j])]
                elif q==best:best_ids.append(int(pred.ids[j]))
        out[int(ref.ids[i])]=tuple(sorted(best_ids))
    return out
start=time.perf_counter();F=D/'fixtures_v0.2';O=D/'measurement_v0.1';O.mkdir(exist_ok=False)
active=None;completed=[]
try:
    receipt=read(F/'GENERATOR_COMPLETE_BEFORE_REFERENCE.json');assert receipt['reference_opened'] is False and receipt['fixture_count']==sum(len(r.get('cases',[])) for r in receipt['receipts'])
    cfg=read(B/'external_natural/RESOURCE_MANIFEST.json'); archive=Path(cfg['archive_path']);assert sha(archive)==cfg['archive_sha256']
    write(O/'BEFORE_REFERENCE.json',dict(UTC=datetime.now(timezone.utc).isoformat(),generator_receipt_sha256=sha(F/'GENERATOR_COMPLETE_BEFORE_REFERENCE.json'),selection_sha256=sha(F/'SELECTION_BEFORE_REFERENCE.json'),protocol_sha256=sha(D/'PROTOCOL.md'),runner_sha256=sha(__file__),measurement_helper_sha256=sha(B/'run_native_noisy_validation_v03.py'),archive_sha256=cfg['archive_sha256'],scope='Accepted baseline natural records only;not pulse fourcell admission'))
    rows=[];reference_pins=[];counts=Counter();eligible_pairs=[]
    paths={'unchanged':[1,1,1,1],'edge_delete':[1,0,0,0],'node_remove':[1,0,0,0],'support_zero':[1,0,0,0],'delete_recover_delete':[1,0,1,0],'delete_recover':[1,0,1,1],'prewindow_omission':[0,0,0,0],'absent_edge_noop':[1,1,1,1],'type_relabel':[1,0,0,0]}
    with zipfile.ZipFile(archive) as z:
        for video in receipt['receipts']:
            film=video['film'];f=video['current_frame'];active=(film,f,video['target'])
            if video['status']!='fixtures_complete':counts[video['status']]+=1;continue
            names=sorted(n for n in z.namelist() if n.startswith(f'CTC/test/{film}_GT/TRA/man_track') and n.endswith('.tif'));refs=[];labels=[]
            for local,t in enumerate((f-1,f)):
                name=names[t];raw=z.read(name);im=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_UNCHANGED);assert im is not None
                ids=np.unique(im);ids=ids[ids>0];labels.append(set(map(int,ids)));refs.append(MaskFrame(local*100000+ids.astype(np.int64),np.array([im==i for i in ids],dtype=bool),local,'public disjoint reference selected only after prediction freeze'))
                reference_pins.append(dict(film=film,frame=t,member=name,sha256=hashlib.sha256(raw).hexdigest()))
            track_member=f'CTC/test/{film}_GT/TRA/man_track.txt';raw=z.read(track_member);table=np.loadtxt(io.BytesIO(raw),dtype=int,ndmin=2);reference_pins.append(dict(film=film,member=track_member,sha256=hashlib.sha256(raw).hexdigest()))
            refedges={(n,100000+n):'continuation' for n in labels[0]&labels[1]}
            for n,s,e,parent in table:
                if s==f and parent and parent in labels[0] and n in labels[1]:refedges[int(parent),100000+int(n)]='division'
            target_pred=tuple(video['target']);baseline_case=next(c for c in video['cases'] if c['arm']=='unchanged')
            def decode(case):
                p=F/case['fixture'];assert sha(p)==case['sha256']
                with np.load(p,allow_pickle=False) as a:return [{'ids':a[f'ids{k}'],'masks':a[f'masks{k}'],'edges':set(map(tuple,a[f'edges{k}'])),'division':set(map(tuple,a[f'division{k}']))} for k in range(4)]
            baseline=decode(baseline_case)[0];bd=frames(baseline,refs,literal_domains);inv={p:r for r,opts in bd.items() for p in opts if len(opts)==1}
            target=(inv[target_pred[0]],inv[target_pred[1]]) if all(p in inv for p in target_pred) else None
            eligible=target is not None and refedges.get(target)=='division'
            eligible_pairs.append(dict(film=film,current_frame=f,predicted_edge=list(target_pred),reference_edge=None if target is None else list(target),typed_reference_eligible=eligible))
            for case in video['cases']:
                views=decode(case);measured,domains=measure(views,refs,refedges);od=[frames(v,refs,literal_domains) for v in views];assert domains==od
                row=dict(film=film,current_frame=f,predicted_edge=list(target_pred),arm=case['arm'],typed_reference_eligible=eligible,reference_edge=None if target is None else list(target),fixture_sha256=case['sha256'],all_reference_records=len(measured),production_domains_equal_literal_oracle=True)
                if not eligible:row['status']='withheld-baseline-reference-ineligible';rows.append(row);continue
                got=next(m for m in measured if tuple(m['reference_edge'])==target);bounds=[]
                for v,d in zip(views,od):
                    possibilities=[(a,b) in v['division'] for a in d[target[0]] for b in d[target[1]]];bounds.append((bool(possibilities) and all(possibilities),any(possibilities)))
                assert got['bounds']==bounds
                if any(lo!=hi for lo,hi in bounds):row.update(status='withheld-correspondence-ambiguity',oracle_bounds=bounds);rows.append(row);continue
                truth=[int(lo) for lo,hi in bounds]
                if case['arm'] in paths:assert truth==paths[case['arm']],(active,case['arm'],'overlay history mismatch')
                losses=[k for k in range(1,4) if truth[k-1] and not truth[k]];gains=[k for k in range(1,4) if not truth[k-1] and truth[k]];last=losses[-1] if not truth[-1] and losses else None
                assert got['visibility']==truth and got['loss_stages']==losses and got['gain_stages']==gains and got['unique_boundary']==last
                direct=independent_diff_baseline(views,domains,target,'division');assert direct==last
                row.update(status='evaluated-controlled-path',oracle_visibility=truth,last_loss=last,framework_last_loss=got['unique_boundary'],equal_information_last_loss=direct,first_missing=next((k for k,v in enumerate(truth) if not v),None) if not truth[-1] else None,final_only=None,boundary_task_eligible=last is not None,selected_measurement=got,raw_selected_pair_present=[target_pred in v['edges'] for v in views]);rows.append(row)
            completed.append(dict(film=film,current_frame=f,predicted_edge=list(target_pred),typed_reference_eligible=eligible));print(json.dumps(completed[-1]),flush=True)
    task=[r for r in rows if r.get('boundary_task_eligible')];summary=dict(cases=len(rows),selected_movies=receipt['selected_movies'],selected_pairs=receipt['selected_pairs'],eligible_division_pairs=sum(r['typed_reference_eligible'] for r in eligible_pairs),reference_ineligible=sum(r['status']=='withheld-baseline-reference-ineligible' for r in rows),ambiguous=sum(r['status']=='withheld-correspondence-ambiguity' for r in rows),determinate=sum(r['status']=='evaluated-controlled-path' for r in rows),known_last_loss_cases=len(task),framework_correct=sum(r['framework_last_loss']==r['last_loss'] for r in task),equal_information_correct=sum(r['equal_information_last_loss']==r['last_loss'] for r in task),first_missing_concordant=sum(r['first_missing']==r['last_loss'] for r in task),final_only_refusals=len(task),type_relabel_eligible=sum(r['arm']=='type_relabel' and r.get('typed_reference_eligible') for r in rows),no_new_biological_N=True)
    assert len(rows)==receipt['fixture_count']
    write(O/'CASE_RECORDS.json',rows);write(O/'TARGET_ELIGIBILITY.json',eligible_pairs);write(O/'REFERENCE_CONSUMED.json',reference_pins)
    write(O/'RESULT.json',dict(UTC=datetime.now(timezone.utc).isoformat(),status='ACTUAL_PREDICTED_DIVISION_WINDOW_CONTROLS_COMPLETE_PENDING_INDEPENDENT_AUDIT',summary=summary,protocol_sha256=sha(D/'PROTOCOL.md'),generator_receipt_sha256=sha(F/'GENERATOR_COMPLETE_BEFORE_REFERENCE.json'),runner_sha256=sha(__file__),case_records_sha256=sha(O/'CASE_RECORDS.json'),eligibility_sha256=sha(O/'TARGET_ELIGIBILITY.json'),elapsed_seconds=time.perf_counter()-start,post_discovery=True,scientific_Major_closed=False,new_biological_N=0))
    print(json.dumps(summary),flush=True)
except BaseException:
    write(O/'MEASUREMENT_FAILURE.json',dict(active=active,completed=completed,exception=traceback.format_exc()));raise
