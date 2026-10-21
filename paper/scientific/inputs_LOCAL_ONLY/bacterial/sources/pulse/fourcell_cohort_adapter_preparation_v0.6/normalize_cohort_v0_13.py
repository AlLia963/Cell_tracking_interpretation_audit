"""One-film-at-a-time cohort normalization preparation. No GT/model imports.
Production execution requires a separately frozen ROOT authorization and all four
actual independent technical result bindings. Current preparation does not run it.
"""
from pathlib import Path
import collections,hashlib,importlib.util,json,traceback,datetime,zipfile
import numpy as np,tifffile
D=Path(__file__).resolve().parent;F=D.parent;P=F/'fourcell_raw_adapter_preparation_v0.1';S=F/'source_preparation_v0.3'
CELLS=('WW','AW','WA','AA');FILMS=[f'{i:02d}' for i in range(1,30)]
KINDS=('before_model','consumer_stack','consumer_effective_content','consumer_reference_points','raw_model_output','consumer_applicability','native_operator','postprocess_M_G','frame_serialization')
NAREASON={'consumer_stack':'no_native_track_query_keys','consumer_effective_content':'no_native_track_query_keys','consumer_reference_points':'no_native_track_query_keys','native_operator':'native_postprocess_not_called','postprocess_M_G':'native_postprocess_not_called','frame_serialization':'native_mask_not_saved'}
def req(x,msg):
 if not x:raise ValueError(msg)
def h(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):
 with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,indent=2,allow_nan=False)
def bound(p,want):req(h(p)==want,'Bound file changed '+str(p));return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def import_file(name,p):
 spec=importlib.util.spec_from_file_location(name,p);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def checked_path(value,base=None,fresh=False):
 p=Path(value)
 req(p.is_absolute() and '..' not in p.parts,'Absolute path without parent traversal required')
 # Check lexical ancestors before resolve, since resolving a junction would hide it.
 for node in [p,*p.parents]:
  try:info=node.lstat()
  except FileNotFoundError:continue
  req(not (getattr(info,'st_file_attributes',0)&0x400) and not node.is_symlink() and not (hasattr(node,'is_junction') and node.is_junction()),'Reparse/symlink path refused '+str(node))
 resolved=p.resolve(strict=False)
 if base is not None:
  parent=checked_path(base);req(resolved.is_relative_to(parent) and resolved!=parent,'Resolved path escapes intended root')
 if fresh:req(not resolved.exists(),'Fresh destination required')
 return resolved

def header_guard(job,authorization,counts,taus):
 req(set(job)=={'schema','arm_inputs','output_root','authorization_path','authorization_sha256'},'Job exact field inventory, no reference path')
 req(job['schema']=='fourcell_stream_normalization_job_v2_AW_twoattempt' and set(job['arm_inputs'])==set(CELLS),'All four actual arms required before normalization')
 req(authorization['status']=='FOURCELL_NORMALIZATION_AUTHORIZED','Further ROOT execution authorization absent')
 req(authorization['entry_sha256']==h(__file__),'Actual entry bound by ROOT')
 req(authorization['frames_by_film']==counts and sum(counts.values())==5340 and sorted(counts)==FILMS,'Exact29/5340 frame counts')
 req(authorization['tau_by_film']==taus,'Actual source03 tau schedule, no retuning')
 req(authorization['arm_inputs']==job['arm_inputs'] and authorization['output_root']==job['output_root'],'ROOT exact path/result scope')
 req(authorization['WW01_independent_integration_accepted'] is True,'Actual WW01 independent review acceptance required')
 root=checked_path(job['output_root'],F,fresh=True)
 for c,spec in job['arm_inputs'].items():
  req(spec['arm']==c and spec['independent_technical_accepted'] is True,'Own-arm technical acceptance required')
  req(spec['native_root']==authorization['effective_native_roots'][c],'Bound actual source route')
  req(spec['frames_by_film']==counts and spec['tau_by_film']==taus,'Arm domain and schedule')
  req(spec['technical_result_status']=={'WW':'BOUNDED_WW_PREDICATE_CORRECTION_AND_CONSUMED_REVALIDATION_PASS','AA':'PASS_FULL29_AA_PREDICTION_ONLY','AW':'PASS_ASSEMBLED_TWOATTEMPT29_AW_PREDICTION_ONLY','WA':'PASS_FULL29_WA_PREDICTION_ONLY'}[c],'Exact known own-arm checker status required')

