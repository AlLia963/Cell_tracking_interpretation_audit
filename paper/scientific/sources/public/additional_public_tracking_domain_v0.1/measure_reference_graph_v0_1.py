"""Reference-relative, untyped full census on the frozen epithelial output."""
from pathlib import Path
import json,hashlib,datetime,time,traceback,collections,importlib.util,csv
import numpy as np
import tifffile
P=Path(__file__).parent
STAGES=P/'actual_raw_stages_v0.1'
OUT=P/'actual_reference_measurement_v0.1'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,x):
 assert not p.exists(),str(p)
 p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
spec=importlib.util.spec_from_file_location('fixed_local_core',P.parent/'generic_raw_local_workflow_v0.1'/'local_graph_core.py')
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
def category(h):return core.final_category(h)
def exact_iou_map(reference,prediction):
 rvals,rcounts=np.unique(reference,return_counts=True)
 pvals,pcounts=np.unique(prediction,return_counts=True)
 ra={int(k):int(v) for k,v in zip(rvals,rcounts) if k>0}
 pa={int(k):int(v) for k,v in zip(pvals,pcounts) if k>0}
 pairs,counts=np.unique(np.stack([reference.ravel(),prediction.ravel()],axis=1),axis=0,return_counts=True)
 mapping={};candidates=[]
 for (r,p),i in zip(pairs,counts):
  r,p,i=int(r),int(p),int(i)
  if r>0 and p>0 and 3*i>ra[r]+pa[p]:
   assert r not in mapping,'Nonunique reference mask candidate'
   assert p not in mapping.values(),'Noninjective mask candidate'
   mapping[r]=p;candidates.append({'reference_label':r,'predicted_label':p,'intersection':i,'union':ra[r]+pa[p]-i})
 return mapping,candidates
def measure(movie,design,cohort):
 refrec=next(r for r in design['records'] if r['movie']==movie and r['role']=='curated_labels')
 refpath=Path(refrec['local_path']);assert sha(refpath)==refrec['sha256']
 with tifffile.TiffFile(refpath) as t:
  axes=t.series[0].axes;ref=t.series[0].asarray()
 if axes=='YX':ref=ref[None]
 elif axes!='TYX':raise ValueError('Reference axis unsupported '+axes)
 assert np.all(np.isfinite(ref)) and np.all(ref>=0) and np.all(ref==np.floor(ref)), 'Reference schema not nonnegative finite integer labels'
 ref=ref.astype(np.int64)
 assert len(ref)==cohort['time_frames']
 ids=[set(map(int,np.unique(mask)))-{0} for mask in ref]
 redges=[((t-1,i),(t,i)) for t in range(1,len(ref)) for i in sorted(ids[t-1]&ids[t])]
 paths=[((t-1,i),(t,i),(t+1,i)) for t in range(1,len(ref)-1) for i in sorted(ids[t-1]&ids[t]&ids[t+1])]
 base={'movie':movie,'frames':len(ref),'reference_nodes':sum(map(len,ids)),'reference_edges':len(redges),'reference_paths':len(paths),'reference_sha256':refrec['sha256'],'identity':'movie/frame/local-label','biological_relation_type':'unspecified; same curated label only','stages':[]}
 if len(ref)<3:
  base.update(status='INELIGIBLE_SINGLE_IMAGE_NOT_TRACKING',edge_records=[],path_records=[])
  return base
 allmaps=[];alladj=[];stage_edges=[];frame_certificates=[]
 for stage in cohort['stages']:
  if stage['status']!='COMPLETE_UNTYPED_CONTINUATION_GRAPH':
   base.update(status='WITHHELD_STAGE_GRAPH',stage_failure=stage,edge_records=None,path_records=None)
   return base
  mp=STAGES/stage['mask_file'];gp=STAGES/stage['graph_file']
  assert sha(mp)==stage['mask_sha256'] and sha(gp)==stage['graph_sha256']
  pred=tifffile.imread(mp);g=json.loads(gp.read_text(encoding='utf-8'))
  assert pred.shape==ref.shape
  maps={};cert=[]
  for t,(r,p) in enumerate(zip(ref,pred)):
   match,frame=exact_iou_map(r,p)
   maps.update({(t,k):int(t*100000+v) for k,v in match.items()})
   cert.append({'frame':t,'reference_objects':len(ids[t]),'predicted_objects':int(len(np.unique(p))-int(0 in p)),'matches':frame})
  pedges=set(map(tuple,g['edges']));outgoing=collections.defaultdict(set);incoming=collections.defaultdict(set)
  for a,b in pedges:outgoing[a].add(b);incoming[b].add(a)
  tp=sum((maps.get(a),maps.get(b)) in pedges for a,b in redges)
  base['stages'].append({'view':stage['view'],'reference_edge_TP':tp,'reference_edge_FN':len(redges)-tp,'all_predicted_pair_FP':len(pedges)-tp,'predicted_nodes':len(g['nodes']),'predicted_edges':len(pedges),'mapped_reference_nodes':len(maps)})
  allmaps.append(maps);alladj.append((outgoing,incoming));stage_edges.append(pedges);frame_certificates.append({'view':stage['view'],'frames':cert})
 er=[]
 for a,b in redges:
  h=''.join(str(int((maps.get(a),maps.get(b)) in pe)) for maps,pe in zip(allmaps,stage_edges))
  er.append({'id':f'{movie}|{a[0]}:{a[1]}|{b[0]}:{b[1]}','nodes':[list(a),list(b)],'history':h,'category':category(h),
   'first_missing_view':next((k for k,v in enumerate(h) if v=='0'),None),
   'last_observed_loss_view':next((k for k in range(3,0,-1) if h[k-1:k+1]=='10'),None)})
 pr=[]
 for nodes in paths:
  vals=[core.local_graph_query_value('three_node_path',[maps.get(n) for n in nodes],*adj) for maps,adj in zip(allmaps,alladj)]
  rh=''.join(str(v[0]) for v in vals);ch=''.join(str(v[1]) for v in vals)
  # Separate conventional full-neighbourhood/Boolean arithmetic, same information.
  conventional=[]
  for maps,adj,pe in zip(allmaps,alladj,stage_edges):
   a,b,c=[maps.get(n) for n in nodes]
   r=int(a is not None and b is not None and c is not None and (a,b) in pe and (b,c) in pe)
   check=int(r and adj[0].get(a,set())=={b} and adj[0].get(b,set())=={c} and adj[1].get(b,set())=={a} and adj[1].get(c,set())=={b})
   conventional.append((r,check))
  assert [(v[0],v[1]) for v in vals]==conventional
  pr.append({'id':f'{movie}|path|{nodes[0][0]}:{nodes[0][1]}','nodes':[list(n) for n in nodes],
   'pair_recovery_history':rh,'structural_consistency_history':ch,'pair_recovery_category':category(rh),'structural_consistency_category':category(ch),
   'same_information_conventional_equal':True})
 base.update(status='COMPLETE_REFERENCE_RELATIVE_MEASUREMENT',edge_records=er,path_records=pr,frame_matching_certificates=frame_certificates)
 base['edge_categories']=dict(collections.Counter(r['category'] for r in er))
 base['edge_histories']=dict(collections.Counter(r['history'] for r in er))
 base['path_recovery_categories']=dict(collections.Counter(r['pair_recovery_category'] for r in pr))
 base['path_structural_categories']=dict(collections.Counter(r['structural_consistency_category'] for r in pr))
 base['path_recovery_structural_disagreement']=sum(r['pair_recovery_history']!=r['structural_consistency_history'] for r in pr)
 base['boundaries']=[{'later_view':k,'gain':sum(r['history'][k-1:k+1]=='01' for r in er),'loss':sum(r['history'][k-1:k+1]=='10' for r in er)} for k in range(1,4)]
 assert all(base['stages'][k]['reference_edge_TP']-base['stages'][k-1]['reference_edge_TP']==b['gain']-b['loss'] for k,b in enumerate(base['boundaries'],1))
 return base
