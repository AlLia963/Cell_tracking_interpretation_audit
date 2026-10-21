"""CPU raw-format adapters. No model, GT, production admission or cohort runner.
Functions operate one authorized film at a time; fixture runner alone is enabled.
"""
import collections,hashlib,io,json,pickle,re,zipfile
from pathlib import Path
import numpy as np
import tifffile

def require(x,msg):
 if not x: raise ValueError(msg)
def canon(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha_bytes(b):return hashlib.sha256(b).hexdigest()
def sha_file(p):return sha_bytes(Path(p).read_bytes())
def write_json(p,x):
 with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,indent=2,allow_nan=False)
STATE=('cells','all_indices','div_track','prevcells','track_indices','object_indices','div_indices')
STAGES=('resized_probabilities','winner_threshold_binary','component_retained_binary')
NATIVE49={'entry_boxes','entry_num_TQs','runtime_threshold','runtime_mask_threshold'}|{'entry_'+k for k in STATE}|{s for s in STAGES}|{s+'_'+k for s in STAGES for k in STATE}|{s+'_'+k for s in STAGES for k in ('num_TQs','boxes')}|{'return_'+k for k in STATE if k!='prevcells'}|{'return_masks','return_boxes'}
CONSUMERS=('consumer_stack','consumer_effective_content','consumer_reference_points')
DIRECT=('before_model','raw_model_output','postprocess_M_G','consumer_applicability')+CONSUMERS
class NoneLoader(pickle.Unpickler):
 def find_class(self,m,n):
  if (m,n) in [('numpy','ndarray'),('numpy','dtype')]:return getattr(np,n)
  if m in ('numpy.core.multiarray','numpy._core.multiarray') and n=='_reconstruct':return np.core.multiarray._reconstruct
  raise ValueError('Unapproved pickle global')
def read_arrays(path,native=False):
 # Native writer uses np.asarray(None). Only scalar object None is allowed.
 result={}
 with zipfile.ZipFile(path) as z:
  require(len(z.namelist())==len(set(z.namelist())),'Duplicate NPZ members')
  for name in z.namelist():
   require(name.endswith('.npy'),'Unexpected NPZ member')
   b=io.BytesIO(z.read(name));version=np.lib.format.read_magic(b)
   require(version in ((1,0),(2,0)),'NPY header version unsupported')
   shape,fortran,dtype=(np.lib.format.read_array_header_1_0 if version==(1,0) else np.lib.format.read_array_header_2_0)(b)
   if dtype.hasobject:
    require(native and shape==() and dtype==np.dtype('O'),'Only native scalar None permits object encoding')
    a=NoneLoader(b).load();require(isinstance(a,np.ndarray) and a.shape==() and a.item() is None,'Object value is not None')
   else:
    b.seek(0);a=np.lib.format.read_array(b,allow_pickle=False)
   result[name[:-4]]=a
 return result

def array_token(a):
 if a.dtype.hasobject:
  require(a.shape==() and a.item() is None,'Object not scalar None');return {'dtype':'object','shape':[],'value':'None'}
 require(a.dtype.fields is None,'Structured arrays unsupported')
 return {'dtype':a.dtype.str,'shape':list(a.shape),'C_value_sha256':sha_bytes(a.tobytes(order='C'))}

def canonical_topology(topology,exclude_arm=False):
 require('root' in topology,'Missing topology root')
 t={p:dict(v) for p,v in topology.items()}
 # Key insertion order is not a dict semantic; sequence order remains semantic.
 for p,v in t.items():
  if v['type']=='dict':
   keys=v['keys'];require(len(keys)==len(set(keys)),'Duplicate topology keys');v['keys']=sorted(keys)
   require(all(p+'/'+k in t for k in keys),'Missing child topology')
  if v['type'] in ('list','tuple'):require(all(p+'/'+str(i) in t for i in range(v['length'])),'Missing sequence child')
 if exclude_arm:
  require(t.get('root/arm',{}).get('type')=='str','Expected arm routing token')
  t.pop('root/arm');t['root']['keys'].remove('arm')
 return t