def validate_arm_manifest(manifest,cell,counts):
 req(manifest.get('arm')==cell and manifest.get('selected_video_count')==29 and manifest.get('completed')==29,'Actual top-level own-arm completed manifest')
 reports=manifest['all_video_reports']
 req(len(reports)==29 and {r['video'] for r in reports}==set(FILMS) and all(r['arm']==cell and r['status']=='completed' and r['input_frames']==r['output_masks']==counts[r['video']] for r in reports),'Complete exact29 OWN-ARM per-film metadata; partial/wrong-arm run refused')
 return reports

class Consume:
 def __init__(self,root,expected):self.root=checked_path(root);self.expected=expected;self.records={}
 def __call__(self,p):
  p=checked_path(p,self.root);key=str(p);req(key in self.expected,'Actual consumed source missing original SHA binding')
  got=h(p);req(got==self.expected[key],'Source changed '+key)
  if key in self.records:req(got==self.records[key]['sha256'],'Concurrent source change');self.records[key]['hash_calls']+=1
  else:self.records[key]={'sha256':got,'bytes':p.stat().st_size,'hash_calls':1}
  return got

class ArrayWriter:
 """Refs to frozen ORIGINAL compact NPZ/TIFF; no raw-array duplication or hex."""
 def __init__(self,path):self.path=Path(path).with_name('array_sources.json');self.keys=set();self.sources={};self.source=None;self.format=None;self.file_hashes={}
 def set_source(self,path,format):self.source=Path(path);self.format=format
 def put(self,key,array):
  a=np.asarray(array);req(self.source is not None and key not in self.keys,'Unique source reference required');self.keys.add(key)
  if a.dtype.hasobject:
   req(a.shape==() and a.item() is None,'Only native scalar None');token={'dtype':'|O','shape':[],'None_only':True}
  else:
   req(a.dtype.kind in 'biuf' and bool(np.isfinite(a).all()),'Finite numeric typed array required')
   token={'dtype':a.dtype.str,'shape':list(a.shape),'C_value_sha256':hashlib.sha256(a.tobytes(order='C')).hexdigest()}
  source_path=str(self.source)
  if source_path not in self.file_hashes:self.file_hashes[source_path]=h(self.source)
  self.sources[key]={'source_path':source_path,'source_sha256':self.file_hashes[source_path],'format':self.format,'source_key':key.split('/',1)[1] if self.format=='npz' else None}
  return {'@array_ref':{'ref_id':key,'token':token}}
 def close(self):write(self.path,{'scope':'immutable originally bound raw NPZ/TIFF refs; no numeric array copy','sources':self.sources})

def reconstruct(topology,arrays,writer,prefix,path='root'):
 node=topology[path];kind=node['type']
 if kind in ('numpy','tensor'):return writer.put(prefix+'/'+path,arrays[path])
 if kind=='dict':return {k:reconstruct(topology,arrays,writer,prefix,path+'/'+k) for k in node['keys']}
 if kind in ('list','tuple'):
  values=[reconstruct(topology,arrays,writer,prefix,path+'/'+str(i)) for i in range(node['length'])]
  return values if kind=='list' else {'@tuple':values}
 if kind=='NestedTensor':return {k:reconstruct(topology,arrays,writer,prefix,path+'/'+k) for k in ('tensors','mask')}
 req(kind in ('NoneType','bool','str','int','float'),'Unsupported source type '+kind);return node['value']

