"""Certify complete recorded scopes after narrow native-source repair.

Retains the original failed unified run, actual successful completed commands,
and the independently executed continuation. This is not a pristine clean pass.
"""
from pathlib import Path
import datetime,hashlib,json,os,subprocess,sys,time
HERE=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,x):
    with p.open('x',encoding='utf-8')as f:json.dump(x,f,ensure_ascii=False,indent=2)
def pin(p):
    with p.open('rb')as f:h=hashlib.file_digest(f,'sha256').hexdigest()
    return {'path':str(p),'bytes':p.stat().st_size,'sha256':h}
def main():
    prior=HERE/'records/unified_r1_01';recovery=HERE/'records/bacterial_native_recovery_r1_01'
    out=HERE/'records/completion_r1_01';out.mkdir(exist_ok=False)
    assert (prior/'RUN_FAILURE.json').is_file() and not(prior/'RUN_COMPLETE.json').exists()
    old=[read(p)for p in sorted((prior/'commands').glob('*.json'))]
    assert len(old)==26
    assert sum(r['exit_code']!=r['expected_exit']for r in old)==1
    failed=[r for r in old if r['exit_code']!=r['expected_exit']][0]
    assert failed['name']=='bacterial_public_fixed_archive_and_identity_replay'
    assert read(prior/'bacterial/scientific_routes/RESULT.json')['all_completed']is True
    compared=read(prior/'bacterial/full_comparison/FULL_RECORD_COMPARISON.json')
    assert compared['all_scientific_records_equal']is True and len(compared['comparison_units'])==155
    resumed=read(recovery/'RUN_COMPLETE.json')
    assert resumed['status']=='ALL_BACTERIAL_FIXED_ARCHIVE_SOURCE_ROUTES_FULL_RECORDS_CROSSWALK_AND_PIXELS_PASS'
    assert all(r['exit_code']==0 for r in resumed['commands'])
    assert resumed['completed_archive_routes_reused']is True
    comparison=read(recovery/'CROSSWALK_AND_SPECIMEN_COMPLETE_COMPARISON.json')
    assert comparison['all_complete_objects_equal']and comparison['all_support_pixel_arrays_and_dtypes_equal']
    argv=[sys.executable,'-B','-X','utf8',str(HERE/'normalize_query_metadata_r1.py'),
          '--records',str(prior),'--output',str(out/'QUERY_NAME_SIDECAR.json')]
    t=time.perf_counter();p=subprocess.run(argv,cwd=HERE,capture_output=True,text=True,encoding='utf-8')
    metadata={'name':'normalize_selected_path_exclusivity_metadata','argv':argv,'cwd':str(HERE),
        'source':pin(HERE/'normalize_query_metadata_r1.py'),'exit_code':p.returncode,'expected_exit':0,
        'elapsed_seconds':time.perf_counter()-t,'stdout':p.stdout,'stderr':p.stderr}
    write(out/'027_metadata_COMMAND.json',metadata);assert p.returncode==0,p.stderr
    resolved={**failed,'exit_code':0,'completion_exit_code_origin':str(recovery/'RUN_COMPLETE.json'),
        'argv':[sys.executable,'-B','-X','utf8',str(HERE/'run_bacterial_packaged.py'),
            '--reuse-completed-archive',str(prior/'bacterial'),'--output',str(recovery)],
        'script':pin(HERE/'run_bacterial_packaged.py'),'elapsed_seconds':resumed['elapsed_seconds'],
        'elapsed_seconds_origin':'recorded continuation RUN_COMPLETE elapsed_seconds; excludes its final output-manifest write',
        'stdout':'Continuation completed; actual five nested command records retained in its RUN_COMPLETE.json',
        'stderr':'','original_failed_actual_attempt':failed,'pristine_single_run':False,
        'completed_original_archive_and_full_comparison_reused':True,
        'actual_successful_continuation_commands':resumed['commands']}
    resolved.pop('utc_start',None)
    logical=[resolved if r['name']==failed['name']else {**r,'reused_actual_original_command':True}for r in old]+[metadata]
    assert len(logical)==27 and all(r['exit_code']==r['expected_exit']for r in logical)
    write(out/'COMBINED_EXECUTION_COMMANDS.json',{'logical_scope_command_count':27,
        'successful_original_root_commands_reused':25,'original_root_failed_attempts_retained':1,
        'new_bacterial_continuation':str(recovery),'metadata_command_executed':True,
        'pristine_single_clean_run':False,'commands':logical})
    result={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'status':'UNIFIED_R1_COMPLETE_WITH_RETAINED_FAILURE_AND_VERIFIED_CONTINUATION',
        'command_count':27,'command_count_interpretation':'27 completed logical scopes; 25 original successful commands reused, bacterial outer repaired through actual continuation, metadata executed after repair',
        'pristine_single_clean_run':False,'original_failure_retained':str(prior/'RUN_FAILURE.json'),
        'original_execution_outputs':str(prior),'bacterial_continuation_outputs':str(recovery),
        'commands':str(out/'COMBINED_EXECUTION_COMMANDS.json'),
        'new_biological_N':0,'prior_results_known':True,'blind_validation':False,'public_release':False,
        'code_licence_granted_by_execution':False,'portable_actual_whole_map_witness_extension_included':True,
        'restricted_inputs_and_entire_working_packet_local_only':True,
        'expected_refusals_are_retained_results':True,'new_model_inference':False,'new_normalization':False,
        'archive_11_scientific_routes_pass':True,'full_bacterial_comparison_units':155,
        'native16_windows_and_complete_crosswalk_pixels_pass':True}
    write(out/'RUN_COMPLETE.json',result)
    write(out/'OUTPUT_MANIFEST.json',{'self_excluded':True,'files':[pin(p)for p in sorted(out.rglob('*'))if p.is_file()]})
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
