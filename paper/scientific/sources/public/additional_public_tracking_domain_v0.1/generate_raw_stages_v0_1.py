"""Untrained raw-only epithelial segmentation/association execution.

The curated reference arrays are deliberately never opened by this producer.
Algorithm and full cohort were frozen before image-array decoding.
"""
from pathlib import Path
import json, hashlib, datetime, time, traceback
import numpy as np
import scipy.ndimage as ndi
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist
from skimage.filters import threshold_otsu
from skimage.morphology import binary_closing, disk
from skimage.feature import peak_local_max
from skimage.segmentation import watershed, relabel_sequential
import tifffile

P=Path(__file__).parent
DESIGN=P/'RAW_EXPERIMENT_DESIGN_v0.1.json'
OUT=P/'actual_raw_stages_v0.1'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,obj):
 assert not p.exists(),str(p)
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def segment(frame):
 # C,Y,X or Y,X; all available channels participate without GT selection.
 if frame.ndim==2:frame=frame[None]
 channels=[]
 for channel in frame:
  lo,hi=np.percentile(channel.astype(np.float64),(1,99))
  channels.append(np.clip((channel-lo)/(hi-lo),0,1) if hi>lo else np.zeros(channel.shape))
 signal=ndi.gaussian_filter(np.mean(channels,axis=0),sigma=1)
 if np.ptp(signal)==0:return [np.zeros(signal.shape,dtype=np.uint32) for _ in range(4)]
 interior=~binary_closing(signal>threshold_otsu(signal),footprint=disk(1))
 s0=ndi.label(interior,structure=np.ones((3,3),int))[0].astype(np.uint32)
 sizes=np.bincount(s0.ravel()); keep=sizes>=64;keep[0]=False
 s1=relabel_sequential(np.where(keep[s0],s0,0))[0].astype(np.uint32)
 distance=ndi.distance_transform_edt(s1>0)
 peaks=peak_local_max(distance,min_distance=5,exclude_border=False,labels=s1)
 seeds=np.zeros(s1.shape,dtype=np.int32)
 for k,(y,x) in enumerate(peaks,1):seeds[y,x]=k
 next_seed=len(peaks)+1
 for lab in np.unique(s1):
  if lab and not np.any(seeds[s1==lab]):
   y,x=np.unravel_index(np.argmax(np.where(s1==lab,distance,-1)),s1.shape)
   seeds[y,x]=next_seed;next_seed+=1
 s2=watershed(-distance,markers=seeds,mask=s1>0).astype(np.uint32)
 border=np.unique(np.concatenate([s2[0],s2[-1],s2[:,0],s2[:,-1]]))
 s3=relabel_sequential(np.where(np.isin(s2,border),0,s2))[0].astype(np.uint32)
 return [s0,s1,s2,s3]
def graph(stack):
 nodes=[]; by_frame=[]
 for t,mask in enumerate(stack):
  labs=np.unique(mask);labs=labs[labs>0]
  if len(labs)>1000:return {'status':'WITHHELD_OBJECT_CAP','frame':t,'objects':len(labs),'nodes':None,'edges':None}
  centers=ndi.center_of_mass(np.ones(mask.shape),mask,labs)
  row=[]
  for lab,(y,x) in zip(labs,centers):
   n={'id':int(t*100000+lab),'frame':t,'label':int(lab),'y':float(y),'x':float(x)}
   nodes.append(n);row.append(n)
  by_frame.append(row)
 edges=[];windows=[]
 for t,(prev,cur) in enumerate(zip(by_frame,by_frame[1:]),1):
  n,m=len(prev),len(cur)
  selected=[]
  if n and m:
   dist=cdist([[p['y'],p['x']] for p in prev],[[p['y'],p['x']] for p in cur])
   penalty=(n+m+1)*26.
   cost=np.full((n+m,n+m),penalty)
   cost[n:,m:]=0
   cost[:n,:m]=np.where(dist<=25,dist,penalty*4*(n+m+1))
   ri,ci=linear_sum_assignment(cost)
   for i,j in zip(ri,ci):
    if i<n and j<m and dist[i,j]<=25:
     edges.append([prev[i]['id'],cur[j]['id']])
     selected.append({'previous_label':prev[i]['label'],'current_label':cur[j]['label'],'distance_pixels':float(dist[i,j])})
  windows.append({'current_frame':t,'previous_objects':n,'current_objects':m,'links':selected})
 return {'status':'COMPLETE_UNTYPED_CONTINUATION_GRAPH','nodes':nodes,'edges':edges,'windows':windows}