def main():
 assert not OUT.exists();OUT.mkdir()
 start=time.monotonic()
 design=json.loads((P/'RAW_EXPERIMENT_DESIGN_v0.1.json').read_text(encoding='utf-8'))
 freeze=json.loads((STAGES/'OUTPUT_FREEZE.json').read_text(encoding='utf-8'))
 assert freeze['reference_arrays_opened'] is False
 cohort=json.loads((STAGES/'COHORT_SUMMARY.json').read_text(encoding='utf-8'))
 save(OUT/'RUN_START.json',{'utc':utc(),'stage_freeze_sha256':sha(STAGES/'OUTPUT_FREEZE.json'),'source_sha256':sha(Path(__file__)),'core_sha256':sha(P.parent/'generic_raw_local_workflow_v0.1'/'local_graph_core.py'),'design_sha256':sha(P/'RAW_EXPERIMENT_DESIGN_v0.1.json')})
 records=[]
 for cm in cohort['movies']:
  try:r=measure(cm['movie'],design,cm)
  except Exception as e:r={'movie':cm['movie'],'status':'FAILED_REFERENCE_SCHEMA_OR_MEASUREMENT','error':repr(e),'traceback':traceback.format_exc()}
  save(OUT/(cm['movie']+'_complete_result.json'),r)
  records.append({k:v for k,v in r.items() if k not in ['edge_records','path_records','frame_matching_certificates']})
  print(json.dumps(records[-1],ensure_ascii=False),flush=True)
 summary={'utc':utc(),'status':'ACTUAL_ALL_SELECTED_MOVIES_MEASURED_WITH_FAILURES_OR_INELIGIBILITY_RETAINED_NOT_AUDIT_ACCEPTED','movies':records,'no_retuning':True,'no_biological_type_or_lineage_truth':True,'new_independent_biological_replication_claim':False,'same_information_superiority_claim':False}
 save(OUT/'SUMMARY.json',summary)
 files=[{'path':str(p.relative_to(OUT)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(OUT.iterdir()) if p.is_file()]
 save(OUT/'OUTPUT_FREEZE.json',{'utc':utc(),'files':files,'design_sha256':sha(P/'RAW_EXPERIMENT_DESIGN_v0.1.json'),'not_independent_audit':True})
 save(OUT/'RUN_COMPLETE.json',{'utc':utc(),'elapsed_seconds':time.monotonic()-start,'status':summary['status']})
if __name__=='__main__':
 try:main()
 except Exception as e:
  if OUT.exists() and not (OUT/'RUN_FAILURE.json').exists():save(OUT/'RUN_FAILURE.json',{'utc':utc(),'error':repr(e),'traceback':traceback.format_exc(),'partial_outputs_preserved':True})
  raise