def queries_present(fields):
 target=fields['targets']
 if target is None:return False
 req(type(target) is list and target,'Actual target batch required');values=[]
 for t in target:
  main=t['main'];req(type(main) is dict and 'cur_target' in main and type(main['cur_target']) is dict,'Actual source03 cur_target branch required; query-range siblings retained');branch=main['cur_target'];q='track_query_hs_embeds' in branch
  req(not q or 'track_query_boxes' in branch,'Content key without geometry');values.append(q)
 req(len(set(values))==1,'Target-batch consumer applicability drift');return values[0]

# Compact semantic storage; load_one_film later expands references only for that
# film into comparator literal payloads. Original topology is compared separately.
def convert_history(native,nframes,out,a,consume,history_schema):
 native=Path(native);out=Path(out);trace=native/'direct_trace';ops=native/'operator_states';journal=[json.loads(l) for l in (ops/'frame_journal.jsonl').read_text(encoding='utf-8-sig').splitlines() if l.strip()]
 completed={r['frame']:r for r in journal if r['event']=='frame_complete'}
 req(set(completed)==set(range(nframes)) and not any(r['event'].endswith('failed') for r in journal),'Complete actual source journal')
 inventory=json.loads((trace/'inventory.json').read_text(encoding='utf-8-sig'));actual={(r['frame'],r['kind'],r['ordinal']):r for r in inventory};req(len(actual)==len(inventory),'Duplicate source event')
 req(all(k[2]==0 for k in actual),'Comparator03 single-call domain: extra ordinal refused')
 archive=out/'canonical_event_arrays.npz';writer=ArrayWriter(archive);contexts={};count=0
 try:
  with (out/'canonical_events.jsonl').open('x',encoding='utf-8') as stream:
   for t in range(nframes):
    complete=completed[t];before=None
    for kind in KINDS:
     source_topology={};app=True
     if kind in a.DIRECT:
      if (t,kind,0) in actual:
       stem=f'{t:04d}_{kind}_00';p=trace/(stem+'.npz');consume(p);consume(p.with_suffix('.json'));meta=json.loads(p.with_suffix('.json').read_text(encoding='utf-8-sig'));arrays=a.read_arrays(p);writer.set_source(p,'npz');source_topology=a.canonical_topology(meta['topology']);fields=reconstruct(source_topology,arrays,writer,stem)
      elif kind in a.CONSUMERS:app=False;fields={'reason':NAREASON[kind]}
      elif kind=='postprocess_M_G' and complete['operator_applicable'] is False:app=False;fields={'reason':NAREASON[kind]}
      else:raise ValueError('Missing required actual source event '+kind)
     elif kind=='native_operator':
      if complete['operator_applicable']:
       p=ops/f'frame{t:03d}.npz';consume(p);arrays=a.read_arrays(p,True);writer.set_source(p,'npz');req(set(arrays)==a.NATIVE49,'Native49 exact domain');fields={k:writer.put(f'{t:04d}_native_operator/'+k,v) for k,v in sorted(arrays.items())};source_topology={'root':{'type':'dict','keys':sorted(arrays)}}
       source_topology.update({'root/'+k:{'type':'numpy','dtype':str(v.dtype),'shape':list(v.shape)} for k,v in arrays.items()})
      else:app=False;fields={'reason':NAREASON[kind]}
     else:
      if complete['mask_saved']:
       p=native/f'mask{t:03d}.tif';consume(p);v=tifffile.imread(p);writer.set_source(p,'tiff');fields={'labels':writer.put(f'{t:04d}_frame_serialization/labels',v)};source_topology={'root':{'type':'dict','keys':['labels']},'root/labels':{'type':'numpy','dtype':str(v.dtype),'shape':list(v.shape)}}
      else:app=False;fields={'reason':NAREASON[kind]}
     if kind=='before_model':before=fields;contexts[t]={'consumer_queries_present':queries_present(before),'operator_called':complete['operator_applicable'],'mask_saved':complete['mask_saved']}
     context=contexts[t];expected_app=not(kind in a.CONSUMERS and not context['consumer_queries_present']) and not(kind in ('native_operator','postprocess_M_G') and not context['operator_called']) and not(kind=='frame_serialization' and not context['mask_saved'])
     req(app==expected_app,'Source packets vs before-target/journal applicability mismatch')
     if kind in a.CONSUMERS and app:req(fields['output_target']=='cur_target','Actual consumer branch vs before target selection mismatch')
     if kind=='postprocess_M_G' and app:req(fields['arm'] in CELLS and type(fields['active']) is bool,'Actual arm/active metadata')
     record={'schema':history_schema,'t':t,'kind':kind,'ordinal':0,'applicability':'applicable' if app else 'not_applicable','context':context,'source_topology':source_topology,'fields':fields}
     stream.write(json.dumps(record,sort_keys=True,allow_nan=False)+'\n');count+=1
 finally:writer.close()
 req(count==9*nframes,'Nine actual-source-supported events per frame')
 return {'events':count,'numeric_array_members':len(writer.keys),'array_sources_sha256':h(out/'array_sources.json'),'records_sha256':h(out/'canonical_events.jsonl'),'storage':'perfilm compact prediction NPZ + JSONL typed tokens referencing frozen raw arrays; no duplicate arrays/hex','N_A_evidence':'actual before target keys + original consumer applicability + frame_complete journal; no tensor imputation'}

