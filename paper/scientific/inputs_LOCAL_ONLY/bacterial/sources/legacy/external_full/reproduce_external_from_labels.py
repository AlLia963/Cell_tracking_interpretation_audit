"""Independent complete-policy scorer: exact integers, no old score/oracle input."""
from pathlib import Path
import argparse,json,hashlib,zipfile,io,datetime,collections
import numpy as np,tifffile
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def write(p,v):
 with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,allow_nan=False)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def actual_matches(ref,pred,t):
 assert ref.shape==pred.shape and ref.ndim==pred.ndim==2
 assert ref.dtype.kind in 'ui' and pred.dtype.kind in 'ui'
 ri,rc=np.unique(ref[ref>0],return_counts=True);pi,pc=np.unique(pred[pred>0],return_counts=True)
 rarea=dict(zip(map(int,ri),map(int,rc)));parea=dict(zip(map(int,pi),map(int,pc)))
 sel=(ref>0)&(pred>0)
 pairs,counts=np.unique(np.column_stack((ref[sel],pred[sel])),axis=0,return_counts=True)
 forward={};reverse={}
 for (r,p),n in zip(pairs,counts):
  r,p,n=int(r),int(p),int(n);union=rarea[r]+parea[p]-n
  if 2*n>union:
   assert r not in forward and p not in reverse,'Strict-half disjoint matching unexpectedly ambiguous'
   forward[r]=p;reverse[p]=r
 return {(t,r):(t,p) for r,p in forward.items()},{'reference_objects':len(ri),'prediction_objects':len(pi),'matched_objects':len(forward),'eligible_correspondence_unique':True}
def observed_graph(images,lineage):
 labels=[set(map(int,np.unique(a[a>0]))) for a in images]
 nodes={(t,i) for t,s in enumerate(labels) for i in s}
 edges={(t,i,t+1,i,0) for t,s in enumerate(labels[:-1]) for i in s&labels[t+1]}
 missing=[];declared=set()
 for ident,start,end,parent in lineage:
  ident,start,end,parent=map(int,[ident,start,end,parent])
  assert ident>0 and ident not in declared and 0<=start<=end<len(images) and parent>=0 and parent!=ident
  declared.add(ident)
  if parent:
   e=(start-1,parent,start,ident,1)
   if (start-1,parent) in nodes and (start,ident) in nodes:edges.add(e)
   else:missing.append(list(e))
 return nodes,edges,missing
