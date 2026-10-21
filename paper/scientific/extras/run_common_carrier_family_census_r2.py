"""Retrospective fixed-cohort shared-map census, not another tracker experiment."""
from pathlib import Path
from itertools import product
from types import SimpleNamespace
import collections,datetime,hashlib,importlib.util,json,shutil,sys,time,traceback
import numpy as np

V=Path(__file__).resolve().parent;O=V/'common_carrier_family_census_r2';O.mkdir(exist_ok=False)
INPUT=V/'Supplementary_Software_1_r1_working/inputs_LOCAL_ONLY/bacterial/inputs_LOCAL_ONLY/common_carrier96'
SRC=V/'frozen_review_packet_r1_complete/Software_Source_Inspection/extensions/natural/sources/family'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):
    with Path(p).open('x',encoding='utf-8')as f:json.dump(x,f,ensure_ascii=False,indent=2)
arms=['unchanged','strict','affirmative','blend','endpoint','strict_blend']
refs=sorted(INPUT.glob('*_reference_pixel.npz'));assert len(refs)==16
protocol={'frozen_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'selection':'All16 existing common-carrier films and all6 saved arms, without selecting by ambiguity or outcome. Retrospectively selected old cohort, not a new independent biological sample.',
 'previous_knowledge':'Known same-carrier policy endpoint effects and original eight-film ambiguity are known. No results of this full96 family census have been measured by this script before this protocol.',
 'factors':'Six policy outputs are alternative fixed snapshots, not chronological processing stages or a coupled lineage posterior.',
 'objective':'Inclusive7um, maximum cardinality then exact sum of calculated numpy.hypot.reduce float64 costs. Pixel inputs multiply z/y/x by1.625/.40625/.40625 once. This is a new declared audit contract, distinct from historical np.linalg.norm canonical score.',
 'query':'All reference three-node paths with distinct increasing-time nodes and unique incoming/outgoing middle; both incident reference relations must coexist under one complete map per involved acquisition frame. Compare this joint predicate with independently favourable incident-edge feasibility. Keep every film/arm, cap/failure/null and every identity.',
 'frame_cap':1048576,'local_query_cap':1048576,
 'no_information_advantage_over_full_constrained_baseline_claim':True,
 'no_new_inference_or_biological_N':True,'inputs': [{'path':str(p),'sha256':sha(p)}for p in refs+sorted(INPUT.glob('*.npz'))if not p.name.endswith('_reference_pixel.npz')or p in refs],
 'source':str(SRC/'reconstruct.py'),'source_sha256':sha(SRC/'reconstruct.py')}
