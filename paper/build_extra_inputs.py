"""Copy the declared next-call and historical negative-result inputs locally.

Read-only source assets are never modified. This author-side packaging command
does not upload data and is unnecessary once the input companion is supplied.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import shutil


def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--research-root',type=Path,required=True)
    p.add_argument('--iws-root',type=Path,required=True)
    p.add_argument('--reference-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);r=a.research_root
    def copy(f,rel,pin=None):
        if pin and sha(f)!=pin: raise ValueError('Historical input changed: '+str(f))
        q=a.output/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,q)
        return {'path':q.relative_to(a.output).as_posix(),'sha256':sha(q)}
    projection=read(r/'pulse_factorial_control_v0.1/geometry_projection_consequence_v0.1/actual_v0.1/RESULT.json')
    job=read(r/'pulse_factorial_control_v0.1/ROOT_COHORT06_NORMALIZATION_JOB_v0.1/JOB.json')
    cases=[]
    for row in projection['rows']:
        film,t=row['film'],row['tau'];arms={}
        for arm in ['WW','WA']:
            d=Path(job['arm_inputs'][arm]['native_root'])/film/'direct_trace';items={}
            for kind,frame in [('postprocess_M_G',t),('before_model',t+1),('consumer_stack',t+1),('consumer_reference_points',t+1),('raw_model_output',t+1)]:
                f=d/f'{frame:04d}_{kind}_00.npz';items[kind]=copy(f,Path('projection')/film/arm/f.name,projection['input_sha256'][str(f)])
            arms[arm]=items
        cases.append({'film':film,'tau':t,'arms':arms})
    (a.output/'PROJECTION_INPUTS.json').write_text(json.dumps({'cases':cases,'no_GT':True},indent=2),encoding='utf-8')
    source=r/'03_方法框架与专项分析/intervention_registry_v0.1/independent_output_audit'
    rows=list(csv.DictReader((source/'paired_counts.csv').open(encoding='utf-8-sig')));pins=read(source/'input_hashes.json');cohorts=[];films=set()
    def resolve(old):
        s=old.replace('\\','/');return a.iws_root/s.split('IWS（只读勿动）/',1)[-1]
    for row,pin in zip(rows,pins):
        stem=row['stem'];films.add(stem);base=Path('historical')/row['mechanism']/stem
        cohorts.append({'film':stem,'split':row['split'],'mechanism':row['mechanism'],
                        'before':copy(resolve(pin['control_path']),base/'before.npz',pin['control_sha256']),
                        'after':copy(resolve(pin['path']),base/'after.npz',pin['sha256'])})
    sdy=a.iws_root/'0929最后一次提交窗口/SDY/05_experiments/E5_head_v2'
    for tag in ['zero','head','head_pool','head_traj','head_pool_traj']:
        f=sdy/(tag+'_pp')/'submission.csv';copy(f,Path('sdy')/(tag+'.csv'))
        with f.open(encoding='utf-8-sig') as h:films.update(x['dataset'] for x in csv.DictReader(h))
    refs={}
    for film in sorted(films):
        src=a.reference_root/(film+'.geff');dest=a.output/'references'/(film+'.geff');shutil.copytree(src,dest);refs[film]=dest.relative_to(a.output).as_posix()
    (a.output/'HISTORICAL_INPUTS.json').write_text(json.dumps({'cohorts':cohorts,'references':refs,'scope':'fixed saved SVM/SDY output comparison; not new training'},indent=2),encoding='utf-8')
    # Separate targets are opened only after each new calculation is written.
    copy(source/'report.json','expected/SVM_report.json')
    copy(source/'paired_counts.csv','expected/SVM_pairs.csv')
    copy(r/'01_原3D与IWS_SVM_SDY/SDY_sparse_recount_v0.1/report.json','expected/SDY_report.json')
    copy(r/'pulse_factorial_control_v0.1/geometry_projection_consequence_v0.1/actual_v0.1/RESULT.json','expected/PROJECTION_report.json')
    ff=[{'path':f.relative_to(a.output).as_posix(),'sha256':sha(f),'bytes':f.stat().st_size} for f in sorted(a.output.rglob('*')) if f.is_file()]
    (a.output/'EXTRA_INPUT_MANIFEST.json').write_text(json.dumps({'local_only':True,'files':ff},indent=2),encoding='utf-8')
    print(json.dumps({'projection_cases':len(cases),'historical_pairs':len(cohorts),'files':len(ff),'bytes':sum(f['bytes'] for f in ff)}))


if __name__=='__main__':main()
