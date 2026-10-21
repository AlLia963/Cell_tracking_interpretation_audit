"""CPU-only source and captured-input preprocessing check; no model invocation."""
from pathlib import Path
import argparse, inspect, json, shutil, sys
import cv2, numpy as np, PIL, PIL.Image, torch
from torchvision.transforms.functional import to_tensor, normalize
from run_archive import HERE, sha, read, write, require
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input-root',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();root=a.input_root.resolve();out=a.output.resolve();require(not out.exists(),'Output must be absent');out.mkdir(parents=True);shutil.copy2(__file__,out/'EXECUTED_ADAPTER.py')
    engine=HERE/'sources/pulse/source_preparation_v0.3/source/src/trackformer/engine.py';image_source=Path(inspect.getsourcefile(PIL.Image.Image.resize));shutil.copy2(image_source,out/'EXECUTED_Pillow_Image.py')
    rows=[]
    for film,t in [('29',41),('21',57)]:
        array=read(root/'pulse_factorial_control_v0.1/actual_fourcell_cohort_v0.1/WW'/film/'array_sources.json')['sources'];entry=array[f'{t:04d}_before_model_00/root/samples'];trace=Path(entry['source_path']);require(sha(trace)==entry['source_sha256'],'Actual trace input bytes')
        raw=root/'external_end_to_end_feasibility_v0.1/raw_all29_v0.1'/film/f't{t:03d}.tif';im=cv2.imdecode(np.fromfile(raw,dtype=np.uint8),cv2.IMREAD_ANYDEPTH);arr=(255*(im/np.max(im))).astype(np.uint8);img=PIL.Image.fromarray(arr)
        with np.load(trace,allow_pickle=False) as z:actual=z[entry['source_key']].copy()
        target=tuple(reversed(actual.shape[-2:]));tests={}
        for name,method in [('omitted_default',None),('explicit_BICUBIC',PIL.Image.Resampling.BICUBIC),('explicit_BILINEAR',PIL.Image.Resampling.BILINEAR),('explicit_NEAREST',PIL.Image.Resampling.NEAREST)]:
            resized=img.resize(target) if method is None else img.resize(target,resample=method)
            computed=normalize(to_tensor(resized.convert('RGB')),[.485,.456,.406],[.229,.224,.225])[None].numpy();tests[name]={'array_equal_to_captured':bool(np.array_equal(computed,actual)),'max_abs_error':float(np.max(np.abs(computed-actual)))}
        for p in [raw,trace]:shutil.copy2(p,out/(film+'_'+p.name))
        rows.append({'film':film,'frame':t,'raw_origin':str(raw),'raw_sha256':sha(raw),'trace_origin':str(trace),'trace_sha256':sha(trace),'trace_member':entry['source_key'],'input_dtype':str(im.dtype),'input_shape':list(im.shape),'pre_resize_mode':img.mode,'target_wh':list(target),'captured_dtype':str(actual.dtype),'captured_shape':list(actual.shape),'comparisons':tests})
    require(all(r['pre_resize_mode']=='L' for r in rows),'Executed uint8 grayscale mode')
    write(out/'RESULT.json',{'operation':'CPU-only captured-input preprocessing check','Pillow_version_checked_now':PIL.__version__,'Pillow_Image_source_sha256':sha(image_source),'engine_source_sha256':sha(engine),'configured_resample_argument':'omitted in executed engine','resolved_checked_source_default':'resample=None becomes BICUBIC; modes 1/P switch to NEAREST; actual L takes BICUBIC; reducing_gap=None','historical_generation_Pillow_version':'not recorded in provenance_before_inference.versions; current environment version is not asserted to be historical','historical_behavior_evidence':'two actual before_model sample tensors compared to checked current source branch','records':rows,'new_inference':False,'all_frame_or_model_bit_parity_claim':False})
    write(out/'OUTPUT_FREEZE.json',{'files':{p.relative_to(out).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in out.rglob('*') if p.is_file()}})
if __name__=='__main__':main()
