"""Root second implementation; not an independent human or paper review.

Raw exhaustive gated-bipartite construction is frozen before reading producer
answers. Direct path enumeration uses only three nodes, proved independent of
all other gated components in these explicitly constructed cases.
"""
import argparse, hashlib, importlib.util, itertools, json, sys, time
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
NAT=HERE.parent/'natural'
sys.path.insert(0,str(NAT/'sources/family'))
spec=importlib.util.spec_from_file_location('literal',NAT/'literal_constrained_baseline_v03.py')
literal=importlib.util.module_from_spec(spec);spec.loader.exec_module(literal)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def emit(p,x):
    with Path(p).open('x',encoding='utf-8')as h:json.dump(x,h,ensure_ascii=False,indent=2);h.write('\n')
def category(h):
    last=[i for i in range(1,len(h))if h[i-1:i+1]=='10']
    return 'final_present'if h[-1]=='1'else f'loss_stage_{last[-1]}'if last else 'persistent_absence'
def main(inputrun,out):
    out.mkdir(exist_ok=False);t=time.perf_counter();manifest=read(inputrun/'INPUT_COHORT_FROZEN_BEFORE_QUERY.json');own=[];rawfamilies={};graphs={};frames=0;rawleaves=0
    for case in manifest['cases']:
        ref=literal.load_npz(inputrun/case['files'][0]['path']);ss=[literal.load_npz(inputrun/f['path'])for f in case['files'][1:]]
        cm=[];allmaps=[];adj=[]
        for si,s in enumerate(ss):
            mapping={};fs={}
            for frame in (0,1,2):
                base,block,cert=literal.build_frame(ref,s,frame,2,65536);mapping.update(base);fs[frame]=[dict(m)for m in cert['whole_maps']];frames+=1;rawleaves+=cert['enumerated_partial_injection_leaves']
            cm.append(mapping);allmaps.append(fs)
            inc={int(q):set()for q in s.ids};outg={int(q):set()for q in s.ids}
            for a,b in s.edges:outg[int(a)].add(int(b));inc[int(b)].add(int(a))
            adj.append((outg,inc))
        # Prove from raw gated geometry that a focal path's variable domain has
        # no competing reference at the same acquisition frame.
        n=case['objects_per_frame'];nodes=[tuple(map(int,ref.ids[[j,n+j,2*n+j]]))for j in range(n)]
        rcoords={int(q):c for q,c in zip(ref.ids,ref.coords)}
        caseown=[]
        for conv in ('per_view_product','unchanged_geometry_equality'):
            for a,b,c in nodes:
                domains=[]
                for si,s in enumerate(ss):
                    ds=sorted({m.get(b)for m in allmaps[si][1]},key=repr);domains.append(ds)
                    for p in ds:
                        pc=s.coords[np.flatnonzero(s.ids==p)[0]]
                        distance=np.hypot.reduce(ref.coords[:,1:]-pc[1:],axis=1)
                        rr=ref.ids[(ref.coords[:,0]==1)&(distance<=2)]
                        if set(map(int,rr))!={b}:raise AssertionError('Focal projection is not independently extendible')
                histories=set();pairs=set()
                for values in itertools.product(*domains):
                    if conv=='unchanged_geometry_equality'and len(set(values))!=1:continue
                    rh=[];eh=[]
                    for si,pb in enumerate(values):
                        pa,pc=cm[si][a],cm[si][c];og,ic=adj[si]
                        r=int(pb in og[pa]and pc in og[pb]);e=int(r and og[pa]=={pb}and og[pb]=={pc}and ic[pb]=={pa}and ic[pc]=={pb})
                        rh.append(str(r));eh.append(str(e))
                    pair=(''.join(rh),''.join(eh));pairs.add(pair);histories.add(pair[0])
                row={'case':case['name'],'convention':conv,'query_id':case['name']+':three_node_path:'+str(b),'histories':sorted(histories),'categories':sorted({category(h)for h in histories}),'pairs':sorted(map(list,pairs))}
                caseown.append(row);own.append(row)
        rawfamilies[case['name']]=allmaps;graphs[case['name']]=(ref,ss,adj,cm)
    emit(out/'RAW_RESULTS_FROZEN_BEFORE_PRODUCER_COMPARISON.json',{'frames':frames,'raw_partial_injection_leaves':rawleaves,'reports':own})
    # Only now read actual producer scientific outputs.
    actualreports={};framescompared=0;membership=0
    for case in manifest['cases']:
        for conv in ('per_view_product','unchanged_geometry_equality'):
            p=read(inputrun/case['name']/(conv+'.json'))
            for row in p['new']:actualreports[case['name'],conv,row['query_id']]=row
            for block in p['original_blocks']:
                ds={tuple(m.get(q)for q in block['references'])for m in rawfamilies[case['name']][int(block['stage'][1:])][block['frame']]}
                ps={tuple(a[str(q)]for q in block['references'])for a in block['assignments']}
                if ds!=ps:raise AssertionError('Whole-frame families differ from raw literal optimum')
                framescompared+=1
            for proof in p['factor_proofs']:
                b=p['original_blocks'][proof['original_frame_block_index']];ss=[p['split_blocks'][i]for i in proof['factor_block_indices']]
                combined={tuple({q:p for bb,a in zip(ss,aa)for q,p in a.items()}[str(q)]for q in b['references'])for aa in itertools.product(*(bb['assignments']for bb in ss))}
                original={tuple(a[str(q)]for q in b['references'])for a in b['assignments']}
                if combined!=original:raise AssertionError('Literal projection product contains missing/extra whole map')
                membership+=1
    for r in own:
        a=actualreports[r['case'],r['convention'],r['query_id']]
        if a['pair_recovery']['histories']!=r['histories']or a['pair_recovery']['categories']!=r['categories']or a['joint_history_pairs']!=r['pairs']:raise AssertionError('Direct node-level enumeration disagrees')
    witnessrows=read(inputrun/'HISTORY_WITNESS_MEMBERSHIP_AND_REPLAY.json');replayed=0
    cache={}
    for w in witnessrows:
        key=(w['case'],w['convention'])
        if key not in cache:cache[key]=read(inputrun/w['case']/(w['convention']+'.json'))
        p=cache[key];ref,ss,adj,cm=graphs[w['case']];maps=[dict(m)for m in cm]
        for b,idx in zip(p['original_blocks'],w['whole_frame_family_indices']):
            si=int(b['stage'][1:]);a=b['assignments'][idx]
            for q,x in a.items():
                maps[si].pop(int(q),None)
                if x is not None:maps[si][int(q)]=x
            rm=rawfamilies[w['case']][si][b['frame']]
            if tuple(maps[si].get(q)for q in b['references'])not in{tuple(m.get(q)for q in b['references'])for m in rm}:raise AssertionError('Witness not in independently recovered raw full family')
        b=int(w['query_id'].rsplit(':',1)[1]);n=len(ref.ids)//3;a,c=b-n,b+n;h=[]
        for m,(og,ic)in zip(maps,adj):
            pa,pb,pc=[m[q]for q in(a,b,c)];r=pb in og[pa]and pc in og[pb]
            v=r if w['readout']=='pair_recovery'else r and og[pa]=={pb}and og[pb]=={pc}and ic[pb]=={pa}and ic[pc]=={pb};h.append(str(int(v)))
        if ''.join(h)!=w['history']:raise AssertionError('Witness actual readout failed')
        replayed+=1
    emit(out/'AUDIT_COMPLETE.json',{'status':'ROOT_RAW_LITERAL_SECOND_IMPLEMENTATION_EQUAL','cases':len(manifest['cases']),'raw_frame_optimum_sets':frames,'actual_projection_blocks_compared':framescompared,'exact_product_set_proofs':membership,'reports_equal':len(own),'whole_map_membership_and_history_replays':replayed,'elapsed_seconds':time.perf_counter()-t,'independent_paper_review':False,'producer_read_after_own_results_freeze':True})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input-run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.input_run,a.output)
