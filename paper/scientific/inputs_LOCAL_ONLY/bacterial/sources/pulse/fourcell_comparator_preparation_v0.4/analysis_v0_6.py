"""Bounded result-layer preparation v03. No model/GT import.

Raw TIFF/CTC/direct-trace adapters and independent admission-passport production
are NOT IMPLEMENTED here. Kernels consume explicitly normalized frozen JSON.
"""
from pathlib import Path
import collections,hashlib,itertools,json,math
CELLS=('WW','AW','WA','AA')
FILMS=[f'{i:02d}' for i in range(1,30)]
KINDS=('before_model','consumer_stack','consumer_effective_content','consumer_reference_points','raw_model_output','native_operator','postprocess_M_G','frame_serialization')
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
def digest(x):return hashlib.sha256(canonical(x)).hexdigest()
def read_bound(path,want):
 raw=Path(path).read_bytes()
 if hashlib.sha256(raw).hexdigest()!=want:raise ValueError('Bound file mismatch '+str(path))
 return json.loads(raw)
def ensure(condition,message):
 if not condition:raise ValueError(message)
def endpoint_score(pred,reference):
 pn,pe,pp,ps=nodes_and_edges(pred);rn,re,rp,rs=nodes_and_edges(reference)
 ensure(len(pred['frames'])==len(reference['frames']) and ps==rs,'Same reference/frame spatial domain required')
 mapping={};reverse={};fractions=[]
 for r,rset in sorted(rp.items()):
  for p,pset in sorted(pp.items()):
   if r[0]!=p[0]:continue
   inter=len(rset&pset);union=len(rset|pset)
   if 2*inter>union:
    ensure(r not in mapping and p not in reverse,'Strict-IoU match uniqueness failure')
    mapping[r]=p;reverse[p]=r;fractions.append([*r,p[1],inter,union])
 visible=set();rawvisible=set();fp=set();rawfp=set();rawref={e[:4] for e in re}
 for e in pe:
  t,a,u,b,k=e;ra=reverse.get((t,a));rb=reverse.get((u,b));mapped=None if ra is None or rb is None else (*ra,*rb)
  if mapped in rawref:rawvisible.add(mapped)
  else:rawfp.add(e)
  if mapped is not None and (*mapped,k) in re:visible.add((*mapped,k))
  else:fp.add(e)
 metrics={'node_TP':len(mapping),'node_FN':len(rn)-len(mapping),'node_FP':len(pn)-len(mapping),'reference_edges':len(re),'predicted_edges':len(pe),'typed_TP':len(visible),'typed_FN':len(re)-len(visible),'typed_FP':len(fp),'untyped_TP':len(rawvisible),'untyped_FN':len(rawref)-len(rawvisible),'untyped_FP':len(rawfp)}
 for k,name in ((0,'continuation'),(1,'division_daughter')):
  rr={e for e in re if e[4]==k};pr={e for e in pe if e[4]==k};vv={e for e in visible if e[4]==k}
  metrics.update({name+'_reference':len(rr),name+'_predicted':len(pr),name+'_TP':len(vv),name+'_FN':len(rr)-len(vv),name+'_FP':len(pr)-len(vv)})
 return {'metrics':metrics,'visible':visible,'reference_edges':re,'matching_fractions':fractions}
def edge_domain(edge,tau,nframes):
 ensure(tau is None or type(tau) is int and 0<=tau<nframes,'Tau None or in-range integer only')
 t,a,u,b,k=edge;ensure(u==t+1,'Unsupported time schema')
 if tau is None:return 'no_trigger'
 if t==tau or u==tau:return 'incident'
 if t<tau and u<tau:return 'pre'
 if t>tau and u>tau:return 'beyond'
 raise ValueError('Unassigned edge domain')
def direction(tp,fp):
 if tp==fp==0:return 'measured-null'
 if tp>=0 and fp<=0:return 'beneficial'
 if tp<=0 and fp>=0:return 'harmful'
 return 'mixed'
def _endpoint_impl(film,tau,predictions,reference):
 ensure(set(predictions)==set(CELLS),'Four same-information outputs required')
 scores={c:endpoint_score(predictions[c],reference) for c in CELLS};n=len(reference['frames'])
 ensure(tau is None or type(tau) is int and 0<=tau<n,'Invalid tau')
 edges=sorted(scores['WW']['reference_edges']);rows=[]
 domains={d:{'pattern_histogram':{''.join(map(str,b)):0 for b in itertools.product((0,1),repeat=4)},'H_histogram':{str(h):0 for h in range(-2,3)},'reference_edges':0} for d in ('pre','incident','beyond','no_trigger')}
 for edge in edges:
  bits=[int(edge in scores[c]['visible']) for c in CELLS];h=bits[3]-bits[1]-bits[2]+bits[0];domain=edge_domain(edge,tau,n)
  rows.append({'reference_key':[film,*edge],'domain':domain,'Y':bits,'H':h,'endpoint_pattern':''.join(map(str,bits))})
  domains[domain]['reference_edges']+=1;domains[domain]['pattern_histogram'][''.join(map(str,bits))]+=1;domains[domain]['H_histogram'][str(h)]+=1
 contrasts={}
 for c in CELLS[1:]:
  gains=scores[c]['visible']-scores['WW']['visible'];losses=scores['WW']['visible']-scores[c]['visible'];m=scores[c]['metrics'];b=scores['WW']['metrics'];dtp=m['typed_TP']-b['typed_TP'];dfp=m['typed_FP']-b['typed_FP']
  ensure(dtp==len(gains)-len(losses),'Gross/net identity consistency')
  contrasts[c]={'delta_TP':dtp,'delta_FP':dfp,'direction':direction(dtp,dfp),'gains':[list(e) for e in sorted(gains)],'losses':[list(e) for e in sorted(losses)],'by_domain':{d:{'gains':sum(edge_domain(e,tau,n)==d for e in gains),'losses':sum(edge_domain(e,tau,n)==d for e in losses)} for d in domains}}
 return {'film':film,'tau':tau,'frames':n,'cell_order':list(CELLS),'metrics':{c:s['metrics'] for c,s in scores.items()},'matching_fractions':{c:s['matching_fractions'] for c,s in scores.items()},'edge_rows':rows,'domains':domains,'contrasts':contrasts,'empty_reference_edge_domain':not edges,'future_censored':tau is not None and tau==n-1,'H_is_internal_operator_coupling':False}


