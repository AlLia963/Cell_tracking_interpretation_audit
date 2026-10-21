from pathlib import Path
import argparse,json,collections,numpy as np
from source_relative_score import score
root=Path(__file__).resolve().parent
args=argparse.ArgumentParser();args.add_argument('--output',type=Path,required=True);a=args.parse_args();assert not a.output.exists()
arms=['unchanged','strict','affirmative','blend','endpoint','strict_blend'];records=[]
def load(p):
 with np.load(p,allow_pickle=False) as z:
  ids,coords,edges=z['ids'],z['coords'],z['edges']
 return {'nodes':{int(i):list(c) for i,c in zip(ids,coords)},'edges':list(map(tuple,edges.tolist()))}
for p in sorted(root.glob('*_reference_pixel.npz')):
 film=p.name.removesuffix('_reference_pixel.npz')
 with np.load(p,allow_pickle=False) as z:truth=(z['ids'],z['coords'],set(map(tuple,z['edges'].tolist())))
 before,bv=score(load(root/(film+'_unchanged.npz')),truth)
 for arm in arms:
  after,av=score(load(root/(film+'_'+arm+'.npz')),truth);dt=after['TP']-before['TP'];df=after['FP']-before['FP']
  good=dt>0 or df<0;bad=dt<0 or df>0;category='mixed' if good and bad else 'beneficial' if good else 'harmful' if bad else 'measured-null'
  records.append({'film':film,'arm':arm,'before':before,'after':after,'gains':len(av-bv),'losses':len(bv-av),'gain_edges':sorted(av-bv),'loss_edges':sorted(bv-av),'category':category})
 print('RECONSTRUCTED96',film,flush=True)
assert len(records)==96
summaries={}
for arm in arms:
 rr=[r for r in records if r['arm']==arm];summaries[arm]={'films':len(rr),'gains':sum(r['gains'] for r in rr),'losses':sum(r['losses'] for r in rr),'delta_TP':sum(r['after']['TP']-r['before']['TP'] for r in rr),'delta_FP':sum(r['after']['FP']-r['before']['FP'] for r in rr),'categories':dict(collections.Counter(r['category'] for r in rr))}
with a.output.open('x',encoding='utf-8') as f:json.dump({'records':records,'summaries':summaries,'scope':'source-relative sparse-reference recount of all 96 frozen outputs; not a new policy execution or biological replication'},f,indent=2)
print(json.dumps(summaries),flush=True)
