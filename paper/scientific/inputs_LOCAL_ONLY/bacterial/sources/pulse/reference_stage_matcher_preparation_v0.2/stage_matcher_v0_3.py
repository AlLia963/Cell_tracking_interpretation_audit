"""Pure reference-relative matcher candidate. No GT reader or production CLI."""
from pathlib import Path
from types import SimpleNamespace
import hashlib,importlib.util,itertools
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
ENVELOPE=ROOT/'mask_ambiguity_v0.1/exact_disjoint_envelope.py'
ENVELOPE_SHA='864c95d22820ab0cfd607b795f7f71c0fe16d0c6ce0c971b24e755ef8d37514c'
def req(x,m):
 if not x:raise ValueError(m)
def integer(x,domain):
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
 ids=integer_sequence(ids,'support ID',0);masks=np.asarray(masks)
 req(masks.dtype==np.bool_ and masks.ndim==3 and len(ids)==len(masks),'boolean support row schema')
 req(len(set(ids))==len(ids),'unique candidate row IDs')
 return ids,masks
def frame(ids,masks,t):
 ids,masks=checked(ids,masks);return SimpleNamespace(ids=ids,masks=masks,frame=integer(t,"frame"))
def independent_options(pred,ref):
 """Literal same-information baseline; no call to proposed envelope."""
 req(pred.frame==ref.frame and pred.masks.shape[1:]==ref.masks.shape[1:],'registered same-frame grid')
 req(not np.any(ref.masks.sum(axis=0)>1),'reference overlapping unsupported')
 result={};owner={}
 for rid,rm in zip(ref.ids,ref.masks):
  eligible=[]
  for pid,pm in zip(pred.ids,pred.masks):
   i=int((pm&rm).sum());u=int((pm|rm).sum())
   if u and 2*i>u:
    req(pid not in owner,'strict IoU uniqueness invariant');owner[pid]=rid;eligible.append((pid,i,u))
  winners=[]
  for pid,i,u in eligible:
   if all(i*v>=j*u for _,j,v in eligible):winners.append(pid)
  result[rid]=tuple(sorted(winners))
 return result

def load_envelope():
 req(hashlib.sha256(ENVELOPE.read_bytes()).hexdigest()==ENVELOPE_SHA,'exact envelope source pin')
 s=importlib.util.spec_from_file_location('frozen_exact_envelope',ENVELOPE);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def history_bounds(stage_intervals):
 """Set bounds on four independently optimal stage correspondences, fixed anchor."""
 req(len(stage_intervals)==4,'four ABCD stages')
 bits=[]
 for certain,possible in stage_intervals:
  req(not certain or possible,'invalid visibility interval')
  bits.append([1] if certain else ([0,1] if possible else [0]))
 histories=list(itertools.product(*bits));names='ABCD';events={'first_missing':set(),'first_interstage_loss':set(),'last_interstage_loss':set(),'gain_transitions':set(),'D_missing_last_loss':set()}
 for b in histories:
  losses=[names[k+1] for k in range(3) if b[k]==1 and b[k+1]==0];gains=tuple(names[k+1] for k in range(3) if b[k]==0 and b[k+1]==1)
  events['first_missing'].add(next((names[k] for k,x in enumerate(b) if not x),None));events['first_interstage_loss'].add(losses[0] if losses else None);events['last_interstage_loss'].add(losses[-1] if losses else None);events['gain_transitions'].add(gains)
  if b[3]==0:events['D_missing_last_loss'].add(losses[-1] if losses else None)
 def status(values):return 'not_applicable' if not values else ('determined' if len(values)==1 else 'ambiguous')
 return {'outcome_sets':{k:sorted(v,key=repr) for k,v in events.items()},'product_classification_status':{k:status(v) for k,v in events.items()},'per_stage_optimal_visibility_product':[list(b) for b in histories],'observational_product_scope':'marginal stage matching optima on one fixed incoming window only; NOT feasible coupled ABCD source histories or causal witnesses','coupled_global_history':'unidentifiable_withheld'}

