import sys
sys.dont_write_bytecode=True
import ast, hashlib, json, time, traceback
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import torch
ROOT=Path(__file__).resolve().parent; OUT=ROOT/'S3_image_veto_scores_strict_v0.1'
INPUT=ROOT/'S3_image_veto_inputs_v0.2/manifest.json'
WEIGHT=ROOT.parents[2]/'cell（只读勿动）/community_dataset/Biohub DeepCenterUNet3D Center Prior V1/weights/full_frame_center/best.pt'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    OUT.mkdir(exist_ok=False); start=time.monotonic()
    manifest=json.loads(INPUT.read_text(encoding='utf-8'));source=Path(manifest['source_path']);assert sha(source)==manifest['source_sha256']
    tree=ast.parse(source.read_text(encoding='utf-8-sig')); ns=dict(torch=torch,np=np,USE_DEEPCENTER_VETO=True,DEEPCENTER_SCORE_WIN_Z=1,DEEPCENTER_SCORE_WIN_YX=2)
    classes={n.name:n for n in ast.walk(tree) if isinstance(n,ast.ClassDef) and n.name in ['_DCConvBlock3d','_DCDeepCenterUNet3D']}
    for name in ['_DCConvBlock3d','_DCDeepCenterUNet3D']:
        exec(compile(ast.Module(body=[classes[name]],type_ignores=[]),str(source),'exec'),ns)
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='deepcenter_score_point')
    exec(compile(ast.Module(body=[fn],type_ignores=[]),str(source),'exec'),ns)
    checkpoint=torch.load(WEIGHT,map_location='cpu',weights_only=False);assert checkpoint['epoch']==2
    cfg=SimpleNamespace(**checkpoint['config'])
    for k,v in manifest['preprocessing_config'].items():assert getattr(cfg,k)==v
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    assert torch.cuda.is_available();device=torch.device('cuda')
    model=ns['_DCDeepCenterUNet3D'](base_channels=cfg.base_channels);model.load_state_dict(checkpoint['model_state'],strict=True);model.to(device);model.eval()
    bundle=dict(cfg=cfg); rows=[]
    for index,r in enumerate(manifest['rows']):
        path=Path(r['input_path']);assert sha(path)==r['input_sha256']
        with np.load(path) as d:image=d['image']
        with torch.no_grad(): heatmap=torch.sigmoid(model(torch.from_numpy(image[None,None,...]).to(device=device,dtype=torch.float32)))[0,0].detach().cpu().numpy().astype(np.float32,copy=False)
        ns['deepcenter_heatmap_for_frame']=lambda *args:heatmap
        scores=[]
        for point in r['queries']:
            value=ns['deepcenter_score_point'](r['film'],r['frame'],tuple(point),bundle,{},{});assert value is not None
            scores.append(dict(point=point,score=value,accepted=value>=0.25))
        rows.append(dict(film=r['film'],frame=r['frame'],scores=scores,heatmap_sha256=hashlib.sha256(heatmap.tobytes()).hexdigest()))
        if index%25==0:print('frames',index+1,'/',len(manifest['rows']),flush=True)
    (OUT/'scores.json').write_text(json.dumps(dict(rows=rows,input_manifest_sha256=sha(INPUT),source_sha256=sha(source),weight_path=str(WEIGHT),weight_sha256=sha(WEIGHT),checkpoint_epoch=checkpoint['epoch'],checkpoint_config=checkpoint['config'],script_sha256=sha(Path(__file__)),torch_version=torch.__version__,device=torch.cuda.get_device_name(0),float_policy='float32 tensors no AMP eval no_grad; matmul/cudnn TF32 disabled',matmul_tf32=torch.backends.cuda.matmul.allow_tf32,cudnn_tf32=torch.backends.cudnn.allow_tf32,threshold=0.25,runtime_seconds=time.monotonic()-start),indent=2),encoding='utf-8')
if __name__=='__main__':
    try:main()
    except Exception:
        if OUT.exists():(OUT/'failure.json').write_text(json.dumps(dict(traceback=traceback.format_exc())),encoding='utf-8')
        raise