def load_fixed_frames_contract():
 path=Path(__file__).resolve().parent/'frames_contract.json'
 raw=path.read_bytes();contract=json.loads(raw);fixed=Path(__file__).resolve().parent.parent.parent/'external_end_to_end_feasibility_v0.1/raw_all29_manifest.json'
 ensure(Path(contract['raw_manifest_path']).resolve()==fixed.resolve(),'Fixed raw metadata path')
 raw_metadata=fixed.read_bytes()
 ensure(hashlib.sha256(raw_metadata).hexdigest()==contract['raw_manifest_sha256']=='9b391b416a88d2bb85d4bcc9a72ad9dd5581719f6bc3077b505ec17b705607ff','Original raw manifest metadata binding')
 counts=contract['frames_by_film'];ensure(sorted(counts)==FILMS and all(type(n) is int and n>0 for n in counts.values()) and sum(counts.values())==contract['total_frames']==5340,'Fixed complete29/5340 counts')
 metadata=json.loads(raw_metadata);domains={f:[] for f in FILMS}
 for key in metadata['input_sha256']:
  pieces=key.split('/');ensure(len(pieces)==4 and pieces[:2]==['CTC','test'] and pieces[2] in domains and pieces[3].startswith('t') and pieces[3].endswith('.tif'),'Raw frame path schema')
  domains[pieces[2]].append(int(pieces[3][1:-4]))
 ensure(all(sorted(domains[f])==list(range(counts[f])) for f in FILMS),'Counts agree with actual bound raw metadata keys')
 return counts,hashlib.sha256(raw).hexdigest()


def _mechanism_impl(control_summary,hist,endpoint):
 if control_summary.get('controls_independent_valid') is not True or hist['status']!='valid_normalized_history':return 'invalid_withhold'
 if endpoint['tau'] is None:
  return 'no_trigger_control_equal' if all(x['status']=='equal' for x in hist['pairs']) and all(all(y==r['Y'][0] for y in r['Y']) for r in endpoint['edge_rows']) else 'invalid_no_trigger_parity'
 if control_summary.get('prefix_treatment_consumer_PASS') is not True:return 'invalid_treatment_conformance'
 if endpoint['future_censored']:return 'future_not_evaluable_last_frame'
 futures=control_summary.get('future_factorization_pairs')
 if futures is None:return 'not_implemented_actual_future_trace_assessment'
 ensure(set(futures)=={'AW_vs_WW','WA_vs_AA'},'Both prespecified factor pairs required')
 if any(v.get('status')!='evaluated' for v in futures.values()):return 'not_evaluable_future'
 if any(v['actual_input_equal'] is not True or v['raw_model_output_equal'] is not True for v in futures.values()):return 'sole_Q_path_falsification_candidate_not_unique_cause'
 if any(v['downstream_semantic_equal'] is not True for v in futures.values()):return 'downstream_or_serialization_path_candidate'
 if any(r['domain']=='beyond' and (r['Y'][1]!=r['Y'][0] or r['Y'][2]!=r['Y'][3]) for r in endpoint['edge_rows']):return 'invalid_endpoint_domain_oracle_inconsistency'
 return 'bounded_factorization_with_endpoint_interaction' if any(r['H']!=0 for r in endpoint['edge_rows']) else 'bounded_factorization'

"""New definitions assembled into standalone analysis_v0_5.py; not a runtime patch."""
import struct,re

GRAPH_SCHEMA='persistent_ctc_track_id_v1'
HISTORY_SCHEMA='source03_complete_history_v1_PENDING_ADAPTER'
TARGET_SCHEMA='fourcell_EP_HIST_typed_targets_v1'
KINDS=('before_model','consumer_stack','consumer_effective_content','consumer_reference_points','raw_model_output','consumer_applicability','native_operator','postprocess_M_G','frame_serialization')
SOURCE_ROOT=Path(__file__).resolve().parent.parent/'source_preparation_v0.3'
SCHEDULE_SHA='4f4d5d48295116efa4389fc4edb0b1d225ff79d26a7f684f8aa125c8b191ee22'
SOURCE_PINS={
 'fixed_schedule.json':SCHEDULE_SHA,
 'direct_input_observer_v0_1.py':'17b81e62f4a766cc2e059966ebe84d70e16da13ecb49f16e2df05c3a92250a35',
 'source/src/trackformer/engine.py':'0049d7c5ee0831a87eabe4cca65f6dc8b9e578cb9db19ded057e48bf4bd903b0',
 'native_stage_observer_v04_copy.py':'fc9371ea6370e4c01b91c76114bcc0405864fb5c157d1353e1213bf3eacb884b',
 'source/src/trackformer/models/deformable_transformer.py':'1dbb6ad25f8cfc9ff6227c91a9dbdd97f0df00b77a47f8b3997afd0f80bc5fda',
 'source/src/trackformer/models/detr_tracking.py':'19121f59f636fc29767cf03502cc1dedb9bd66b773512aed3c3cf890ef1a1de6',
 'source/src/trackformer/models/deformable_detr.py':'34c9c8d4f858d98be6c2c2595a5a9868897e1eedc9dc84854e5f13e5701175dc',
 'source/src/trackformer/models/detr_segmentation.py':'121343a15a5a9d12913be563759acde25c0365f9e3f6887e7474fdb74476a122'}
