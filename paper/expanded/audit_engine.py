"""Exact fixed-graph audit for the 1013 corpus. No tracker inference or GT repair."""
from pathlib import Path
from collections import defaultdict
from itertools import product
from fractions import Fraction
import gzip,hashlib,json,math,sys
import numpy as np
if not __debug__:raise RuntimeError('ASSERTIONS_DISABLED')
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'reference_backend'))
import reconstruct as backend
Graph=backend.load_npz.__globals__['Graph']
GATE=7.0;FRAME_CAP=1048576;QUERY_CAP=65536;BASELINE_CAP=1048576
ENGINE_SHA=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
BACKEND_SHA=hashlib.sha256(Path(backend.__file__).read_bytes()).hexdigest()

def load_graph(p):
    g=backend.load_npz(p)
    if g.unit!='um':raise ValueError('Normalized analysis inputs must explicitly declare um')
    return g

def raw_component_family(ref,pred,cap=BASELINE_CAP):
    """Independent exact partial-injection enumeration of raw gated components."""
    rr=list(map(int,ref.ids));pp=list(map(int,pred.ids))
    d=np.hypot.reduce(ref.coords[:,None,1:]-pred.coords[None,:,1:],axis=2)
    options={i:list(map(int,np.flatnonzero(d[i]<=GATE)))for i in range(len(rr))}
    owners=defaultdict(set)
    for i,cs in options.items():
        for j in cs:owners[j].add(i)
    remaining=set(options);components=[];visited=0
    ratios={(i,j):float(d[i,j]).as_integer_ratio()for i,js in options.items()for j in js}
    den=max((v[1]for v in ratios.values()),default=1);cost={k:a*(den//b)for k,(a,b)in ratios.items()}
    while remaining:
        seed=min(remaining);group={seed};remaining.remove(seed);todo=[seed]
        while todo:
            i=todo.pop()
            for j in options[i]:
                for k in owners[j]&remaining:remaining.remove(k);group.add(k);todo.append(k)
        order=sorted(group,key=lambda i:(len(options[i]),rr[i]));best_k=-1;best_c=None;worlds=[];used=set();mapping={}
        def visit(k,n,c):
            nonlocal visited,best_k,best_c,worlds
            visited+=1
            if visited>cap:raise OverflowError('ORDINARY_ENUMERATION_CAP')
            potential=n+len(order)-k
            if potential<best_k:return
            if potential==best_k and best_c is not None and c>best_c:return
            if k==len(order):
                if n>best_k or(n==best_k and(best_c is None or c<best_c)):best_k,best_c,worlds=n,c,[]
                if n==best_k and c==best_c:worlds.append(dict(mapping))
                return
            i=order[k]
            for j in sorted(options[i],key=lambda j:(cost[i,j],pp[j])):
                if j in used:continue
                used.add(j);mapping[rr[i]]=pp[j];visit(k+1,n+1,c+cost[i,j]);used.remove(j);mapping.pop(rr[i])
            visit(k+1,n,c)
        visit(0,0,0);components.append(worlds)
    number=math.prod(len(x)for x in components)
    if number>cap:raise OverflowError('ORDINARY_WHOLE_FRAME_FAMILY_CAP')
    worlds=[{q:p for part in choice for q,p in part.items()}for choice in product(*components)]
    return worlds,{'component_count':len(components),'enumeration_nodes':visited,'whole_maps':len(worlds),'objective':'max cardinality then exact calculated-distance sum'}

def frame_result(ref,pred,frame):
    canonical=backend.match(pred,ref,GATE);original_seed=dict(canonical)
    ordinary=None;check={}
    try:ordinary,check=raw_component_family(ref,pred)
    except OverflowError as e:check={'status':'WITHHELD','reason':str(e)}
    fallback=None
    try:cert,finite,numeric,withheld=backend.frame_family(ref,pred,canonical,GATE,frame,FRAME_CAP)
    except ValueError as e:
        if ordinary is None:raise
        # A floating assignment proposal can miss the exact rational optimum.
        # Use a fully enumerated optimum only when available, then recertify it.
        fallback={'initial_seed_failure':str(e),'source':'ordinary complete enumeration seed; not independent producer seeding'}
        canonical=dict(ordinary[0]);cert,finite,numeric,withheld=backend.frame_family(ref,pred,canonical,GATE,frame,FRAME_CAP)
    if withheld:return {'status':'WITHHELD_CONSTRUCTION','reason':withheld,'canonical':canonical,'certificate':cert,'ordinary':check}
    worlds=[]
    for choice in finite['assignments']if finite else[{}]:
        m=dict(canonical)
        for q,p in choice.items():
            m.pop(int(q),None)
            if p is not None:m[int(q)]=int(p)
        worlds.append(m)
    ids=list(map(int,ref.ids));sig=lambda w:tuple(w.get(q)for q in ids)
    if ordinary is not None:
        if {sig(w)for w in worlds}!={sig(w)for w in ordinary}:raise RuntimeError('INDEPENDENT_COMPLETE_FAMILY_MISMATCH')
        check.update(status='EXACT_COMPLETE_FAMILY_EQUAL',shared_seed_in_fallback=fallback is not None)
    ci=next(i for i,w in enumerate(worlds)if sig(w)==sig(canonical))
    return {'status':'COMPLETE','reference_ids':ids,'canonical':canonical,'canonical_index':ci,'worlds':worlds,
            'certificate':cert,'ordinary':check,'seed_fallback':fallback,'initial_floating_seed':original_seed}

def framed(g,t):
    at=np.flatnonzero(g.coords[:,0]==t)
    return Graph(g.ids[at],g.coords[at],np.empty((0,2),np.int64),'um')

def frame_key(film,frame,ref,pred):
    h=hashlib.sha256();h.update((film+'|'+str(frame)+'|hypot-float64-exact-7um|1013-v1|'+str(FRAME_CAP)+'|'+str(BASELINE_CAP)+'|'+ENGINE_SHA+'|'+BACKEND_SHA+'|'+np.__version__).encode())
    for x in [ref.ids,ref.coords,pred.ids,pred.coords]:h.update(str(x.shape).encode());h.update(x.tobytes())
    return h.hexdigest()

def save_json_gz(p,x):
    p.parent.mkdir(exist_ok=True,parents=True)
    with gzip.open(p,'wt',encoding='utf8')as f:json.dump(x,f,ensure_ascii=False,separators=(',',':'))

def read_json_gz(p):
    with gzip.open(p,'rt',encoding='utf8')as f:x=json.load(f)
    if'worlds'in x:x['worlds']=[{int(q):p for q,p in w.items()}for w in x['worlds']]
    if'canonical'in x:x['canonical']={int(q):p for q,p in x['canonical'].items()}
    return x

def adjacency(edges):
    out=defaultdict(set);inc=defaultdict(set)
    for a,b in edges:out[int(a)].add(int(b));inc[int(b)].add(int(a))
    return out,inc

def query_value(kind,values,out,inc):
    a,b,c=values
    if kind=='path':
        bits=(int(a is not None and b is not None and b in out.get(a,())),int(b is not None and c is not None and c in out.get(b,())))
        recovery=int(all(bits));exclusive=int(recovery and out.get(a,set())=={b}and out.get(b,set())=={c}and inc.get(b,set())=={a}and inc.get(c,set())=={b})
    else:
        bits=(int(a is not None and b is not None and b in out.get(a,())),int(a is not None and c is not None and c in out.get(a,())))
        recovery=int(all(bits));exclusive=int(recovery and out.get(a,set())=={b,c}and inc.get(b,set())=={a}and inc.get(c,set())=={a})
    return recovery,exclusive,bits

def query(kind,nodes,times,frames,out,inc):
    ts=sorted({times[q]for q in nodes});options=[]
    for t in ts:
        if frames[t]['status']!='COMPLETE':return {'status':'WITHHELD_FRAME','frames':ts}
        qs=[q for q in nodes if times[q]==t];unique={}
        for i,w in enumerate(frames[t]['worlds']):unique.setdefault(tuple(w.get(q)for q in qs),(i,dict(zip(qs,(w.get(q)for q in qs)))))
        options.append(list(unique.values()))
    n=math.prod(len(x)for x in options)
    if n>QUERY_CAP:return {'status':'WITHHELD_QUERY_CAP','frames':ts,'required':n}
    rs=set();ss=set();bits=[set(),set()];witness={}
    for choice in product(*options):
        m={q:p for _,w in choice for q,p in w.items()};rv,sv,ev=query_value(kind,[m.get(q)for q in nodes],out,inc)
        rs.add(rv);ss.add(sv);bits[0].add(ev[0]);bits[1].add(ev[1]);ix=[i for i,w in choice]
        witness.setdefault('r'+str(rv),ix);witness.setdefault('s'+str(sv),ix)
    relaxed={a*b for a,b in product(*bits)}
    # Literal independent arithmetic replays every stored extremum witness.
    for key,ix in witness.items():
        m={q:p for t,i in zip(ts,ix)for q,p in frames[t]['worlds'][i].items()}
        vv=[m.get(q)for q in nodes];a,b,c=vv
        if kind=='path':literal=int(a is not None and b is not None and c is not None and b in out.get(a,())and c in out.get(b,()))
        else:literal=int(a is not None and b is not None and c is not None and b in out.get(a,())and c in out.get(a,()))
        if key.startswith('r')and literal!=int(key[1:]):raise AssertionError('Literal witness replay mismatch')
        got=query_value(kind,vv,out,inc)[int(key.startswith('s'))]
        if got!=int(key[1:]):raise AssertionError('Exclusive witness replay mismatch')
    canonical={q:frames[times[q]]['canonical'].get(q)for q in nodes}
    rc,sc,_=query_value(kind,[canonical[q]for q in nodes],out,inc)
    return {'status':'COMPLETE','frames':ts,'r_values':sorted(rs),'s_values':sorted(ss),'independent_edge_values':sorted(relaxed),
            'r_canonical':rc,'s_canonical':sc,'witnesses':witness,'configurations':n,'strict_relaxation_difference':rs!=relaxed}

def reference_queries(ref):
    outgoing,incoming=adjacency(ref.edges);paths=[];forks=[]
    for b in sorted(set(outgoing)&set(incoming)):
        for a,c in product(sorted(incoming[b]),sorted(outgoing[b])):paths.append((a,b,c))
    for a,kids in sorted(outgoing.items()):
        if len(kids)==2:forks.append((a,*sorted(kids)))
    return paths,forks

def edge_domains(ref,pairs,times,frames):
    canonical=[];minimum=[];maximum=[];failed=[]
    for a,b in map(tuple,ref.edges.tolist()):
        fa,fb=frames[times[a]],frames[times[b]]
        canonical.append(int((fa.get('canonical',{}).get(a),fb.get('canonical',{}).get(b))in pairs))
        if fa['status']!='COMPLETE'or fb['status']!='COMPLETE':minimum.append(-1);maximum.append(-1);failed.append(True);continue
        aa={w.get(a)for w in fa['worlds']};bb={w.get(b)for w in fb['worlds']}
        values={(u,v)in pairs for u,v in product(aa,bb)}
        minimum.append(int(all(values)));maximum.append(int(any(values)));failed.append(False)
    return np.array(canonical,np.int8),np.array(minimum,np.int8),np.array(maximum,np.int8),np.array(failed,bool)

def audit_graph(graph,ref,film,cache):
    frames={};locators={};cache_hits=0;frame_fail=[]
    for t in map(int,np.unique(ref.coords[:,0])):
        rf,pf=framed(ref,t),framed(graph,t);key=frame_key(film,t,rf,pf);p=cache/key[:2]/(key+'.json.gz')
        if p.exists():result=read_json_gz(p);cache_hits+=1
        else:
            try:result=frame_result(rf,pf,t)
            except Exception as e:
                result={'status':'WITHHELD_CONSTRUCTION_ERROR','reason':type(e).__name__+': '+str(e),'canonical':backend.match(pf,rf,GATE)}
            result.update(film=film,frame=t,cache_key=key);save_json_gz(p,result)
        frames[t]=result;locators[t]=str(p.relative_to(cache))
        if result['status']!='COMPLETE':frame_fail.append({'frame':t,'status':result['status'],'reason':result.get('reason')})
    times=dict(zip(map(int,ref.ids),map(int,ref.coords[:,0])));pairs=set(map(tuple,graph.edges.tolist()));can,lo,hi,fail=edge_domains(ref,pairs,times,frames)
    cm={q:p for f in frames.values()for q,p in f.get('canonical',{}).items()};reverse={p:q for q,p in cm.items()};re=set(map(tuple,ref.edges.tolist()));ro={a for a,b in re};ri={b for a,b in re};fp=ignored=0
    for a,b in pairs:
        mapped=(reverse.get(a),reverse.get(b))
        if mapped in re:continue
        if mapped[0]in ro or mapped[1]in ri:fp+=1
        else:ignored+=1
    paths,forks=reference_queries(ref);out,inc=adjacency(graph.edges);queries={};exceptions=[]
    for kind,triples in [('path',paths),('fork',forks)]:
        records=[]
        for index,nodes in enumerate(triples):
            q=query(kind,nodes,times,frames,out,inc);q.update(query_index=index,reference_nodes=list(nodes));records.append(q)
            if q['status']!='COMPLETE'or q.get('strict_relaxation_difference')or len(q.get('r_values',[]))>1:exceptions.append({'kind':kind,**q})
        queries[kind]=records
    summary={'reference_nodes':len(ref.ids),'reference_edges':len(ref.edges),'reference_frames':len(frames),'constructed_frames':len(frames)-cache_hits,'geometry_cache_reuses':cache_hits,
       'canonical_TP':int(can.sum()),'canonical_FN':len(can)-int(can.sum()),'canonical_FP':fp,'canonical_ignored_predictions':ignored,
       'certain_visible':int((lo==1).sum()),'certain_absent':int((hi==0).sum()),'ambiguous_relations':int(((lo==0)&(hi==1)).sum()),'withheld_relations':int(fail.sum()),
       'nonunique_frames':sum(len(f.get('worlds',[]))>1 for f in frames.values()),'ordinary_equal_frames':sum(f.get('ordinary',{}).get('status')=='EXACT_COMPLETE_FAMILY_EQUAL'for f in frames.values()),
       'ordinary_withheld_frames':sum(f.get('ordinary',{}).get('status')=='WITHHELD'for f in frames.values()),'ordinary_seed_fallback_frames':sum(bool(f.get('seed_fallback'))for f in frames.values()),
       'frame_failures':frame_fail,'frame_locators':locators,'canonical_map':cm,'new_biological_N':0}
    for kind,rs in queries.items():
        summary[kind]={'queries':len(rs),'complete':sum(q['status']=='COMPLETE'for q in rs),'withheld':sum(q['status']!='COMPLETE'for q in rs),
                       'always_recovered':sum(q.get('r_values')==[1]for q in rs),'never_recovered':sum(q.get('r_values')==[0]for q in rs),
                       'ambiguous_recovery':sum(q.get('r_values')==[0,1]for q in rs),'strict_relaxation_differences':sum(q.get('strict_relaxation_difference',False)for q in rs)}
    return summary,{'canonical':can,'minimum':lo,'maximum':hi,'withheld':fail},queries,exceptions

def contrast_features(b,a):
    return {'before_TP':int(b),'after_TP':int(a),'gains':int(not b and a),'losses':int(b and not a),'net':int(a)-int(b)}

def coupled_contrast(gb,ga,ref,sb,sa,vb,va,cache,cap=1048576):
    """Exact additive two-output bounds under independent complete frame maps.

    Components share every relevant whole-frame map. They partition uncertain
    relation factors; separate extrema carry globally extendible witnesses.
    """
    metrics=['before_TP','after_TP','gains','losses','net']
    if np.any(vb['minimum']<0)or np.any(va['minimum']<0):return {'status':'WITHHELD_FRAME','bounds':None}
    edges=[tuple(map(int,e))for e in ref.edges];times=dict(zip(map(int,ref.ids),map(int,ref.coords[:,0])))
    vs=[vb,va];summaries=[sb,sa];graphs=[gb,ga];pairs=[set(map(tuple,g.edges.tolist()))for g in graphs]
    frames={};base=[{int(q):p for q,p in s['canonical_map'].items()}for s in summaries]
    active=[];fixed={k:0 for k in metrics};factor_vars={}
    def frame(s,t):
        key=(s,t)
        if key not in frames:frames[key]=read_json_gz(cache/summaries[s]['frame_locators'].get(str(t),summaries[s]['frame_locators'].get(t)))
        return frames[key]
    for i,(a,b)in enumerate(edges):
        uncertain=[vs[s]['minimum'][i]!=vs[s]['maximum'][i]for s in range(2)]
        if not any(uncertain):
            for k,v in contrast_features(vb['canonical'][i],va['canonical'][i]).items():fixed[k]+=v
            continue
        active.append(i);variables=set()
        for s in range(2):
            if not uncertain[s]:continue
            for q in(a,b):
                t=times[q];f=frame(s,t)
                if f['status']!='COMPLETE':return {'status':'WITHHELD_FRAME','bounds':None}
                if len({w.get(q)for w in f['worlds']})>1:variables.add((s,t))
        if not variables:raise AssertionError('Ambiguous edge lacks a variable')
        factor_vars[i]=variables
    parent={v:v for vv in factor_vars.values()for v in vv}
    def find(v):
        while parent[v]!=v:parent[v]=parent[parent[v]];v=parent[v]
        return v
    for vv in factor_vars.values():
        vv=sorted(vv)
        for v in vv[1:]:parent[find(v)]=find(vv[0])
    groups=defaultdict(list)
    for v in parent:groups[find(v)].append(v)
    components=[]
    def visible(s,i,choice):
        if vs[s]['minimum'][i]==vs[s]['maximum'][i]:return int(vs[s]['minimum'][i])
        a,b=edges[i]
        def mapped(q):
            t=times[q];key=(s,t)
            return frames[key]['worlds'][choice[key]].get(q)if key in choice else base[s].get(q)
        return int((mapped(a),mapped(b))in pairs[s])
    for values in sorted(groups.values()):
        variables=sorted(values);iset=[i for i in active if factor_vars[i]&set(variables)]
        count=math.prod(len(frame(*v)['worlds'])for v in variables)
        if count>cap:return {'status':'WITHHELD_COMPONENT_CAP','required':count,'cap':cap,'bounds':None,'affected_reference_edge_indices':iset}
        lo=None;hi=None;lw={};hw={}
        for indexes in product(*(range(len(frame(*v)['worlds']))for v in variables)):
            choice=dict(zip(variables,indexes));value={k:0 for k in metrics}
            for i in iset:
                for k,v in contrast_features(visible(0,i,choice),visible(1,i,choice)).items():value[k]+=v
            if lo is None:lo=dict(value);hi=dict(value);lw={k:list(indexes)for k in metrics};hw=dict(lw)
            else:
                for k,v in value.items():
                    if v<lo[k]:lo[k]=v;lw[k]=list(indexes)
                    if v>hi[k]:hi[k]=v;hw[k]=list(indexes)
        components.append({'variables':[list(v)for v in variables],'reference_edge_indices':iset,'configurations':count,
                           'minimum':lo,'maximum':hi,'minimum_witness':lw,'maximum_witness':hw})
    bounds={k:{'minimum':fixed[k]+sum(c['minimum'][k]for c in components),'maximum':fixed[k]+sum(c['maximum'][k]for c in components)}for k in metrics}
    witnesses={}
    for metric in metrics:
        for side in ['minimum','maximum']:
            choice={tuple(v):i for c in components for v,i in zip(c['variables'],c[side+'_witness'][metric])}
            value=dict(fixed)
            for i in active:
                for k,v in contrast_features(visible(0,i,choice),visible(1,i,choice)).items():value[k]+=v
            if value[metric]!=bounds[metric][side]:raise AssertionError('Extended aggregate endpoint witness failed')
            witnesses[metric+'_'+side]={'frame_map_choices':[[s,t,i]for(s,t),i in sorted(choice.items())],'values':value,'all_other_frames':'canonical complete-family members'}
    return {'status':'COMPLETE','bounds':bounds,'fixed_edge_contributions':fixed,'components':components,'whole_map_endpoint_witnesses':witnesses,
            'proof':'Components partition relation factors and use disjoint whole-frame family variables; product contract gives independent extension. Each scalar endpoint is separate.',
            'simultaneous_extrema_vector_certified':False,'new_biological_N':0}