def packet(path,expected_frame,expected_kind,expected_ordinal):
 p=Path(path);m=json.loads(p.with_suffix('.json').read_text(encoding='utf-8'));a=read_arrays(p)
 require((m['frame'],m['kind'],m['ordinal'])==(expected_frame,expected_kind,expected_ordinal),'Packet identity mismatch')
 topology=canonical_topology(m['topology'],expected_kind=='postprocess_M_G')
 required={'before_model':{'targets','samples','mapping','runtime'},'raw_model_output':{'pred_logits','pred_boxes','pred_masks','hs_embed'},'postprocess_M_G':{'M','G','cells','all_indices','active'},'consumer_stack':{'prev_boxes','prev_hs_embed','output_target'},'consumer_effective_content':{'prev_tgt','output_target'},'consumer_reference_points':{'reference_points','num_track_queries','output_target'},'consumer_applicability':{'captured','anchors_present','original_consumer_returned','scope'}}
 require(set(topology['root'].get('keys',[]))==required[expected_kind],'Actual kind field schema')
 need={k for k,v in topology.items() if v['type'] in ('tensor','numpy')}
 require(set(a)==need,'Packet array topology mismatch')
 for k,v in a.items():
  node=topology[k];require(list(v.shape)==node['shape'],'Packet shape mismatch')
  dtype=str(v.dtype);decl=node['dtype'].removeprefix('torch.')
  require(dtype==decl,'Packet dtype mismatch')
 payload={'topology':topology,'arrays':{k:array_token(v) for k,v in sorted(a.items())}}
 return {'semantic_sha256':sha_bytes(canon(payload)),'semantic':payload,'raw_bindings':{p.name:sha_file(p),p.with_suffix('.json').name:sha_file(p.with_suffix('.json'))},'raw_metadata':m}

def ctc_prediction_film(native,nframes,destination):
 native=Path(native);destination=Path(destination);destination.mkdir(exist_ok=False)
 rows={};lineage=native/'res_track.txt'
 lineage_sha=sha_file(lineage)
 for line in lineage.read_text(encoding='utf-8-sig').splitlines():
  if not line.strip():continue
  tokens=line.split();require(len(tokens)==4 and all(re.fullmatch(r'\d+',x) for x in tokens),'CTC integer row schema')
  i,s,e,p=map(int,tokens);require(i>0 and i not in rows and 0<=s<=e<nframes and p!=i,'CTC ID/interval invalid');rows[i]=(s,e,p)
 children={}
 for i,(s,e,p) in rows.items():
  if p:
   require(p in rows and rows[p][1]+1==s,'Parent must exist and end immediately before daughter')
   children.setdefault(p,[]).append(i)
 require(all(len(v)==2 for v in children.values()),'Source binary CTC division contract not met')
 expected={f'mask{t:03d}.tif' for t in range(nframes)}
 require({p.name for p in native.glob('mask*.tif')}==expected,'Exact final mask inventory')
 arrays={};seen={};bindings={lineage.name:lineage_sha};shape=None
 for t in range(nframes):
  p=native/f'mask{t:03d}.tif';mask_sha=sha_file(p);a=tifffile.imread(p)
  require(a.ndim==2 and a.dtype.kind in 'ui' and (a>=0).all(),'2D nonnegative integer labels required')
  require(shape is None or shape==a.shape,'Spatial domain drift');shape=a.shape
  labels=set(int(x) for x in np.unique(a) if x);require(labels<=set(rows),'Pixel ID absent from lineage')
  for i in labels:seen.setdefault(i,[]).append(t)
  arrays[f'frame_{t:04d}']=a;bindings[p.name]=mask_sha
 require(set(seen)==set(rows),'Lineage ID without pixel support')
 require(all(seen[i]==list(range(s,e+1)) for i,(s,e,p) in rows.items()),'Pixel occurrence does not match full lineage interval')
 edges=[]
 for i,(s,e,p) in rows.items():
  edges.extend([t,i,t+1,i,0] for t in range(s,e))
  if p:edges.append([s-1,p,s,i,1])
 edges.sort();arrays['typed_edges']=np.asarray(edges,dtype=np.int64).reshape(-1,5)
 archive=destination/'prediction.npz'
 with archive.open('xb') as f:np.savez_compressed(f,**arrays)
 index={'format':'perfilm_prediction_v1','frames':nframes,'shape':list(shape),'original_ctc_ids':True,'typed_kind':{'0':'continuation','1':'division_daughter'},'frame_keys':[f'frame_{t:04d}' for t in range(nframes)],'archive_sha256':sha_file(archive),'source_bindings':bindings,'array_semantics':{k:array_token(v) for k,v in arrays.items()},'units':'one computational film, no biological N'}
 write_json(destination/'prediction_index.json',index);return index