FIELDS={
 'before_model':{'targets','samples','mapping','runtime'},
 'consumer_stack':{'prev_boxes','prev_hs_embed','output_target'},
 'consumer_effective_content':{'prev_tgt','output_target'},
 'consumer_reference_points':{'reference_points','num_track_queries','output_target'},
 'raw_model_output':{'pred_logits','pred_boxes','pred_masks','hs_embed'},
 'consumer_applicability':{'captured','anchors_present','original_consumer_returned','scope'},
 'postprocess_M_G':{'M','G','cells','all_indices','arm','active'},
 'frame_serialization':{'labels'},
}
NATIVE_FIELDS={'entry_boxes','entry_num_TQs','runtime_threshold','runtime_mask_threshold'}
NATIVE_FIELDS|={'entry_'+k for k in ('cells','all_indices','div_track','prevcells','track_indices','object_indices','div_indices')}
for _stage in ('resized_probabilities','winner_threshold_binary','component_retained_binary'):
 NATIVE_FIELDS|={_stage,_stage+'_num_TQs',_stage+'_boxes'}|{_stage+'_'+k for k in ('cells','all_indices','div_track','prevcells','track_indices','object_indices','div_indices')}
NATIVE_FIELDS|={'return_'+k for k in ('cells','all_indices','div_track','track_indices','object_indices','div_indices','masks','boxes')}
FIELDS['native_operator']=NATIVE_FIELDS
ensure(len(NATIVE_FIELDS)==49,'Source03 native field-domain construction')

_ARRAY_ATTESTATION=object()
class VerifiedArrayDigest:
 """Ephemeral capability generated from actual decoded bytes, not JSON claims.

 Callers still need independently consumed file bindings; this is not authority.
 No array retained, payload_hex persisted, or caller-supplied finite flag trusted.
 """
 __slots__=('dtype','shape','sha256')
 def __init__(self,dtype,shape,sha256,attestation):
  ensure(attestation is _ARRAY_ATTESTATION,'Use verified_array_digest on actual arrays')
  object.__setattr__(self,'dtype',dtype);object.__setattr__(self,'shape',tuple(shape));object.__setattr__(self,'sha256',sha256)
 def __setattr__(self,name,value):raise TypeError('Verified token is immutable')

def verified_array_digest(array,expected_token=None):
 """Actual one-array finite/schema/bytes validation; compact normalized storage
 is rehydrated by a reviewed reader calling this function on actual values.
 """
 import numpy as np
 a=np.asarray(array)
 if a.dtype.hasobject:
  ensure(a.dtype==np.dtype('O') and a.shape==() and a.item() is None,'Actual native object array must be scalar None')
  if expected_token is not None:
   ensure(type(expected_token) is dict and set(expected_token)=={'dtype','shape','None_only'} and expected_token['dtype']=='|O' and type(expected_token['shape']) is list and expected_token['shape']==[] and expected_token['None_only'] is True,'Actual scalar None compact token schema/value/shape mismatch')
  return array_payload(a)
 ensure(a.dtype.fields is None and a.dtype.kind in 'biuf' and bool(np.isfinite(a).all()),'Actual finite numeric array domain')
 dt=a.dtype.str;shape=list(a.shape);sha=hashlib.sha256(a.tobytes(order='C')).hexdigest()
 if expected_token is not None:
  ensure(type(expected_token) is dict and set(expected_token)=={'dtype','shape','C_value_sha256'},'Compact token exact inventory; finite is checked from actual bytes')
  ensure(expected_token['dtype']==dt and typed_digest(expected_token['shape'])==typed_digest(shape) and expected_token['C_value_sha256']==sha,'Actual bytes vs stored token mismatch')
 return VerifiedArrayDigest(dt,shape,sha,_ARRAY_ATTESTATION)

