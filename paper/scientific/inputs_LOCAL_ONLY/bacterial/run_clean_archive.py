"""Clean standalone archive pass, with separate per-route fresh output directories."""
from pathlib import Path
import argparse, concurrent.futures, json, subprocess, sys
from run_archive import HERE,sha,read,write,require
ROUTES=['common','full','natural','timing','cca','chains','duties','initial-overlays','division-overlays','pulse-endpoint','stage-archive']
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--input-root',type=Path,default=HERE/'fixed_archive_root');ap.add_argument('--routes',nargs='+',default=ROUTES,choices=ROUTES);ap.add_argument('--workers',type=int,default=2);a=ap.parse_args();out=a.output.resolve();require(not out.exists(),'Output must be absent');out.mkdir(parents=True)
    def run(route):
        command=[sys.executable,'-B','-X','utf8',str(HERE/'run_archive.py'),route,'--input-root',str(a.input_root.resolve()),'--output',str(out/route)]
        p=subprocess.run(command,capture_output=True,text=True,encoding='utf-8');(out/(route+'_STDOUT.txt')).write_text(p.stdout,encoding='utf-8');(out/(route+'_STDERR.txt')).write_text(p.stderr,encoding='utf-8');print('CLEAN_ROUTE',route,p.returncode,flush=True);return {'route':route,'returncode':p.returncode,'command':command}
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:records=list(pool.map(run,a.routes))
    write(out/'RESULT.json',{'all_completed':all(x['returncode']==0 for x in records),'records':records,'no_model_inference':True,'no_normalization':True,'reader_ROOT_approval_required':False,'input_root':str(a.input_root.resolve()),'archive_input_freeze_sha256':sha(a.input_root/'FIXED_INPUT_FREEZE.json')});require(all(x['returncode']==0 for x in records),'One or more standalone routes failed; inspect preserved logs')
if __name__=='__main__':main()
