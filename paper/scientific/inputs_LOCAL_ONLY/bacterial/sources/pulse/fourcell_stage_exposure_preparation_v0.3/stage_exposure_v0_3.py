"""Real full-cohort stage exposure candidate; no data access at import.
Needs independently accepted cohort06 AND actual measurement09 before reference.
Output endpoint arm bits and within-arm ABCD stage bits are different objects.
"""
from pathlib import Path
from types import SimpleNamespace
import ast,collections,hashlib,importlib.util,itertools,json,traceback,zipfile
import numpy as np,tifffile
F=Path(__file__).resolve().parent.parent
CELLS=('WW','AW','WA','AA');FILMS=tuple(f'{i:02d}' for i in range(1,30))
MEAS=F/'fourcell_scientific_measurement_preparation_v0.3/measurement_driver_v0_9.py'
BRIDGE=F/'fourcell_cohort_adapter_preparation_v0.6/normalize_cohort_v0_13.py'
MATCH=F/'reference_stage_matcher_preparation_v0.2/stage_matcher_v0_3.py'
HELPER=F/'fourcell_cohort_adapter_preparation_v0.6/raw_adapters_v0_4.py'
PINS={str(MEAS):'cb98d77996b956a454035f874228b943b22ead8b86a08e6fd512a60bcdefbe7e',str(BRIDGE):'9f28ff99f8cc3573a86812644c97e95fec1cbe2b9e0e4fb41ed39a69309e8789',str(MATCH):'c75a4f3e2bbf646782d0f9771f1cf783ab672ed32d6412fde6e39c98c88bc0c5',str(HELPER):'b44737aff9bf0222d15a46e07fafb58a2199412e9b124fcb25db45c763a35c50'}

def req(value,message):
 if not value:raise ValueError(message)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def bound(path,want):req(sha(path)==want,'Current bound source changed '+str(path));return read(path)
def write(path,payload):
 with Path(path).open('x',encoding='utf-8') as f:json.dump(payload,f,indent=2,allow_nan=False)
def load(name,path):
 req(sha(path)==PINS[str(path)],'Current scientific source pin '+str(path));spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def relations(previous,cells,flags):
 # Same literal native identity/flag rule as actual WW01 producer, no argmax stage matching.
 req(len(set(map(int,previous)))==len(previous) and len(set(map(int,cells)))==len(cells),'nonunique native identity')
 req(len(cells)==len(flags),'division flag alignment');edges=[];used=set()
 for p,cell in enumerate(previous):
  found=np.flatnonzero(cells==cell)
  if not len(found):continue
  r=int(found[0]);flag=int(flags[r])
  if flag==-1:edges.append((p,r,0))
  else:
   ds=np.flatnonzero(flags==flag);req(len(ds)==2,'nonbinary native division group');req(flag not in used,'multiple native parent division group');used.add(flag);edges.extend((p,int(d),1) for d in ds)
 linked={r for _,r,k in edges if k==1};req(all(int(flag)==-1 or r in linked for r,flag in enumerate(flags)),'orphan flagged native row')
 return sorted(edges)

