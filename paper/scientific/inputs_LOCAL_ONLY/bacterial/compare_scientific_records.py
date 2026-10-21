"""Full scientific-record comparison; input locations/provenance compared separately."""
from pathlib import Path
import argparse, json
from run_archive import HERE,read,write,sha,require
TARGETS={'common':'common_run01','full':'full_run01','natural':'natural_run01','timing':'timing_run01','cca':'cca_run01','chains':'chains_run01','duties':'duties_run01','initial-overlays':'initial-overlays_run01','division-overlays':'division-overlays_run01','pulse-endpoint':'pulse-endpoint_run02','stage-archive':'stage-archive_run01'}
def difference(x,y,path='$'):
    if type(x)!=type(y):return [{'path':path,'old':x,'new':y}]
    if isinstance(x,dict):
        result=[]
        for k in sorted(set(x)|set(y)):
            if k not in x or k not in y:result.append({'path':path+'.'+k,'old':x.get(k),'new':y.get(k)})
            else:result.extend(difference(x[k],y[k],path+'.'+k))
        return result
    if isinstance(x,list):
        if len(x)!=len(y):return [{'path':path+'.length','old':len(x),'new':len(y)}]
        return [r for i,(a,b) in enumerate(zip(x,y)) for r in difference(a,b,f'{path}[{i}]')]
    return [] if x==y else [{'path':path,'old':x,'new':y}]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--new-root',type=Path,required=True);ap.add_argument('--targets-root',type=Path,default=HERE/'results');ap.add_argument('--route-override',action='append',default=[]);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();out=a.output.resolve();require(not out.exists(),'Output must be absent');out.mkdir(parents=True);overrides={k:Path(v) for k,v in (x.split('=',1) for x in a.route_override)};rows=[]
    def compare(route,relative,selector=None):
        old=a.targets_root/TARGETS[route]/relative;new=overrides.get(route,a.new_root/route)/relative;xo=read(old) if old.suffix!='.jsonl' else [json.loads(x) for x in old.read_text(encoding='utf-8').splitlines()];xn=read(new) if new.suffix!='.jsonl' else [json.loads(x) for x in new.read_text(encoding='utf-8').splitlines()]
        if selector:xo=selector(xo);xn=selector(xn)
        diff=difference(xo,xn);location=[]
        if route=='cca' and relative=='measurement/IDENTITIES_AND_LENGTHS.json':
            location=[r for r in diff if r['path'].endswith('.prediction_track_path')];diff=[r for r in diff if not r['path'].endswith('.prediction_track_path')]
            # Every other field including prediction_track_sha256 remains exact.
            for r in location:require(str(r['old']).replace('\\','/').split('/external_trajectory_intervention_v0.1/')[-1]==str(r['new']).replace('\\','/').split('/external_trajectory_intervention_v0.1/')[-1],'CCA location changed underlying input identity')
        rows.append({'route':route,'scientific_record':relative,'old_sha256':sha(old),'new_sha256':sha(new),'whole_record_or_explicit_selector_equal':not diff,'selected_record_count':len(xo) if isinstance(xo,list) else None,'same_byte_input_location_differences':location,'differences':diff});return not diff
    compare('common','RESULT.json')
    for film in [f'{i:02d}' for i in range(1,30)]:
        compare('full',f'measurement/{film}_results.json');compare('natural',f'measurement/{film}_edge_records.jsonl');compare('timing',f'measurement/{film}_EVENTS.json');compare('chains',f'measurement/{film}_RECORDS.json');compare('pulse-endpoint',f'{film}_ENDPOINT.json')
    compare('cca','measurement/IDENTITIES_AND_LENGTHS.json')
    compare('duties','measurement/fixtures.json',lambda d:d['trials'])
    compare('duties','measurement/fixtures.json',lambda d:[{'film':r['film'],'contract':r['contract']} for r in d['carriers']])
    compare('initial-overlays','work/native_noisy_validation_v0.3/case_records.json')
    compare('division-overlays','measurement/CASE_RECORDS.json');compare('division-overlays','measurement/TARGET_ELIGIBILITY.json')
    for p in ['IDENTITIES.json','PULSE_LOSS_IDENTITIES.json','WITHHELD.json']:compare('stage-archive',p)
    write(out/'FULL_RECORD_COMPARISON.json',{'all_scientific_records_equal':all(r['whole_record_or_explicit_selector_equal'] for r in rows),'comparison_units':rows,'excluded_from_scientific_record_comparison':'route input paths, UTC/runtime and provenance receipts; these remain complete in actual output and input/output manifests. No scientific row/identity/type/withheld result is excluded.','no_tolerance_or_rounding':True});require(all(r['whole_record_or_explicit_selector_equal'] for r in rows),'Scientific record differences, see complete diff file');print('FULL_RECORD_COMPARISONS',len(rows),'PASS',flush=True)
if __name__=='__main__':main()
