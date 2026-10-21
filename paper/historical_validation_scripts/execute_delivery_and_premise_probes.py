from pathlib import Path
import copy, hashlib, importlib.util, itertools, json, shutil, subprocess, sys
import numpy as np
R=Path(__file__).resolve().parents[1];C=R/'05_附属程序候选/stage-resolved-tracking-audit-v1.2'
OLD=R.parent/'GitHub发布/2026-10-07/stage-resolved-tracking-audit/outputs/paper_20261010/analyst-path/measurement'
O=R/'02_补充证据/actual_delivery_and_probes';O.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):
    with p.open('x',encoding='utf8') as f:json.dump(x,f,ensure_ascii=False,indent=2)
def run(label,args):
    p=subprocess.run([sys.executable,'-X','utf8',*map(str,args)],capture_output=True,text=True,encoding='utf8')
    dump(O/(label+'_PROCESS.json'),{'args':list(map(str,args)),'exitcode':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
    if p.returncode:raise RuntimeError(p.stderr)
def module(name,p):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
contract=json.loads((OLD/'INPUT_AND_QUERY_CONTRACT.json').read_text(encoding='utf8'))
inputs=O/'LOCAL_ONLY_INPUTS';inputs.mkdir()
raw=[]
for key in ('reference','prediction'):
    source=Path(contract[key]['path']);target=inputs/(key+'.npz');shutil.copy2(source,target)
    assert sha(source)==sha(target)==contract[key]['sha256'];raw.append(target)
task=O/'NEW_ROOT_TASK'
args=[C/'paper/analysis_task.py','--reference',raw[0],'--prediction',raw[1],'--unit',contract['unit_in'],'--gate-um',contract['gate_um_inclusive'],'--path',*contract['reference_path'],'--proposed-value',1,'--output',task]
run('EXPLICIT_INPUT_TASK',args)
fresh=json.loads((task/'REPORT.json').read_text(encoding='utf8'));previous=json.loads((OLD/'REPORT.json').read_text(encoding='utf8'))
assert fresh==previous
binding=json.loads((task/'REPORT_BINDING.json').read_text(encoding='utf8'))
rep=module('actual_witness_replayer',C/'paper/replay_path_witness.py')
indices=fresh['whole_frame_witness_indices']['0']
run('EXPLICIT_WITNESS_REPLAY',[C/'paper/replay_path_witness.py','--report',task,'--indices',*indices,'--value',0,'--output',O/'VALID_WITNESS_REPLAY.json'])
matrix=[]
def probe(name,fn,error):
    try:result=fn()
    except ValueError as e:
        if error not in str(e):raise
        matrix.append({'probe':name,'actual_call':'replay_path_witness.replay','status':'REJECTED','message':str(e)})
    else:raise AssertionError(name+' unexpectedly accepted')
probe('bad_whole_map_index',lambda:rep.replay(task,[0,2,0],0),'index outside')
probe('wrong_claimed_value',lambda:rep.replay(task,indices,1),'differs from graph replay')
tampered=O/'TAMPERED_FAMILY_ARTIFACT';shutil.copytree(task,tampered)
ff=json.loads((tampered/'COMPLETE_FRAME_FAMILIES.json').read_text(encoding='utf8'));ff['whole_maps'][1]=ff['whole_maps'][1][:1]
(tampered/'COMPLETE_FRAME_FAMILIES.json').write_text(json.dumps(ff),encoding='utf8')
probe('bound_family_artifact_changed',lambda:rep.replay(tampered,indices,0),'hash mismatch')
sys.path.insert(0,str(C/'src'))
from portable_analysis_candidate import Graph,MaskFrame,account_from_mapping_families,account_typed_mask_window
def graph(p):
    with np.load(p,allow_pickle=False) as z:
        coords=z['coords'].astype(float,copy=True)
        if contract['unit_in']=='pixel':coords[:,1:]*=[1.625,.40625,.40625]
        return Graph(z['ids'].copy(),coords,z['edges'].copy(),'um')
ref,pred=map(graph,raw)
constructor=module('delivery_constructor',C/'paper/scientific/extras/analyst/constructor/reconstruct.py')
base=constructor.match(pred,ref,contract['gate_um_inclusive'])
family=json.loads((task/'COMPLETE_FRAME_FAMILIES.json').read_text(encoding='utf8'))['whole_maps']
whole=[]
for combo in itertools.product(*family):
    m=dict(base)
    for frame_map in combo:m.update({int(r):int(p) for r,p in frame_map.items()})
    whole.append(m)
kwargs={'cross_stage_constraints':'none_in_correspondence_estimand'}
complete=account_from_mapping_families([pred,pred],ref,[whole,whole],**kwargs)
omitted=account_from_mapping_families([pred,pred],ref,[[whole[0]],[whole[0]]],**kwargs)
edge=contract['reference_path'][:2]
fullrow=next(r for r in complete['records'] if r['reference_edge']==edge)
shortrow=next(r for r in omitted['records'] if r['reference_edge']==edge)
assert not complete['family_completeness_and_optimality_certified_by_this_module'] and not omitted['family_completeness_and_optimality_certified_by_this_module']
assert fullrow['stage_visibility_domains']==[[0,1],[0,1]] and all(len(x)==1 for x in shortrow['stage_visibility_domains'])
matrix.append({'probe':'legal_optimal_map_omitted','actual_call':'account_from_mapping_families','status':'ACCEPTED_CONDITIONALLY_NOT_CERTIFIED_COMPLETE','complete_record':fullrow,'omitted_record':shortrow,'coverage_certified':False,'comparison_against_raw_constructed_family_detects_omission':len(whole)!=1})
def reject_api(name,fn,text):
    try:fn()
    except ValueError as e:
        if text not in str(e):raise
        matrix.append({'probe':name,'status':'REJECTED_BY_ACTUAL_API','message':str(e)})
    else:raise AssertionError('Expected domain rejection: '+name)
bad=copy.deepcopy(whole[0]);r1,r2=contract['reference_path'][:2];bad[r2]=bad[r1]
reject_api('noninjective_map',lambda:account_from_mapping_families([pred,pred],ref,[[bad],[whole[0]]],**kwargs),'one-to-one')
badframe=copy.deepcopy(whole[0]);badframe[r1]=badframe[r2];badframe.pop(r2)
reject_api('wrong_frame_correspondence',lambda:account_from_mapping_families([pred,pred],ref,[[badframe],[whole[0]]],**kwargs),'same-frame')
mask=np.ones((1,2,2),dtype=bool)
refs=[MaskFrame(np.array([1]),mask.copy(),0,'constructed singleton'),MaskFrame(np.array([2]),mask.copy(),1,'constructed singleton')]
prev=MaskFrame(np.array([11]),mask.copy(),0,'constructed singleton');cur=MaskFrame(np.array([12]),mask.copy(),1,'constructed singleton')
view={'previous':prev,'current':cur,'edges':[(11,12)],'division':[]}
valid=account_typed_mask_window([view,copy.deepcopy(view)],refs,{(1,2):'continuation'})
dump(O/'VALID_TYPED_API_CONTROL.json',valid)
badtype=copy.deepcopy(view);badtype['division']=[(11,13)]
reject_api('division_label_outside_raw_edges',lambda:account_typed_mask_window([badtype,view],refs,{(1,2):'continuation'}),'subset')
badwindow=copy.deepcopy(view);badwindow['current'].frame=2
reject_api('wrong_explicit_window_frame',lambda:account_typed_mask_window([badwindow,view],refs,{(1,2):'continuation'}),'matching frame')
dump(O/'ACTUAL_INTERFACE_PROBES.json',{'matrix':matrix,'old_v11_schema_pass_was_not_API_test':True,'old_v11_bad_index_was_only_Python_index_exception':True,'replay_does_not_recertify_optimality_or_coverage':True,'unsupported_coverage_remains_conditional':True})
capargs=list(args);capargs[-1]=O/'QUERY_CAP_ONE';capargs.extend(['--query-cap',1]);run('REAL_FRONTEND_QUERY_CAP_ONE',capargs)
assert json.loads((O/'QUERY_CAP_ONE/REPORT.json').read_text(encoding='utf8'))['status']=='WITHHELD_QUERY_CAP'
dump(O/'COMPLETE.json',{'status':'ACTUAL_EXPLICIT_INPUT_DELIVERY_AND_INTERFACE_PROBES_PASS','actual_scientific_report_equal_to_existing_D47':True,'new_input_path':str(inputs),'input_bytes':sum(p.stat().st_size for p in raw),'actual_probes':len(matrix),'cap_refusal':True,'source_sha256':sha(Path(__file__)),'no_new_scientific_cohort':True})
print(json.dumps({'status':'COMPLETE','actual_probes':len(matrix),'fresh_report_equal':True}))
