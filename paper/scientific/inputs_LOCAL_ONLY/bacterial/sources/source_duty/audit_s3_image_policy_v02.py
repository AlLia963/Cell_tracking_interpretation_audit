import json, hashlib, math
from pathlib import Path
from collections import defaultdict
import numpy as np
import zarr
R=Path(__file__).resolve().parent
O=R/'S3_image_policy_independent_audit_v0.2'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 O.mkdir(exist_ok=False)
 M=json.loads((R/'S3_image_veto_inputs_v0.2/manifest.json').read_text()); S=json.loads((R/'S3_image_veto_scores_v0.1/scores.json').read_text()); T=json.loads((R/'S3_allocation_trace_v0.1/report.json').read_text()); P=json.loads((R/'S3_image_veto_replay_v0.1/report.json').read_text())
 assert S['input_manifest_sha256']==sha(R/'S3_image_veto_inputs_v0.2/manifest.json')
 assert S['source_sha256']==M['source_sha256']==T['source_sha256']==P['source_sha256']==sha(M['source_path'])
 assert sha(S['weight_path'])==S['weight_sha256']
 for p,h in M['image_source_hashes'].items(): assert sha(p)==h
 for p,h in P['input_hashes'].items(): assert sha(p)==h
 lookup={}; sequence={}; accepted=0; min_margin=1.
 for row in S['rows']:
  sequence[row['film'],row['frame']]=[q['point'] for q in row['scores']]
  for q in row['scores']:
   k=(row['film'],row['frame'],*q['point']);v=q['score'];assert math.isfinite(v) and 0<=v<=1
   assert q['accepted']==(v>=.25)
   if k in lookup: assert lookup[k]==v
   lookup[k]=v;accepted+=int(v>=.25); min_margin=min(min_margin,abs(v-.25))
 for row in M['rows']:
  assert row['queries']==sequence[row['film'],row['frame']]
  assert sha(row['input_path'])==row['input_sha256']
 replay_queries=[(row['film'],q['frame'],*q['point']) for row in P['rows'] for q in row['queries']]
 assert len(replay_queries)==sum(len(x['queries']) for x in M['rows'])==928
 assert set(replay_queries)==set(lookup) and len(lookup)==859
 film_results=[]
 for film in T['rows']:
  name=film['film']; src=next(Path(p) for p in P['input_hashes'] if name in p and p.endswith('S2_gap_closing.npz'))
  with np.load(src) as a: nodes={int(i):c.tolist() for i,c in zip(a['node_ids'],a['coords'])}
  groups=defaultdict(list)
  for order,p in enumerate(film['allocation']):
   c=nodes[p['target']]; k=(name,int(c[0]),*c[1:]);v=lookup[k]
   groups[p['frame']].append(dict(p,point=c[1:],image_score=v,image_accepted=v>=.25,trace_order=order))
  selected=[];used_source=set();used_target=set();ledger=[]
  for frame in sorted(groups):
   count=0
   for p in sorted(groups[frame],key=lambda x:(x['score'],x['trace_order'])):
    pair=(p['source'],p['target']);p['global_selected_before']=len(selected);p['frame_selected_before']=count
    if not p['image_accepted']: reason='image_veto'
    elif len(selected)>=p['global_cap']:reason='global_cap'
    elif count>=p['frame_cap']:reason='frame_cap'
    elif p['target'] in used_target:reason='target_used'
    elif p['source'] in used_source:reason='source_used'
    else:
     reason='accepted';selected.append(pair);used_source.add(p['source']);used_target.add(p['target']);count+=1
    p['independent_decision']=reason;ledger.append(p)
  hist=next(x for x in P['rows'] if x['film']==name)['added_edges'];assert sorted(selected)==[tuple(p) for p in hist]
  film_results.append(dict(film=name,independent_expected_winners=sorted(selected),proposal_decision_ledger=ledger,exact_archived_parity=True))
 # Read raw source, independently calculate pooling/percentiles on first frame.
 row=M['rows'][0];base=R.parents[2]/'IWS（只读勿动）/IWS7/research/current_images_subset/train'/f"{row['film']}.zarr"/'0'
 raw=np.asarray(zarr.open_array(str(base),mode='r')[row['frame']]);z,y,x=raw.shape;factor=4
 pooled=raw[:,:y//4*4,:x//4*4].astype(np.float32).reshape(z,y//4,4,x//4,4).mean(axis=(2,4))
 lo=float(np.percentile(pooled,50));hi=float(np.percentile(pooled,99.5));tensor=np.clip((pooled-lo)/(hi-lo),-.5,6.).astype(np.float32)
 with np.load(row['input_path']) as a: assert np.array_equal(tensor,a['image'])
 closest=min(S['rows'],key=lambda r:min(abs(q['score']-.25) for q in r['scores']))
 subset=[(row['film'],row['frame']),(closest['film'],closest['frame'])]
 summary=dict(frames=len(M['rows']),query_invocations=928,unique_queries=len(lookup),accepted_invocations=accepted,rejected_invocations=928-accepted,min_threshold_margin=min_margin,proposals=sum(len(x['proposal_decision_ledger']) for x in film_results),expected_winners=sum(len(x['independent_expected_winners']) for x in film_results),raw_preprocessing_sample=dict(film=row['film'],frame=row['frame'],shape=list(raw.shape),exact_tensor_parity=True),gpu_targeted_frames=subset,source_sha256=M['source_sha256'],script_sha256=sha(__file__),result_rows=film_results)
 (O/'decision_ledger.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
 print({k:v for k,v in summary.items() if k!='result_rows'})
if __name__=='__main__':main()