def project_native_frame(z,image,previous):
 """Actual native49 → per-stage supports/row/typed graphs. No algorithm rerun."""
 supports={'A':z['resized_probabilities']>0.5,'B':z['winner_threshold_binary']>0,'C':z['component_retained_binary']>0,'D':z['return_masks']>0}
 prefix={'A':'resized_probabilities','B':'winner_threshold_binary','C':'component_retained_binary','D':'return'}
 cells={s:z[k+'_cells'] for s,k in prefix.items()};flags={s:z[k+'_div_track'] for s,k in prefix.items()};queries={s:z[k+'_all_indices'] for s,k in prefix.items()}
 keep=np.flatnonzero(supports['B'].any(axis=(1,2)));req(np.array_equal(supports['C'][keep],supports['D']),'C actual M→D keep projection')
 req(all(np.array_equal(x['C'][keep],x['D']) for x in (cells,flags,queries)),'Actual C→D row mapping')
 ctc=[]
 for mask in supports['D']:
  values=np.unique(image[mask]);req(len(values)==1 and values[0]>0,'D unique actual CTC label');v=int(values[0]);req(np.array_equal(image==v,mask),'D exact final-grid support');ctc.append(v)
 req(len(ctc)==len(set(ctc))==len(set(map(int,np.unique(image)))-{0}),'Complete D label inventory')
 stages={}
 for s in 'ABCD':
  rows=keep if s=='D' else np.arange(len(cells[s]));m=supports[s];req(m.ndim==3 and m.dtype==np.bool_ and len(m)==len(rows)==len(cells[s])==len(flags[s])==len(queries[s]),'Stage row/support schema')
  edges=[];status='UNSUPPORTED_PREVIOUS_NATIVE_ANCHOR' if previous is None else 'VALID_NATIVE_CONDITIONAL_GRAPH'
  if previous is not None:
   req(np.array_equal(z['entry_prevcells'],previous['cells']),'Actual priorD identity')
   try:edges=[[int(previous['rows'][p]),int(rows[r]),k] for p,r,k in relations(previous['cells'],cells[s],flags[s])]
   except ValueError:status='UNSUPPORTED_NATIVE_RELATION'
  stages[s]={'status':status,'entry_rows':rows.tolist(),'native_cells':cells[s].tolist(),'division_flags':flags[s].tolist(),'query_all_indices':queries[s].tolist(),'incoming_edges_previous_entryrow_current_entryrow_type':edges}
 record={'stages':stages,'previous_actualD_entry_rows':[] if previous is None else previous['rows'].tolist()}
 anchor={'cells':cells['D'].copy(),'rows':keep.copy(),'masks':supports['D'].copy(),'ctc':ctc}
 return record,supports,anchor

def load_final_typed_edges(filmout,index,nframes):
 rel=str(Path('prediction')/'prediction.npz');p=filmout/rel;req(rel in index['output_bindings'] and sha(p)==index['output_bindings'][rel],'Actual normalized prediction hash BEFORE typed-edge decode')
 with np.load(p,allow_pickle=False) as z:array=z['typed_edges'].copy()
 req(array.dtype==np.int64 and array.ndim==2 and array.shape[1]==5,'Exact normalized int64 typed_edges schema')
 edges=[tuple(map(int,row)) for row in array]
 req(len(edges)==len(set(edges)) and all(0<=t<u<nframes and u==t+1 and x>0 and y>0 and k in (0,1) for t,x,u,y,k in edges),'Unique adjacent complete final CTC typed relation schema')
 return set(edges),{'prediction_path':str(p),'prediction_sha256':index['output_bindings'][rel]}

def typed_serialization_bridge(t,record,previous,current,final_edges):
 stage=record['stages']['D']
 if previous is None or stage['status']!='VALID_NATIVE_CONDITIONAL_GRAPH':return {'status':'UNSUPPORTED_D_TYPED_BRIDGE'}
 left=dict(zip(map(int,previous['rows']),previous['ctc']));right=dict(zip(stage['entry_rows'],current['ctc']))
 req(len(left)==len(previous['rows'])==len(previous['ctc']) and len(right)==len(stage['entry_rows'])==len(current['ctc']),'Exact D-entry-row→CTC bijections')
 req(len(set(left.values()))==len(left) and len(set(right.values()))==len(right),'D CTC labels unique')
 native=set()
 for x,y,k in stage['incoming_edges_previous_entryrow_current_entryrow_type']:
  req(x in left and y in right and type(k) is int and k in (0,1),'Actual D graph endpoint/type schema')
  native.add((t-1,left[x],t,right[y],k))
 final={e for e in final_edges if e[0]==t-1 and e[2]==t}
 return {'status':'EXACT_D_TYPED_SERIALIZATION_BRIDGE' if native==final else 'WITHHELD_D_TYPED_SERIALIZATION_MISMATCH','frame':t,'native_D_mapped_CTC_typed_edges':sorted(native),'final_normalized_CTC_typed_edges':sorted(final),'native_only':sorted(native-final),'final_only':sorted(final-native),'includes_false_positive_relations':True,'reference_visibility_used_as_graph_proxy':False}