def main():
 assert not OUT.exists(),'Never overwrite prior execution.'
 OUT.mkdir()
 started=time.monotonic();design=json.loads(DESIGN.read_text(encoding='utf-8'))
 save(OUT/'RUN_START.json',{'utc':utc(),'design_sha256':sha(DESIGN),'producer_sha256':sha(Path(__file__)),'reference_arrays_opened':False})
 summary=[]
 for movie in ['movie1','movie2','movie3','movie4']:
  record=next(r for r in design['records'] if r['movie']==movie and r['role']=='raw')
  path=Path(record['local_path']);assert sha(path)==record['sha256']
  with tifffile.TiffFile(path) as f:
   axes=f.series[0].axes;raw=f.series[0].asarray()
  if axes=='TYX':frames=raw
  elif axes=='TCYX':frames=raw
  elif axes=='CYX':frames=raw[None]
  else:raise ValueError('Unsupported frozen raw axes '+axes)
  stages=[[] for _ in range(4)]
  for frame in frames:
   for j,mask in enumerate(segment(frame)):stages[j].append(mask)
  entry={'movie':movie,'time_frames':len(frames),'source_axes':axes,'raw_sha256':record['sha256'],'structurally_tracking_eligible':len(frames)>=3,'stages':[]}
  for j,sequence in enumerate(stages):
   stack=np.stack(sequence)
   mask_path=OUT/movie/('S'+str(j)+'_labels.tif');mask_path.parent.mkdir(exist_ok=True)
   tifffile.imwrite(mask_path,stack,metadata={'axes':'TYX'},compression='zlib')
   g=graph(stack);gp=mask_path.with_name('S'+str(j)+'_graph.json');save(gp,g)
   entry['stages'].append({'view':'S'+str(j),'mask_file':str(mask_path.relative_to(OUT)),'mask_sha256':sha(mask_path),'graph_file':str(gp.relative_to(OUT)),'graph_sha256':sha(gp),'status':g['status'],'nodes':len(g['nodes']) if g['nodes'] is not None else None,'edges':len(g['edges']) if g['edges'] is not None else None})
  summary.append(entry)
  print(json.dumps({'movie':movie,'frames':len(frames),'stages':[(s['view'],s['nodes'],s['edges'],s['status']) for s in entry['stages']]}),flush=True)
 save(OUT/'COHORT_SUMMARY.json',{'utc':utc(),'movies':summary,'reference_arrays_opened':False})
 files=[{'path':str(p.relative_to(OUT)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(OUT.rglob('*')) if p.is_file()]
 save(OUT/'OUTPUT_FREEZE.json',{'utc':utc(),'status':'ACTUAL_RAW_ONLY_ALL4_STAGES_FROZEN_BEFORE_REFERENCE_MEASUREMENT','design_sha256':sha(DESIGN),'reference_arrays_opened':False,'files':files})
 save(OUT/'RUN_COMPLETE.json',{'utc':utc(),'status':'RAW_STAGE_GENERATION_COMPLETE_NOT_SCIENTIFIC_ACCEPTANCE','elapsed_seconds':time.monotonic()-started,'output_freeze_sha256':sha(OUT/'OUTPUT_FREEZE.json'),'reference_arrays_opened':False})
if __name__=='__main__':
 try:main()
 except Exception as e:
  if OUT.exists() and not (OUT/'RUN_FAILURE.json').exists():save(OUT/'RUN_FAILURE.json',{'utc':utc(),'error':repr(e),'traceback':traceback.format_exc(),'partial_outputs_preserved':True})
  raise
