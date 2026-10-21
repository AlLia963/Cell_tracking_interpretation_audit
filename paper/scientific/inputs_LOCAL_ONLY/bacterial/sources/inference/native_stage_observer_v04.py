"""Read-only capture of actual author operator states; no annotation or policy changes."""
import ast
import hashlib
import inspect
import json
from pathlib import Path
import sys
import types
import numpy as np

def install_observer(predictor):
 original=predictor.post_process_masks
 func=original.__func__
 source=Path(inspect.getsourcefile(func))
 tree=ast.parse(source.read_text())
 definition=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='post_process_masks')
 def assignment(name,expression=None):
  return next(n for n in definition.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets) and (expression is None or expression in ast.unparse(n.value)))
 # A line event occurs BEFORE that line executes: select the following statement.
 transpose=assignment('masks','np.transpose(masks,')
 threshold=assignment('masks','self.mask_threshold')
 filter_cells=next(n for n in definition.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Attribute) and t.attr=='cells' for t in n.targets))
 index=definition.body.index(transpose)
 points={definition.body[index+1].lineno:'resized_probabilities',definition.body[definition.body.index(threshold)+1].lineno:'winner_threshold_binary',filter_cells.lineno:'component_retained_binary'}
 out=predictor.output_dir/'operator_states'
 out.mkdir(exist_ok=False)
 metadata={'operator_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'trace_line_points':points,'scope':'Actual local operator states; not causal whole-film counterfactuals','records':[]}
 (out/'observer_protocol.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
 def observed(self,masks,boxes):
  captured={'entry_boxes':boxes.detach().cpu().numpy().copy(), 'entry_num_TQs':np.array(self.num_TQs), 'runtime_threshold':np.array(self.threshold), 'runtime_mask_threshold':np.array(self.mask_threshold)}
  for key in ['cells','all_indices','div_track','prevcells','track_indices','object_indices','div_indices']:
   captured['entry_'+key]=np.asarray(getattr(self,key)).copy()
  def local_trace(frame,event,arg):
   if event=='line' and frame.f_lineno in points:
    captured[points[frame.f_lineno]]=np.asarray(frame.f_locals['masks']).copy()
    stage=points[frame.f_lineno]
    for key in ['cells','all_indices','div_track','prevcells','track_indices','object_indices','div_indices']:
     captured[stage+'_'+key]=np.asarray(getattr(self,key)).copy()
    captured[stage+'_num_TQs']=np.array(self.num_TQs)
    captured[stage+'_boxes']=frame.f_locals['boxes'].detach().cpu().numpy().copy()
   return local_trace
  def dispatch(frame,event,arg):
   return local_trace if frame.f_code is func.__code__ else None
  previous=sys.gettrace()
  if previous is not None:raise RuntimeError('Unexpected prior trace; observer requires untraced execution')
  try:
   sys.settrace(dispatch)
   returned=original(masks,boxes)
  except Exception as error:
   failed=out/f'frame{self.i:03d}_failed_partial.npz'
   np.savez_compressed(failed,**captured)
   journal({'frame':int(self.i),'event':'postprocess_failed','reason':repr(error),'partial_sha256':hashlib.sha256(failed.read_bytes()).hexdigest()})
   raise
  finally:sys.settrace(previous)
  for key in ['cells','all_indices','div_track','track_indices','object_indices','div_indices']:
   captured['return_'+key]=np.asarray(getattr(self,key)).copy()
  captured['return_masks']=np.asarray(returned[0]).copy()
  captured['return_boxes']=returned[1].detach().cpu().numpy().copy()
  assert all(stage in captured for stage in points.values()),captured.keys()
  destination=out/f'frame{self.i:03d}.npz'
  assert not destination.exists()
  np.savez_compressed(destination,**captured)
  metadata['records'].append({'frame':int(self.i),'entry_instances':len(captured['entry_cells']),'returned_instances':len(captured['return_cells']),'state_sha256':hashlib.sha256(destination.read_bytes()).hexdigest()})
  (out/'observer_protocol.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
  journal({'frame':int(self.i),'event':'postprocess_success','instances_in':len(captured['entry_cells']),'instances_out':len(captured['return_cells'])})
  return returned
 predictor.post_process_masks=types.MethodType(observed,predictor)

 journal_path=out/'frame_journal.jsonl'
 def journal(record):
  with journal_path.open('a',encoding='utf-8') as stream:
   stream.write(json.dumps(record)+'\n')
   stream.flush()
 current={'frame':None,'called':False}
 def finish_frame():
  if current['frame'] is None:return
  exists=(predictor.output_dir/f"mask{current['frame']:03d}.tif").exists()
  journal({'frame':current['frame'],'event':'frame_complete','operator_applicable':current['called'],'mask_saved':exists})
 original_preprocess=predictor.preprocess_img
 def preprocess(self,fp):
  finish_frame()
  current.update(frame=int(self.i),called=False)
  journal({'frame':int(self.i),'event':'frame_started','input_file':str(fp)})
  return original_preprocess(fp)
 wrapped_post=predictor.post_process_masks
 def post(self,masks,boxes):
  current['called']=True
  return wrapped_post(masks,boxes)
 original_forward=predictor.forward
 def forward(self):
  try:
   returned=original_forward()
   finish_frame()
   return returned
  except Exception as error:
   journal({'frame':current['frame'],'event':'forward_failed','reason':repr(error)})
   raise
 predictor.preprocess_img=types.MethodType(preprocess,predictor)
 predictor.post_process_masks=types.MethodType(post,predictor)
 predictor.forward=types.MethodType(forward,predictor)
