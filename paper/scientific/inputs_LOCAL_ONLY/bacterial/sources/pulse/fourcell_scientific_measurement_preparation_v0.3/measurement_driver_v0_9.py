"""Retrospective four-cell per-film measurement candidate. Main requires explicit
new ROOT measurement authorization; importing pure kernels opens no reference.
Independent EP never calls proposed endpoint_score/_endpoint_impl.
"""
from pathlib import Path
import inspect,re
import numpy as np,collections,itertools,hashlib,json,math,struct,io,zipfile,importlib.util,traceback,datetime
D=Path(__file__).resolve().parent;F=D.parent;CELLS=('WW','AW','WA','AA');FILMS=tuple(f'{i:02d}' for i in range(1,30));DOMAINS=('pre','incident','beyond','no_trigger')
PINS={'entry_path':str(F/'fourcell_cohort_adapter_preparation_v0.6/normalize_cohort_v0_13.py'),'entry_sha256':'9f28ff99f8cc3573a86812644c97e95fec1cbe2b9e0e4fb41ed39a69309e8789','comparator_path':str(F/'fourcell_comparator_preparation_v0.4/analysis_v0_6.py'),'comparator_sha256':'89058bc77357554d4c896222075778a585ec81701d1ae626138449fa8ae5b4cf','reference_path':str(F.parent/'external_validation_v0.1/CTC.zip')}
def require(x,m):
 if not x:raise ValueError(m)
def sha(p):
 z=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):z.update(b)
 return z.hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def bound(p,w):require(sha(p)==w,'Bound bytes changed '+str(p));return read(p)
def write(p,v):
 with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,allow_nan=False)