class ActualRefReader:
 def __init__(self,sources,c):self.sources=sources;self.c=c;self.last_path=None;self.last_arrays=None;self.a=import_file('derived_reader',D/'raw_adapters_v0_4.py')
 def get(self,r):
  source=self.sources[r['ref_id']];p=checked_path(source['source_path']);req(h(p)==source['source_sha256'],'Frozen referenced source changed')
  if source['format']=='tiff':array=tifffile.imread(p)
  else:
   if self.last_path!=str(p):self.last_arrays=self.a.read_arrays(p,native=p.parent.name=='operator_states');self.last_path=str(p)
   array=self.last_arrays[source['source_key']]
  token=r['token']
  if array.dtype.hasobject:
   req(token=={'dtype':'|O','shape':[],'None_only':True} and array.shape==() and array.item() is None,'Actual None reference verification');return self.c.verified_array_digest(array,token)
  return self.c.verified_array_digest(array,token)

def expand_refs(v,reader):
 if type(v) is dict and set(v)=={'@array_ref'}:return reader.get(v['@array_ref'])
 if type(v) is dict and set(v)=={'@tuple'}:return tuple(expand_refs(x,reader) for x in v['@tuple'])
 if type(v) is dict:return {k:expand_refs(x,reader) for k,x in v.items()}
 if type(v) is list:return [expand_refs(x,reader) for x in v]
 return v

def load_one_film_bridge(out,c,prepared_index=None):
 out=Path(out);index=prepared_index if prepared_index is not None else json.loads((out/'FILM_COMPLETE.json').read_text(encoding='utf-8-sig'));req(index['status']==('FILM_NORMALIZATION_PREPARED' if prepared_index is not None else 'FILM_NORMALIZATION_COMPLETE'),'Partial film never admitted')
 for rel,want in index['output_bindings'].items():req(h(out/rel)==want,'Compact normalized output binding')
 with np.load(out/'prediction/prediction.npz',allow_pickle=False) as z:
  movie={'identifier_schema':'persistent_ctc_track_id_v1','gap_policy':'reject_no_imputation','frames':[{'t':t,'labels':z[f'frame_{t:04d}'].tolist()} for t in range(index['frames'])],'lineage':index['lineage'],'typed_edges':z['typed_edges'].tolist()}
 reader=ActualRefReader(json.loads((out/'array_sources.json').read_text(encoding='utf-8-sig'))['sources'],c)
 events=[expand_refs(json.loads(l),reader) for l in (out/'canonical_events.jsonl').read_text(encoding='utf-8-sig').splitlines()]
 # Structural validators only, no reference and no endpoint score.
 c.nodes_and_edges(movie);c.validate_history(events,index['frames'])
 for r in events:
  if r['kind']=='frame_serialization' and r['applicability']=='applicable':
   expected=c.verified_array_digest(np.asarray(movie['frames'][r['t']]['labels'],dtype=np.uint16))
   req(c.typed_digest(r['fields']['labels'])==c.typed_digest(expected),'Serialized actual bytes vs normalized graph label map')
 return movie,events