def pattern_summary(patterns):
 req(type(patterns) is list and patterns,'Nonempty marginal visibility product')
 states=[]
 for raw in patterns:
  req(type(raw) is list and len(raw)==4 and all(type(x) is int and x in (0,1) for x in raw),'ABCD exact integer bits, never four arm Y')
  losses=[k for k in range(1,4) if raw[k-1]==1 and raw[k]==0];gains=[k for k in range(1,4) if raw[k-1]==0 and raw[k]==1];missing=next((k for k,v in enumerate(raw) if v==0),None)
  states.append({'pattern':''.join(map(str,raw)),'first_missing':None if missing is None else 'ABCD'[missing],'final_D_missing':raw[3]==0,'gain':bool(gains),'reloss_after_gain':any(g<l for g in gains for l in losses),'first_missing_has_later_gain':missing is not None and any(g>missing for g in gains),'last_loss':None if not losses else 'ABCD'[losses[-1]]})
 def interval(key):return {'certain':all(x[key] for x in states),'possible':any(x[key] for x in states)}
 return {'states':states,'pattern_set':[x['pattern'] for x in states],'first_missing_set':sorted({x['first_missing'] for x in states},key=repr),'D_missing':interval('final_D_missing'),'gain':interval('gain'),'reloss_after_gain':interval('reloss_after_gain'),'first_missing_has_later_gain':interval('first_missing_has_later_gain'),'scope':'marginal per-stage optimal product only; not coupled feasible history/causality'}

def analyze_stage_window(proposed,baseline,film,cell,t,endpoint_rows):
 """Fair literal same-info equivalence and lossiness of restricted summaries."""
 p=dict(proposed);b=dict(baseline);p.pop('baseline',None);b.pop('baseline',None);equal=p==b
 rows=[]
 for edge in proposed['edges']:
  x,y,k=edge['reference_edge'];key=(t-1,x,t,y,k)
  if edge['status']!='REFERENCE_RELATIVE_BOUNDED':rows.append({'reference_key':[film,*key],'cell':cell,'status':edge['status']});continue
  patterns=edge['per_stage_optimal_visibility_product'];summary=pattern_summary(patterns)
  req(key in endpoint_rows,'Actual stage/reference relation missing from measurement09 endpoint domain')
  final=endpoint_rows[key]['Y'][CELLS.index(cell)];req(type(final) is int and final in (0,1),'Endpoint arm bit schema')
  # Disjoint nativeD has unique matching; any stageD ambiguity is retained/withheld.
  dvalues={v[3] for v in patterns};req(dvalues=={final},'StageD visibility vs independently measured final typed endpoint mismatch')
  rows.append({'reference_key':[film,*key],'cell':cell,'status':'BOUNDED_REFERENCE_RELATIVE','summary':summary,'final_output_only':{'D_visible':final,'stage_origin':'unidentifiable'},'first_missing_only':{'label_set':summary['first_missing_set'],'claims_no_later_event':False},'same_information_equal':equal,'additional_information_vs_strong_baseline':0 if equal else 'mismatch_not_advantage'})
 return rows

def aggregate_film(rows,film,cell):
 supported=[r for r in rows if r['status']=='BOUNDED_REFERENCE_RELATIVE'];out={'film':film,'cell':cell,'relations':len(rows),'supported':len(supported),'unsupported':len(rows)-len(supported),'statistical_unit':'film; relation counts descriptive, not independent N','same_information_mismatches':sum(not r['same_information_equal'] for r in supported)}
 for key in ['D_missing','gain','reloss_after_gain','first_missing_has_later_gain']:
  out[key]={'certain_count':sum(r['summary'][key]['certain'] for r in supported),'possible_count':sum(r['summary'][key]['possible'] for r in supported),'denominator':len(supported)}
 return out

