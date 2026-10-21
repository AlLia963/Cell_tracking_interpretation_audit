"""Copy exact scientific sources and compact inputs; never alter the source tree."""
from pathlib import Path
import argparse, hashlib, json, shutil, ast

HERE=Path(__file__).resolve().parent
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input-root',type=Path,required=True);a=ap.parse_args()
    root=a.input_root.resolve();art=root/'article_strengthening_20261004_v1';rep=art/'reproduction_LOCAL_ONLY_v0.1';pulse=root/'pulse_factorial_control_v0.1'
    records=[]
    def cp(src,dest):
        src=Path(src);dest=HERE/dest
        if not src.is_file():raise FileNotFoundError(src)
        dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():assert sha(dest)==sha(src)
        else:shutil.copy2(src,dest)
        records.append({'source':str(src),'package':dest.relative_to(HERE).as_posix(),'bytes':dest.stat().st_size,'sha256':sha(dest)})
    def tree(src,dest,patterns=('*.py','*.json','*.md')):
        for pattern in patterns:
            for p in sorted(Path(src).rglob(pattern)):cp(p,Path(dest)/p.relative_to(src))
    for name in ['common_carrier96','external_full','external_natural','analysis_framework_v0.8','mask_ambiguity_v0.1','typed_pathway_adapter_v0.2','reusable_analysis_package_v0.1','real_policy_contract_v0.1','real_policy_contract_v0.2']:
        tree(rep/name,Path('sources/legacy')/name)
    for p in sorted((rep/'common_carrier96').glob('*.npz')):cp(p,Path('inputs_LOCAL_ONLY/common_carrier96')/p.name)
    cp(rep/'common_carrier96/reproduce96.py','inputs_LOCAL_ONLY/common_carrier96/reproduce96.py');cp(rep/'common_carrier96/source_relative_score.py','inputs_LOCAL_ONLY/common_carrier96/source_relative_score.py')
    for p in ['run_native_noisy_validation_v03.py','native_noisy_control_protocol_v0.1.md']:cp(rep/p,Path('sources/legacy')/p)
    cp(root/'generate_native_noisy_controls_v02.py','sources/legacy/generate_native_noisy_controls_v02.py')
    for name in ['division_window_controls_v0.1','division_timing_sensitivity_v0.1','cca_existing_cohort_v0.1','lineage_consequence_v0.1','closest_prior_lineage_definitions_v0.1']:
        for p in sorted((art/name).glob('*.py')):
            if any(k in p.name for k in ['origin','native','probe','repair','prepare','audit']):continue
            cp(p,Path('sources')/name/p.name)
        for p in sorted((art/name).glob('PROTOCOL.md')):cp(p,Path('sources')/name/p.name)
    cp(art/'audit_final_only_observation_classes_v01.py','sources/final_only.py')
    cp(art/'reproduction_LOCAL_ONLY_v0.1/S3_image_policy_independent_audit_v0.2/decision_ledger.json','inputs_LOCAL_ONLY/decision_ledger.json')
    for n in ['fourcell_scientific_measurement_preparation_v0.3','fourcell_stage_exposure_preparation_v0.3','reference_stage_matcher_preparation_v0.2','fourcell_cohort_adapter_preparation_v0.6','fourcell_comparator_preparation_v0.4']:
        tree(pulse/n,Path('sources/pulse')/n,('*.py',))
    tree(pulse/'source_preparation_v0.3/source',Path('sources/pulse/source_preparation_v0.3/source'),('*.py',))
    for p in ['source_preparation_v0.3/run_factorial_arm.py','source_preparation_v0.3/native_stage_observer_v04_copy.py','source_preparation_v0.3/direct_input_observer_v0_1.py','source_preparation_v0.3/direct_input_observer_v0.1.py','source_preparation_v0.3/failure_receipt_v03.py','source_preparation_v0.3/fixed_schedule.json','source_preparation_v0.3/anchor_verifier_v03.py','source_preparation_v0.3/actual_anchor_binding_v02.json','source_preparation_v0.3/delivery_hashes_v03.json','source_preparation_v0.2/delivery_hashes_v02.json']:
        cp(pulse/p,Path('sources/pulse')/p)
    cp(root/'external_trajectory_intervention_v0.1/run_arm.py','sources/inference/run_arm.py')
    for p in ['execute_common_carrier_v01.py','replay_svm_topology_v02.py','recount_sdy_sparse_v01.py','common_carrier_protocol_v0.1.md']:cp(root/p,Path('sources/common_policy')/p)
    iws=Path('legacy_inputs/IWS（只读勿动）/SVM/SVM5/research')
    for p in ['event_gate/event_consensus.py','event_gate/affirmative_veto.py','measurement_fusion/measurement_fusion.py','topology/endpoint_consistency.py']:cp(iws/p,Path('sources/common_policy/policies')/p)
    cp(art/'closest_prior_lineage_definitions_v0.1/FETCH.json','provenance/lineage_metric_FETCH.json')
    for p in ['audit_s3_image_policy_v02.py','replay_s3_image_veto_v01.py','trace_s3_allocation_v01.py','infer_s3_image_veto_strict_v01.py','real_S3_policy_sensitivity_v0.1/run_sensitivity.py']:cp(root/p,Path('sources/source_duty')/p)
    duty_manifest=json.loads((root/'S3_image_veto_inputs_v0.2/manifest.json').read_text(encoding='utf-8'))
    cp(Path(duty_manifest['source_path']),'sources/source_duty/executed_producer.py')
    for p in ['S3_image_veto_inputs_v0.2/manifest.json','S3_image_veto_scores_v0.1/scores.json','S3_allocation_trace_v0.1/report.json','S3_image_veto_replay_v0.1/report.json']:cp(root/p,Path('provenance/source_duty')/p)
    cp(root/'external_end_to_end_feasibility_v0.1/native_stage_observer_v04.py','sources/inference/native_stage_observer_v04.py')
    for name in ['baseline','max_area','all_components']:
        tree(root/'external_trajectory_intervention_v0.1/sources'/name,Path('sources/inference/policies')/name,('*.py',))
    for p in ['external_validation_v0.1/download_manifest.json','external_end_to_end_feasibility_v0.1/acquisition_manifest.json','external_end_to_end_feasibility_v0.1/raw_all29_manifest.json','external_trajectory_intervention_v0.1/source_patch_manifest.json','external_trajectory_intervention_v0.1/source_binding_addendum_v0.1.json']:
        cp(root/p,Path('provenance')/Path(p).name)
    for p in ['ROOT_MEASUREMENT09_ACTUAL_JOB_v0.1/JOB.json','ROOT_STAGE03_ACTUAL_JOB_v0.1/JOB.json','ROOT_FOURCELL_REGISTRATION_ACTUAL_v0.1/REGISTRATION_ACCEPTED.json','actual_fourcell_cohort_v0.1/COHORT_COMPLETE.json','actual_fourcell_cohort_v0.1/NORMALIZATION_START.json']:
        cp(pulse/p,Path('provenance/pulse')/p)
    contract={'schema':'bacterial_extension_inputs_v1','local_only':True,'input_root':str(root),'article_root_relative':'article_strengthening_20261004_v1','reference_archive_relative':'external_validation_v0.1/CTC.zip','archive_sha256':json.loads((rep/'external_full/RESOURCE_MANIFEST.json').read_text(encoding='utf-8'))['archive_sha256'],'pulse_cohort_relative':'pulse_factorial_control_v0.1/actual_fourcell_cohort_v0.1','pulse_stage_relative':'pulse_factorial_control_v0.1/actual_fourcell_stage_exposure_v0.1','pulse_endpoint_relative':'pulse_factorial_control_v0.1/actual_fourcell_scientific_measurement_v0.1','source_files':records,'prediction_only_generation':True,'new_inference_executed':False,'publication_permission':False}
    (HERE/'CONFIG_LOCAL_ONLY.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'copied_files':len(records),'copied_bytes':sum(r['bytes'] for r in records)},ensure_ascii=False))
if __name__=='__main__':main()
