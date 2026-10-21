"""Construct standalone fixed archives; copy bytes, derive thresholded supports explicitly."""
from pathlib import Path
import argparse, copy, json, shutil, sys
import numpy as np
from run_archive import HERE, sha, read, write, require
sys.dont_write_bytecode=True
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input-root',type=Path,required=True);ap.add_argument('--output',type=Path,default=HERE/'fixed_archive_root');a=ap.parse_args()
    root=a.input_root.resolve();out=a.output.resolve();require(not out.exists(),'Output must be absent');out.mkdir(parents=True)
    art=root/'article_strengthening_20261004_v1'; rep=art/'reproduction_LOCAL_ONLY_v0.1';pulse=root/'pulse_factorial_control_v0.1';records=[]
    def cp(p,relative=None):
        p=Path(p);d=out/(relative if relative is not None else p.relative_to(root));d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d);h=sha(p);require(sha(d)==h,'Copy bytes')
        records.append({'kind':'byte_copy','origin':str(p),'package':d.relative_to(out).as_posix(),'bytes':d.stat().st_size,'sha256':h});return d
    cp(root/'external_validation_v0.1/CTC.zip')
    for arm in ['baseline','max_area','all_components']:
        base=root/'external_trajectory_intervention_v0.1'/arm/'native'
        for p in sorted(base.rglob('*')):
            if p.is_file() and (p.name.startswith('mask') and p.suffix=='.tif' or p.name=='res_track.txt'):cp(p)
    for film in [f'{i:02d}' for i in range(1,30)]:
        for p in [art/f'external_natural_support_actual_v0.1/{film}_edge_records.jsonl',art/f'external_full_integer_actual_v0.1/{film}_results.json']:cp(p)
    for name in ['external_full','external_natural']:
        for p in sorted((rep/name).glob('*.json')):cp(p)
    for p in sorted((rep/'3d_original_pixel_stage_exports').rglob('*.npz')):
        if p.name in ['S2_gap_closing.npz','S3_safe_divisions.npz']:cp(p)
    cp(rep/'S3_image_veto_replay_v0.1/report.json')
    cp(root/'native_noisy_control_protocol_v0.1.md')
    original=root/'external_end_to_end_feasibility_v0.1'; support_root=out/'external_end_to_end_feasibility_v0.1'
    for p in [original/'native_conditional_graph_v0.2/report.json',original/'native_graph_provenance_v0.2/manifest.json']:cp(p)
    cfg=read(rep/'external_natural/RESOURCE_MANIFEST.json');derived=[]
    for spec in cfg['films']:
        film=spec['film'];side=read(rep/'external_natural'/spec['sidecar_relative']);mapping={}
        for row in side['records']:
            p=original/row['state_path_relative_to_root'];require(sha(p)==row['state_sha256'],'Original support hash')
            relative=f'compact_supports/{film}/frame{row["frame"]:03d}.npz';d=support_root/relative;d.parent.mkdir(parents=True,exist_ok=True)
            with np.load(p,allow_pickle=False) as z:
                arrays={'resized_probabilities':z['resized_probabilities']>.5,'winner_threshold_binary':z['winner_threshold_binary'].astype(bool),'component_retained_binary':z['component_retained_binary'].astype(bool),'return_masks':z['return_masks'].astype(bool)}
            np.savez_compressed(d,**arrays);h=sha(d);mapping[row['state_path_relative_to_root']]=(relative,h)
            rec={'kind':'derived_thresholded_supports','origin':str(p),'origin_sha256':row['state_sha256'],'package':d.relative_to(out).as_posix(),'sha256':h,'bytes':d.stat().st_size,'frame':row['frame'],'film':film,'derivation':{'resized_probabilities':'original probability > 0.5, saved as bool; reader >0.5 is identical','winner_threshold_binary':'astype(bool)','component_retained_binary':'astype(bool)','return_masks':'astype(bool)'},'original_float_probabilities_preserved':False}
            records.append(rec);derived.append(rec)
        for row in side['records']:
            old=row['state_path_relative_to_root'];row['state_path_relative_to_root'],row['state_sha256']=mapping[old]
            if row['previous_D_anchor']:
                anchor=row['previous_D_anchor'];old=anchor['state_path_relative_to_root'];anchor['state_path_relative_to_root'],anchor['state_sha256']=mapping[old]
        oldgp=side['graph_path_relative_to_root'];side['graph_path_relative_to_root']=oldgp.replace('\\','/');cp(original/oldgp)
        side['compact_derivation_note']='Only four actual support members preserved; probability threshold is strict >0.5. Native query/cell/type metadata remain from original graph sidecar; no inference executed.'
        original_side=rep/'external_natural'/spec['sidecar_relative'];side['original_sidecar_sha256']=sha(original_side)
        for d in [out/rep.relative_to(root)/'external_natural'/spec['sidecar_relative'],support_root/'native_graph_provenance_v0.2'/f'{film}_sidecar.json']:
            d.parent.mkdir(parents=True,exist_ok=True)
            if d.exists():d.write_text(json.dumps(side,ensure_ascii=False,indent=2),encoding='utf-8')
            else:write(d,side)
        spec['sidecar_sha256']=sha(out/rep.relative_to(root)/'external_natural'/spec['sidecar_relative']);spec['support_paths_resolve_under']=str(support_root)
        print('COMPACT_SUPPORTS',film,len(side['records']),flush=True)
    cpath=out/rep.relative_to(root)/'external_natural/RESOURCE_MANIFEST.json';cfg['archive_path']=str(out/'external_validation_v0.1/CTC.zip');cpath.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
    cfg2=read(out/rep.relative_to(root)/'external_full/RESOURCE_MANIFEST.json');cfg2['archive_path']=str(out/'external_validation_v0.1/CTC.zip')
    for row in cfg2['arms']:row['native_root']=str(out/'external_trajectory_intervention_v0.1'/row['arm']/'native')
    (out/rep.relative_to(root)/'external_full/RESOURCE_MANIFEST.json').write_text(json.dumps(cfg2,ensure_ascii=False,indent=2),encoding='utf-8')
    cohort=pulse/'actual_fourcell_cohort_v0.1'
    for p in [cohort/'COHORT_COMPLETE.json',cohort/'NORMALIZATION_START.json']:cp(p)
    for arm in ['WW','AW','WA','AA']:
        for film in [f'{i:02d}' for i in range(1,30)]:
            for name in ['FILM_COMPLETE.json','prediction/prediction.npz']:cp(cohort/arm/film/name)
    for p in sorted((pulse/'actual_fourcell_scientific_measurement_v0.1').glob('*_measurement.json')):cp(p)
    for p in sorted((pulse/'actual_fourcell_stage_exposure_v0.1').glob('*_stage_windows.jsonl')):cp(p)
    write(out/'DERIVED_SUPPORT_ORIGINS.json',derived)
    write(out/'COPY_AND_DERIVATION_ORIGINS.json',{'records':records,'local_only':True,'inference_executed':False,'normalizer_executed':False,'source_byte_copy_hashes_are_before_resource_relocation':True,'relocated_files':['external_natural/RESOURCE_MANIFEST.json','external_natural/*_sidecar.json','external_full/RESOURCE_MANIFEST.json']})
    write(out/'FIXED_INPUT_FREEZE.json',{'files':{p.relative_to(out).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(out.rglob('*')) if p.is_file()},'archive_analysis_only':True,'local_only':True,'new_inference':False})
if __name__=='__main__':main()
