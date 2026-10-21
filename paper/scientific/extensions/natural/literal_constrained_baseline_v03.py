"""Straightforward same-information constrained baseline, with full refusal cost.

Partitions only the raw gated bipartite graph; enumerates all partial injections
inside each component without reading producer certificates or forced options.
The downstream shared component readout is intentionally the SAME function:
this tests construction scope/cost, not superiority to informed arithmetic.
"""
import argparse,collections,hashlib,itertools,json,sys,time
from pathlib import Path
from fractions import Fraction
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'sources/family'))
from reconstruct import load_npz,account_from_matches,joint_readout,links_from_geometry
def emit(p,x):
    with p.open('x',encoding='utf-8')as f:json.dump(x,f,ensure_ascii=False,separators=(',',':'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build_frame(ref,pred,frame,gate,cap):
    ri=np.flatnonzero(ref.coords[:,0]==frame);pi=np.flatnonzero(pred.coords[:,0]==frame)
    ri=ri[np.argsort(ref.ids[ri])];pi=pi[np.argsort(pred.ids[pi])]
    rs=list(map(int,ref.ids[ri]));ps=list(map(int,pred.ids[pi]));dist=np.hypot.reduce(ref.coords[ri,None,1:]-pred.coords[None,pi,1:],axis=2)
    allowed=dist<=gate;cost={(int(i),int(j)):Fraction.from_float(float(dist[i,j]))for i,j in zip(*np.nonzero(allowed))}
    rows={i:list(map(int,np.flatnonzero(allowed[i])))for i in range(len(rs))};reverse=collections.defaultdict(set)
    for i,js in rows.items():
        for j in js:reverse[j].add(i)
    seen=set();components=[]
    for seed in range(len(rs)):
        if seed in seen:continue
        rr={seed};todo=[seed];seen.add(seed)
        while todo:
            i=todo.pop()
            for j in rows[i]:
                for k in reverse[j]:
                    if k not in seen:seen.add(k);rr.add(k);todo.append(k)
        components.append(sorted(rr))
    count=0;domains=[];bestk=0;bestcost=Fraction(0)
    for component in components:
        optimum=(-1,None);maps=[]
        def dfs(idx,used,current,c):
            nonlocal count,optimum,maps
            if idx==len(component):
                count+=1
                if count>cap:raise OverflowError('WITHHELD_LITERAL_COMPONENT_CANDIDATE_LEAF_CAP')
                k=len(current)
                if k>optimum[0]or(k==optimum[0]and(optimum[1]is None or c<optimum[1])):optimum=(k,c);maps=[dict(current)]
                elif k==optimum[0]and c==optimum[1]:maps.append(dict(current))
                return
            i=component[idx]
            dfs(idx+1,used,current,c)
            for j in rows[i]:
                if j in used:continue
                current[i]=j;used.add(j);dfs(idx+1,used,current,c+cost[i,j]);used.remove(j);del current[i]
        dfs(0,set(),{},Fraction(0));domains.append(maps);bestk+=optimum[0];bestcost+=optimum[1]
    n=1
    for ds in domains:n*=len(ds)
    if n>cap:raise OverflowError('WITHHELD_LITERAL_WHOLE_FRAME_OUTPUT_CAP')
    full=[]
    for choices in itertools.product(*domains):
        d={rs[i]:ps[j]for v in choices for i,j in v.items()};full.append(d)
    full.sort(key=lambda d:tuple((q,d.get(q,-1))for q in rs))
    canonical=full[0];variable=[q for q in rs if len({m.get(q)for m in full})>1]
    assignments=[{str(q):m.get(q)for q in variable}for m in full]
    return canonical,{'frame':int(frame),'references':variable,'assignments':assignments}if variable else None,{'frame':int(frame),'reference_ids':rs,'max_cardinality':bestk,'exact_calculated_distance_sum':str(bestcost),'whole_maps':[[[q,p]for q,p in sorted(m.items())]for m in full],'enumerated_partial_injection_leaves':count}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input-root',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--compare-family',type=Path,required=True);ap.add_argument('--cap',type=int,default=1048576);a=ap.parse_args()
    out=a.output.resolve();out.mkdir(exist_ok=False);t=time.perf_counter();data={};records=[];blocks=[];certs=[];fail=[]
    # Every selected natural input used, no positive case selection.
    for film in sorted(a.input_root.iterdir()):
        if not film.is_dir()or not(film/'reference.npz').exists():continue
        ref=load_npz(film/'reference.npz');states=[load_npz(film/f'stage_{k}.npz')for k in range(7)];maps=[]
        for k,state in enumerate(states):
            cm={}
            for frame in np.unique(ref.coords[:,0]):
                try:m,b,c=build_frame(ref,state,frame,7,a.cap)
                except OverflowError as error:fail.append({'film':film.name,'stage':k,'frame':int(frame),'status':str(error)});continue
                cm.update(m);c.update({'film':film.name,'stage':k});certs.append(c)
                if b:b.update({'film':film.name,'stage':k});blocks.append(b)
            maps.append(cm)
        data[film.name]=(ref,states,maps)
        records.extend({'film':film.name,'reference_edge':r['reference_edge'],'history':''.join(map(str,r['visibility'])),'matched_pairs':r['matched_pairs']}for r in account_from_matches(states,ref,maps))
    emit(out/'ALL_FRAME_DOMAINS.json',certs);emit(out/'REFUSALS.json',fail)
    construction=time.perf_counter()-t
    if fail:emit(out/'RESULT.json',{'status':'WITHHELD_LITERAL_BASELINE','construction_seconds':construction,'refusals':fail});return
    links=links_from_geometry(data,blocks)
    for name,ls in [('unconstrained',[]),('geometry_constrained',links['links'])]:
        result,joint,derived=joint_readout(data,records,blocks,ls,a.cap)
        emit(out/(name+'.json'),{'result':result,'histories':derived['histories']if derived else None,'witnesses':derived['witnesses']if derived else None})
    elapsed=time.perf_counter()-t
    emit(out/'SCIENTIFIC_RESULTS_BEFORE_COMPARISON.json',{'construction_seconds_including_input_load':construction,'construction_plus_shared_scalar_report_seconds_including_serialize':elapsed,'frames':len(certs),'reference_relations':len(records),'raw_partial_injection_leaves':sum(c['enumerated_partial_injection_leaves']for c in certs),'refusals':0,'baseline':'Plain gated bipartite component exhaustive partial-injection search; same information and shared downstream joint readout; not fastest known constrained solver.'})
    # Only now consult newly constructed comparison domain/answers.
    bykey={(c['film'],c['stage'],c['frame']):c for c in certs};differences=[]
    for fp in sorted(a.compare_family.glob('*.json')):
        p=json.loads(fp.read_text(encoding='utf-8'))
        if not isinstance(p,dict):continue
        film=p.get('film')
        if 'frame_certificates'not in p:continue
        base=[dict((int(q),int(v))for q,v in m)for m in p['canonical_maps']];bb={(b['stage'],b['frame']):b for b in p['finite_blocks']}
        for c in p['frame_certificates']:
            k=c['stage'];frame=c['frame'];ids=set(c['reference_ids']);expected=[]
            for choice in bb.get((k,frame),{'assignments':[{}]})['assignments']:
                m={q:v for q,v in base[k].items()if q in ids}
                for q,v in choice.items():
                    if v is None:m.pop(int(q),None)
                    else:m[int(q)]=v
                expected.append(tuple(sorted(m.items())))
            actual=[tuple(map(tuple,m))for m in bykey[(film,k,frame)]['whole_maps']]
            if set(expected)!=set(actual):differences.append({'film':film,'stage':k,'frame':frame})
    for name in ['unconstrained','geometry_constrained']:
        actual=json.loads((out/(name+'.json')).read_text(encoding='utf-8'));e=a.compare_family/'finite'/name
        expected=json.loads((e/'ALL5751_HISTORY_SETS.json').read_text(encoding='utf-8'))
        av={(r['film'],tuple(r['reference_edge'])):(r['admissible_visibility_strings'],r['categories'])for r in actual['histories']}
        ev={(r['film'],tuple(r['reference_edge'])):(r['admissible_visibility_strings'],r['categories'])for r in expected}
        if av!=ev:differences.append({'branch':name,'history_sets':'different'})
        bounds=json.loads((e/'ALL31_SCALAR_BOUNDS.json').read_text(encoding='utf-8'))
        for field,b in bounds.items():
            y=actual['result']['all31_scalar_bounds'][field]
            if(y['minimum'],y['maximum'])!=(b['minimum'],b['maximum']):differences.append({'branch':name,'field':field})
    emit(out/'COMPLETE_FAMILY_AND_SCIENTIFIC_COMPARISON.json',{'frames':len(certs),'history_sets_compared_per_convention':len(records),'scalar_fields_per_convention':31,'differences':differences,'pass':not differences})
    assert not differences
    print(json.dumps({'status':'LITERAL_BASELINE_COMPLETE_EQUAL','frames':len(certs),'construction_seconds':construction,'full_seconds':elapsed}))
if __name__=='__main__':main()
