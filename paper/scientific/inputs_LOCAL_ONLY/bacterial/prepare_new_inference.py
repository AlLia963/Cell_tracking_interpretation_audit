"""Prepare exact executed sources and relocation launcher; never execute inference."""
from pathlib import Path
import argparse, json, shutil
from run_archive import HERE, sha, read, write, require
LAUNCHER='''from pathlib import Path
import ast,sys
rawroot=Path(sys.argv.pop(1)).resolve()
runner=Path(__file__).parent/"RUNNER_SOURCE.py"
ns={"__file__":str(runner),"__name__":"__main__"}
tree=ast.parse(runner.read_text(encoding="utf-8"))
for node in tree.body:
    if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id=="ROOT":
        ns["ROOT"]=rawroot;continue
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(runner),"exec"),ns)
'''
def main():
    ap=argparse.ArgumentParser();ap.add_argument('kind',choices=['full','pulse']);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();out=a.output.resolve();require(not out.exists(),'Output must be absent');out.mkdir(parents=True)
    if a.kind=='full':
        src=HERE/'sources/inference';shutil.copytree(src/'policies',out/'sources');runner=src/'run_arm.py';shutil.copy2(runner,out/'RUNNER_SOURCE.py');shutil.copy2(src/'native_stage_observer_v04.py',out/'native_stage_observer_v04.py');(out/'PROTOCOL.md').write_text('Re-execution recipe of fixed29 movies and baseline/max_area/all_components original policies. Source and metadata provenance bound by prepare manifest. No public permission or compiled-backend parity asserted.\n',encoding='utf-8');command='python execute.py EXTERNAL_RAW_ROOT baseline (then max_area and all_components; each fresh arm output)'
        contract=['checkpoint_moma.pth','raw_all29_v0.1/<01..29>/t*.tif','raw_all29_manifest.json','raw_input_v0.1/01/t000.tif','native_stage_observer_v04.py (copy supplied exact observer to rawroot)','native_all29_v0.1/manifest.json (original local archive for unchanged runner baseline parity check)']
    else:
        src=HERE/'sources/pulse/source_preparation_v0.3';prep=out/'source_preparation_v0.3';shutil.copytree(src,prep);runner=src/'run_factorial_arm.py';shutil.copy2(runner,prep/'RUNNER_SOURCE.py');(prep/'execute.py').write_text(LAUNCHER,encoding='utf-8');shutil.copytree(HERE/'sources/pulse/source_preparation_v0.2',out/'source_preparation_v0.2');command='python source_preparation_v0.3/execute.py EXTERNAL_RAW_ROOT WW (then AW,WA,AA; distinct fresh runs)';contract=['all full raw-root inputs above','original native baseline manifest','original four pulse historical anchor paths identified in actual_anchor_binding_v02.json, if re-executing original byte-comparison diagnostics. They are computation comparison archives, not approval gates.']
    if a.kind=='full':(out/'execute.py').write_text(LAUNCHER,encoding='utf-8')
    write(out/'PREPARED_RECIPE.json',{'kind':a.kind,'source_runner_origin':str(runner),'source_runner_sha256':sha(runner),'command':command,'input_root_contract':contract,'source_changes':'only runtime ROOT path assignment overridden by launcher; original runner remains byte exact','inference_executed':False,'normalization_executed':False,'GPU_required':True,'backend':'author PyTorch debug forward shim; compiled extension bit parity unverified','historic_environment_pin_limit':'generation provenance lists torch/torchvision/numpy/scipy/scikit-image/opencv-python; Pillow historical version absent','exact_original_runner_includes_archive_comparison_preconditions':True,'reader_archive_analysis_does_not_require_them':True,'public_acquisition_alone_not_sufficient_for_historical_archive_comparison':True,'files':{p.relative_to(out).as_posix():sha(p) for p in sorted(out.rglob('*')) if p.is_file()}})
if __name__=='__main__':main()
