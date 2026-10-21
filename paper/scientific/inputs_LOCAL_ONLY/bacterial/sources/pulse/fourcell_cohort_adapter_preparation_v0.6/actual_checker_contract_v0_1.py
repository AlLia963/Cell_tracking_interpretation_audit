"""Strict acceptance of actual frozen AA02/mixed02 report layouts.
No top-level arm is invented; known constructors, status/rows/counts, manifest
identity and ROOT exact accepted artifacts supply the own-arm binding together.
"""
import re
STATUSES={'AA':'PASS_FULL29_AA_PREDICTION_ONLY','AW':'PASS_ASSEMBLED_TWOATTEMPT29_AW_PREDICTION_ONLY','WA':'PASS_FULL29_WA_PREDICTION_ONLY','WW':'BOUNDED_WW_PREDICATE_CORRECTION_AND_CONSUMED_REVALIDATION_PASS'}
MANDATORY_COUNTS={'actual strict checkpoint load':1,'actual manifest frame counts':29,'trace exact file inventory':29,'frame complete exact domain':29,'no failed frame events':29,'actual raw four heads':5340,'bound raw pixels to actual samples bits':5340,'original consumer returned':5340,'native exact output inventory':29,'source binding':1,'observer effective source':1}
def req(v,msg):
 if not v:raise ValueError(msg)
def validate_actual_result(result,cell,counts):
 req(cell in STATUSES and result.get('status')==STATUSES[cell],'Known actual checker own-arm status only; arbitrary PASS refused')
 if cell=='WW':
  req(type(result.get('checks')) is dict and result['checks'] and all(v is True for v in result['checks'].values()),'WW bounded correction evidence all true')
  return {'profile':'WW_bounded_correction','status':result['status']}
 if cell=='AW':
  req(result.get('profile')=='AW_dualphysicalroot_twoattempt29_v0.1','Exact admitted twoattempt source profile required')
  oldroot='E:/kaggle_factorial_control_20261003_v0.2/AW';newroot='E:/kaggle_factorial_control_20261004_v0.1/AW'
  expectedhomes={f'{i:02d}':(oldroot if i<=22 else newroot) for i in range(1,30)};actual=result.get('physical_home_by_video')
  req(type(actual) is dict and set(actual)==set(counts) and all(actual[v].replace('\\','/').rstrip('/').casefold()==expectedhomes[v].casefold() for v in counts),'Exact disjoint original22/recovery7 physical roots')
  req(result.get('producer_attempt_by_video')=={f'{i:02d}':('original22' if i<=22 else 'recovery7') for i in range(1,30)},'Exact29 actual producer attempt mapping')
 # Actual frozen constructors have no top-level arm. Preserve that format.
 req(result.get('failures')==[],'Actual independent failures must be present and empty')
 checks=result.get('checks');req(type(checks) is dict and checks and all(type(n) is int and n>0 for n in checks.values()),'Completed numeric checker counts, not self-PASS flags')
 for key,want in MANDATORY_COUNTS.items():req(checks.get(key)==(2 if cell=='AW' and key in ('source binding','observer effective source') else want),'Actual completed check domain '+key)
 rows=result.get('rows');req(type(rows) is list and len(rows)==29,'Actual29 report rows')
 req(all(type(r) is dict for r in rows) and len({r.get('video') for r in rows})==29 and {r.get('video') for r in rows}==set(counts),'Own result exact29 films, no duplicates')
 total_records=0;applicable=0
 for row in rows:
  film=row['video'];n=counts[film];req(type(row.get('frames_per_run')) is int and row['frames_per_run']==n,'Actual result per-film fixed frame count')
  app=row.get('applicable_postprocess_frames');req(type(app) is int and 0<=app<=n,'Actual native applicability count')
  records=row.get('all_kind_records_per_run');req(type(records) is dict and set(records)=={cell},'Actual checker row own-arm record mapping')
  nr=records[cell];req(type(nr) is int and 3*n<=nr<=7*n,'Actual raw packet-count domain');total_records+=nr;applicable+=app
 req(sum(r['frames_per_run'] for r in rows)==5340,'Actual result total5340')
 scope=result.get('actual_applicability_scope_counts');req(type(scope) is dict,'Actual branch census required')
 for k in ('absent_query','empty_query','nonempty_query','operator_applicable','no_operator','last_frames'):req(type(scope.get(k)) is int and scope[k]>=0,'Actual strict branch count '+k)
 req(scope['absent_query']+scope['empty_query']+scope['nonempty_query']==5340,'Actual query census total')
 req(scope['operator_applicable']==applicable and applicable+scope['no_operator']==5340 and scope['last_frames']==29,'Actual native/terminal census')
 req(total_records==3*5340+applicable+3*(scope['empty_query']+scope['nonempty_query']),'Actual packet counts agree with source branch census')
 if cell in ('AW','WA'):req(scope.get('None_query')==0 and scope.get('invalid_query')==0,'Actual mixed invalid/None query branch refused')
 req(type(result.get('storage')) is dict and set(result['storage'])=={cell},'Actual own-arm storage metadata')
 # Future factorization differences/not_evaluable are observations, not failures.
 return {'profile':'AA02' if cell=='AA' else ('AW_assembled29' if cell=='AW' else 'mixed02'),'status':result['status'],'films':29,'frames':5340,'records':total_records,'applicable':applicable}

def validate_sha_mapping(mapping):
 req(type(mapping) is dict and mapping,'Complete original consumed SHA mapping required')
 req(all(type(p) is str and p and type(v) is str and re.fullmatch('[0-9a-f]{64}',v) for p,v in mapping.items()),'Actual path/SHA mapping types')
 return mapping
