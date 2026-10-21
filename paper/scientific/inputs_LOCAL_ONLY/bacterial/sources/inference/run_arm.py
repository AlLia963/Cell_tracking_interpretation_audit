"""Strict-load author checkpoint and one raw image using author inference core.

No reference masks, reference coordinates, GT IDs or lineage data are loaded.
The extension shim routes inference to the author's own debug PyTorch core.
No claim of parity with the original compiled extension is made.
"""
import sys
sys.dont_write_bytecode=True
import argparse
import importlib
import importlib.metadata
import json
from pathlib import Path
import time
import types
import torch

ROOT=Path('legacy_inputs/论文工作区/10_长期研究推进/2026-10-02_启动/external_end_to_end_feasibility_v0.1')
EXP=Path(__file__).resolve().parent
ARM=sys.argv[1]
assert ARM in ['baseline','max_area','all_components']
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(EXP/'sources'/ARM/'src'))
backend=types.ModuleType('MultiScaleDeformableAttention')
def forward(value,shapes,locations,weights,step):
    module=importlib.import_module('trackformer.models.ops.functions.ms_deform_attn_func')
    return module.ms_deform_attn_core_pytorch(value,shapes,locations,weights)
def backward(*args):
    raise RuntimeError('Inference-only author PyTorch core shim; backward forbidden')
backend.ms_deform_attn_forward=forward
backend.ms_deform_attn_backward=backward
sys.modules['MultiScaleDeformableAttention']=backend

