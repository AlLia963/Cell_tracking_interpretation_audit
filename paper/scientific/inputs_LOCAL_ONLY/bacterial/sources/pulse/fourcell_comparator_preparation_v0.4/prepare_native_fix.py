from pathlib import Path
import ast,json,hashlib,difflib,datetime
O=Path(__file__).resolve().parent;old=O.parent/'fourcell_comparator_preparation_v0.3';S=O.parent/'source_preparation_v0.3'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
original=(old/'analysis_v0_5.py').read_text(encoding='utf-8');assert sha(old/'analysis_v0_5.py')=='db64872251febf936823e359429c19203a0117ecbfe1243255261554cfde4d53'
start=original.index("  if kind=='before_model':\n");end=original.index("  if kind=='consumer_applicability':",start)
oldblock=original[start:end]
newblock="  if kind=='before_model':validate_before_fields(fields,r['source_topology'],context)\n"
new=original[:start]+newblock+original[end:]
helper='''
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
'''
position=new.index("if __name__=='__main__':")
new=new[:position]+helper+'\n'+new[position:]
oldline=" if a.dtype.hasobject:return array_payload(a)"
assert new.count(oldline)==1
new=new.replace(oldline,""" if a.dtype.hasobject:
  ensure(a.dtype==np.dtype('O') and a.shape==() and a.item() is None,'Actual native object array must be scalar None')
  if expected_token is not None:
   ensure(type(expected_token) is dict and set(expected_token)=={'dtype','shape','None_only'} and expected_token['dtype']=='|O' and type(expected_token['shape']) is list and expected_token['shape']==[] and expected_token['None_only'] is True,'Actual scalar None compact token schema/value/shape mismatch')
  return array_payload(a)""")
consumer_check="if kind in ('consumer_stack','consumer_effective_content','consumer_reference_points'):ensure(type(fields['output_target']) is str,'Actual output_target string')"
assert new.count(consumer_check)==1
new=new.replace(consumer_check,"if kind in ('consumer_stack','consumer_effective_content','consumer_reference_points'):ensure(type(fields['output_target']) is str and fields['output_target']==SOURCE_OUTPUT_TARGET,'Actual source03 consumer output_target must be cur_target')")
new=new.replace("ensure(type(v) in (list,tuple) and len(v)==node['length'],'Field vs sequence topology')", "ensure(type(v).__name__==kind and len(v)==node['length'],'Logical sequence must restore exact source list/tuple kind')")
# Add source pins for the exact actual selected branch, not a caller override.
pin_anchor=" 'source/src/trackformer/models/deformable_transformer.py':'1dbb6ad25f8cfc9ff6227c91a9dbdd97f0df00b77a47f8b3997afd0f80bc5fda'}"
extra=['source/src/trackformer/models/detr_tracking.py','source/src/trackformer/models/deformable_detr.py','source/src/trackformer/models/detr_segmentation.py']
assert new.count(pin_anchor)==1
new=new.replace(pin_anchor,pin_anchor[:-1]+','+','.join('\n '+repr(n)+':'+repr(sha(S/n)) for n in extra)+'}')
with (O/'analysis_v0_6.py').open('x',encoding='utf-8') as f:f.write(new)
with (O/'comparator03_to04.diff').open('x',encoding='utf-8') as f:f.write(''.join(difflib.unified_diff(original.splitlines(True),new.splitlines(True),fromfile='frozen03/analysis_v0_5.py',tofile='NEW04/analysis_v0_6.py')))
for name in ('frames_contract.json','RAW_READINESS.json'):
 with (O/name).open('xb') as f:f.write((old/name).read_bytes())
def functions(tree):return {n.name:ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,ast.FunctionDef)}
a,b=functions(ast.parse(original)),functions(ast.parse(new));changed=[n for n in a if a[n]!=b[n]];assert set(changed)=={'validate_history','verified_array_digest','validate_topology_values'}
record={'saved_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'old_actual_SHA256':sha(old/'analysis_v0_5.py'),'new_actual_SHA256':sha(O/'analysis_v0_6.py'),'changed_existing_function_AST':changed,'added_functions':sorted(set(b)-set(a)),'all_other_function_AST_unchanged':[n for n in a if a[n]==b[n]],'new_target_callchain_pins':{n:sha(S/n) for n in extra},'no_actual_arrays_model_GT_E':True}
with (O/'PREPARATION_RECORD.json').open('x',encoding='utf-8') as f:json.dump(record,f,indent=2)
print(json.dumps(record))
