"""Compact all-per-movie tables retain adverse, null and unsupported records."""
from pathlib import Path
from collections import Counter
import argparse, json
from run_archive import HERE,read,write,require,sha
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--results-root',type=Path,default=HERE/'results/standalone_clean_run01');ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();out=a.output.resolve();require(not out.exists(),'Absent output');out.mkdir(parents=True);table=[];bykind={k:Counter() for k in ['continuation','division']};totals=Counter()
    for film in [f'{i:02d}' for i in range(1,30)]:
        p=a.results_root/'natural/measurement'/f'{film}_edge_records.jsonl';rows=[json.loads(x) for x in p.read_text(encoding='utf-8').splitlines()];c=Counter()
        for r in rows:
            c['reference_relations']+=1;k=bykind[r['kind']];k['reference_relations']+=1
            for j,s in enumerate('ABCD'):
                lo,hi=r['bounds'][j];ulo,uhi=r['untyped_bounds'][j];require(lo==hi and ulo==uhi,'No invented summary of ambiguous bounds');c['typed_'+s]+=lo;c['raw_'+s]+=ulo
            for name in ['final_missing','persistent_absence']:
                c[name]+=bool(r[name]);k[name]+=bool(r[name])
            loss=bool(r['loss_stages']) and r['final_missing'];gain=bool(r['gain_stages']);c['observed_last_loss']+=loss;c['ever_gain']+=gain;k['observed_last_loss']+=loss;k['ever_gain']+=gain
        table.append({'film':film,**dict(c),'complete_edge_records_sha256':sha(p)});totals.update(c)
    require(totals['reference_relations']==31093,'All29 relation inventory');write(out/'NATURAL29_TYPED_RAW_PERMOVIE.json',{'records':table,'totals':dict(totals),'relation_kinds':{k:dict(v) for k,v in bykind.items()},'source':'fresh compact-support run retains every mathematical eligibility/visibility/type record','causal_scope':'Observed local histories only; persistent omission is not a localized loss and native histories do not establish biological causality'})
    for route,filename in [('common','RESULT.json'),('full','measurement/RESULT.json'),('timing','measurement/RESULT.json'),('cca','measurement/RESULT.json'),('chains','measurement/RESULT.json'),('pulse-endpoint','RESULT.json'),('stage-archive','RESULT.json')]:write(out/(route+'_RESULT.json'),read(a.results_root/route/filename))
    write(out/'OUTPUT_FREEZE.json',{'files':{p.name:sha(p) for p in out.iterdir() if p.is_file()}})
if __name__=='__main__':main()
