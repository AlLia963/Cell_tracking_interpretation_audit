from pathlib import Path
import importlib.util,sys,json,hashlib,datetime,copy
sys.dont_write_bytecode=True
import numpy as np
O=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('comparator04',O/'analysis_v0_6.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
results=[];bindings={};samples={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def case(name,fn):
 try:results.append({'id':name,'PASS':True,'actual':fn()})
 except Exception as exc:results.append({'id':name,'PASS':False,'exception':repr(exc)})
def reject(fn):
 try:fn()
 except ValueError as exc:return str(exc)
 raise AssertionError('Invalid input accepted')
def clone(v):
 if isinstance(v,m.VerifiedArrayDigest):return v
 if type(v) is dict:return {k:clone(x) for k,x in v.items()}
 if type(v) is list:return [clone(x) for x in v]
 if type(v) is tuple:return tuple(clone(x) for x in v)
 return v
def reconstruct(top,p='root'):
 node=top[p];kind=node['type']
 if kind in ('tensor','numpy'):
  # Every array below is SYNTHETIC zeros; no NPZ/TIFF or actual array opened.
  return m.verified_array_digest(np.zeros(node['shape'],dtype=np.dtype(node['dtype'].removeprefix('torch.'))))
 if kind=='dict':return {k:reconstruct(top,p+'/'+k) for k in node['keys']}
 if kind in ('list','tuple'):
  values=[reconstruct(top,p+'/'+str(i)) for i in range(node['length'])];return values if kind=='list' else tuple(values)
 if kind=='NestedTensor':return {k:reconstruct(top,p+'/'+k) for k in ('tensors','mask')}
 assert kind in ('NoneType','bool','int','float','str');return node['value']
observation=O.parent/'fourcell_cohort_adapter_preparation_v0.1/ACTUAL_METADATA_SCHEMA_MISMATCH.json'
bindings[str(observation)]=sha(observation);obs=json.loads(observation.read_text())['observations']
assert [r['frame'] for r in obs]==[0,1,35,69]
for item in obs:
 path=Path(item['path']);actual=sha(path);assert actual==item['sha256'];bindings[str(path)]=actual
 raw=json.loads(path.read_text());assert raw['frame']==item['frame'] and raw['kind']=='before_model' and raw['ordinal']==0
 top=raw['topology'];assert top==item['raw_topology'];fields=reconstruct(top)
 branch=fields['targets'][0]['main']['cur_target'];q='track_query_hs_embeds' in branch
 event={'schema':m.HISTORY_SCHEMA,'t':item['frame'],'kind':'before_model','ordinal':0,'applicability':'applicable','context':{'consumer_queries_present':q,'operator_called':True,'mask_saved':True},'fields':fields,'source_topology':top}
 samples[item['frame']]=event
def four_actual_templates():
 rows=[]
 for t,event in samples.items():
  value=m.validate_complete_before_event(event,70);main=event['fields']['targets'][0]['main']
  assert isinstance(event['fields']['samples'],m.VerifiedArrayDigest) and event['source_topology']['root/samples']['type']=='tensor'
  rows.append({'source_frame':t,'accepted_domain':value,'retained_main_keys':list(main),'query_range_metadata':{k:main[k] for k in ('start_query_ind','end_query_ind') if k in main},'array_values':'synthetic zeros, not actual source values','complete_before_event':True,'other_stage_context_flags':'synthetic operator/mask flags; not actual call certificate'})
 return rows
case('FC03G01_G02_four_actual_metadata_templates',four_actual_templates)
def negatives():
 rows={}
 for name in ('missing_selected','nondict_selected','content_without_geometry','missing_sibling_topology'):
  e=clone(samples[1]);main=e['fields']['targets'][0]['main'];top=e['source_topology']
  if name=='missing_selected':main.pop('cur_target')
  elif name=='nondict_selected':main['cur_target']=None
  elif name=='content_without_geometry':main['cur_target'].pop('track_query_boxes')
  else:top.pop('root/targets/0/main/start_query_ind')
  rows[name]=reject(lambda e=e:m.validate_complete_before_event(e,70))
 return rows
case('FC03G02_missing_false_target_or_metadata_refuses',negatives)
def no_fabrication():
 e=clone(samples[0]);a=e['fields']['samples'];e['fields']['samples']={'tensors':a,'mask':a}
 return {'fake_NestedTensor_with_original_tensor_topology':reject(lambda:m.validate_complete_before_event(e,70))}
case('FC03G01_no_pseudo_NestedTensor_conversion',no_fabrication)
def scalar_list_domains():
 rows={}
 for name,value in [('scalar',1.0),('list',[]),('tuple',())]:
  e=clone(samples[0]);e['fields']['samples']=value
  e['source_topology']['root/samples']={'type':type(value).__name__,'value':value} if name=='scalar' else {'type':name,'length':0}
  rows[name]=reject(lambda e=e:m.validate_complete_before_event(e,70))
 return rows
case('samples_unsupported_actual_source_kinds_refuse',scalar_list_domains)
def siblings_retained():
 e=clone(samples[1]);first=m.typed_digest(e['fields']);e['fields']['targets'][0]['main']['start_query_ind']=1;e['source_topology']['root/targets/0/main/start_query_ind']['value']=1
 m.validate_complete_before_event(e,70);assert first!=m.typed_digest(e['fields'])
 return {'same_selected_cur_target_with_other_metadata_preserved':True,'sibling_value_change_retained_in_semantics':True,'not_accepted_as_actual_source_parity':True}
case('siblings_preserved_as_values_not_discarded',siblings_retained)
def none_valid():
 a=np.asarray(None);token={'dtype':'|O','shape':[],'None_only':True};value=m.verified_array_digest(a,token)
 assert m.typed(value)==['object_None_array','|O',[],['None']]
 return {'actual_synthetic_scalar_None_semantics':m.typed(value),'numeric_pointer_bytes_never_hashed':True}
case('FC03G03_scalar_None_correct_compact_schema',none_valid)
def none_bad():
 tokens={'wrong_numeric':{'dtype':'<f4','shape':[99],'C_value_sha256':'0'*64},'wrong_dtype':{'dtype':'object','shape':[],'None_only':True},'wrong_shape':{'dtype':'|O','shape':[1],'None_only':True},'false_value':{'dtype':'|O','shape':[],'None_only':False},'int_as_boolean':{'dtype':'|O','shape':[],'None_only':1},'extra_field':{'dtype':'|O','shape':[],'None_only':True,'finite':True}}
 return {name:reject(lambda token=token:m.verified_array_digest(np.asarray(None),token)) for name,token in tokens.items()}
case('FC03G03_all_wrong_None_expectations_reject',none_bad)
case('FC03G03_unsupported_object_contents_shapes',lambda:{'not_None':reject(lambda:m.verified_array_digest(np.asarray(1,dtype=object))),'vector_None':reject(lambda:m.verified_array_digest(np.asarray([None],dtype=object)))})
def exact_sequences():
 top={'root':{'type':'dict','keys':['v']},'root/v':{'type':'tuple','length':1},'root/v/0':{'type':'int','value':1}}
 m.validate_source_topology(top,{'v'});m.validate_topology_values(top,{'v':(1,)})
 wrongtuple=reject(lambda:m.validate_topology_values(top,{'v':[1]}))
 top['root/v']={'type':'list','length':1};m.validate_topology_values(top,{'v':[1]});wronglist=reject(lambda:m.validate_topology_values(top,{'v':(1,)}))
 return {'restored_tuple_and_list_accepted':True,'JSON_list_must_restore_source_tuple':wrongtuple,'source_list_not_tuple':wronglist,'scope':'synthetic canonical-reader domain, not observed native tuple claim'}
case('FC03G04_single_exact_sequence_construction',exact_sequences)
payload={'status':'BOUNDED_NATIVE_DOMAIN_PREPARATION_GUARDS_PASS' if all(r['PASS'] for r in results) else 'FAIL','saved_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_actual_SHA256':sha(O/'analysis_v0_6.py'),'metadata_source_frames':[0,1,35,69],'actual_arrays_opened':0,'arrays_in_guards':'synthetic zeros and synthetic None objects only','no_full70_or_all29_semantic_PASS':True,'old35_47_rerun':False,'GT_GPU_model_E':False,'cases':results,'failures':[r for r in results if not r['PASS']],'actual_small_metadata_bindings':bindings}
with (O/'CPU_NATIVE_DOMAIN_RESULTS.json').open('x',encoding='utf-8') as f:json.dump(payload,f,indent=2)
print(json.dumps({'cases':len(results),'failures':payload['failures'],'actual_arrays_opened':0}))
if payload['failures']:raise SystemExit(1)