def typed(x):
 """JSON-safe canonical type tree; scalar signed zero and field presence survive."""
 if isinstance(x,VerifiedArrayDigest):return ['array',x.dtype,list(x.shape),x.sha256]
 if x is None:return ['None']
 if type(x) is bool:return ['bool',x]
 if type(x) is int:return ['int',str(x)]
 if type(x) is float:
  ensure(math.isfinite(x),'Nonfinite scalar');return ['float64',struct.pack('>d',x).hex()]
 if type(x) is str:return ['str',x]
 if type(x) in (list,tuple):return [type(x).__name__,[typed(v) for v in x]]
 if type(x) is dict:
  ensure(all(type(k) is str for k in x),'String-only normalized field keys')
  ensure(not any(k in x for k in ('@array_digest','@array_ref')),'Unverified JSON array token/ref: reviewed reader must decode actual bytes first')
  if set(x)=={'@array'}:
   a=x['@array'];ensure(set(a)=={'dtype','shape','payload_hex'},'Array descriptor exact domain')
   ensure(type(a['dtype']) is str and type(a['shape']) is list and all(type(n) is int and n>=0 for n in a['shape']),'Array dtype/shape schema')
   try:raw=bytes.fromhex(a['payload_hex'])
   except (ValueError,TypeError):raise ValueError('Array payload hex')
   # NumPy is used only for decoding exact normalized payloads, never model/GT imports.
   import numpy as np
   dt=np.dtype(a['dtype']);ensure(dt.str==a['dtype'] and not dt.hasobject and dt.kind in 'biuf','Canonical numeric array dtype only')
   ensure(len(raw)==math.prod(a['shape'])*dt.itemsize,'Array payload shape/size')
   values=np.frombuffer(raw,dtype=dt);ensure(bool(np.isfinite(values).all()),'Nonfinite array payload')
   return ['array',dt.str,a['shape'],hashlib.sha256(raw).hexdigest()]
  if set(x)=={'@object_None_array'}:
   a=x['@object_None_array'];ensure(set(a)=={'dtype','shape','values'} and a['dtype']=='|O','Native None object-array schema')
   ensure(type(a['shape']) is list and all(type(n) is int and n>=0 for n in a['shape']) and type(a['values']) is list and len(a['values'])==math.prod(a['shape']) and all(v is None for v in a['values']),'Only actual native None object-array values supported; no pickle/address bytes')
   return ['object_None_array','|O',a['shape'],['None']*len(a['values'])]
  return ['dict',[[k,typed(x[k])] for k in sorted(x)]]
 raise ValueError('Unsupported canonical field type '+str(type(x)))

def typed_digest(x):return digest(typed(x))

def array_payload(array):
 """Called on actual decoded arrays; includes dtype/shape and C-order exact bytes."""
 import numpy as np
 a=np.asarray(array)
 if a.dtype.hasobject:
  ensure(all(v is None for v in a.ravel().tolist()),'Unsupported native object contents')
  result={'@object_None_array':{'dtype':'|O','shape':list(a.shape),'values':a.ravel().tolist()}}
 else:result={'@array':{'dtype':a.dtype.str,'shape':list(a.shape),'payload_hex':a.tobytes(order='C').hex()}}
 typed(result);return result

def nodes_and_edges(movie):
 ensure(set(movie)=={'identifier_schema','gap_policy','frames','lineage','typed_edges'},'Normalized graph complete exact field inventory; bindings live separately')
 ensure(movie.get('identifier_schema')==GRAPH_SCHEMA,'Explicit persistent CTC schema required; frame-local IDs unsupported here')
 ensure(movie.get('gap_policy')=='reject_no_imputation','Source03 interval holes are rejected, never filled or bridged')
 frames=movie['frames'];ensure(type(frames) is list and len(frames)>0,'Nonempty frame domain')
 nodes=set();pixels={};shape=None
 for t,f in enumerate(frames):
  ensure(set(f)=={'t','labels'} and type(f['t']) is int and f['t']==t,'Strict ordered integer frame domain')
  image=f['labels'];ensure(type(image) is list and image and all(type(row) is list for row in image),'Label image list domain')
  h=len(image);w=len(image[0]);ensure(w>0 and all(len(row)==w for row in image),'Rectangular nonempty image')
  ensure(shape is None or shape==(h,w),'Frame shape drift');shape=(h,w)
  for y,row in enumerate(image):
   for x,label in enumerate(row):
    ensure(type(label) is int and 0<=label<=65535,'Native uint16 labels, no Boolean')
    if label:nodes.add((t,label));pixels.setdefault((t,label),set()).add((y,x))
 tracks={};children=collections.defaultdict(list)
 for row in movie['lineage']:
  ensure(type(row) is list and len(row)==4 and all(type(v) is int for v in row),'CTC lineage [id,start,end,parent] integer row')
  i,s,e,p=row;ensure(0<i<=65535 and i not in tracks and 0<=s<=e<len(frames) and p>=0 and p!=i,'CTC interval/identity schema')
  tracks[i]=(s,e,p);children[p].append(i)
 ensure(set(tracks)=={i for t,i in nodes},'Mask IDs and bound lineage IDs exact equality')
 implied=set()
 for i,(s,e,p) in tracks.items():
  ensure({t for t,j in nodes if j==i}==set(range(s,e+1)),'CTC interval mask hole/end mismatch; no interpolation')
  implied|={(t,i,t+1,i,0) for t in range(s,e)}
  if p:
   ensure(p in tracks and tracks[p][1]+1==s,'Division parent end-to-child start must be adjacent')
   implied.add((s-1,p,s,i,1))
 for p,ids in children.items():
  if p:ensure(len(ids)==2 and len({tracks[i][0] for i in ids})==1,'Exactly two simultaneous daughter tracks')
 given=movie['typed_edges'];ensure(type(given) is list and all(type(e) is list and len(e)==5 and all(type(v) is int for v in e) for e in given),'Typed edge exact integer domain')
 edges={tuple(e) for e in given};ensure(len(edges)==len(given) and edges==implied,'Explicit edges must exactly equal native lineage-implied graph')
 return nodes,edges,pixels,shape