AW_NATIVE_BY_FILM={f'{i:02d}':('E:/kaggle_factorial_control_20261003_v0.2/AW/native' if i<=22 else 'E:/kaggle_factorial_control_20261004_v0.1/AW/native') for i in range(1,30)}
def validate_assembled_AW_inputs(spec,authorization,expected,result,manifest,counts):
 req(spec['native_root'] is None and authorization['effective_native_roots']['AW'] is None,'AW has no invented single physical native root')
 actual=spec.get('native_root_by_film');req(type(actual) is dict and set(actual)==set(FILMS),'AW29 physical map exact cover')
 req(actual==authorization['AW_native_roots_by_film'],'ROOT exact AW physical map')
 for v,home in actual.items():req(checked_path(home)==checked_path(AW_NATIVE_BY_FILM[v]),'AW exact physical source root '+v)
 resultdir=Path(spec['technical_result_path']).parent
 req(checked_path(spec['manifest_path'])==checked_path(resultdir/'assembled29_input_manifest.json'),'AW actual generated logical manifest paired with checker result')
 ap=checked_path(spec['assembled_ROOT_acceptance_path']);req(ap==checked_path(F/'ROOT_AW_ASSEMBLED29_ACTUAL_ACCEPTED_v0.1.json'),'AW independent actual acceptance exact ROOT path')
 req(str(ap)==authorization['AW_assembled_acceptance_path'] and spec['assembled_ROOT_acceptance_sha256']==authorization['AW_assembled_acceptance_sha256'],'ROOT normalization binds distinct actual AW acceptance')
 accepted=bound(ap,spec['assembled_ROOT_acceptance_sha256'])
 req(accepted.get('status')=='ACCEPTED_ASSEMBLED_TWOATTEMPT29_AW_PREDICTION_ONLY' and accepted.get('arm')=='AW' and accepted.get('scope')=='AW_dualphysicalroot_twoattempt29_actual' and accepted.get('original_attempt_interrupted') is True,'AW actual ROOT scope not original whole-process success')
 for key in ('technical_result_path','technical_result_sha256','consumed_receipt_path','consumed_receipt_sha256','manifest_path','manifest_sha256','checker_path','checker_sha256'):
  req(accepted.get(key)==spec[key],'AW actual ROOT artifact binding '+key)
 req(accepted.get('native_root_by_film')==actual and accepted.get('frames_by_film')==counts and accepted.get('films')==29 and accepted.get('frames')==5340,'AW actual ROOT exact full domain')
 req(manifest.get('video_physical_homes')==result.get('physical_home_by_video') and set(manifest.get('producer_attempts',{}))=={'original22','recovery7'},'AW actual result/logical manifest domain agreement')
 domain={'original22':[f'{i:02d}' for i in range(1,23)],'recovery7':[f'{i:02d}' for i in range(23,30)]}
 req({k:v['videos'] for k,v in manifest['producer_attempts'].items()}==domain,'AW disjoint genuine attempt film membership')
 requiremap=lambda p:bound(p,expected[str(p)])
 for name,films in domain.items():
  home=checked_path(actual[films[0]]).parent;provpath=home/'provenance_before_inference.json';prov=requiremap(provpath)
  req(checked_path(prov['effective_args']['output_dir'])==home/'native','AW genuine attempt output_dir preserved')
  producer=requiremap(home/'manifest.json')
  if name=='recovery7':
   req(producer.get('arm')=='AW' and producer.get('selected_video_count')==producer.get('completed')==7 and len(producer['all_video_reports'])==7 and {r['video'] for r in producer['all_video_reports']}==set(films) and sum(r['input_frames'] for r in producer['all_video_reports'])==1265 and all(r['status']=='completed' for r in producer['all_video_reports']),'AW recovered7 real completed manifest')
  for v in films:
   report=requiremap(home/(v+'_execution_report.json'));row=next(r for r in manifest['all_video_reports'] if r['video']==v)
   req(report==row and report['status']=='completed' and report['arm']=='AW' and report['input_frames']==report['output_masks']==counts[v],'AW genuinely generated completed film report '+v)
  req(str(provpath) in expected and str(home/'manifest.json') in expected,'AW actual checker consumed genuine producer metadata')
 terminal=F/'AW_recovery7_entry_preparation_v0.1/runtime/attempt_3b8e710499594a849a0db8bd0d4e8c7d/terminal.json';t=requiremap(terminal)
 req(t.get('status')=='child_exit_zero_not_prediction_validated' and type(t.get('child_exit_code')) is int and t['child_exit_code']==0 and t['intended_films']==domain['recovery7'],'AW actual recovered7 terminal')
 req(not (terminal.parent/'terminal_failure.json').exists(),'AW contradictory recovery failure refused')
 return actual

