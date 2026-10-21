"""Run the declared-input reviewer workflow and consequential failure probes.

Only deterministic constructed coordinates are generated. All subprocess
commands and exit outcomes are retained; existing directories are refused.
"""
from pathlib import Path
import argparse, hashlib, json, os, platform, shutil, subprocess, sys
import numpy as np
import scipy

REPO = Path(__file__).resolve().parents[1]

def check(condition,message):
    if not condition: raise RuntimeError(message)

def load(path):return json.loads(Path(path).read_text(encoding='utf8'))

def bind_again(task):
    p=task/'REPORT_BINDING.json'; binding=load(p)
    for name in binding['files']:
        binding['files'][name]=hashlib.sha256((task/name).read_bytes()).hexdigest()
    p.write_text(json.dumps(binding,indent=2),encoding='utf8')

def run_review(output):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    records=[]
    def command(label,args,code=0,env=None,contains=None):
        p=subprocess.run([sys.executable,*map(str,args)],cwd=REPO,env=env,text=True,encoding='utf8',capture_output=True)
        record={'label':label,'argv':[sys.executable,*map(str,args)],'cwd':str(REPO),
                'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
        records.append(record)
        (out/'PROCESS_RECORDS.json').write_text(json.dumps(records,indent=2),encoding='utf8')
        check(p.returncode==code,label+': unexpected exit code; see PROCESS_RECORDS.json')
        if contains:check(contains in p.stdout+p.stderr,label+': required refusal marker missing')
        return p
    inputs=out/'inputs'
    command('generate_constructed_inputs',['examples/generate_review_inputs.py','--output',inputs])
    spec=load(inputs/'SPECIFICATION.json')
    for name,expected in spec['examples'].items():
        task=out/(name+'_task'); source=inputs/name
        args=['paper/analysis_task.py','--reference',source/'reference.npz','--prediction',source/'prediction.npz',
              '--unit','um','--gate-um','1.25','--path',*expected['path'],'--proposed-value',1]
        command(name+'_construction',[*args,'--output',task])
        report=load(task/'REPORT.json')
        check(report['attainable_values']==expected['attainable_values'] and
              report['independent_edge_relaxation_values']==expected['relaxation'] and
              report['complete_frame_family_sizes']==expected['family_sizes'],name+': constructed answer differs')
        command(name+'_primitive_verification',['paper/verify_primitive_path.py','--report',task,'--output',out/(name+'_verification.json')])
        for value,ix in report['whole_frame_witness_indices'].items():
            command(name+'_witness_'+value,['paper/replay_path_witness.py','--report',task,'--indices',*ix,'--value',value,'--output',out/(name+'_witness_'+value+'.json')])
        for flag,status in [('--query-cap','WITHHELD_QUERY_CAP'),('--frame-cap','WITHHELD_CONSTRUCTION')]:
            target=out/(name+flag.replace('--','_'))
            command(name+flag,[*args,flag,1,'--output',target])
            withheld=load(target/'REPORT.json')
            check(withheld['status']==status and 'attainable_values' not in withheld and 'whole_frame_witness_indices' not in withheld,'Partial answer published under cap')
    shared=out/'shared_choice_task'
    command('independent_enumerator_cap',['paper/verify_primitive_path.py','--report',shared,'--cap',1,'--output',out/'independent_cap.json'],2,contains='WITHHELD_INDEPENDENT_ENUMERATION')
    check(load(out/'independent_cap.json')['status']=='WITHHELD_INDEPENDENT_ENUMERATION','Independent cap not withheld')
    # Make a lawful subset and rebind hashes, so integrity alone cannot detect it.
    omitted=out/'omitted_legal_map';shutil.copytree(shared,omitted)
    p=omitted/'COMPLETE_FRAME_FAMILIES.json';ff=load(p);ff['whole_maps'][1]=ff['whole_maps'][1][:1]
    p.write_text(json.dumps(ff,indent=2),encoding='utf8')
    p=omitted/'REPORT.json';subset=load(p)
    subset['complete_frame_family_sizes']=[1,1,1]
    subset['complete_joint_truth_table']=[r for r in subset['complete_joint_truth_table'] if r['whole_frame_map_indices'][1]==0]
    subset['independent_edge_relaxation_values']=[0];subset['strict_relaxation_difference']=False
    subset['whole_frame_witness_indices']={'0':[0,0,0]}
    p.write_text(json.dumps(subset,indent=2),encoding='utf8');bind_again(omitted)
    command('lawful_subset_existence_replay',['paper/replay_path_witness.py','--report',omitted,'--indices',0,0,0,'--value',0,'--output',out/'subset_existence_only.json'])
    command('lawful_omission_rebound',['paper/verify_primitive_path.py','--report',omitted,'--output',out/'omission_should_not_pass.json'],1,contains='Incomplete or incorrect supplied optimum family')
    badcost=out/'altered_cost_rebound';shutil.copytree(shared,badcost)
    p=badcost/'COMPLETE_FRAME_FAMILIES.json';ff=load(p);ff['certificates'][1]['allowed_costs'][0][3]='999'
    p.write_text(json.dumps(ff),encoding='utf8');bind_again(badcost)
    command('primitive_cost_tamper_rebound',['paper/verify_primitive_path.py','--report',badcost,'--output',out/'cost_should_not_pass.json'],1,contains='Stored cost representations differ')
    command('wrong_witness_value',['paper/replay_path_witness.py','--report',shared,'--indices',0,0,0,'--value',1,'--output',out/'wrong_value_should_not_pass.json'],1,contains='Claimed value differs')
    command('out_of_range_witness',['paper/replay_path_witness.py','--report',shared,'--indices',0,2,0,'--value',0,'--output',out/'wrong_index_should_not_pass.json'],1,contains='outside supplied family')
    changed=out/'altered_bound_report';shutil.copytree(shared,changed)
    with (changed/'REPORT.json').open('a',encoding='utf8')as f:f.write(' ')
    command('bound_artifact_altered',['paper/replay_path_witness.py','--report',changed,'--indices',0,0,0,'--value',0,'--output',out/'hash_should_not_pass.json'],1,contains='hash mismatch')
    # Input-unit conflicts can reverse a graph decision; producer and independent
    # verifier must both refuse the contradictory contract before certification.
    units=out/'unit_controls';units.mkdir()
    for kind,ids,zcoord in [('reference',[1,2,3],0),('prediction',[101,102,103],1)]:
        np.savez_compressed(units/(kind+'.npz'),ids=np.array(ids,dtype=np.int64),
            coords=np.array([[t,zcoord,0,0]for t in range(3)],dtype=float),
            edges=np.array([[ids[0],ids[1]],[ids[1],ids[2]]],dtype=np.int64),unit=np.array('um'))
    unit_args=['paper/analysis_task.py','--reference',units/'reference.npz','--prediction',units/'prediction.npz',
        '--gate-um',1.25,'--path',1,2,3,'--proposed-value',1]
    unit_task=out/'correct_unit_task'
    command('correct_um_metadata',[*unit_args,'--unit','um','--output',unit_task])
    check(load(unit_task/'REPORT.json')['attainable_values']==[1],'Unit control expected recovery')
    command('correct_um_verification',['paper/verify_primitive_path.py','--report',unit_task,'--output',out/'correct_um_check.json'])
    for kind in ('reference','prediction'):
        with np.load(units/(kind+'.npz'),allow_pickle=False)as z:
            values={k:z[k].copy()for k in z.files if k!='unit'}
        np.savez_compressed(units/(kind+'_legacy.npz'),**values)
    legacy_task=out/'legacy_explicit_unit_task'
    command('no_metadata_explicit_um',['paper/analysis_task.py','--reference',units/'reference_legacy.npz',
        '--prediction',units/'prediction_legacy.npz','--unit','um','--gate-um',1.25,'--path',1,2,3,'--proposed-value',1,'--output',legacy_task])
    check(load(legacy_task/'REPORT.json')==load(unit_task/'REPORT.json'),'Legacy explicit unit changed scientific answer')
    command('no_metadata_verification',['paper/verify_primitive_path.py','--report',legacy_task,'--output',out/'legacy_unit_check.json'])
    conflict=out/'conflicting_unit_task'
    command('conflicting_cli_unit',[*unit_args,'--unit','pixel','--output',conflict],1,contains='NPZ unit metadata conflicts')
    check(not conflict.exists(),'Conflicting unit emitted a task')
    with np.load(units/'prediction.npz',allow_pickle=False)as z: values={k:z[k].copy()for k in z.files if k!='unit'}
    for label,metadata,marker in [('opposed_metadata',np.array('pixel'),'NPZ unit metadata conflicts'),
                                   ('malformed_metadata',np.array(['um']),'Invalid NPZ unit metadata')]:
        target=units/(label+'.npz');np.savez_compressed(target,**values,unit=metadata)
        dest=out/label
        command(label,['paper/analysis_task.py','--reference',units/'reference.npz','--prediction',target,
            '--unit','um','--gate-um',1.25,'--path',1,2,3,'--proposed-value',1,'--output',dest],1,contains=marker)
        check(not dest.exists(),'Invalid metadata emitted a task')
    rebound=out/'unit_contract_rebound';shutil.copytree(unit_task,rebound)
    p=rebound/'INPUT_AND_QUERY_CONTRACT.json';contract=load(p);contract['unit_in']='pixel';p.write_text(json.dumps(contract),encoding='utf8');bind_again(rebound)
    command('primitive_conflicting_unit',['paper/verify_primitive_path.py','--report',rebound,'--output',out/'unit_must_not_pass.json'],1,contains='NPZ unit metadata conflicts')
    # A checksum rebind cannot repair a report/contract semantic disagreement.
    for label,field,value,marker in [('wrong_report_proposal','proposed_value',0,'Report proposal differs'),
                                     ('wrong_query_identity','query_name','unsupported_query','query identity')]:
        target=out/label;shutil.copytree(shared,target);p=target/'REPORT.json';r=load(p);r[field]=value
        p.write_text(json.dumps(r),encoding='utf8');bind_again(target)
        command(label,['paper/verify_primitive_path.py','--report',target,'--output',out/(label+'_must_not_pass.json')],1,contains=marker)
    zero=out/'valid_proposed_zero'
    command('valid_proposed_zero',['paper/analysis_task.py','--reference',inputs/'shared_choice/reference.npz',
        '--prediction',inputs/'shared_choice/prediction.npz','--unit','um','--gate-um',1.25,'--path',1,2,3,
        '--proposed-value',0,'--output',zero])
    check(load(zero/'REPORT.json')['proposal_status']=='WITNESSED','Valid zero proposal was not admitted')
    command('valid_zero_verification',['paper/verify_primitive_path.py','--report',zero,'--output',out/'zero_proposal_check.json'])
    # Test both optimization mechanisms before any input read or output creation.
    for mechanism in ['-O','PYTHONOPTIMIZE']:
        env=os.environ.copy();env.pop('PYTHONOPTIMIZE',None)
        if mechanism=='PYTHONOPTIMIZE':env['PYTHONOPTIMIZE']='1'
        prefix=['-O']if mechanism=='-O'else[]
        target=out/('disabled_'+mechanism.replace('-',''))
        command('early_refusal_'+mechanism,[*prefix,'paper/analysis_task.py','--output',target],1,env=env,contains='CONSTRUCTOR_ASSERTIONS_DISABLED')
        check(not target.exists(),'Optimized constructor created an output')
        for relative in ['workflows/coordinate/scientific_backend/reconstruct.py',
                         'paper/scientific/extras/analyst/constructor/reconstruct.py',
                         'paper/scientific/sources/primitive/scientific_backend/reconstruct.py',
                         'paper/scientific/extensions/natural/sources/family/reconstruct.py',
                         'paper/scientific/extensions/natural/sources/local/scientific_backend/reconstruct.py']:
            code="import importlib.util, sys; from pathlib import Path; p=Path("+repr(str(REPO/relative))+"); sys.path[:0]=[str(p.parent/'sources/executed'), str(p.parent)]; s=importlib.util.spec_from_file_location('guard_probe',p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.frame_family(None,None,None,None,None,None)"
            command('direct_constructor_'+mechanism+'_'+relative,[*prefix,'-c',code],1,env=env,contains='CONSTRUCTOR_ASSERTIONS_DISABLED')
        for relative in ['paper/scientific/extras/analyst/audit_path_statement.py','workflows/coordinate/workflow.py']:
            command('direct_frontend_'+mechanism+'_'+relative,[*prefix,relative],1,env=env,contains='CONSTRUCTOR_ASSERTIONS_DISABLED')
    command('existing_output_refused',['paper/analysis_task.py','--output',shared],1,contains='Existing output refused')
    summary={'status':'REVIEW_SMOKE_PASS','python':sys.version,'executable':sys.executable,'numpy':np.__version__,'scipy':scipy.__version__,
             'platform':platform.platform(),'processes':len(records),'original_study_experiments_rerun':0,
             'constructed_controls':2,'primitive_optimum_and_coverage_verified':True,
             'lawful_omission_after_rebinding_detected':True,'optimized_constructor_entry_and_direct_calls_refused':True,
             'unit_metadata_conflicts_rejected_by_producer_and_verifier':True,
             'report_proposal_and_query_identity_checked':True,
             'study_data_included':False,'dependency_install_isolation':'See package INSTALLATION_RECEIPT.json; same host, fresh venv'}
    (out/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
    return summary

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True)
    print(json.dumps(run_review(ap.parse_args().output)))