write(O/'PROTOCOL_BEFORE_CENSUS.json',protocol)
source=O/'source';shutil.copytree(SRC,source)
spec=importlib.util.spec_from_file_location('carrier_family_constructor',source/'reconstruct.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
G=mod.load_npz.__globals__['Graph'];results=[];frame_records=[];local_records=[];began=time.perf_counter()
def graph(p):
    with np.load(p,allow_pickle=False)as z:
        coords=z['coords'].astype(float,copy=True);coords[:,1:]*=np.array([1.625,.40625,.40625])
        return G(z['ids'],coords,z['edges'],'um')
for rp in refs:
    film=rp.name.removesuffix('_reference_pixel.npz');ref=graph(rp);times=dict(zip(map(int,ref.ids),map(int,ref.coords[:,0])))
    incoming=collections.defaultdict(set);outgoing=collections.defaultdict(set)
    for a,b in ref.edges:outgoing[int(a)].add(int(b));incoming[int(b)].add(int(a))
    paths=[]
    for b in sorted(times):
        if len(incoming[b])==len(outgoing[b])==1:
            a=next(iter(incoming[b]));c=next(iter(outgoing[b]))
            if len({a,b,c})==3 and times[a]<times[b]<times[c]:paths.append((a,b,c))
    for arm in arms:
        p=INPUT/f'{film}_{arm}.npz';pred=graph(p);pairs=set(map(tuple,pred.edges.tolist()));canonical=mod.match(pred,ref,7)
        frames={};failures=[]
        for t in sorted(set(times.values())):
            try:
                cert,finite,numeric,withheld=mod.frame_family(ref,pred,canonical,7,t,1048576)
                choices=finite['assignments']if finite else [{}]
                if withheld:frames[t]=None;failures.append({'frame':t,'reason':withheld})
                else:
                    maps=[]
                    fixed={r:q for r,q in canonical.items()if times[r]==t}
                    for choice in choices:
                        m=dict(fixed)
                        for r,q in choice.items():
                            m.pop(int(r),None)
                            if q is not None:m[int(r)]=int(q)
                        maps.append(m)
                    frames[t]=maps
                frame_records.append({'film':film,'arm':arm,'frame':t,'certificate':cert,'finite':finite,'withheld':withheld})
            except Exception as e:
                frames[t]=None;failures.append({'frame':t,'reason':repr(e)})
                frame_records.append({'film':film,'arm':arm,'frame':t,'failure':repr(e),'traceback':traceback.format_exc()})
        count=collections.Counter();nonunique_frames=sum(len(m)>1 for m in frames.values()if m is not None)
        for a,b,c in paths:
            ts=(times[a],times[b],times[c]);fs=[frames[t]for t in ts]
            if any(m is None for m in fs):
                local_records.append({'film':film,'arm':arm,'path':[a,b,c],'status':'WITHHELD_FRAME','value_set':None});count['withheld']+=1;continue
            domains=[list(dict.fromkeys(tuple(sorted((r,m.get(r))for r in (a,b,c)if times[r]==t))for m in maps))for t,maps in zip(ts,fs)]
            nc=np.prod([len(d)for d in domains],dtype=object)
            if nc>1048576:
                local_records.append({'film':film,'arm':arm,'path':[a,b,c],'status':'WITHHELD_QUERY_CAP','value_set':None});count['withheld']+=1;continue
            values=set();edge_values=[set(),set()];witnesses={}
            for choices in product(*domains):
                m={r:p for choice in choices for r,p in choice if p is not None}
                v1=a in m and b in m and(m[a],m[b])in pairs;v2=b in m and c in m and(m[b],m[c])in pairs
                val=int(v1 and v2);values.add(val);edge_values[0].add(int(v1));edge_values[1].add(int(v2))
                if val not in witnesses:
                    ix=[next(i for i,whole in enumerate(maps)if all(whole.get(r)==q for r,q in choice))for maps,choice in zip(fs,choices)]
                    witnesses[val]=ix
            relaxed={x*y for x,y in product(*edge_values)}
            count['complete']+=1;count['ambiguous']+=int(len(values)>1);count['strict_relaxation_difference']+=int(relaxed!=values)
            local_records.append({'film':film,'arm':arm,'path':[a,b,c],'frames':list(ts),'status':'COMPLETE','value_set':sorted(values),'incident_relaxation_value_set':sorted(relaxed),'strict_relaxation_difference':relaxed!=values,'whole_frame_witness_indices':witnesses})
        results.append({'film':film,'arm':arm,'reference_nodes':len(ref.ids),'reference_relations':len(ref.edges),'paths':len(paths),'frame_failures_or_refusals':failures,'nonunique_complete_frames':nonunique_frames,'counts':dict(count)})
        print(json.dumps({'film':film,'arm':arm,'nonunique_frames':nonunique_frames,**dict(count)}),flush=True)
write(O/'ALL_FRAME_CERTIFICATES.json',frame_records);write(O/'ALL_PATH_REPORTS.json',local_records);write(O/'ALL96_FILM_ARM_CENSUS.json',results)
write(O/'RESULT.json',{'status':'FULL96_RECORDED_WITH_FAILURES_AND_REFUSALS_EXPLICIT','film_arms':len(results),'frame_records':len(frame_records),'path_reports':len(local_records),
 'nonunique_frame_domains':sum(x['nonunique_complete_frames']for x in results),'counts':dict(sum((collections.Counter(x['counts'])for x in results),collections.Counter())),
 'failed_or_withheld_frame_domains':sum(len(x['frame_failures_or_refusals'])for x in results),'elapsed_seconds':time.perf_counter()-began,
 'no_new_biological_N':True,'source_grid_sensitivity_contract_not_physical_uncertainty':True,'source_selection_retrospective':True,'not_independent_new_corpus':True})
print(json.dumps(json.loads((O/'RESULT.json').read_text(encoding='utf-8'))))