def main():
 p=argparse.ArgumentParser();p.add_argument('--resources',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
 cfg=read(args.resources);root=args.resources.resolve().parent;O=args.output;O.mkdir(exist_ok=False)
 archive=Path(cfg['archive_path']);assert sha(archive)==cfg['archive_sha256']
 pins={str(archive):cfg['archive_sha256']};manifests={};files={}
 # All prediction bytes frozen and verified before any reference decode.
 for arm in cfg['arms']:
  ap=root/arm['manifest_relative'];assert sha(ap)==arm['manifest_sha256'];pins[str(ap)]=sha(ap)
  mf=read(ap);records=mf['all_video_reports'];assert len(records)==29 and {r['video'] for r in records}=={f'{i:02d}' for i in range(1,30)}
  assert all(r['status']=='completed' for r in records) and sum(r['input_frames'] for r in records)==5340
  manifests[arm['arm']]={r['video']:r for r in records}
  for r in records:
   folder=Path(arm['native_root'])/r['video'];paths=sorted(folder.glob('mask*.tif'));assert len(paths)==r['input_frames']
   for path in paths+[folder/'res_track.txt']:
    h=sha(path);assert h==r['output_hashes'][path.name];pins[str(path)]=h
   files[arm['arm'],r['video']]=(paths,folder/'res_track.txt')
 write(O/'INPUTS_BEFORE_REFERENCE.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'resource_manifest_sha256':sha(args.resources),'inputs':pins,'three_arms_all29_frames_frozen':True})
 rows=[];pairs=[];coverage=collections.Counter()
 with zipfile.ZipFile(archive) as z:
  for film in [f'{i:02d}' for i in range(1,30)]:
   names=sorted(n for n in z.namelist() if n.startswith(f'CTC/test/{film}_GT/TRA/man_track') and n.endswith('.tif'))
   refs=[tifffile.imread(io.BytesIO(z.read(n))) for n in names]
   lineage=np.loadtxt(io.BytesIO(z.read(f'CTC/test/{film}_GT/TRA/man_track.txt')),dtype=int,ndmin=2)
   rn,re,missing=observed_graph(refs,lineage);assert not missing,'Unresolved reference endpoints'
   visible={};filmrows=[]
   for arm in ['baseline','max_area','all_components']:
    paths,lp=files[arm,film];assert len(paths)==len(refs)
    pred=[tifffile.imread(path) for path in paths];pl=np.loadtxt(lp,dtype=int,ndmin=2)
    pn,pe,pmissing=observed_graph(pred,pl);mapping={};framecov=[]
    for t,(ref,pr) in enumerate(zip(refs,pred)):
     m,c=actual_matches(ref,pr,t);mapping.update(m);framecov.append(c)
    inverse={p:r for r,p in mapping.items()};mapped=set()
    for t,a,u,b,k in pe:
     if (t,a) in inverse and (u,b) in inverse:
      r,s=inverse[t,a],inverse[u,b];mapped.add((r[0],r[1],s[0],s[1],k))
    v=re&mapped;visible[arm]=v
    row={'film':film,'arm':arm,'frames':len(refs),'reference_nodes':len(rn),'predicted_nodes':len(pn),'node_TP':len(mapping),'node_FN':len(rn)-len(mapping),'node_FP':len(pn)-len(mapping),'reference_edges':len(re),'predicted_edges':len(pe),'typed_TP':len(v),'typed_FN':len(re-v),'typed_FP':len(pe)-len(v),'missing_predicted_lineage_endpoints':pmissing,'determinate_reference_edge_evaluations':len(re),'ambiguous_reference_edge_evaluations':0,'exact_integer_matching_frames':len(framecov)}
    rows.append(row);filmrows.append(row);coverage[arm+'_frames']+=len(framecov);coverage[arm+'_determinate_edges']+=len(re)
   for arm in ['max_area','all_components']:
    gain=visible[arm]-visible['baseline'];loss=visible['baseline']-visible[arm]
    b=next(r for r in filmrows if r['arm']=='baseline');a=next(r for r in filmrows if r['arm']==arm)
    dt,df=a['typed_TP']-b['typed_TP'],a['typed_FP']-b['typed_FP']
    cat='measured-null' if dt==df==0 else 'beneficial' if dt>=0 and df<=0 else 'harmful' if dt<=0 and df>=0 else 'mixed'
    pair={'film':film,'arm':arm,'gains':len(gain),'losses':len(loss),'gain_edges':sorted(gain),'loss_edges':sorted(loss),'delta_typed_TP':dt,'delta_typed_FP':df,'category':cat,'both_gains_and_losses':bool(gain and loss),'any_visibility_change':bool(gain or loss)}
    pairs.append(pair)
   write(O/(film+'_results.json'),{'rows':filmrows,'paired':[r for r in pairs if r['film']==film]})
   print('RECONSTRUCTED_EXTERNAL',film,[(r['arm'],r['typed_TP'],r['typed_FP']) for r in filmrows],flush=True)
 summaries={}
 for arm in ['baseline','max_area','all_components']:
  rr=[r for r in rows if r['arm']==arm];pp=[r for r in pairs if r['arm']==arm]
  summaries[arm]={'chambers':len(rr),'totals':{k:sum(r[k] for r in rr) for k in ['frames','reference_edges','predicted_edges','typed_TP','typed_FN','typed_FP','determinate_reference_edge_evaluations','ambiguous_reference_edge_evaluations']},'gains':sum(p['gains'] for p in pp),'losses':sum(p['losses'] for p in pp),'categories':dict(collections.Counter(p['category'] for p in pp))}
 result={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'rows':rows,'paired':pairs,'summaries':summaries,'coverage':dict(coverage),'input_pins_sha256':sha(O/'INPUTS_BEFORE_REFERENCE.json'),'scope':'fresh independent integer-IoU/typed graph measurement from actual complete-policy masks; not new model forward, local A-D supports, biological validation or utility','source_code_sha256':sha(Path(__file__))}
 write(O/'RESULT.json',result);print(json.dumps(summaries),flush=True)
if __name__=='__main__':main()
