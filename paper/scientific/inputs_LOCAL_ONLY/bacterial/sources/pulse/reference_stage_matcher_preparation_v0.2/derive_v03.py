from pathlib import Path
import hashlib,json,datetime,ast,difflib
D=Path(__file__).resolve().parent;F=D.parent;old=F/'reference_stage_matcher_preparation_v0.1';gate=F/'reference_stage_matcher_independent_gate_v0.1'
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert h(old/'DELIVERY_HASHES.json')=='9f90404e07b2bd954f1eab0b7e219010bd104cd1ef87412f9534bf0e9085406c'
assert h(gate/'DELIVERY_HASHES.json' if (gate/'DELIVERY_HASHES.json').exists() else gate/'delivery_hashes.json')=='fd9d98fcbba2945b3a9f2dfb57c79ffbb4374772b875ed04921eb3571b829848'
x=(old/'stage_matcher_v0_2.py').read_text(encoding='utf-8-sig')
x=x.replace('def checked(ids,masks):\n ids=tuple(map(int,ids));masks=np.asarray(masks)', '''def integer(x,domain):
 req(isinstance(x,(int,np.integer)) and not isinstance(x,(bool,np.bool_)),domain+' requires integer, not bool/float/string')
 return int(x)
def integer_sequence(values,domain,minimum=None):
 values=tuple(integer(x,domain) for x in values)
 req(minimum is None or all(x>=minimum for x in values),domain+' out of range')
 return values
def typed_edge(e,domain):
 req(isinstance(e,(tuple,list)) and len(e)==3,domain+' triple required')
 x,y,k=integer_sequence(e,domain)
 req(x>=0 and y>=0 and k in (0,1),domain+' endpoint/type out of domain')
 return x,y,k
def checked(ids,masks):
 ids=integer_sequence(ids,'support ID',0);masks=np.asarray(masks)''')
x=x.replace('frame=int(t)','frame=integer(t,"frame")')
x=x.replace("'history_status':{k:status(v) for k,v in events.items()},'admissible_binary_histories':[list(b) for b in histories],'Cartesian_scope':'definition: independent per-stage optimal correspondence choices; shared unique previousD anchor fixed; not statistical independence or coupled global matching'", "'product_classification_status':{k:status(v) for k,v in events.items()},'per_stage_optimal_visibility_product':[list(b) for b in histories],'observational_product_scope':'marginal stage matching optima on one fixed incoming window only; NOT feasible coupled ABCD source histories or causal witnesses','coupled_global_history':'unidentifiable_withheld'")
x=x.replace(" if t==0:return", " t=integer(t,'frame');req(t>=0,'negative frame')\n req(integer(record['frame'],'record frame')==t,'record time mismatch')\n reference_edges=[typed_edge(e,'reference edge') for e in reference_edges]\n reference_censored_edges=[typed_edge(e,'reference censored edge') for e in reference_censored_edges]\n req(len(reference_edges)==len(set(reference_edges)),'duplicate reference edge')\n req(set(reference_censored_edges)<=set(reference_edges),'orphan reference censorship')\n req(all(x>0 and y>0 for x,y,k in reference_edges),'reference original IDs must be positive')\n integer_sequence(record['previous_actualD_entry_rows'],'previous actualD entry row',0)\n if t==0:\n  req(not reference_edges,'frame0 has no incoming reference edges')\n  return")
x=x.replace("req(record['previous_actualD_entry_rows']==list(anchor.ids)","req(tuple(record['previous_actualD_entry_rows'])==integer_sequence(anchor.ids,'anchor entry row',0)")
x=x.replace("  req(len(meta['native_cells'])", "  integer_sequence(meta['entry_rows'],'stage entry row',0)\n  integer_sequence(meta['native_cells'],'stage native cell',0)\n  integer_sequence(meta['division_flags'],'stage division flag',-1)\n  integer_sequence(meta['query_all_indices'],'stage query index',0)\n  req(len(meta['native_cells'])")
x=x.replace('tuple(map(int,e)) for e in meta[',"typed_edge(e,'native edge') for e in meta[")
x=x.replace('tuple(map(int,e)) for e in reference_censored_edges','typed_edge(e,\'reference censored edge\') for e in reference_censored_edges')
x=x.replace('x,y,k=map(int,edge);','x,y,k=edge;')
ast.parse(x)
with (D/'stage_matcher_v0_3.py').open('x',encoding='utf-8') as f:f.write(x)
with (D/'SOURCE_DIFF.patch').open('x',encoding='utf-8') as f:f.write(''.join(difflib.unified_diff((old/'stage_matcher_v0_2.py').read_text(encoding='utf-8-sig').splitlines(True),x.splitlines(True),fromfile='immutable v02',tofile='new v03')))
check=(old/'check_two_cases_v0_2.py').read_text(encoding='utf-8-sig').replace('stage_matcher_v0_2.py','stage_matcher_v0_3.py').replace('CHECK_RESULTS_v02.json','CHECK_RESULTS_v03.json').replace('admissible_binary_histories','per_stage_optimal_visibility_product')
needle=" results.append({'name':'overlapping_A_exact_tied_optima'"
addition=""" bad_refusals={}
 for label,badedge in [('exact_formal_float_counterexample',(1.9,2,0)),('bool_ID',(True,2,0)),('string_type',(1,2,'0'))]:
  try:m.match_window(1,anchor,supports,record,left,right,[badedge])
  except ValueError as error:bad_refusals[label]=str(error)
  else:raise AssertionError('silent reference coercion: '+label)
 npcase=m.match_window(np.int64(1),anchor,supports,record,left,right,[(np.int64(1),np.int64(2),np.int64(0))],supplied_log={'origin':'C','tau':48})
 assert comparable(npcase)==comparable(a)
"""
check=check.replace(needle,addition+needle).replace("'proposed':a,'independent_sameinfo':b})", "'proposed':a,'independent_sameinfo':b,'malformed_reference_refusals':bad_refusals})",1)
with (D/'check_minimal_v03.py').open('x',encoding='utf-8') as f:f.write(check)
with (D/'PRE_CHECK_FREEZE.json').open('x',encoding='utf-8') as f:json.dump({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':{p.name:h(p) for p in D.iterdir() if p.is_file()},'formal_old_NO_GO_receipt':'fd9d98fcbba2945b3a9f2dfb57c79ffbb4374772b875ed04921eb3571b829848'},f,indent=2)