def main():
    out=EXP/ARM
    out.mkdir(exist_ok=False)
    assert torch.cuda.is_available()
    torch.serialization.add_safe_globals([argparse.Namespace])
    checkpoint=torch.load(ROOT/'checkpoint_moma.pth',map_location='cpu',weights_only=True)
    args=checkpoint['args']
    args.device='cuda'
    # Author YAML training-only freeze default; checkpoint predates this flag.
    args.freeze_backbone_and_encoder=False
    args.eval_only=True
    args.hooks=False
    args.avg_attn_weight_maps=False
    args.output_dir=out/'native'
    args.output_dir.mkdir()
    import hashlib
    import importlib.metadata
    from datetime import datetime,timezone
    def fingerprint(path):return hashlib.sha256(path.read_bytes()).hexdigest()
    raw_manifest=json.loads((ROOT/'raw_all29_manifest.json').read_text())
    selected_inputs={}
    for file in sorted((ROOT/'raw_all29_v0.1').glob('*/*.tif')):
        key=f'CTC/test/{file.parent.name}/{file.name}'
        actual=fingerprint(file)
        assert actual==raw_manifest['input_sha256'][key]
        selected_inputs[key]=actual
    assert len(selected_inputs)==5340 and len({k.split('/')[2] for k in selected_inputs})==29
    binding={'created_UTC':datetime.now(timezone.utc).isoformat(),'raw_manifest_SHA256':fingerprint(ROOT/'raw_all29_manifest.json'),
        'selected_raw_SHA256':selected_inputs,'checkpoint_SHA256':fingerprint(ROOT/'checkpoint_moma.pth'),
        'runner_SHA256':fingerprint(Path(__file__)),'observer_SHA256':fingerprint(ROOT/'native_stage_observer_v04.py'),
        'protocol_SHA256':fingerprint(EXP/'PROTOCOL.md'),
        'execution_source_SHA256':{str(p.relative_to(EXP/'sources'/ARM)):fingerprint(p) for p in sorted((EXP/'sources'/ARM).rglob('*.py'))},
        'effective_args':vars(args),'versions':{name:importlib.metadata.version(name) for name in ['torch','torchvision','numpy','scipy','scikit-image','opencv-python']},
        'scope':'Local pre-inference binding; no external timestamp or historical training-isolation proof'}
    (out/'provenance_before_inference.json').write_text(json.dumps(binding,indent=2,default=str),encoding='utf-8')

    torch.manual_seed(42)
    torch.cuda.manual_seed_all(42)
    from trackformer.models import build_model
    import cv2
    import numpy as np
    import tempfile
    original_read=cv2.imread
    original_write=cv2.imwrite
    def unicode_read(filename,flags=cv2.IMREAD_COLOR):
        return cv2.imdecode(np.fromfile(filename,dtype=np.uint8),flags)
    def unicode_write(filename,image,params=None):
        ok,data=cv2.imencode(Path(filename).suffix,image,[] if params is None else params)
        if not ok:return False
        Path(filename).write_bytes(data.tobytes())
        return True
    # Verify exact native/OpenCV pixel equivalence on an ASCII filesystem path.
    raw=sorted((ROOT/'raw_input_v0.1/01').glob('*.tif'))[0]
    with tempfile.TemporaryDirectory(prefix='celltractr_unicode_QC_') as temp:
        ascii_path=Path(temp)/'input.tif'
        ascii_path.write_bytes(raw.read_bytes())
        expected=original_read(str(ascii_path),cv2.IMREAD_ANYDEPTH)
        decoded=unicode_read(raw,cv2.IMREAD_ANYDEPTH)
        assert np.array_equal(expected,decoded)
        test_path=Path(temp)/'roundtrip.tif'
        assert unicode_write(test_path,expected)
        assert np.array_equal(expected,original_read(str(test_path),cv2.IMREAD_ANYDEPTH))
    cv2.imread=unicode_read
    cv2.imwrite=unicode_write
    from trackformer.engine import pipeline
    from trackformer.models.ops.functions.ms_deform_attn_func import ms_deform_attn_core_pytorch
    errors=[]
    with torch.no_grad():
        for seed in range(20):
            generator=torch.Generator().manual_seed(seed)
            shapes=torch.tensor([[8,8],[4,4],[2,2]])
            value=torch.randn(1,84,8,18,generator=generator)
            locations=torch.rand(1,7,8,3,4,2,generator=generator)*2-.5
            weights=torch.rand(1,7,8,3,4,generator=generator)
            weights=weights/weights.sum((-1,-2),keepdim=True)
            cpu=ms_deform_attn_core_pytorch(value,shapes,locations,weights)
            gpu=ms_deform_attn_core_pytorch(value.cuda(),shapes.cuda(),locations.cuda(),weights.cuda()).cpu()
            error=(cpu-gpu).abs().max().item()
            assert error<1e-5
            errors.append(error)
    model,criterion=build_model(args)
    incompatible=model.load_state_dict(checkpoint['model'],strict=True)
    assert not incompatible.missing_keys and not incompatible.unexpected_keys
    model.to('cuda').eval()
    model.train_model=False
    criterion.eval_only=True
    import hashlib
    import traceback
    reports=[]
    for folder in sorted((ROOT/'raw_all29_v0.1').iterdir()):
        files=sorted(folder.glob('*.tif'))
        started=time.perf_counter()
        predictor=None
        try:
            predictor=pipeline(model,files,args)
            predictor.write_video=False
            predictor.display_enc_map=lambda *a,**kw:None
            from native_stage_observer_v04 import install_observer
            install_observer(predictor)
            predictor.forward()
            torch.cuda.synchronize()
            masks=sorted(predictor.output_dir.glob('mask*.tif'))
            lineage=predictor.output_dir/'res_track.txt'
            assert len(masks)==len(files) and lineage.exists()
            frozen=json.loads((ROOT/'native_all29_v0.1/manifest.json').read_text())
            expected=next(r for r in frozen['all_video_reports'] if r['video']==folder.name)['output_hashes']
            parity=all(hashlib.sha256(p.read_bytes()).hexdigest()==expected[p.name] for p in masks+[lineage])
            if ARM=='baseline':assert parity
            report={'video':folder.name,'input_frames':len(files),'output_masks':len(masks),'status':'completed', 'final_output_byte_parity':parity, 'arm':ARM,
                'seconds':time.perf_counter()-started,
                'output_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in masks+[lineage]}}
        except Exception:
            report={'video':folder.name,'input_frames':len(files),'status':'failed-or-partial',
                'seconds':time.perf_counter()-started,'traceback':traceback.format_exc(),
                'partial_masks':len(list((out/'native'/folder.name).glob('mask*.tif')))}
        (out/f'{folder.name}_execution_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        reports.append(report)
        print('COMPLETED-STATE',folder.name,report['status'],flush=True)
    manifest={'all_video_reports':reports,'completed':sum(r['status']=='completed' for r in reports),
        'selected_video_count':29,'reference_input':False,'torch':torch.__version__,'cuda':torch.version.cuda,
        'checkpoint_strict_load':True,'core_cpu_gpu_probes':20,'core_max_absolute_error':max(errors),
        'backend':'author debug PyTorch core forward shim, compiled-extension parity unverified',
        'compatibility':['signed int32 div_track sentinel','Unicode decode/encode path shim pixel-parity QC',
            'training-only freeze_backbone_and_encoder=False','optional final encoder visualization/video disabled'],
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'arm':ARM,'scope':'Full restarted trajectory intervention; each captured state conditional on own prior D; not biological causality or unseen validation'}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('All selected:',len(reports),'completed:',manifest['completed'],flush=True)

if __name__=='__main__':main()