def execute(job_path):
 job=read(job_path);auth=bound(job['authorization_path'],job['authorization_sha256'])
 req(auth['status']=='ROOT_FOURCELL_REFERENCE_STAGE_EXPOSURE_AUTHORIZED' and auth['allow_GT_reference_read'] is True and auth['source_sha256']==sha(__file__),'New exact ROOT stage-exposure authorization')
 req(auth['job_scope']=={k:v for k,v in job.items() if k not in ('authorization_path','authorization_sha256')},'Exact stage job scope')
 me=load('measurement09_pure',MEAS);e=load('cohort06_pure',BRIDGE);m=load('stage03_pure',MATCH);a=load('raw04_pure',HELPER)
 ma=bound(auth['measurement_authorization_path'],auth['measurement_authorization_sha256']);req(ma['measurement_driver_sha256']==PINS[str(MEAS)] and ma['status']=='FOURCELL_SCIENTIFIC_MEASUREMENT_AUTHORIZED','Actual09 measurement authority')
 root=e.checked_path(job['cohort_root']);complete=bound(root/'COHORT_COMPLETE.json',ma['cohort_complete_sha256']);start=bound(root/'NORMALIZATION_START.json',ma['normalization_start_sha256']);counts=ma['frames_by_film'];taus=ma['tau_by_film']
 req(set(counts)==set(FILMS) and sum(counts.values())==5340,'Whole29 raw frame contract');me.validate_actual_normalization_registry(ma,e,root,complete,start,counts,taus)
 measurement=e.checked_path(job['measurement_root']);mc=bound(measurement/'MEASUREMENT_COMPLETE.json',auth['measurement_complete_sha256']);req(mc['status']=='COMPLETE_RETROSPECTIVE_29_COMPUTATIONAL_SEQUENCES' and len(mc['rows'])==29 and {r['film'] for r in mc['rows']}==set(FILMS),'Actual09 complete29 science required')
 accepted=bound(auth['actual_measurement_acceptance_path'],auth['actual_measurement_acceptance_sha256'])
 req(accepted['status']=='ROOT_ACCEPTED_ACTUAL_MEASUREMENT09_RETROSPECTIVE29' and accepted['measurement_driver_sha256']==PINS[str(MEAS)] and accepted['measurement_complete_sha256']==auth['measurement_complete_sha256'] and e.checked_path(accepted['measurement_root'])==measurement and accepted['independent_actual_accepted'] is True,'Separate actual09 independent acceptance required')
 registration=bound(auth['registration_path'],auth['registration_sha256']);req(set(registration)==set(FILMS),'Actual registration evidence full29')
 for film,reg in registration.items():
  req(reg['status']=='ROOT_ACCEPTED_IDENTITY_GRID_WITH_SOURCE_EVIDENCE' and reg['film']==film and reg['transform']=='identity_yx' and reg['frame_indices']==list(range(counts[film])) and reg['upstream_source_evidence_bindings'],'No inferred registration from shape equality')
  for path,h in reg['upstream_source_evidence_bindings'].items():req(sha(e.checked_path(path))==h,'Registration source-current chain')
 # Verify all compact products before any reference archive access. Actual raw sources
 # are individually hashed just before decoding; do not repeat96k source census.
 indices={}
 for r in complete['films']:
  filmout=root/r['arm']/r['film'];idx=bound(filmout/'FILM_COMPLETE.json',r['film_complete_sha256']);req(idx['status']=='FILM_NORMALIZATION_COMPLETE','Actual film complete')
  for rel,h in idx['output_bindings'].items():req(sha(e.checked_path(filmout/rel,filmout))==h,'Actual normalized compact binding')
  indices[(r['arm'],r['film'])]=idx
 req(len(indices)==116,'Actual full116 normalization indices')
 archive=Path(me.PINS['reference_path']);req(auth['reference_archive_sha256']==ma['reference_archive_sha256'] and job['reference_archive_path']==str(archive) and sha(archive)==auth['reference_archive_sha256'],'Separately authorized actual archive SHA after all gates')
 out=e.checked_path(job['output_root'],F,True);out.mkdir(exist_ok=False);done=[];active=None
 try:
  write(out/'START.json',{'source_sha256':sha(__file__),'authorization_sha256':job['authorization_sha256'],'scope':'reference-relative full4 stage exposure, no causal/information/utility advantage assumed'})
  with zipfile.ZipFile(archive) as z:
   req(len(z.namelist())==len(set(z.namelist())),'Duplicate archive members')
   for film in FILMS:
    packet=bound(measurement/(film+'_measurement.json'),next(r['measurement_sha256'] for r in mc['rows'] if r['film']==film));endpoint={(r['reference_key'][1],*r['reference_key'][2:]):r for r in packet['endpoint']['edge_rows']}
    reference=me.reference_film(z,film,counts[film]);images,nodes,edges,shape,profile=me.reference_graph(reference);req(list(shape)==registration[film]['shape'],'Actual accepted physical grid');refs=[]
    for t,image in enumerate(images):
     ids=tuple(int(x) for x in np.unique(image) if x);masks=np.stack([image==x for x in ids]) if ids else np.zeros((0,*image.shape),bool);refs.append(SimpleNamespace(frame=t,ids=ids,masks=masks))
    for cell in CELLS:
     active=[cell,film];filmout=root/cell/film;final_edges,final_binding=load_final_typed_edges(filmout,indices[(cell,film)],counts[film]);receipt=read(filmout/'CONSUMED_RECEIPT.json');expected={p:v['sha256'] for p,v in receipt['actual_files'].items()};sources=read(filmout/'array_sources.json')['sources'];selected={v['source_path'] for v in sources.values() if v['format']=='npz' and Path(v['source_path']).parent.name=='operator_states'}
     native=Path(next(iter(selected))).parent.parent if selected else None;previous=None;rows=[]
     expected_native=Path(e.AW_NATIVE_BY_FILM[film])/film if cell=='AW' else (F/'runs_v0.3'/cell/'native'/film if cell in ('WW','AA') else Path('E:/kaggle_factorial_control_20261003_v0.2/WA/native')/film)
     if native is not None:req(e.checked_path(native)==e.checked_path(expected_native) and all(Path(p).parent.parent.resolve()==native.resolve() for p in selected),'Single actual own-arm/film native physical root')
     canonical=[json.loads(line) for line in (filmout/'canonical_events.jsonl').read_text(encoding='utf-8').splitlines()];operator=[r for r in canonical if r['kind']=='native_operator'];req(len(operator)==counts[film] and {r['t'] for r in operator}==set(range(counts[film])),'Every actual normalized operator applicability once')
     applicable={r['t'] for r in operator if r['applicability']=='applicable'};req({int(Path(p).stem.removeprefix('frame')) for p in selected}==applicable,'Missing native49 only when original operator not applicable')
     with (out/(film+'_'+cell+'_stage_windows.jsonl')).open('x',encoding='utf-8') as stream:
      for t in range(counts[film]):
       if native is None or str(native/'operator_states'/f'frame{t:03d}.npz') not in selected:
        previous=None
        for f,x,g,y,k in edges:
         if f==t-1 and g==t:rows.append({'reference_key':[film,f,x,g,y,k],'cell':cell,'status':'UNSUPPORTED_NATIVE_OPERATOR_OR_PRIOR_ANCHOR'})
        stream.write(json.dumps({'frame':t,'status':'UNSUPPORTED_NATIVE_OPERATOR_OR_PRIOR_ANCHOR'})+'\n');continue
       p=native/'operator_states'/f'frame{t:03d}.npz';req(str(p) in expected and sha(p)==expected[str(p)],'Native49 source SHA before decode');payload=a.read_arrays(p,native=True);req(set(payload)==a.NATIVE49,'Exact native49')
       for v in payload.values():req(v.dtype.hasobject or np.isfinite(v).all(),'Finite stage numeric source')
       mp=native/f'mask{t:03d}.tif';req(str(mp) in expected and sha(mp)==expected[str(mp)],'Final TIFF SHA before decode');image=tifffile.imread(mp)
       record,supports,newanchor=project_native_frame(payload,image,previous);record['frame']=t
       bridge=typed_serialization_bridge(t,record,previous,newanchor,final_edges)
       if bridge['status']=='WITHHELD_D_TYPED_SERIALIZATION_MISMATCH':
        write(out/(film+'_'+cell+'_frame'+str(t)+'_D_TYPED_BRIDGE_MISMATCH.json'),dict(bridge,source_binding=final_binding,native49_path=str(p),native49_sha256=expected[str(p)]))
        stream.write(json.dumps({'frame':t,'status':bridge['status'],'bridge':bridge})+'\n')
        raise ValueError('Full typed D→serialization graph premise fails; both domains retained; no stage/endpoint equivalence classified')
       if t and previous is not None and not profile['censored_relations']:
        req(refs[t-1].frame==t-1 and refs[t].frame==t and previous['frame']==t-1,'Exact adjacent original times');req(all(v.shape[1:]==shape for v in supports.values()),'Accepted stage/reference grids')
        anchor=SimpleNamespace(frame=t-1,ids=tuple(previous['rows']),masks=previous['masks']);local=[(x,y,k) for f,x,g,y,k in sorted(edges) if f==t-1 and g==t]
        proposed=m.match_window(t,anchor,supports,record,refs[t-1],refs[t],local,supplied_log={'stage':'C','frame':taus[film]});baseline=m.match_window(t,anchor,supports,record,refs[t-1],refs[t],local,supplied_log={'stage':'C','frame':taus[film]},baseline=True)
        windowrows=analyze_stage_window(proposed,baseline,film,cell,t,endpoint);rows.extend(windowrows);stream.write(json.dumps({'frame':t,'proposed':proposed,'strong_same_information':baseline,'comparisons':windowrows})+'\n')
        req(all(r.get('same_information_equal',True) for r in windowrows),'Same-info mismatch retained, not advantage')
       elif t:
        reason='UNSUPPORTED_REFERENCE_CENSORSHIP' if profile['censored_relations'] else 'UNSUPPORTED_PREVIOUS_NATIVE_ANCHOR'
        rows.extend({'reference_key':[film,f,x,g,y,k],'cell':cell,'status':reason} for f,x,g,y,k in edges if f==t-1 and g==t);stream.write(json.dumps({'frame':t,'status':reason})+'\n')
       newanchor['frame']=t;previous=newanchor
     req(len(rows)==len(edges) and len({tuple(r['reference_key']) for r in rows})==len(edges),'Every reference relation once, unsupported retained')
     summary=aggregate_film(rows,film,cell)
     summary['same_information_EP_equal_by_arm']={r['arm']:r['same_information_EP_equal'] for r in packet['same_information_comparisons']}
     summary['same_information_HIST_equal']=packet['same_information_HIST_equal']
     summary['final_typed_graph_source_binding']=final_binding
     summary['D_bridge_scope']='Exact full incoming typed relation set including FP; unsupported native/priorD windows retained separately'
     req(set(summary['same_information_EP_equal_by_arm'])==set(CELLS),'Original complete4 EP comparison')
     summary['comparison_scope']='Strong EP/HIST and stage literal baseline have supplied same information; endpoint-only/firstmissing restricted summaries are not equal-budget superiority comparators'
     write(out/(film+'_'+cell+'_summary.json'),summary);done.append(summary)
  req(len(done)==116,'Complete116 arm-films');write(out/'COMPLETE.json',{'status':'COMPLETE_FOURCELL_REFERENCE_RELATIVE_STAGE_EXPOSURE','arm_films':116,'film_units':29,'relations_descriptive_only':True,'rows':done,'novel_information_vs_sameinfo_baseline':'not demonstrated','natural_cause':'unidentifiable','human_utility':'not measured','SF_M1':'open'})
 except BaseException:
  write(out/'FAILURE.json',{'active':active,'completed':done,'exception':traceback.format_exc(),'overall_complete':False});raise

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('job');args=parser.parse_args();execute(args.job)