def source_schedule(counts):
 for name,want in SOURCE_PINS.items():ensure(hashlib.sha256((SOURCE_ROOT/name).read_bytes()).hexdigest()==want,'Actual source03 bytes drift '+name)
 schedule=json.loads((SOURCE_ROOT/'fixed_schedule.json').read_bytes())['tau_by_video'];validate_tau(schedule,counts)
 return schedule

def validate_tau(schedule,counts):
 ensure(set(schedule)==set(counts),'Exact tau film inventory')
 for f,t in schedule.items():ensure(t is None or type(t) is int and 0<=t<counts[f],'Tau None or strict in-range integer '+f)

def validate_history(records,nframes):
 ensure(type(records) is list,'History list required');table={};contexts={}
 for r in records:
  ensure(set(r)=={'schema','t','kind','ordinal','applicability','context','fields','source_topology'},'Complete event field/presence inventory')
  ensure(r['schema']==HISTORY_SCHEMA and type(r['t']) is int and 0<=r['t']<nframes and r['kind'] in KINDS and type(r['ordinal']) is int and r['ordinal']==0,'Single native call source03 history schema')
  key=(r['t'],KINDS.index(r['kind']),0);ensure(key not in table,'Duplicate history event')
  context=r['context'];ensure(type(context) is dict and set(context)=={'consumer_queries_present','operator_called','mask_saved'} and all(type(v) is bool for v in context.values()),'Actual source-derived branch context required')
  ensure(r['t'] not in contexts or typed_digest(contexts[r['t']])==typed_digest(context),'Per-frame applicability context inconsistency');contexts[r['t']]=context
  kind=r['kind'];app=not (kind.startswith('consumer_') and kind!='consumer_applicability' and not context['consumer_queries_present']) and not (kind in ('native_operator','postprocess_M_G') and not context['operator_called']) and not (kind=='frame_serialization' and not context['mask_saved'])
  ensure(r['applicability']==('applicable' if app else 'not_applicable'),'Native branch applicability mismatch')
  fields=r['fields'];ensure(type(fields) is dict,'Fields must be complete mapping')
  if app:ensure(set(fields)==FIELDS[kind],'Source-bound complete stage field inventory '+kind)
  else:ensure(fields=={'reason':{'consumer_stack':'no_native_track_query_keys','consumer_effective_content':'no_native_track_query_keys','consumer_reference_points':'no_native_track_query_keys','native_operator':'native_postprocess_not_called','postprocess_M_G':'native_postprocess_not_called','frame_serialization':'native_mask_not_saved'}[kind]},'Explicit native N/A reason; no missing/None substitution')
  typed(fields)
  validate_source_topology(r['source_topology'],FIELDS[kind] if app else None)
  if app:validate_topology_values(r['source_topology'],fields)
  if app:
   array_keys={'raw_model_output':FIELDS['raw_model_output'],'native_operator':NATIVE_FIELDS,'postprocess_M_G':{'M','G','cells','all_indices'},'consumer_stack':{'prev_boxes','prev_hs_embed'},'consumer_effective_content':{'prev_tgt'},'consumer_reference_points':{'reference_points'},'frame_serialization':{'labels'}}.get(kind,set())
   for k in array_keys:ensure(isinstance(fields[k],VerifiedArrayDigest) or type(fields[k]) is dict and set(fields[k]) in ({'@array'},{'@object_None_array'}),'Source array field required '+kind+'/'+k)
   if kind in ('consumer_stack','consumer_effective_content','consumer_reference_points'):ensure(type(fields['output_target']) is str and fields['output_target']==SOURCE_OUTPUT_TARGET,'Actual source03 consumer output_target must be cur_target')
   if kind=='consumer_reference_points':ensure(type(fields['num_track_queries']) is int and fields['num_track_queries']>=0,'Actual num_track_queries integer, empty allowed')
  if kind=='before_model':validate_before_fields(fields,r['source_topology'],context)
  if kind=='consumer_applicability':
   expected=['consumer_stack','consumer_effective_content','consumer_reference_points'] if context['consumer_queries_present'] else []
   ensure(fields['captured']==expected and fields['anchors_present'] is True and fields['original_consumer_returned'] is True and type(fields['scope']) is str,'Consumer return/applicability complete; not a whole-call certificate')
  table[key]=r
 ensure(set(table)=={(t,k,0) for t in range(nframes) for k in range(len(KINDS))},'Complete source03 stages on every frame; explicit N/A required')
 for t,context in contexts.items():
  if context['operator_called']:
   mg=table[(t,KINDS.index('postprocess_M_G'),0)]['fields'];ensure(mg['arm'] in CELLS and type(mg['active']) is bool,'M/G actual policy metadata')
 return table

def history_targets(events,tau,nframes):
 ensure(set(events)==set(CELLS),'Four history bundles');validate_tau({'fixture':tau},{'fixture':nframes})
 tables={c:validate_history(events[c],nframes) for c in CELLS};pairs=[]
 for left,right in itertools.combinations(CELLS,2):
  first=None
  for key in sorted(tables[left]):
   a,b=tables[left][key],tables[right][key]
   if typed_digest(history_semantic(a))!=typed_digest(history_semantic(b)):
    first={'frame':key[0],'kind':a['kind'],'ordinal':0,'left_digest':typed_digest(a),'right_digest':typed_digest(b)};break
  pairs.append({'pair':[left,right],'first_actual_difference':first,'status':'different' if first else 'equal'})
 return {'status':'valid_normalized_history','schema':HISTORY_SCHEMA,'supplied_intervention_origin':None if tau is None else {'stage':'C','frame':tau},'origin_source':'Pinned source03 post-discovery fixed schedule; not unique natural cause','pairs':pairs,'unique_natural_error_cause':'withheld','future_censored':tau is not None and tau==nframes-1}

