from pathlib import Path
import importlib.util,json,copy,datetime,hashlib,traceback
import numpy as np
D=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('matcher',D/'stage_matcher_v0_3.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def meta(rows,edges,flags=None):return {'status':'VALID_NATIVE_CONDITIONAL_GRAPH','entry_rows':rows,'native_cells':[9+i for i in rows],'division_flags':flags if flags is not None else [-1]*len(rows),'query_all_indices':[50+i for i in rows],'incoming_edges_previous_entryrow_current_entryrow_type':edges}
def comparable(x):x=copy.deepcopy(x);x.pop('baseline');return x
results=[];start=datetime.datetime.now(datetime.timezone.utc).isoformat()
try:
 left=m.frame([1],np.array([[[1,1,0,0]]],bool),0);right=m.frame([2],np.array([[[1,1,0,0]]],bool),1);anchor=m.frame([7],left.masks,0)
 exact=right.masks.copy();double=np.concatenate([exact,exact]);supports={'A':double,'B':exact,'C':exact,'D':exact}
 record={'frame':1,'previous_actualD_entry_rows':[7],'stages':{q:meta([0,1] if q=='A' else [0],[[7,0,0]]) for q in 'ABCD'}}
 a=m.match_window(1,anchor,supports,record,left,right,[(1,2,0)],supplied_log={'origin':'C','tau':48});b=m.match_window(1,anchor,supports,record,left,right,[(1,2,0)],supplied_log={'origin':'C','tau':48},baseline=True)
 assert comparable(a)==comparable(b)
 e=a['edges'][0];assert e['stages']['A']['target_options']==[0,1] and not e['stages']['A']['certain'] and e['stages']['A']['possible'];assert set(e['outcome_sets']['first_missing'])=={None,'A'};assert len(e['per_stage_optimal_visibility_product'])==2
 bad_refusals={}
 for label,badedge in [('exact_formal_float_counterexample',(1.9,2,0)),('bool_ID',(True,2,0)),('string_type',(1,2,'0'))]:
  try:m.match_window(1,anchor,supports,record,left,right,[badedge])
  except ValueError as error:bad_refusals[label]=str(error)
  else:raise AssertionError('silent reference coercion: '+label)
 npcase=m.match_window(np.int64(1),anchor,supports,record,left,right,[(np.int64(1),np.int64(2),np.int64(0))],supplied_log={'origin':'C','tau':48})
 assert comparable(npcase)==comparable(a)
 results.append({'name':'overlapping_A_exact_tied_optima','status':'PASS','proposed':a,'independent_sameinfo':b,'malformed_reference_refusals':bad_refusals})
 left=m.frame([1],np.array([[[1,1,1,1]]],bool),0);right=m.frame([2,3],np.array([[[1,1,0,0]],[[0,0,1,1]]],bool),1);anchor=m.frame([7],left.masks,0)
 supports={'A':right.masks,'B':right.masks,'C':right.masks,'D':right.masks[:1]}
 record={'frame':1,'previous_actualD_entry_rows':[7],'stages':{'A':meta([0,1],[[7,0,1],[7,1,1]],[0,0]),'B':meta([0,1],[[7,0,1],[7,1,1]],[0,0]),'C':meta([0,1],[[7,0,0]],[-1,-1]),'D':meta([0],[[7,0,0]],[-1])}}
 a=m.match_window(1,anchor,supports,record,left,right,[(1,2,1)]);b=m.match_window(1,anchor,supports,record,left,right,[(1,2,1)],baseline=True);assert comparable(a)==comparable(b)
 e=a['edges'][0];assert e['per_stage_optimal_visibility_product']==[[1,1,0,0]];assert e['outcome_sets']['first_missing']==e['outcome_sets']['first_interstage_loss']==e['outcome_sets']['last_interstage_loss']==['C']
 bad=copy.deepcopy(record);bad['stages']['D']['incoming_edges_previous_entryrow_current_entryrow_type']=[[7,1,0]]
 try:m.match_window(1,anchor,supports,bad,left,right,[(1,2,1)])
 except ValueError as err:refusal=str(err);assert 'endpoint/row/type' in refusal
 else:raise AssertionError('malformed D entry-row map accepted')
 results.append({'name':'cancelled_division_type_and_D_entryrow_refusal','status':'PASS','proposed':a,'independent_sameinfo':b,'invalid_rowmap_refusal':refusal})
 status='TWO_FINITE_MATCHER_CHECKS_PASS'
except BaseException as err:
 status='FAILED_RETAINED';results.append({'exception':repr(err),'traceback':traceback.format_exc()});raise
finally:
 with (D/'CHECK_RESULTS_v03.json').open('x',encoding='utf-8') as f:json.dump({'status':status,'start_UTC':start,'finish_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cases':results,'actual_GT_read':False,'scope':'two finite necessary checks, not production or universal correctness'},f,indent=2)
print(status)

