"""Unified entry to the finalized LOCAL ONLY standalone bacterial source capsule."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,subprocess,sys,time,traceback
HERE=Path(__file__).resolve().parent
CAPSULE=HERE/'inputs_LOCAL_ONLY/bacterial'
def pin(p):
    with p.open('rb')as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    return {'path':str(p),'bytes':p.stat().st_size,'sha256':sha}
def write(p,x):
    with p.open('x',encoding='utf-8')as f:json.dump(x,f,ensure_ascii=False,indent=2)
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--reuse-completed-archive',type=Path,help='Explicit prior failed outer run whose all11 routes and full scientific comparison actually completed; immutable prior records are retained')
    a=ap.parse_args()
    out=a.output.resolve();out.mkdir(exist_ok=False);began=time.perf_counter();calls=[]
    if not(CAPSULE/'FINALIZED_LOCAL_ONLY.json').exists():raise FileNotFoundError('Finalized bacterial capsule required')
    reused=None
    if a.reuse_completed_archive:
        reused=a.reuse_completed_archive.resolve()
        previous_manifest=reused/'INPUT_SOURCE_TARGETS_BEFORE_EXECUTION.json'
        prior=read(previous_manifest);checks=[]
        for r in prior['files']:
            p=Path(r['path']);st=p.stat()
            assert st.st_size==r['bytes'] and st.st_mtime_ns<=previous_manifest.stat().st_mtime_ns, 'Prior input changed: '+str(p)
            if p.suffix=='.py':assert pin(p)['sha256']==r['sha256'], 'Scientific source changed: '+str(p)
            checks.append({'path':r['path'],'bytes':r['bytes'],'sha256':r['sha256'],
                'current_size_equal':True,'mtime_not_after_previous_manifest':True,
                'python_source_current_hash_equal':True if p.suffix=='.py'else None})
        assert read(reused/'scientific_routes/RESULT.json')['all_completed']is True
        assert read(reused/'full_comparison/FULL_RECORD_COMPARISON.json')['all_scientific_records_equal']is True
        write(out/'COMPLETED_ARCHIVE_REUSE_RECEIPT.json',{'prior_failed_outer_run':str(reused),
            'all11_completed_scientific_routes_reused':True,'all155_complete_record_comparisons_reused':True,
            'prior_failure_logs_retained':True,'prior_manifest':pin(previous_manifest),
            'prior_source_input_size_mtime_checks':checks,'no_second_unchanged_input_hash_pass':True})
        repair=read(HERE/'SELECTED_NATIVE_INPUT_REPAIR_RECEIPT.json')
        input_pins=[pin(HERE/r['path'])for r in repair['added_files']]+[pin(CAPSULE/'SELECTED_NATIVE_ROOT_MAP.json')]
    else:input_pins=[pin(p)for p in sorted(CAPSULE.rglob('*'))if p.is_file()and '__pycache__'not in p.parts and p.suffix!='.pyc']
    write(out/'INPUT_SOURCE_TARGETS_BEFORE_EXECUTION.json',{'local_only':True,'files':input_pins,
        'all_supplied_new_native_inputs_hashed_before_scientific_execution':True,
        'prior_full_archive_manifest_reused':str(reused/'INPUT_SOURCE_TARGETS_BEFORE_EXECUTION.json')if reused else None,
        'prior_targets_known':True,'scientific_producers_consume_target_answers':False})
    def call(name,script,arguments):
        argv=[sys.executable,'-B','-X','utf8',str(CAPSULE/script),*map(str,arguments)]
        t=time.perf_counter();env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1';env['PYTHONUTF8']='1'
        p=subprocess.run(argv,cwd=CAPSULE,env=env,capture_output=True,text=True,encoding='utf-8')
        record={'name':name,'argv':argv,'cwd':str(CAPSULE),'script':pin(CAPSULE/script),
            'exit_code':p.returncode,'elapsed_seconds':time.perf_counter()-t,'stdout':p.stdout,'stderr':p.stderr}
        write(out/(name+'_COMMAND.json'),record);calls.append(record)
        print(json.dumps({'bacterial_command':name,'exit_code':p.returncode,'elapsed_seconds':record['elapsed_seconds']}),flush=True)
        if p.returncode:raise RuntimeError('Bacterial command failed; full logs retained: '+name)
    try:
        root=CAPSULE/'fixed_archive_root';routes=reused/'scientific_routes'if reused else out/'scientific_routes'
        if reused:
            for name in ['all11_standalone_routes','complete_scientific_record_comparison']:
                record=read(reused/(name+'_COMMAND.json'));assert record['exit_code']==0
                calls.append({**record,'reused_completed_actual_command':True,'reused_origin_record':str(reused/(name+'_COMMAND.json'))})
        else:
            call('all11_standalone_routes','run_clean_archive.py',['--input-root',root,'--output',routes])
            call('complete_scientific_record_comparison','compare_scientific_records.py',
                 ['--new-root',routes,'--targets-root',CAPSULE/'results','--output',out/'full_comparison'])
        comparison=read((reused if reused else out)/'full_comparison/FULL_RECORD_COMPARISON.json')
        assert comparison['all_scientific_records_equal'] is True
        call('native16_window_actual_support_type_and_pixel_replay','rematch_stage.py',
             ['--input-root',root,'--native-root-map',CAPSULE/'SELECTED_NATIVE_ROOT_MAP.json',
              '--windows','21:57,21:61,21:62,29:41','--output',out/'native_windows'])
        call('complete_relation_event_chain_and_exact_specimen_crosswalk','identity_crosswalk.py',
             ['--input-root',root,'--timing-root',routes/'timing/measurement',
              '--chains-root',routes/'chains/measurement','--native-window-root',out/'native_windows',
              '--output',out/'identity_crosswalk'])
        call('actual_append_authority_boundaries','validate_duty_boundary.py',
             ['--input-root',root,'--authority',routes/'duties/authority.json','--output',out/'duty_boundaries'])
        # Full science comparisons for the newly generated crosswalk and specimen.
        expected=CAPSULE/'results/identity_crosswalk_standalone_run04';difference_records=[]
        for name in ['ALL123_WRONG_TYPE_RELATION_EVENT_CROSSWALK.json','EVENT_UNITS.json',
                     'ALL30_STRICT_CHAIN_INCOMING_EVENT_CROSSWALK.json',
                     'FIGURE4_EXACT_SINGLE_RELATION_AND_COMPANION_TYPE_TABLE.json','RESULT.json']:
            target=read(expected/name);actual=read(out/'identity_crosswalk'/name)
            assert target==actual,'Crosswalk complete scientific object differs: '+name
            difference_records.append({'file':name,'expected':pin(expected/name),'actual':pin(out/'identity_crosswalk'/name),'complete_object_differences':[]})
        import numpy as np
        pixels='FIGURE4_29_040_041_SUPPORT_PIXELS.npz'
        with np.load(expected/pixels,allow_pickle=False)as left,np.load(out/'identity_crosswalk'/pixels,allow_pickle=False)as right:
            assert set(left.files)==set(right.files)
            assert all(left[k].dtype==right[k].dtype and np.array_equal(left[k],right[k])for k in left.files)
        write(out/'CROSSWALK_AND_SPECIMEN_COMPLETE_COMPARISON.json',{'all_complete_objects_equal':True,
            'records':difference_records,'all_support_pixel_arrays_and_dtypes_equal':True,'science_fields_excluded':[]})
        result={'status':'ALL_BACTERIAL_FIXED_ARCHIVE_SOURCE_ROUTES_FULL_RECORDS_CROSSWALK_AND_PIXELS_PASS',
            'commands':calls,'elapsed_seconds':time.perf_counter()-began,'local_only':True,
            'full_comparison_record_units':len(comparison['comparison_units']),
            'input_path_differences_retained':sum(len(r['same_byte_input_location_differences'])for r in comparison['comparison_units']),
            'strict_identity_units_not_pooled':True,'identity_crosswalk':read(out/'identity_crosswalk/RESULT.json'),
            'new_model_inference':False,'new_normalization':False,'new_biological_N':0,
            'scope':'Scientific remeasurement of fixed archives and selected original native windows; upstream generation is a separate recorded recipe.'}
        result.update(completed_archive_routes_reused=bool(reused),prior_failed_outer_run=str(reused)if reused else None,
            scientific_route_output=str(routes),full_comparison_output=str((reused if reused else out)/'full_comparison'))
        write(out/'RUN_COMPLETE.json',result)
    except Exception as e:
        write(out/'RUN_FAILURE.json',{'error':repr(e),'traceback':traceback.format_exc(),'partial_outputs_retained':True});raise
    finally:
        write(out/'OUTPUT_MANIFEST.json',{'self_excluded':True,'files':[pin(p)for p in sorted(out.rglob('*'))if p.is_file()]})
    print(json.dumps({'status':result['status'],'output':str(out)}))
if __name__=='__main__':main()