def history_semantic(r):
 fields=dict(r['fields'])
 topology={p:dict(v) for p,v in r['source_topology'].items()}
 if r['kind']=='postprocess_M_G' and r['applicability']=='applicable':
  fields.pop('arm');topology.pop('root/arm');topology['root']['keys']=[k for k in topology['root']['keys'] if k!='arm']
 # Routing arm is independently checked against its own bundle below; it is not
 # a model/operator value. Active/M/G/content/index and all other values remain.
 for v in topology.values():
  if v['type']=='dict':v['keys']=sorted(v['keys'])
 return {'applicability':r['applicability'],'context':r['context'],'fields':fields,'source_topology':topology}

def validate_source_topology(topology,root_fields):
 ensure(type(topology) is dict,'Actual topology mapping')
 if root_fields is None:ensure(topology=={},'N/A has no invented actual packet topology');return
 ensure('root' in topology and topology['root'].get('type')=='dict' and set(topology['root'].get('keys',[]))==root_fields,'Actual root topology field inventory')
 pending=['root'];seen=set()
 while pending:
  p=pending.pop();ensure(p in topology and p not in seen,'Missing/duplicate topology child');seen.add(p);node=topology[p];ensure(type(node) is dict and type(node.get('type')) is str,'Topology type schema');kind=node['type']
  if kind=='dict':
   keys=node['keys'];ensure(type(keys) is list and all(type(k) is str and '/' not in k for k in keys) and len(keys)==len(set(keys)),'Dictionary topology keys');pending += [p+'/'+k for k in keys]
  elif kind in ('list','tuple'):
   ensure(type(node['length']) is int and node['length']>=0,'Sequence topology length');pending += [p+'/'+str(i) for i in range(node['length'])]
  elif kind=='NestedTensor':pending += [p+'/tensors',p+'/mask']
  elif kind in ('tensor','numpy'):
   ensure(type(node['shape']) is list and all(type(n) is int and n>=0 for n in node['shape']) and type(node['dtype']) is str,'Actual array topology dtype/shape')
   if kind=='tensor':ensure(type(node.get('device')) is str and type(node.get('requires_grad')) is bool,'Actual tensor device/gradient metadata')
  elif kind in ('NoneType','bool','int','float','str'):
   value=node['value'];ensure(type(value).__name__==kind,'Scalar topology exact type');typed(value)
  else:raise ValueError('Unsupported actual topology type '+kind)
  typed(node)
 ensure(seen==set(topology),'Unexpected/orphan topology field refused')

def validate_topology_values(topology,fields):
 """Cross-check each logical field with its full original topology, not its claim."""
 def walk(p,v):
  node=topology[p];kind=node['type']
  if kind=='dict':
   ensure(type(v) is dict and set(v)==set(node['keys']),'Field vs dictionary topology')
   for k in node['keys']:walk(p+'/'+k,v[k])
  elif kind in ('list','tuple'):
   ensure(type(v).__name__==kind and len(v)==node['length'],'Logical sequence must restore exact source list/tuple kind')
   for i,x in enumerate(v):walk(p+'/'+str(i),x)
  elif kind=='NestedTensor':
   ensure(type(v) is dict and set(v)=={'tensors','mask'},'NestedTensor logical fields')
   for k in v:walk(p+'/'+k,v[k])
  elif kind in ('tensor','numpy'):
   import numpy as np
   ensure(isinstance(v,VerifiedArrayDigest) or type(v) is dict and set(v) in ({'@array'},{'@object_None_array'}),'Logical array actual-byte verification required')
   a={'dtype':v.dtype,'shape':list(v.shape)} if isinstance(v,VerifiedArrayDigest) else next(iter(v.values()));decl=np.dtype(node['dtype'].removeprefix('torch.')).str
   ensure(a['dtype']==decl and a['shape']==node['shape'],'Original array topology vs payload dtype/shape')
  else:ensure(typed_digest(v)==typed_digest(node['value']),'Scalar actual topology vs literal value/bit mismatch')
 walk('root',fields)

def fourcell_endpoint(film,tau,predictions,reference):
 result=_endpoint_impl(film,tau,predictions,reference)
 result['admitted_output_digests']={c:typed_digest(predictions[c]) for c in CELLS}
 return result

def mechanism_decision(control_summary,hist,endpoint):
 if control_summary.get('controls_independent_valid') is not True or hist['status']!='valid_normalized_history':return 'invalid_withhold'
 if endpoint['tau'] is None:
  histories=all(x['status']=='equal' for x in hist['pairs'])
  outputs=endpoint.get('admitted_output_digests',{});sameoutputs=set(outputs)==set(CELLS) and len(set(outputs.values()))==1
  samemetrics=all(typed_digest(endpoint['metrics'][c])==typed_digest(endpoint['metrics']['WW']) for c in CELLS)
  sameY=all(len(set(r['Y']))==1 for r in endpoint['edge_rows'])
  return 'no_trigger_control_equal' if histories and sameoutputs and samemetrics and sameY else 'invalid_no_trigger_parity'
 return _mechanism_impl(control_summary,hist,endpoint)