def run_cohort(job_path):
 # No destination claim until missing arms / authorization / all technical receipts
 # are checked. Any post-claim failure gets a durable failure receipt; no retry.
 job=json.loads(Path(job_path).read_text(encoding='utf-8-sig'));authorization=bound(job['authorization_path'],job['authorization_sha256']);counts=json.loads((F/'fourcell_comparator_preparation_v0.2/frames_contract.json').read_text(encoding='utf-8-sig'))['frames_by_film'];taus=json.loads((S/'fixed_schedule.json').read_text(encoding='utf-8-sig'))['tau_by_video'];header_guard(job,authorization,counts,taus)
 prep=bound(P/'DELIVERY_HASHES.json',authorization['raw_helper_receipt_sha256']);original_helper=P/'raw_adapters_v0_3.py';req(h(original_helper)==prep['files'][original_helper.name],'Frozen original helper');helper=D/'raw_adapters_v0_4.py';req(h(helper)==authorization['derived_raw_helper_sha256'],'Reviewed derived helper bound by ROOT')
 req(authorization.get('comparator_independent_accepted') is True,'Further independent comparator acceptance required')
 req(h(authorization['comparator_independent_result_path'])==authorization['comparator_independent_result_sha256'],'ROOT bound actual comparator independent result')
 req(h(authorization['comparator_independent_receipt_path'])==authorization['comparator_independent_receipt_sha256'],'ROOT bound actual comparator independent receipt')
 req(authorization['raw_helper_receipt_sha256']=='3c16057a4d1984cd97fdb24294f7cd70fdecc5a5470a6b9487706052cfd4f64b','Fixed helper delivery')
 pins=json.loads((D/'CONTRACT_PINS.json').read_text(encoding='utf-8-sig'));req(h(D/'CONTRACT_PINS.json')==authorization['contract_pins_sha256'],'Frozen NEW comparator04 pin registry')
 cpath=Path(pins['comparator_path']);req(str(cpath)==authorization['comparator_contract_path'] and h(cpath)==authorization['comparator_contract_sha256']==pins['comparator_sha256'],'Formal frozen comparator04 actual bytes')
 req(h(Path(pins['comparator_receipt_path']))==pins['comparator_receipt_sha256'],'Formal frozen comparator04 receipt')
 pilot=F/'fourcell_raw_adapter_actual_WW01_independent_gate_v0.1/delivery_hashes_v0.2.json';req(h(pilot)==authorization['WW01_independent_receipt_sha256']=='34e20438e1759b1ed8c72f3de75c8a8446eb0dd1152a2925c647907dc11448af','Actual WW01 independent accepted receipt')
 a=import_file('raw_helper',helper);c=import_file('contract_only',cpath);technical=import_file('checker_contract',D/'actual_checker_contract_v0_1.py');expected={};controls={}
 profiles=bound(D/'CHECKER_PROFILES.json',authorization['checker_profiles_sha256'])
 req(h(D/'actual_checker_contract_v0_1.py')==authorization['technical_contract_sha256'],'Bound technical result parser code')
 req(h(F/'fourcell_comparator_preparation_v0.2/frames_contract.json')==authorization['frames_contract_sha256']=='d9f692dd00753c9001a2c097091fea443857d64dc6ab3c6e6bbbdf58df82456e','Actual frames contract binding')
 req(h(S/'fixed_schedule.json')==authorization['schedule_sha256']=='4f4d5d48295116efa4389fc4edb0b1d225ff79d26a7f684f8aa125c8b191ee22','Pinned original source03 schedule')
 req(authorization['source_pins']==c.SOURCE_PINS,'Complete comparator source pins, no caller omissions')
 for rel,want in authorization['source_pins'].items():req(h(S/rel)==want,'Original source03 binding '+rel)
 effective_roots={'WW':str(F/'runs_v0.3/WW/native'),'AA':str(F/'runs_v0.3/AA/native'),'AW':'E:/kaggle_factorial_control_20261003_v0.2/AW/native','WA':'E:/kaggle_factorial_control_20261003_v0.2/WA/native'}
 for cell,spec in job['arm_inputs'].items():
  if cell!='AW':
   req(checked_path(spec['native_root'])==checked_path(effective_roots[cell]),'Source03 effective own-arm native route; no alias')
   req(checked_path(spec['manifest_path'])==checked_path(spec['native_root']).parent/'manifest.json','Actual own-arm native/manifest path closure')
  result=bound(spec['technical_result_path'],spec['technical_result_sha256']);req(result['status']==spec['technical_result_status'],'Actual independent result status');technical.validate_actual_result(result,cell,counts)
  receipts=bound(spec['consumed_receipt_path'],spec['consumed_receipt_sha256']);expected[cell]=receipts if spec['consumed_hash_mapping_key'] is None else receipts[spec['consumed_hash_mapping_key']];technical.validate_sha_mapping(expected[cell])
  req(type(expected[cell]) is dict and all(type(v) is str and len(v)==64 for v in expected[cell].values()),'Actual original SHA mapping')
  manifest=bound(spec['manifest_path'],spec['manifest_sha256']);validate_arm_manifest(manifest,cell,counts)
  if cell=='AW':validate_assembled_AW_inputs(spec,authorization,expected[cell],result,manifest,counts)
  if cell!='WW':
   profile_name='AA02' if cell=='AA' else ('AW_assembled29' if cell=='AW' else 'mixed04');profile=profiles['profiles'][profile_name]
   req(spec['checker_path']==profile['checker_path'] and spec['checker_sha256']==profile['checker_sha256'] and h(Path(spec['checker_path']))==profile['checker_sha256'],'Recognized frozen actual producer code, not arbitrary PASS source')
   req(h(profile['receipt_path'])==profile['receipt_sha256'],'Recognized frozen checker receipt')
   req(spec.get('checker_completed_accepted') is True,'ROOT exact real checker completion acceptance required')
   req(str(Path(spec['technical_result_path']).parent)==str(Path(spec['consumed_receipt_path']).parent) and Path(spec['consumed_receipt_path']).name=='actual_input_bindings.json' and Path(spec['technical_result_path']).name=='full29_'+cell+'_actual_results.json','Actual checker paired result/mapping layout')
   req(spec['consumed_hash_mapping_key'] is None,'Actual AA02/mixed02 mapping is plain JSON, no fabricated wrapper key')
   if cell!='AW':req(expected[cell].get(spec['manifest_path'])==spec['manifest_sha256'],'Actual checker consumed its own manifest hash')
   # AW logical manifest is generated and separately ROOT frozen; genuine producer manifests checked above.
   req(expected[cell].get(str(S/'delivery_hashes_v03.json'))=='0bffec509fae588bd2db5f8b4aedb6d14759d0a0d82a22cba62e7dcefc1dfa18','Actual checker original source03 receipt consumption')
   req(expected[cell].get(str(S/'fixed_schedule.json'))==authorization['schedule_sha256'],'Actual checker pinned tau source consumption')
  controls[cell]={'technical_result_sha256':spec['technical_result_sha256'],'consumed_receipt_sha256':spec['consumed_receipt_sha256'],'manifest_sha256':spec['manifest_sha256']}
  if cell=='WW':
   original=bound(spec['original_failed_result_path'],spec['original_failed_result_sha256']);req(original['status']=='FAIL_OR_WITHHELD_PRESERVED','WW original FAIL preservation chain')
   req(result['status']=='BOUNDED_WW_PREDICATE_CORRECTION_AND_CONSUMED_REVALIDATION_PASS' and all(result['checks'].values()),'WW bounded-only correction acceptance')
 root=checked_path(job['output_root'],F,fresh=True);root.mkdir(exist_ok=False);completed=[];phase='start';active=None
 try:
  write(root/'NORMALIZATION_START.json',{'job_path':str(job_path),'job_sha256':h(job_path),'authorization_sha256':job['authorization_sha256'],'entry_sha256':h(__file__),'controls':controls,'counts':counts,'tau_by_film':taus,'no_GT':True})
  # Four cell files of one film only are active at any time; no cohort movie JSON.
  for film in FILMS:
   for cell in CELLS:
    phase='normalize';active=[cell,film];out=root/cell/film;out.mkdir(parents=True,exist_ok=False);native_root=job['arm_inputs'][cell]['native_root_by_film'][film] if cell=='AW' else job['arm_inputs'][cell]['native_root'];native=checked_path(Path(native_root)/film,native_root);consume=Consume(native,expected[cell]);original_sha=a.sha_file
    a.sha_file=lambda p:consume(p) if Path(p).resolve(strict=False).is_relative_to(native) else h(checked_path(p))
    try:
     for rel in ('res_track.txt','direct_trace/inventory.json','direct_trace/consumer_source_binding.json','operator_states/observer_protocol.json','operator_states/frame_journal.jsonl'):consume(native/rel)
     a.ctc_prediction_film(native,counts[film],out/'prediction');a.normalize_events(native,counts[film],out/'raw_events')
     ev=convert_history(native,counts[film],out,a,consume,c.HISTORY_SCHEMA);lineage=[list(map(int,s.split())) for s in (native/'res_track.txt').read_text(encoding='utf-8-sig').splitlines() if s.strip()]
     write(out/'CONSUMED_RECEIPT.json',{'arm':cell,'film':film,'actual_files':consume.records,'original_technical_bindings':controls[cell]})
     output_bindings={str(p.relative_to(out)):h(p) for p in out.rglob('*') if p.is_file()}
     prepared_index={'status':'FILM_NORMALIZATION_PREPARED','arm':cell,'film':film,'frames':counts[film],'tau':taus[film],'lineage':lineage,'graph_schema':'persistent_ctc_track_id_v1','event_schema':c.HISTORY_SCHEMA,'events':ev,'output_bindings':output_bindings}
     phase='validate bridge';movie,events=load_one_film_bridge(out,c,prepared_index)
     for r in events:
      if r['kind']=='postprocess_M_G' and r['applicability']=='applicable':req(r['fields']['arm']==cell,'Wrong own-arm source routing metadata')
     del movie,events;prepared_index['status']='FILM_NORMALIZATION_COMPLETE';write(out/'FILM_COMPLETE.json',prepared_index);completed.append({'arm':cell,'film':film,'frames':counts[film],'film_complete_sha256':h(out/'FILM_COMPLETE.json')})
    except BaseException:
     write(out/'FILM_FAILURE.json',{'status':'PARTIAL_FILM_RETAINED','phase':phase,'exception':traceback.format_exc(),'consumed_files':consume.records});raise
    finally:a.sha_file=original_sha
  req(len(completed)==116 and sum(r['frames'] for r in completed)==4*5340,'Complete116/21360 only')
  write(root/'COHORT_COMPLETE.json',{'status':'COHORT_NORMALIZATION_COMPLETE_NOT_GT_RELEASED','films':completed,'arms':list(CELLS),'frames_per_arm':5340,'GT_authorized':False,'independent_normalization_review':'required','new_biological_N':0})
 except BaseException:
  write(root/'COHORT_FAILURE.json',{'status':'PARTIAL_COHORT_RETAINED','phase':phase,'active':active,'completed':completed,'exception':traceback.format_exc()});raise

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('job');args=p.parse_args();run_cohort(args.job)