def iter_normalized_frames(destination):
 # Current comparator bridge may materialize ONE film, never four whole cohorts.
 d=Path(destination);index=json.loads((d/'prediction_index.json').read_text(encoding='utf-8-sig'));require(sha_file(d/'prediction.npz')==index['archive_sha256'],'Prediction archive binding')
 with np.load(d/'prediction.npz',allow_pickle=False) as z:
  for t,k in enumerate(index['frame_keys']):yield {'t':t,'labels':z[k].tolist()}
def comparator_movie(destination):
 d=Path(destination)
 with np.load(d/'prediction.npz',allow_pickle=False) as z:edges=z['typed_edges'].tolist()
 return {'frames':list(iter_normalized_frames(d)),'typed_edges':edges}

def normalize_events(native,nframes,destination):
 native=Path(native);trace=native/'direct_trace';ops=native/'operator_states';destination=Path(destination);destination.mkdir(exist_ok=False)
 inventory=json.loads((trace/'inventory.json').read_text(encoding='utf-8-sig'))
 if isinstance(inventory,dict):inventory=inventory['records']
 keys=set();records=[];by={};bindings={}
 for r in inventory:
  t,k,o=r['frame'],r['kind'],r['ordinal'];require(type(t) is int and 0<=t<nframes and k in DIRECT and type(o) is int and o>=0,'Actual packet inventory domain')
  require((t,k,o) not in keys,'Duplicate packet ordinal');keys.add((t,k,o))
  names=r['files'];require(set(names)=={f'{t:04d}_{k}_{o:02d}.npz',f'{t:04d}_{k}_{o:02d}.json'},'Packet names mismatch')
  for name,h in names.items():require(sha_file(trace/name)==h,'Packet source binding');bindings[str(Path('direct_trace')/name)]=h
  data=packet(trace/f'{t:04d}_{k}_{o:02d}.npz',t,k,o);by[t,k,o]=data
  if k!='consumer_applicability':records.append({'t':t,'kind':k,'ordinal':o,'applicability':'applicable','fields':data['semantic']})
 actual_names={p.name for p in trace.iterdir() if re.fullmatch(r'\d{4}_.+_\d{2}\.(npz|json)',p.name)}
 require(actual_names=={name for r in inventory for name in r['files']},'Unindexed or missing direct packet')
 for t in range(nframes):
  for k in DIRECT:
   ords=sorted(o for tt,kk,o in keys if tt==t and kk==k)
   require(ords==list(range(len(ords))),'Noncontiguous event ordinal')
  for k in ('before_model','raw_model_output','consumer_applicability'):require((t,k,0) in by and sum(tt==t and kk==k for tt,kk,o in keys)==1,'Required actual before/raw/applicability exactly once')
  top=by[t,'consumer_applicability',0]['raw_metadata']['topology']
  require(top['root/anchors_present']['value'] is True and top['root/original_consumer_returned']['value'] is True,'Actual consumer failed or source anchors unavailable')
  count=top['root/captured']['length'];captured=[top[f'root/captured/{i}']['value'] for i in range(count)]
  require(set(captured)<=set(CONSUMERS),'Consumer capture list invalid')
  require(collections.Counter(captured)==collections.Counter(kk for tt,kk,o in keys if tt==t and kk in CONSUMERS),'Consumer ordinal counts conflict with actual applicability')
  for k in CONSUMERS:
   present=any(tt==t and kk==k for tt,kk,o in keys);require(present==(k in captured),'Captured applicability conflicts with actual packets')
   if not present:records.append({'t':t,'kind':k,'ordinal':0,'applicability':'not_applicable','fields':{'evidence':'actual consumer_applicability packet: anchor not captured; original consumer returned'}})
 protocol=json.loads((ops/'observer_protocol.json').read_text(encoding='utf-8-sig'));states={r['frame']:r for r in protocol['records']};require(len(states)==len(protocol['records']),'Duplicate native state')
 journal=[json.loads(s) for s in (ops/'frame_journal.jsonl').read_text(encoding='utf-8-sig').splitlines() if s.strip()]
 require(not any(r['event'].endswith('failed') for r in journal),'Failure journal retained and invalid')
 complete={}
 for r in journal:
  if r['event']=='frame_complete':require(r['frame'] not in complete,'Duplicate frame completion');complete[r['frame']]=r
 require(set(complete)==set(range(nframes)),'Complete journal domain')
 require(set(states)=={t for t,r in complete.items() if r['operator_applicable']},'Native applicability inventory mismatch')
 require({p.name for p in ops.glob('frame*.npz')}=={f'frame{t:03d}.npz' for t in states},'Unindexed/missing native state')
 for t,r in complete.items():
  require(r['mask_saved'] is True,'Mask not saved')
  if r['operator_applicable']:
   p=ops/f'frame{t:03d}.npz';require(sha_file(p)==states[t]['state_sha256'],'Native state binding');a=read_arrays(p,True);require(set(a)==NATIVE49,'Native49 field inventory')
   records.append({'t':t,'kind':'native_operator','ordinal':0,'applicability':'applicable','fields':{k:array_token(v) for k,v in sorted(a.items())}});bindings[str(Path('operator_states')/p.name)]=sha_file(p)
   require(any(tt==t and kk=='postprocess_M_G' for tt,kk,o in keys),'Required postprocess return packet')
  else:
   require(not any(tt==t and kk=='postprocess_M_G' for tt,kk,o in keys),'Unexpected postprocess packet in nonoperator frame')
   for k in ('native_operator','postprocess_M_G'):records.append({'t':t,'kind':k,'ordinal':0,'applicability':'not_applicable','fields':{'evidence':'actual frame_complete: operator_applicable false'}})
  bindings[f'mask{t:03d}.tif']=sha_file(native/f'mask{t:03d}.tif')
  a=tifffile.imread(native/f'mask{t:03d}.tif');require(a.ndim==2 and a.dtype.kind in 'ui','Serialized mask schema')
  records.append({'t':t,'kind':'frame_serialization','ordinal':0,'applicability':'applicable','fields':array_token(a)})
 for p in (trace/'inventory.json',ops/'observer_protocol.json',ops/'frame_journal.jsonl',trace/'consumer_source_binding.json'):
  bindings[str(p.relative_to(native))]=sha_file(p)
 # Keep metadata provenance separately, not decision features. No container hash in HIST semantics.
 records.sort(key=lambda r:(r['t'],('before_model','consumer_stack','consumer_effective_content','consumer_reference_points','raw_model_output','native_operator','postprocess_M_G','frame_serialization').index(r['kind']),r['ordinal']))
 with (destination/'events.jsonl').open('x',encoding='utf-8') as f:
  for r in records:f.write(json.dumps(r,sort_keys=True,allow_nan=False)+'\n')
 result={'frames':nframes,'records':len(records),'source_bindings':bindings,'auxiliary_consumer_applicability':[{'t':t,'semantic':by[t,'consumer_applicability',0]['semantic']} for t in range(nframes)],'cross_arm_exclusion':['postprocess_M_G root/arm only; retained in raw bound JSON'],'no_GT':True,'native_operator_source_sha256':protocol['operator_source_sha256'],'actual_consumer_source_binding':json.loads((trace/'consumer_source_binding.json').read_text(encoding='utf-8-sig'))}
 write_json(destination/'events_index.json',result);return result

if __name__=='__main__':raise SystemExit('Production normalization not authorized/implemented as a CLI. Use separately reviewed cohort admission orchestrator; fixtures use functions only.')