def compare_same_information(packet_digest,framework_digest,baseline_targets,framework_targets):
 if packet_digest!=framework_digest:return {'status':'invalid_unequal_information'}
 # Pure value comparison reports missing vs None separately. Materialized production
 # wrappers must additionally validate TARGET_SCHEMA/creator/file bindings below.
 ensure(type(baseline_targets) is dict and type(framework_targets) is dict,'Target mappings required')
 differences=[k for k in sorted(set(baseline_targets)|set(framework_targets)) if k not in baseline_targets or k not in framework_targets or typed_digest(baseline_targets[k])!=typed_digest(framework_targets[k])]
 return {'status':'equal_zero_demonstrated_decision_increment' if not differences else 'different_targets_requires_adjudication','different_fields':differences,'human_utility_measured':False,'method_novelty_certified':False}

def compare_materialized_targets(left,right,schema):
 ensure(schema['schema']==TARGET_SCHEMA and type(schema['keys']) is list and len(schema['keys'])==len(set(schema['keys'])),'Frozen target schema inventory')
 packets=[]
 for p in (left,right):
  ensure(p['schema_sha256']==typed_digest(schema) and type(p['creator_path']) is str and bool(p['creator_path']),'Target creator/schema binding')
  ensure(hashlib.sha256(Path(p['creator_path']).read_bytes()).hexdigest()==p['creator_sha256'],'Actual creator bytes')
  targets=read_bound(p['target_path'],p['target_sha256']);ensure(set(targets)==set(schema['keys']),'Materialized target exact key domain')
  typed(targets);packets.append(targets)
 return compare_same_information(left['information_packet_sha256'],right['information_packet_sha256'],*packets)

def validate_pre_reference(predictions,events,controls,taus,counts,pinned_schedule):
 """No reference object/path argument. Reject all structural defects before access."""
 validate_tau(taus,counts);validate_tau(pinned_schedule,counts)
 ensure(typed_digest(taus)==typed_digest(pinned_schedule),'Actual source03 tau dictionary, no retuning')
 ensure(set(predictions)==set(events)==set(CELLS) and set(controls)==set(counts),'Complete four-arm control domain')
 shapes={};histories={}
 for c in CELLS:
  ensure(set(predictions[c]['films'])==set(events[c]['films'])==set(counts),'Complete normalized film inventories')
  for f,n in counts.items():
   movie=predictions[c]['films'][f];ensure(len(movie['frames'])==n,'Exact source-bound per-film count')
   _,_,_,shape=nodes_and_edges(movie);ensure(f not in shapes or shapes[f]==shape,'Four-arm spatial domain');shapes[f]=shape
   validate_history(events[c]['films'][f],n)
   for r in events[c]['films'][f]:
    if r['kind']=='postprocess_M_G' and r['applicability']=='applicable':ensure(r['fields']['arm']==c,'Own-arm routing metadata mismatch')
    if r['kind']=='frame_serialization':
     ensure(r['applicability']=='applicable','This source03 final-mask contract requires all frames saved, absence is not imputed')
     import numpy as np
     expected=verified_array_digest(np.asarray(movie['frames'][r['t']]['labels'],dtype=np.uint16))
     ensure(typed_digest(r['fields']['labels'])==typed_digest(expected),'Actual serialized uint16 mask bytes vs normalized graph labels')
 for f,n in counts.items():
  s=controls[f];ensure(s.get('controls_independent_valid') is True and s.get('prefix_treatment_consumer_PASS') is True,'Independent technical control PASS required')
  typed(s) # factorization hypothesis equal/different is deliberately not an admission condition.
  if 'future_factorization_pairs' in s and s['future_factorization_pairs'] is not None:
   ensure(set(s['future_factorization_pairs'])=={'AW_vs_WW','WA_vs_AA'},'Complete future pair-control domain')
   for v in s['future_factorization_pairs'].values():
    ensure(type(v) is dict and v.get('status') in ('evaluated','not_evaluable'),'Future control status schema')
    if v['status']=='evaluated':ensure(all(type(v.get(k)) is bool for k in ('actual_input_equal','raw_model_output_equal','downstream_semantic_equal')),'Future observed Boolean evidence required')
  histories[f]=history_targets({c:events[c]['films'][f] for c in CELLS},taus[f],n)
  if taus[f] is None:
   ensure(all(v['status']=='equal' for v in histories[f]['pairs']),'No-trigger full history parity before reference')
   ensure(len({typed_digest(predictions[c]['films'][f]) for c in CELLS})==1,'No-trigger full output parity before reference, includes FP-only changes')
 return {'shapes':shapes,'histories':histories}