def match_window(t,anchor,stage_supports,record,reference_left,reference_right,reference_edges,reference_censored_edges=(),supplied_log=None,baseline=False):
 """Source schema: producer PROJECTIONS frame + compact frameNPZ supports.
 Edges are (reference previousID,currentID,type), already observed reference
 domain; censored occurrences kept unsupported, not relabelled invisible.
 """
 t=integer(t,'frame');req(t>=0,'negative frame')
 req(integer(record['frame'],'record frame')==t,'record time mismatch')
 reference_edges=[typed_edge(e,'reference edge') for e in reference_edges]
 reference_censored_edges=[typed_edge(e,'reference censored edge') for e in reference_censored_edges]
 req(len(reference_edges)==len(set(reference_edges)),'duplicate reference edge')
 req(set(reference_censored_edges)<=set(reference_edges),'orphan reference censorship')
 req(all(x>0 and y>0 for x,y,k in reference_edges),'reference original IDs must be positive')
 integer_sequence(record['previous_actualD_entry_rows'],'previous actualD entry row',0)
 if t==0:
  req(not reference_edges,'frame0 has no incoming reference edges')
  return {'status':'NOT_APPLICABLE_FRAME0','edges':[],'supplied_log':supplied_log,'origin_claim':False}
 req(record['frame']==t and len(reference_edges)==len(set(tuple(e) for e in reference_edges)),'time / duplicate reference edges')
 req(tuple(record['previous_actualD_entry_rows'])==integer_sequence(anchor.ids,'anchor entry row',0),'same-arm previous actualD row anchor')
 refleft=frame(reference_left.ids,reference_left.masks,t-1);refright=frame(reference_right.ids,reference_right.masks,t)
 anchor=frame(anchor.ids,anchor.masks,t-1)
 implementation=independent_options if baseline else load_envelope().envelope
 left=implementation(anchor,refleft)
 req(all(len(v)<=1 for v in left.values()),'shared priorD ambiguous: unsupported anchor')
 req(not np.any(anchor.masks.sum(axis=0)>1),'shared priorD overlapping unsupported')
 options={};graph={};unsupported={}
 for s in 'ABCD':
  meta=record['stages'].get(s)
  if meta is None or meta.get('status')!='VALID_NATIVE_CONDITIONAL_GRAPH':unsupported[s]='missing_stage_or_'+str(None if meta is None else meta.get('status'));continue
  pred=frame(meta['entry_rows'],stage_supports[s],t)
  integer_sequence(meta['entry_rows'],'stage entry row',0)
  integer_sequence(meta['native_cells'],'stage native cell',0)
  integer_sequence(meta['division_flags'],'stage division flag',-1)
  integer_sequence(meta['query_all_indices'],'stage query index',0)
  req(len(meta['native_cells'])==len(pred.ids)==len(meta['division_flags'])==len(meta['query_all_indices']),'actual row/native/query alignment')
  if meta['status']!='VALID_NATIVE_CONDITIONAL_GRAPH':unsupported[s]=meta['status'];continue
  edges={typed_edge(e,'native edge') for e in meta['incoming_edges_previous_entryrow_current_entryrow_type']}
  req(all(x in anchor.ids and y in pred.ids and k in (0,1) for x,y,k in edges),'native edge endpoint/row/type schema')
  graph[s]=edges;options[s]=implementation(pred,refright)
 result=[];censored={typed_edge(e,'reference censored edge') for e in reference_censored_edges}
 for edge in reference_edges:
  x,y,k=edge;req(x in refleft.ids and y in refright.ids and k in (0,1),'reference observed edge endpoint/type domain')
  if (x,y,k) in censored or unsupported:
   result.append({'reference_edge':[x,y,k],'status':'UNSUPPORTED_REFERENCE_CENSORED' if (x,y,k) in censored else 'UNSUPPORTED_NATIVE_STAGE','unsupported_stages':unsupported});continue
  intervals=[];by_stage={}
  for s in 'ABCD':
   states=[(p,q,k) in graph[s] for p in left[x] for q in options[s][y]]
   interval=(bool(states) and all(states),any(states));intervals.append(interval)
   by_stage[s]={'source_options':list(left[x]),'target_options':list(options[s][y]),'certain':interval[0],'possible':interval[1]}
  result.append({'reference_edge':[x,y,k],'status':'REFERENCE_RELATIVE_BOUNDED','stages':by_stage,**history_bounds(intervals)})
 return {'status':'WINDOW_BOUNDED_WITH_RETAINED_UNSUPPORTED' if any(e['status'].startswith('UNSUPPORTED') for e in result) else 'WINDOW_BOUNDED','edges':result,'supplied_log':supplied_log,'known_log_not_natural_cause':True,'baseline':baseline}


