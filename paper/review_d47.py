"""Rebuild, independently verify and replay the authorized worked audit.

Input-root must contain reference.npz and prediction.npz. No competition
inputs are included in the repository. Optional frozen-result comparison
occurs only after fresh construction, checking and refusal.
"""
from pathlib import Path
import argparse,json,subprocess,sys

REPO=Path(__file__).resolve().parents[1]

def run(input_root,output,expected_report=None):
    source=Path(input_root).resolve();out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    records=[]
    def command(label,args):
        p=subprocess.run([sys.executable,*map(str,args)],cwd=REPO,text=True,encoding='utf8',capture_output=True)
        records.append({'label':label,'argv':[sys.executable,*map(str,args)],'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
        (out/'PROCESS_RECORDS.json').write_text(json.dumps(records,indent=2),encoding='utf8')
        if p.returncode:raise RuntimeError(label+': see PROCESS_RECORDS.json')
    args=['paper/analysis_task.py','--reference',source/'reference.npz','--prediction',source/'prediction.npz',
          '--unit','pixel','--gate-um',7,'--path',156000000073,157000000073,158000000073,'--proposed-value',1]
    command('construct',[*args,'--output',out/'task'])
    command('primitive_verification',['paper/verify_primitive_path.py','--report',out/'task','--output',out/'PRIMITIVE_VERIFICATION.json'])
    report=json.loads((out/'task/REPORT.json').read_text(encoding='utf8'))
    if not(report['attainable_values']==[0] and report['independent_edge_relaxation_values']==[0,1] and report['complete_frame_family_sizes']==[1,2,1] and report['proposal_status']=='REJECTED_UNATTAINABLE'):
        raise RuntimeError('Worked audit did not reproduce the declared decision')
    command('witness',['paper/replay_path_witness.py','--report',out/'task','--indices',*report['whole_frame_witness_indices']['0'],'--value',0,'--output',out/'WITNESS_REPLAY.json'])
    command('cap_refusal',[*args,'--query-cap',1,'--output',out/'query_cap_one'])
    cap=json.loads((out/'query_cap_one/REPORT.json').read_text(encoding='utf8'))
    if cap['status']!='WITHHELD_QUERY_CAP' or 'attainable_values'in cap:raise RuntimeError('No genuine no-answer cap refusal')
    zero_args=list(args);zero_args[-1]=0
    command('valid_proposed_zero',[*zero_args,'--output',out/'proposed_zero'])
    zero=json.loads((out/'proposed_zero/REPORT.json').read_text(encoding='utf8'))
    if zero['proposal_status']!='WITNESSED' or zero['proposed_value']!=0 or zero['attainable_values']!=[0]:
        raise RuntimeError('Valid attainable-zero proposal was not admitted')
    command('zero_primitive_verification',['paper/verify_primitive_path.py','--report',out/'proposed_zero','--output',out/'ZERO_PRIMITIVE_VERIFICATION.json'])
    comparison=None
    if expected_report is not None:
        comparison=report==json.loads(Path(expected_report).read_text(encoding='utf8'))
        if not comparison:raise RuntimeError('Fresh complete scientific report differs from frozen record')
    summary={'status':'WORKED_AUDIT_REVIEW_PASS','family_sizes':[1,2,1],'attainable_values':[0],
             'independent_edge_relaxation_values':[0,1],'primitive_optimality_and_coverage_checked':True,
             'witness_replay':'PASS','query_cap_one':'WITHHELD_QUERY_CAP','frozen_complete_scientific_report_equal':comparison,
             'same_real_inputs_valid_zero_proposal':'WITNESSED_AND_INDEPENDENTLY_VERIFIED',
             'new_biological_experiment':False,'historical_timing_rerun':False,'same_host_fresh_venv':None,
             'environment_provenance':'Freshness and host identity are not determined by this script; use the separate installation/execution receipt',
             'python_executable':sys.executable,'virtual_environment':sys.prefix!=sys.base_prefix}
    (out/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
    return summary

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--input-root',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--expected-report',type=Path)
    args=ap.parse_args();print(json.dumps(run(args.input_root,args.output,args.expected_report)))