def admitted_analysis(job_path,output_dir):
 """Production deliberately WITHHELD: concrete adapter/passport equivalence absent.

 Even synthetic forged PASS/ROOT strings cannot unlock this frozen preparation.
 Future readiness requires a new reviewed version, not editing this registry.
 """
 job=json.loads(Path(job_path).read_text(encoding='utf-8'));counts,frame_sha=load_fixed_frames_contract();schedule=source_schedule(counts)
 ensure(job['frames_contract_sha256']==frame_sha and job['schedule_sha256']==SCHEDULE_SHA and job['source_pins']==SOURCE_PINS,'Actual frame/source/schedule binding')
 ensure(set(job['arm_inputs'])==set(CELLS),'All four arms')
 predictions={};events={}
 for c in CELLS:
  a=job['arm_inputs'][c];p=read_bound(a['independent_passport_path'],a['independent_passport_sha256'])
  ensure(p['arm']==c and p['frames_by_film']==counts and p['frames_contract_sha256']==frame_sha and p['schedule_sha256']==SCHEDULE_SHA and typed_digest(p['tau_by_film'])==typed_digest(schedule) and p['source_pins']==SOURCE_PINS,'Independent source-bound passport metadata')
  ensure(p['prediction_sha256']==a['prediction_sha256'] and p['events_sha256']==a['events_sha256'],'Passport outputs bound')
  predictions[c]=read_bound(a['prediction_path'],a['prediction_sha256']);events[c]=read_bound(a['events_path'],a['events_sha256'])
 validate_pre_reference(predictions,events,job['independent_control_summary'],job['tau_by_film'],counts,schedule)
 registry=json.loads((Path(__file__).resolve().parent/'RAW_READINESS.json').read_text(encoding='utf-8'))
 ensure(registry['status']=='WITHHELD_NO_REAL_ADAPTER_OR_INDEPENDENT_PASSPORT_PRODUCER','Frozen preparation readiness registry tampered')
 raise ValueError('Actual GT admission WITHHELD: no concrete independently accepted adapter/passport producer in this frozen version. No reference opened; no output created.')


# Fixed actual prediction call chain: engine model(samples,targets=targets),
# DETRTrackingBase super(...,'cur_target'), DeformableDETR forwards target_name
# to the original transformer. Siblings in main are preserved metadata.
SOURCE_OUTPUT_TARGET='cur_target'

def validate_before_fields(fields,topology,context):
 ensure(type(fields) is dict and set(fields)==FIELDS['before_model'],'Complete before_model fields')
 typed(fields);validate_source_topology(topology,FIELDS['before_model']);validate_topology_values(topology,fields)
 mapping=fields['mapping'];ensure(type(mapping) is dict and set(mapping)=={'cells','all_indices','track_indices','object_indices','div_indices','div_track','prevcells'},'Complete native mapping attribute presence')
 for entry in mapping.values():ensure(type(entry) is dict and set(entry)=={'present','value'} and type(entry['present']) is bool and (entry['present'] or entry['value'] is None),'Native absence vs present None')
 runtime=fields['runtime'];ensure(type(runtime) is dict and runtime and all(type(v) is dict and v.get('training') is False and v.get('train_model',False) is False for v in runtime.values()),'Native runtime branch must be explicitly captured, no training')
 targets=fields['targets'];has_queries=False
 if targets is not None:
  ensure(type(targets) is list and targets,'Native target batch domain')
  flags=[]
  for target in targets:
   ensure(type(target) is dict and type(target.get('main')) is dict and SOURCE_OUTPUT_TARGET in target['main'],'Actual selected cur_target branch required; siblings never removed')
   branch=target['main'][SOURCE_OUTPUT_TARGET];ensure(type(branch) is dict,'Selected main target content')
   q='track_query_hs_embeds' in branch;ensure(not q or 'track_query_boxes' in branch,'Track content without geometry');flags.append(q)
  ensure(len(set(flags))==1,'Target batch applicability consistency');has_queries=flags[0]
 ensure(has_queries==context['consumer_queries_present'],'Actual selected before-target topology vs consumer applicability')
 samples=fields['samples'];node=topology['root/samples']
 if node['type']=='tensor':
  ensure(isinstance(samples,VerifiedArrayDigest) or type(samples) is dict and set(samples)=={'@array'},'Actual tensor samples payload must remain an array, never fake NestedTensor')
  ensure(len(node['shape'])==4 and node['shape'][0]==1 and node['shape'][1]==3 and all(n>0 for n in node['shape']) and node['dtype']=='torch.float32','Native source03 preprocess batched float32 image domain')
 elif node['type']=='NestedTensor':
  # Source forward accepts this container too; no observed WW sample of this
  # branch is claimed. Source topology must preserve its actual container type.
  ensure(type(samples) is dict and set(samples)=={'tensors','mask'},'Explicit actual NestedTensor branch complete')
 else:raise ValueError('Unsupported source03 samples kind; scalar/list/tuple/numpy is not the observed preprocess tensor branch')
 return {'consumer_queries_present':has_queries,'output_target':SOURCE_OUTPUT_TARGET,'samples_source_kind':node['type']}

def validate_complete_before_event(event,nframes):
 ensure(set(event)=={'schema','t','kind','ordinal','applicability','context','fields','source_topology'} and event['schema']==HISTORY_SCHEMA and event['kind']=='before_model' and event['applicability']=='applicable','Complete before event contract')
 ensure(type(event['t']) is int and 0<=event['t']<nframes and type(event['ordinal']) is int and event['ordinal']==0,'Before event identity/range')
 ctx=event['context'];ensure(type(ctx) is dict and set(ctx)=={'consumer_queries_present','operator_called','mask_saved'} and all(type(v) is bool for v in ctx.values()),'Before event complete actual context')
 return validate_before_fields(event['fields'],event['source_topology'],ctx)

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('job');parser.add_argument('output');args=parser.parse_args()
 admitted_analysis(args.job,args.output)