def module(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def graph(movie):
 require(movie['identifier_schema']=='persistent_ctc_track_id_v1' and movie['gap_policy']=='reject_no_imputation','Persistent CTC graph only')
 arrays=[];nodes=set();occ=collections.defaultdict(list);shape=None
 for t,row in enumerate(movie['frames']):
  require(row['t']==t and type(row['t']) is int,'Contiguous frame indices');a=np.asarray(row['labels']);require(a.ndim==2 and a.size and a.dtype.kind in 'ui' and a.max()<=65535,'Nonempty rectangular integer labels')
  require(shape is None or shape==a.shape,'Spatial drift');shape=a.shape;arrays.append(a)
  for i in np.unique(a):
   if i:nodes.add((t,int(i)));occ[int(i)].append(t)
 tracks={};children=collections.defaultdict(list)
 for row in movie['lineage']:
  require(type(row) is list and len(row)==4 and all(type(v) is int for v in row),'Exact integer CTC row');i,s,e,p=row
  require(0<i<=65535 and i not in tracks and 0<=s<=e<len(arrays) and p>=0 and p!=i,'CTC interval/ID');tracks[i]=(s,e,p)
  if p:children[p].append(i)
 require(set(tracks)==set(occ),'Exact mask and lineage IDs');edges=set()
 for i,(s,e,p) in tracks.items():
  require(occ[i]==list(range(s,e+1)),'No interval gaps/imputation');edges.update((t,i,t+1,i,0) for t in range(s,e))
  if p:require(p in tracks and tracks[p][1]+1==s,'Adjacent parent/daughter interval');edges.add((s-1,p,s,i,1))
 for p,ids in children.items():require(len(ids)==2 and len({tracks[i][0] for i in ids})==1,'Two simultaneous daughters')
 given=movie['typed_edges'];require(all(type(e) is list and len(e)==5 and all(type(v) is int for v in e) for e in given),'Exact typed edge integers')
 require(len(given)==len(set(map(tuple,given))) and set(map(tuple,given))==edges,'Complete lineage-implied graph')
 return arrays,nodes,edges,shape

def reference_graph(movie):
 # Annotation profile follows observed same-label adjacency and actual supplied
 # parent relation, NOT the prediction source's binary/full-interval constraints.
 arrays=[];nodes=set();shape=None;occ=collections.defaultdict(list)
 for t,row in enumerate(movie['frames']):
  require(type(row['t']) is int and row['t']==t,'Reference ordered times');a=np.asarray(row['labels']);require(a.ndim==2 and a.size and a.dtype.kind in 'ui','Reference integer label grid');require(shape is None or shape==a.shape,'Reference spatial domain');shape=a.shape;arrays.append(a)
  for i in np.unique(a):
   if i:nodes.add((t,int(i)));occ[int(i)].append(t)
 edges={(t,i,t+1,i,0) for t,i in nodes if (t+1,i) in nodes};tracks={};censored=[];daughter_counts=collections.Counter();holes=[]
 for row in movie['lineage']:
  require(type(row) is list and len(row)==4 and all(type(v) is int for v in row),'Reference integer lineage');i,start,end,parent=row;require(i>0 and i not in tracks and 0<=start<=end<len(arrays) and parent>=0 and parent!=i,'Reference lineage metadata domain');tracks[i]=(start,end,parent)
  observed=occ.get(i,[])
  if observed!=list(range(start,end+1)):holes.append({'id':i,'declared_interval':[start,end],'observed_frames':observed})
  if parent:
   edge=(start-1,parent,start,i,1);daughter_counts[parent]+=1
   if (start-1,parent) in nodes and (start,i) in nodes:edges.add(edge)
   else:censored.append({'relation':list(edge),'reason':'reference_daughter_endpoint_unobserved'})
 for i in set(occ)-set(tracks):censored.append({'id':i,'reason':'observed_reference_ID_missing_lineage'})
 profile={'profile':'ctc_annotation_observed_support_v1','daughter_counts':dict(daughter_counts),'interval_support_metadata':holes,'censored_relations':censored,'policy':'preserve actual annotation; no bridge/imputation/no binary assumption; accepted cohort score withheld for unresolved censored relation'}
 if 'typed_edges' in movie:require(set(map(tuple,movie['typed_edges']))==edges,'Reference explicitly observed typed graph')
 return arrays,nodes,edges,shape,profile

def literal_reference_nodes(movie):
 # Separate literal pixels/set reader for unchanged proposed EP reference side.
 # No call to independent_ep, graph or reference_graph.
 pixels={};nodes=set();shape=None
 for t,row in enumerate(movie['frames']):
  image=row['labels'];shape=(len(image),len(image[0]))
  for y,line in enumerate(image):
   for x,i in enumerate(line):
    if i:nodes.add((t,i));pixels.setdefault((t,i),set()).add((y,x))
 # Use the already validated original typed edge domain. A boundary crop must
 # never infer relation time/type from relabeled local lineage start metadata.
 edges=set(map(tuple,movie['typed_edges']))
 require(len(edges)==len(movie['typed_edges']) and all(len(e)==5 and all(type(v) is int for v in e) and e[4] in (0,1) and e[2]==e[0]+1 and (e[0],e[1]) in nodes and (e[2],e[3]) in nodes for e in edges),'Validated reference edge support/type domain')
 return nodes,edges,pixels,shape

def proposed_reference_ep(pred,reference,c):
 # New reviewed reference-side wrapper only. Original EP body and prediction
 # nodes_and_edges are unchanged; native strict source-profile stays mandatory.
 env=dict(c.__dict__);env['nodes_and_edges']=lambda movie:literal_reference_nodes(movie) if movie is reference else c.nodes_and_edges(movie)
 exec(compile(inspect.getsource(c.endpoint_score),'<frozen_EP_reference_side_wrapper>','exec'),env)
 return env['endpoint_score'](pred,reference)

def strict_matches(ref,pred,t):
 # Sparse vectorized intersection table; integer comparison never uses IoU float.
 r,ra=np.unique(ref[ref>0],return_counts=True);p,pa=np.unique(pred[pred>0],return_counts=True);r_area=dict(zip(map(int,r),map(int,ra)));p_area=dict(zip(map(int,p),map(int,pa)))
 both=(ref>0)&(pred>0);pairs,counts=np.unique(np.column_stack((ref[both],pred[both])),axis=0,return_counts=True);reverse={};fractions=[];seen=set()
 for (ri,pi),inter in zip(pairs,counts):
  ri,pi,inter=int(ri),int(pi),int(inter);union=r_area[ri]+p_area[pi]-inter
  if 2*inter>union:
   require((t,pi) not in reverse and ri not in seen,'Strict >0.5 uniqueness');reverse[(t,pi)]=(t,ri);seen.add(ri);fractions.append([t,ri,pi,inter,union])
 return reverse,fractions

def independent_ep(pred,reference):
 pp,pn,pe,ps=graph(pred);rr,rn,re,rs,profile=reference_graph(reference);require(not profile['censored_relations'],'Unresolved annotated reference relation; withhold cohort scoring');require(len(pp)==len(rr) and ps==rs,'Same frame/spatial reference');inverse={};fractions=[]
 for t,(r,p) in enumerate(zip(rr,pp)):
  m,f=strict_matches(r,p,t);inverse.update(m);fractions.extend(f)
 visible=set();rawvisible=set();fp=set();rawfp=set();rawref={e[:4] for e in re}
 for edge in pe:
  t,a,u,b,k=edge;left=inverse.get((t,a));right=inverse.get((u,b));mapped=None if left is None or right is None else (*left,*right)
  if mapped in rawref:rawvisible.add(mapped)
  else:rawfp.add(edge)
  if mapped is not None and (*mapped,k) in re:visible.add((*mapped,k))
  else:fp.add(edge)
 metrics={'node_TP':len(inverse),'node_FN':len(rn)-len(inverse),'node_FP':len(pn)-len(inverse),'reference_edges':len(re),'predicted_edges':len(pe),'typed_TP':len(visible),'typed_FN':len(re)-len(visible),'typed_FP':len(fp),'untyped_TP':len(rawvisible),'untyped_FN':len(rawref)-len(rawvisible),'untyped_FP':len(rawfp)}
 for k,name in ((0,'continuation'),(1,'division_daughter')):
  ar={e for e in re if e[4]==k};ap={e for e in pe if e[4]==k};av={e for e in visible if e[4]==k};metrics.update({name+'_reference':len(ar),name+'_predicted':len(ap),name+'_TP':len(av),name+'_FN':len(ar)-len(av),name+'_FP':len(ap)-len(av)})
 return {'metrics':metrics,'visible':visible,'reference_edges':re,'matching_fractions':sorted(fractions),'predicted_fp_edges':sorted(fp),'inverse':inverse}

def domain(e,tau,n):
 require(tau is None or type(tau) is int and 0<=tau<n,'Fixed tau domain');t,a,u,b,k=e;require(u==t+1,'Adjacent edge domain')
 if tau is None:return 'no_trigger'
 return 'incident' if tau in (t,u) else 'pre' if u<tau else 'beyond'
def four_ep(film,tau,predictions,reference,scores=None):
 scores={a:independent_ep(predictions[a],reference) for a in CELLS} if scores is None else scores;n=len(reference['frames']);rows=[];domains={d:{'pattern_histogram':{''.join(map(str,b)):0 for b in itertools.product((0,1),repeat=4)},'H_histogram':{str(h):0 for h in range(-2,3)},'reference_edges':0} for d in DOMAINS}
 for edge in sorted(scores['WW']['reference_edges']):
  bits=[int(edge in scores[a]['visible']) for a in CELLS];h=bits[3]-bits[1]-bits[2]+bits[0];d=domain(edge,tau,n);pattern=''.join(map(str,bits));domains[d]['pattern_histogram'][pattern]+=1;domains[d]['H_histogram'][str(h)]+=1;domains[d]['reference_edges']+=1
  rows.append({'reference_key':[film,*edge],'domain':d,'Y':bits,'H':h,'endpoint_pattern':pattern})
 contrasts={}
 for a in CELLS[1:]:
  gain=scores[a]['visible']-scores['WW']['visible'];loss=scores['WW']['visible']-scores[a]['visible'];dt=scores[a]['metrics']['typed_TP']-scores['WW']['metrics']['typed_TP'];df=scores[a]['metrics']['typed_FP']-scores['WW']['metrics']['typed_FP'];require(dt==len(gain)-len(loss),'Gross identity/net consistency')
  direction='measured-null' if dt==df==0 else 'beneficial' if dt>=0 and df<=0 else 'harmful' if dt<=0 and df>=0 else 'mixed'
  contrasts[a]={'delta_TP':dt,'delta_FP':df,'direction':direction,'gains':list(map(list,sorted(gain))),'losses':list(map(list,sorted(loss))),'by_domain':{d:{'gains':sum(domain(e,tau,n)==d for e in gain),'losses':sum(domain(e,tau,n)==d for e in loss)} for d in DOMAINS}}
 return {'film':film,'tau':tau,'frames':n,'cell_order':list(CELLS),'metrics':{a:scores[a]['metrics'] for a in CELLS},'matching_fractions':{a:scores[a]['matching_fractions'] for a in CELLS},'edge_rows':rows,'domains':domains,'contrasts':contrasts,'empty_reference_edge_domain':not rows,'future_censored':tau is not None and tau==n-1,'H_is_internal_operator_coupling':False,'predicted_fp_edges_with_own_arm_IDs':{a:scores[a]['predicted_fp_edges'] for a in CELLS}}

def own_typed(v):
 if hasattr(v,'dtype') and hasattr(v,'shape') and hasattr(v,'sha256'):return ['array',v.dtype,list(v.shape),v.sha256]
 if v is None:return ['None']
 if type(v) in (bool,str):return [type(v).__name__,v]
 if type(v) is int:return ['int',str(v)]
 if type(v) is float:require(math.isfinite(v),'Finite scalar');return ['float64',struct.pack('>d',v).hex()]
 if type(v) in (list,tuple):return [type(v).__name__,[own_typed(x) for x in v]]
 require(type(v) is dict and all(type(k) is str for k in v),'Complete string-key history values');return ['dict',[[k,own_typed(v[k])] for k in sorted(v)]]
def fingerprint(v):return hashlib.sha256(json.dumps(own_typed(v),separators=(',',':')).encode()).hexdigest()
def semantic(event):
 fields=dict(event['fields']);top={p:dict(v) for p,v in event['source_topology'].items()}
 if event['kind']=='postprocess_M_G' and event['applicability']=='applicable':fields.pop('arm');top.pop('root/arm');top['root']['keys']=[k for k in top['root']['keys'] if k!='arm']
 for node in top.values():
  if node['type']=='dict':node['keys']=sorted(node['keys'])
 return {'applicability':event['applicability'],'context':event['context'],'fields':fields,'source_topology':top}
def independent_hist(events,tau,n,kinds):
 tables={a:{(r['t'],kinds.index(r['kind']),r['ordinal']):r for r in events[a]} for a in CELLS};pairs=[];future={}
 for a,b in itertools.combinations(CELLS,2):
  require(set(tables[a])==set(tables[b])=={(t,k,0) for t in range(n) for k in range(len(kinds))},'Complete same-information event inventory');first=None;future_kind_differences=set()
  for key in sorted(tables[a]):
   if fingerprint(semantic(tables[a][key]))!=fingerprint(semantic(tables[b][key])):
    if first is None:first={'frame':key[0],'kind':kinds[key[1]],'ordinal':key[2]}
    if tau is not None and key[0]>tau:future_kind_differences.add(kinds[key[1]])
  pairs.append({'pair':[a,b],'first_actual_difference':first,'status':'different' if first else 'equal'})
  if (a,b) in [('WW','AW'),('WA','AA')]:
   future['AW_vs_WW' if a=='WW' else 'WA_vs_AA']={'status':'not_evaluable' if tau is None or tau==n-1 else 'evaluated','actual_input_equal':not bool(future_kind_differences&{'before_model','consumer_stack','consumer_effective_content','consumer_reference_points'}),'raw_model_output_equal':'raw_model_output' not in future_kind_differences,'downstream_semantic_equal':not bool(future_kind_differences)}
 return {'status':'valid_normalized_history','supplied_intervention_origin':None if tau is None else {'stage':'C','frame':tau},'origin_source':'same supplied fixed retrospective log, not unique natural cause','pairs':pairs,'future_factorization_pairs':future,'unique_natural_error_cause':'withheld','future_censored':tau is not None and tau==n-1}

def beyond_native_domain(predictions,tau):
 result={}
 for left,right,name in [('AW','WW','AW_vs_WW'),('WA','AA','WA_vs_AA')]:
  la,ln,le,_=graph(predictions[left]);ra,rn,re,_=graph(predictions[right]);n=len(la)
  if tau is None or tau==n-1:result[name]={'status':'not_evaluable','beyond_graph_labels_equal':False};continue
  nodes_equal={v for v in ln if v[0]>tau}=={v for v in rn if v[0]>tau}
  edges_equal={v for v in le if v[0]>tau and v[2]>tau}=={v for v in re if v[0]>tau and v[2]>tau}
  labels_equal=all(np.array_equal(la[t],ra[t]) for t in range(tau+1,n))
  result[name]={'status':'evaluated','beyond_nodes_equal':nodes_equal,'beyond_typed_edges_equal':edges_equal,'beyond_labels_equal':labels_equal,'beyond_graph_labels_equal':nodes_equal and edges_equal and labels_equal,'scope':'native persistent IDs for same-source path conformance, not cross-arm reference error attribution'}
 return result

def mechanism(hist,ep,controls):
 if not controls.get('controls_independent_valid') or not controls.get('prefix_treatment_consumer_PASS'):return 'invalid_withhold'
 if ep['tau'] is None:return 'no_trigger_control_equal' if len(set(hist['output_digests'].values()))==1 and all(p['status']=='equal' for p in hist['pairs']) and len({fingerprint(ep['metrics'][a]) for a in CELLS})==1 and all(len(set(r['Y']))==1 for r in ep['edge_rows']) else 'invalid_no_trigger_parity'
 if ep['future_censored']:return 'future_not_evaluable_last_frame'
 pairs=hist['future_factorization_pairs']
 if any(v['status']!='evaluated' for v in pairs.values()):return 'not_evaluable_future'
 if any(not v['actual_input_equal'] or not v['raw_model_output_equal'] for v in pairs.values()):return 'sole_Q_path_falsification_candidate_not_unique_cause'
 if any(not v['downstream_semantic_equal'] for v in pairs.values()):return 'downstream_or_serialization_path_candidate'
 if any(not v['beyond_graph_labels_equal'] for v in pairs.values()):return 'unobserved_link_or_serialization_path_candidate'
 if any(r['domain']=='beyond' and (r['Y'][1]!=r['Y'][0] or r['Y'][2]!=r['Y'][3]) for r in ep['edge_rows']):return 'deterministic_beyond_domain_measurement_inconsistency_check_bindings_matching_events'
 return 'bounded_factorization_with_endpoint_interaction' if any(r['H'] for r in ep['edge_rows']) else 'bounded_factorization'

def reference_film(z,film,n):
 import tifffile
 prefix=f'CTC/test/{film}_GT/TRA/';actual=[k for k in z.namelist() if k.startswith(prefix+'man_track') and k.endswith('.tif')];indices={}
 for k in actual:
  match=re.fullmatch(re.escape(prefix)+r'man_track([0-9]+)\.tif',k);require(match is not None,'Reference frame filename schema');t=int(match[1]);require(t not in indices,'Duplicate reference numeric frame');indices[t]=k
 require(set(indices)==set(range(n)),'Reference exact expected numeric frame domain');names=[indices[t] for t in range(n)]
 arrays=[tifffile.imread(io.BytesIO(z.read(k))) for k in names];lineage=[]
 for line in z.read(prefix+'man_track.txt').decode('utf-8-sig').splitlines():
  if line.strip():row=[int(v) for v in line.split()];require(len(row)==4,'Reference four-column lineage');lineage.append(row)
 edges=[]
 nodes={(t,int(i)) for t,a in enumerate(arrays) for i in np.unique(a) if i};edges=[[t,i,t+1,i,0] for t,i in nodes if (t+1,i) in nodes]
 for i,s,e,p in lineage:
  if p and (s-1,p) in nodes and (s,i) in nodes:edges.append([s-1,p,s,i,1])
 movie={'identifier_schema':'ctc_annotation_observed_support_v1','gap_policy':'preserve_observed_annotation_no_imputation','frames':[{'t':t,'labels':a.tolist()} for t,a in enumerate(arrays)],'lineage':lineage,'typed_edges':sorted(edges)};reference_graph(movie);return movie

def boundary_movie(movie,start,length):
 # Crop only the source graph domain. Parent retained only when its typed edge
 # belongs to this adjacent boundary; IDs and labels are never renumbered.
 frames=[{'t':j,'labels':movie['frames'][start+j]['labels']} for j in range(length)]
 ids={int(i) for f in frames for i in np.unique(f['labels']) if i};tracks={row[0]:row for row in movie['lineage']};rows=[];given=[]
 for i in sorted(ids):
  old=tracks[i];times=[j for j,f in enumerate(frames) if i in np.unique(f['labels'])];s=min(times);e=max(times);p=old[3] if old[3] in ids and old[1]>start and old[1]<start+length else 0;rows.append([i,s,e,p])
 for edge in movie['typed_edges']:
  t,a,u,b,k=edge
  if start<=t and u<start+length:given.append([t-start,a,u-start,b,k])
 return {'identifier_schema':'persistent_ctc_track_id_v1','gap_policy':'reject_no_imputation','frames':frames,'lineage':rows,'typed_edges':given}

def reference_boundary_movie(movie,start,length,validated_edges):
 # Reference-only view: actual supports plus translated original typed edges.
 # Original lineage metadata is retained with ORIGINAL time indices; it is not
 # a locally re-inferred graph and never enters strict prediction validation.
 return {'identifier_schema':'ctc_annotation_validated_boundary_v1','gap_policy':'preserve_original_typed_edges_no_local_lineage_inference','frames':[{'t':j,'labels':movie['frames'][start+j]['labels']} for j in range(length)],'lineage':movie['lineage'],'typed_edges':[[t-start,a,u-start,b,k] for t,a,u,b,k in sorted(validated_edges) if start<=t and u<start+length],'original_reference_frame_domain':[start,start+length-1]}

def proposed_boundary_ep(pred,reference,c):
 # Same unchanged proposed EP kernel, factored over adjacent graph boundaries
 # to avoid its cross-frame totalnodes-squared search. Own baseline does not use it.
 _,_,validated_edges,_,profile=reference_graph(reference);require(not profile['censored_relations'],'Unresolved reference boundary domain');n=len(pred['frames']);visible=set();reference_edges=set();fractions=set();edgecounts=collections.Counter()
 for start in range(max(1,n-1)):
  length=min(2,n);score=proposed_reference_ep(boundary_movie(pred,start,length),reference_boundary_movie(reference,start,length,validated_edges),c)
  visible.update((start+t,a,start+u,b,k) for t,a,u,b,k in score['visible']);reference_edges.update((start+t,a,start+u,b,k) for t,a,u,b,k in score['reference_edges']);fractions.update((start+t,r,p,i,u) for t,r,p,i,u in score['matching_fractions'])
  for key,value in score['metrics'].items():
   if not key.startswith('node_'):edgecounts[key]+=value
 _,pn,_,_=graph(pred);_,rn,_,_,_=reference_graph(reference);metrics=dict(edgecounts);metrics.update({'node_TP':len(fractions),'node_FN':len(rn)-len(fractions),'node_FP':len(pn)-len(fractions)})
 return {'metrics':metrics,'visible':visible,'reference_edges':reference_edges,'matching_fractions':list(map(list,sorted(fractions)))}

NORMALIZATION_REGISTRY=F/'ROOT_FOURCELL_NORMALIZATION_ACTUAL_ACCEPTED_v0.1.json'
def validate_actual_normalization_registry(auth,e,root,complete,start,counts,taus):
 spec=auth['normalization_actual_registry']
 require(e.checked_path(spec['path'])==e.checked_path(NORMALIZATION_REGISTRY),'Fixed actual116/21360 ROOT registry required')
 accepted=bound(NORMALIZATION_REGISTRY,spec['sha256'])
 require(accepted.get('status')=='ROOT_ACCEPTED_FOURCELL_NORMALIZATION_ACTUAL_116_21360' and accepted.get('scope')=='cohort06_AW_assembledtwoattempt_fourcell_actual_normalization' and accepted.get('GT_released') is False,'Actual normalization acceptance scope, no reference release implied')
 require(e.checked_path(accepted['cohort_root'])==root and accepted.get('entry_path')==PINS['entry_path'] and accepted.get('entry_sha256')==PINS['entry_sha256'],'Actual normalized root and exact06 producer')
 require(accepted.get('cohort_complete_sha256')==auth['cohort_complete_sha256'] and accepted.get('normalization_start_sha256')==auth['normalization_start_sha256'],'Actual complete/start ROOT immutable bindings')
 require(accepted.get('arm_films')==116 and accepted.get('arm_frames')==21360 and accepted.get('frames_per_arm')==5340 and accepted.get('frames_by_film')==counts and accepted.get('tau_by_film')==taus,'Accepted exact fourcell denominators')
 require(accepted.get('technical_bindings')==start['controls']==auth['technical_bindings'] and accepted.get('actual_technical_assets')==auth['actual_technical_assets'],'No technical acceptance substitution after normalization')
 require(accepted.get('independent_gate')==auth['normalization_gate'] and accepted.get('independent_gate_receipt')==auth['normalization_gate_receipt'] and accepted.get('independent_actual_accepted') is True,'Separate completed actual normalization independent evidence')
 expected={r['arm']+'/'+r['film']:r['film_complete_sha256'] for r in complete['films']}
 require(len(expected)==116 and accepted.get('film_complete_bindings')==expected,'Exact116 completed film registry, no omitted/duplicate units')
 require(accepted.get('AW_native_roots_by_film')=={f'{i:02d}':('E:/kaggle_factorial_control_20261003_v0.2/AW/native' if i<=22 else 'E:/kaggle_factorial_control_20261004_v0.1/AW/native') for i in range(1,30)},'Preserved AW twoattempt physical source map')
 return accepted

def preflight(job_path):
 job=read(job_path);auth=bound(job['authorization_path'],job['authorization_sha256']);require(auth['status']=='FOURCELL_SCIENTIFIC_MEASUREMENT_AUTHORIZED' and auth['measurement_driver_sha256']==sha(__file__),'Separate exact ROOT measurement authorization absent');require(auth['job_scope']=={k:v for k,v in job.items() if k not in ('authorization_path','authorization_sha256')},'Exact authorized job scope')
 helper=F/'fourcell_cohort_adapter_preparation_v0.6/raw_adapters_v0_4.py';require(sha(helper)=='b44737aff9bf0222d15a46e07fafb58a2199412e9b124fcb25db45c763a35c50','Frozen actual decode helper');epath=Path(PINS['entry_path']);cpath=Path(PINS['comparator_path']);require(sha(epath)==PINS['entry_sha256'] and sha(cpath)==PINS['comparator_sha256'],'Frozen reader/kernel source');e=module('bridge06',epath);c=module('comparator04',cpath)
 require(auth['normalization_independent_accepted'] is True and auth['all_four_actual_technical_accepted'] is True,'Actual all4 technical/normalization acceptance missing')
 for key in ('normalization_gate','normalization_gate_receipt','cohort_entry_gate','cohort_entry_gate_receipt'):
  spec=auth[key];require(sha(e.checked_path(spec['path']))==spec['sha256'],'Actual accepted independent binding '+key)
 root=e.checked_path(job['cohort_root']);complete=bound(root/'COHORT_COMPLETE.json',auth['cohort_complete_sha256']);start=bound(root/'NORMALIZATION_START.json',auth['normalization_start_sha256']);require(complete['status']=='COHORT_NORMALIZATION_COMPLETE_NOT_GT_RELEASED' and set(complete['arms'])==set(CELLS) and complete['frames_per_arm']==5340,'Actual complete all4 normalization')
 counts=bound(F/'fourcell_comparator_preparation_v0.2/frames_contract.json','d9f692dd00753c9001a2c097091fea443857d64dc6ab3c6e6bbbdf58df82456e')['frames_by_film'];taus=bound(F/'source_preparation_v0.3/fixed_schedule.json','4f4d5d48295116efa4389fc4edb0b1d225ff79d26a7f684f8aa125c8b191ee22')['tau_by_video'];require(start['counts']==auth['frames_by_film']==counts and start['tau_by_film']==auth['tau_by_film']==taus,'Bound per-film counts/tau');require(sum(counts.values())==5340 and set(counts)==set(FILMS),'Exact29/5340')
 require(start['entry_sha256']==PINS['entry_sha256'] and start['controls']==auth['technical_bindings'],'Actual normalization producer/technical scope');require(set(auth['actual_technical_assets'])==set(CELLS),'All4 real bound checker reports/mappings/manifests')
 for arm,assets in auth['actual_technical_assets'].items():
  require(set(assets)=={'result','mapping','manifest'},'Three actual technical bindings per arm')
  for key,spec in assets.items():require(sha(e.checked_path(spec['path']))==spec['sha256'],'Actual accepted '+arm+'/'+key)
  require(assets['result']['sha256']==start['controls'][arm]['technical_result_sha256'] and assets['mapping']['sha256']==start['controls'][arm]['consumed_receipt_sha256'] and assets['manifest']['sha256']==start['controls'][arm]['manifest_sha256'],'Actual4 acceptance chain')
 rows=complete['films'];require(len(rows)==116 and {(r['arm'],r['film']) for r in rows}==set(itertools.product(CELLS,FILMS)) and sum(r['frames'] for r in rows)==21360,'Exact116/21360 completion domain')
 for r in rows:
  require(r['frames']==counts[r['film']],'Per-film completed denominator');out=e.checked_path(root/r['arm']/r['film'],root);index=bound(out/'FILM_COMPLETE.json',r['film_complete_sha256']);require(index['status']=='FILM_NORMALIZATION_COMPLETE' and index['arm']==r['arm'] and index['film']==r['film'] and index['frames']==r['frames'] and index['tau']==taus[r['film']],'Actual complete film identity')
  for rel,want in index['output_bindings'].items():require(sha(e.checked_path(out/rel,out))==want,'ALL116 normalized outputs bound before reference')
 validate_actual_normalization_registry(auth,e,root,complete,start,counts,taus)
 controls=bound(auth['controls_path'],auth['controls_sha256']);require(set(controls)==set(FILMS) and all(s.get('controls_independent_valid') is True and s.get('prefix_treatment_consumer_PASS') is True for s in controls.values()),'Independent technical source controls exact29')
 require(job['reference_archive_path']==PINS['reference_path'] and auth['reference_archive_path']==job['reference_archive_path'] and auth['reference_archive_independent_accepted'] is True,'Concrete reference route and independently accepted archive binding required')
 output=e.checked_path(job['output_root'],F,True)
 # First reference-byte read occurs only now, after every admission guard above.
 require(sha(e.checked_path(job['reference_archive_path']))==auth['reference_archive_sha256'],'Accepted reference archive current bytes')
 return job,auth,e,c,root,output,counts,taus,controls

def run(job_path):
 job,auth,e,c,root,out,counts,taus,controls=preflight(job_path);out.mkdir(exist_ok=False);completed=[];active=None
 try:
  write(out/'MEASUREMENT_START.json',{'driver_sha256':sha(__file__),'authorization_sha256':job['authorization_sha256'],'archive_sha256':auth['reference_archive_sha256'],'scope':'retrospective same29 common-reference measurement; no new bioN/utility/novelty','normalization_snapshot':'ROOT accepted independent full normalization; this driver prechecks normalized assets not a repeated raw full-census','TOCTOU':'perfilm raw source refs rehashed before actual decode; later mismatch invalidates whole completion'})
  with zipfile.ZipFile(job['reference_archive_path']) as z:
   for film in FILMS:
    active=film;pred={};events={}
    for arm in CELLS:pred[arm],events[arm]=e.load_one_film_bridge(root/arm/film,c)
    hist=independent_hist(events,taus[film],counts[film],c.KINDS);hist['output_digests']={a:fingerprint(pred[a]) for a in CELLS};graph_domains=beyond_native_domain(pred,taus[film]);
    for name,value in graph_domains.items():hist['future_factorization_pairs'][name].update(value)
    proposed_hist=c.history_targets(events,taus[film],counts[film]);reference=reference_film(z,film,counts[film]);reference_profile=reference_graph(reference)[4];write(out/(film+'_REFERENCE_PROFILE.json'),reference_profile);require(not reference_profile['censored_relations'],'Reference profile has unresolved censored relations; not zero-filled, cohort withheld');scores={arm:independent_ep(pred[arm],reference) for arm in CELLS};ep=four_ep(film,taus[film],pred,reference,scores)
    comparisons=[]
    for arm in CELLS:
     ours=scores[arm];proposed=proposed_boundary_ep(pred[arm],reference,c);same=all(ours[k]==proposed[k] for k in ('metrics','visible','reference_edges','matching_fractions'));comparisons.append({'arm':arm,'same_information_EP_equal':same});
     if not same:write(out/(film+'_'+arm+'_EP_MISMATCH.json'),{'own':{k:(list(map(list,sorted(v))) if isinstance(v,set) else v) for k,v in ours.items() if k!='inverse'},'proposed':{k:(list(map(list,sorted(v))) if isinstance(v,set) else v) for k,v in proposed.items()}})
     require(same,'Independent EP mismatch retained '+arm)
    hist_targets=lambda h:[{'pair':p['pair'],'status':p['status'],'first':None if p['first_actual_difference'] is None else {k:p['first_actual_difference'][k] for k in ('frame','kind','ordinal')}} for p in h['pairs']]
    same_hist=hist_targets(hist)==hist_targets(proposed_hist) and hist['supplied_intervention_origin']==proposed_hist['supplied_intervention_origin'];
    if not same_hist:write(out/(film+'_HIST_MISMATCH.json'),{'own':hist,'proposed':proposed_hist})
    require(same_hist,'Independent HIST mismatch retained')
    ctl=dict(controls[film],future_factorization_pairs=hist['future_factorization_pairs']);decision=mechanism(hist,ep,ctl);packet={'endpoint':ep,'reference_profile':reference_profile,'history_baseline':hist,'same_information_comparisons':comparisons,'same_information_HIST_equal':same_hist,'mechanism':decision,'beyond_native_graph_domain':graph_domains,'legacy04_mechanism_scope':'beyond oracle inconsistency lacks finalgraph equality premise in old04; reviewed new wrapper supplies it and preserves graph-difference candidates','foils':{'finaloutput_only':'EP visibility/incident/beyond only; historical origin unavailable from output alone','first_missing_stage':'not implemented: independent reference-to-A/B/C candidate projection needed; cannot infer natural responsibility from known intervention log','direct_same_information':'ordinary EP plus complete semantic earliest divergence and supplied log; equality means zero demonstrated information increment'},'natural_cause':'withheld','human_utility_measured':False,'new_biological_N':0}
    write(out/(film+'_measurement.json'),packet);require(not decision.startswith(('invalid','deterministic_beyond_domain_measurement_inconsistency')),'Invalid controlled/measurement contrast preserved; overall completion withheld');completed.append({'film':film,'frames':counts[film],'measurement_sha256':sha(out/(film+'_measurement.json'))});del pred,events,reference,ep,hist,scores
  require(len(completed)==29 and sum(r['frames'] for r in completed)==5340,'Complete29 only');write(out/'MEASUREMENT_COMPLETE.json',{'status':'COMPLETE_RETROSPECTIVE_29_COMPUTATIONAL_SEQUENCES','rows':completed,'film_units':29,'biological_independence':'not established','new_biological_N':0,'significance_tests':'none','SF_M1':'not closed'})
 except BaseException:
  write(out/'MEASUREMENT_FAILURE.json',{'status':'PARTIAL_WITHHELD_NOT_COMPLETE','film':active,'completed':completed,'exception':traceback.format_exc()});raise
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('job');args=p.parse_args();run(args.job)
