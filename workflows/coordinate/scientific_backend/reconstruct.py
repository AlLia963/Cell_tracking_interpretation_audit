"""Finite frame families for exact sums of calculated binary64 distances.

Extracted from the project research backend. No fixed-cohort driver or data
is included. Correspondence is reference-relative, not biological truth.
"""
import collections, heapq, itertools, math
from fractions import Fraction
import numpy as np
from stage_accounting import load_npz, match

def residual(nr,npred,allowed,ci,base):
    S=nr+npred; T=S+1; arcs=[]; matchedp=set(base.values())
    for r in range(nr): arcs.append((r,S,0) if r in base else (S,r,0))
    for c in range(npred): arcs.append((T,nr+c,0) if c in matchedp else (nr+c,T,0))
    for r,c in zip(*np.nonzero(allowed)):
        r=int(r);c=int(c); cost=ci[r,c]
        arcs.append((nr+c,r,-cost) if base.get(r)==c else (r,nr+c,cost))
    return S,T,arcs


def potential(n,arcs):
    # Super-source with zero arcs to every vertex; exact Bellman-Ford difference
    # constraints. Feasible potentials certify no negative residual cycle.
    p=[0]*n
    for i in range(n):
        changed=False
        for u,v,c in arcs:
            if p[v]>p[u]+c: p[v]=p[u]+c; changed=True
        if not changed: return p,i+1
    raise ValueError('Canonical map has a negative exact-cost residual cycle; exact optimum withheld')


def reachable(n,arcs,S):
    adj=[[] for _ in range(n)]
    for u,v,c in arcs: adj[u].append(v)
    seen={S}; todo=[S]
    while todo:
        u=todo.pop()
        for v in adj[u]:
            if v not in seen: seen.add(v);todo.append(v)
    return seen


def dijkstra(n,adj,start):
    d=[None]*n; d[start]=0; prev=[None]*n; heap=[(0,start)]
    while heap:
        val,u=heapq.heappop(heap)
        if d[u]!=val: continue
        for v,c in adj[u]:
            nv=val+c
            if d[v] is None or nv<d[v]: d[v]=nv;prev[v]=u;heapq.heappush(heap,(nv,v))
    return d,prev


def frame_family(ref,state,canonical,gate,frame,cap):
    if not __debug__:
        raise RuntimeError('CONSTRUCTOR_ASSERTIONS_DISABLED: run without -O and PYTHONOPTIMIZE')
    ri=np.flatnonzero(ref.coords[:,0]==frame); pi=np.flatnonzero(state.coords[:,0]==frame)
    ri=ri[np.argsort(ref.ids[ri])];pi=pi[np.argsort(state.ids[pi])]
    rids=list(map(int,ref.ids[ri]));pids=list(map(int,state.ids[pi]));nr=len(ri);npred=len(pi)
    delta=ref.coords[ri,None,1:]-state.coords[None,pi,1:]
    dist=np.hypot.reduce(delta,axis=2);allowed=dist<=gate
    rix={x:i for i,x in enumerate(rids)};pix={x:i for i,x in enumerate(pids)}
    base={rix[q]:pix[p] for q,p in canonical.items() if q in rix}
    ratios={(int(r),int(c)):float(dist[r,c]).as_integer_ratio() for r,c in zip(*np.nonzero(allowed))}
    denominator=max([d for a,d in ratios.values()],default=1)
    ci={key:a*(denominator//d) for key,(a,d) in ratios.items()}
    S,T,arcs=residual(nr,npred,allowed,ci,base); n=T+1
    reach=reachable(n,arcs,S)
    if T in reach: raise ValueError('Canonical cardinality is not maximum')
    cover=[['reference',rids[r]] for r in range(nr) if r not in reach]+[['prediction',pids[c]] for c in range(npred) if nr+c in reach]
    assert len(cover)==len(base)
    pot,rounds=potential(n,arcs);adj=[[] for _ in range(n)]
    for u,v,c in arcs:
        rc=c+pot[u]-pot[v];assert rc>=0;adj[u].append((v,rc))
    source_d,_=dijkstra(n,adj,S); cache={}
    exact_base=sum(ci[r,c] for r,c in base.items());fsbase=math.fsum(float(dist[r,c]) for r,c in base.items())
    # A global conservative screen: every numerically admitted map has exact
    # gap <= 66 eps * max(1,K*gate), allowing fsum roundoff on both sides.
    screen=Fraction.from_float(66*np.finfo(float).eps*max(1,len(base)*gate))
    screen_int=math.ceil(screen*denominator)
    supports={r:[] for r in range(nr)};forced=[]
    for r in range(nr):
        for c in map(int,np.flatnonzero(allowed[r])):
            if base.get(r)==c: gap=0
            else:
                if c not in cache: cache[c]=dijkstra(n,adj,nr+c)
                back=cache[c][0][r]
                gap=None if back is None else ci[r,c]+pot[r]-pot[nr+c]+back
            keep=gap is not None and gap<=screen_int
            forced.append([rids[r],pids[c],None if gap is None else str(Fraction(gap,denominator)),bool(keep)])
            if keep: supports[r].append(c)
        if r not in base: gap=0
        else: gap=None if source_d[r] is None else pot[r]-pot[S]+source_d[r]
        keep=gap is not None and gap<=screen_int
        forced.append([rids[r],None,None if gap is None else str(Fraction(gap,denominator)),bool(keep)])
        if keep: supports[r].append(None)
        assert supports[r]
    variable=[r for r in range(nr) if len(supports[r])>1]
    combinations=math.prod(len(supports[r]) for r in variable)
    certificate={'frame':int(frame),'reference_ids':rids,'prediction_ids':pids,'canonical_pairs':[[rids[r],pids[c]] for r,c in sorted(base.items())],
      'max_cardinality':len(base),'minimum_vertex_cover':cover,'exact_cost_denominator':str(denominator),'canonical_exact_integer_sum':str(exact_base),
      'canonical_native_fsum_um':fsbase,'residual_potentials_order':'reference_ids,prediction_ids,source,sink','residual_potentials':[str(v) for v in pot],
      'potential_relaxation_rounds':rounds,'allowed_costs_columns':['reference_id','prediction_id','float_hex','scaled_exact_integer_cost'],
      'allowed_costs':[[rids[r],pids[c],float(dist[r,c]).hex(),str(ci[r,c])] for r,c in sorted(ci)],
      'forced_option_columns':['reference_id','prediction_id_or_null','minimum_exact_same_cardinality_gap_or_null_unreachable','conservative_screen_admitted'],
      'forced_options':forced,'support_screen_exact_um':str(screen),'support_options':[[rids[r],[None if c is None else pids[c] for c in supports[r]]] for r in range(nr)],
      'screened_combinations':combinations,'certificate_kind':'exact_integer_residual_dual_and_equal_cardinality_vertex_cover'}
    if combinations>cap: return certificate,None,None,{'status':'WITHHELD_WHOLE_FRAME_CAP','required':combinations,'cap':cap,'scalar_bounds':None}
    finite=[];numeric=[];checks=[]
    for choices in itertools.product(*(supports[r] for r in variable)):
        mapping=dict(base)
        for r,c in zip(variable,choices):
            mapping.pop(r,None)
            if c is not None: mapping[r]=c
        injective=len(set(mapping.values()))==len(mapping);cardinal=len(mapping)==len(base)
        if not injective or not cardinal:
            checks.append({'choices':[None if c is None else pids[c] for c in choices],'one_to_one':injective,'maximum_cardinality':cardinal,'finite_admitted':False,'numerical_admitted':False});continue
        exact=sum(ci[r,c] for r,c in mapping.items()); gap=exact-exact_base
        assert gap>=0
        fsum=math.fsum(float(dist[r,c]) for r,c in mapping.items());fgap=fsum-fsbase;tol=64*np.finfo(float).eps*max(1,abs(fsum),abs(fsbase))
        nf=bool(abs(fgap)<=tol);ef=gap==0
        replacement={str(rids[r]):None if mapping.get(r) is None else pids[mapping[r]] for r in variable}
        if ef: finite.append(replacement)
        if nf: numeric.append(replacement)
        checks.append({'choices':[None if c is None else pids[c] for c in choices],'one_to_one':True,'maximum_cardinality':True,'native_fsum_um':fsum,'native_fsum_gap_um':fgap,
          'exact_calculated_double_sum_gap':str(Fraction(gap,denominator)),'numeric_threshold_um':float(tol),'finite_admitted':ef,'numerical_admitted':nf})
    assert finite and numeric
    def block(assignments,rule):
        return {'frame':int(frame),'references':[rids[r] for r in variable],'assignments':assignments,'rule':rule} if variable else None
    certificate['whole_map_checks']=checks
    certificate['finite_support_options']=[[rids[r],sorted({a.get(str(rids[r]),canonical.get(rids[r])) for a in finite},key=repr)] for r in variable]
    certificate['numerical_support_options']=[[rids[r],sorted({a.get(str(rids[r]),canonical.get(rids[r])) for a in numeric},key=repr)] for r in variable]
    return certificate,block(finite,'exact_calculated_double_minimum'),block(numeric,'64epsilon_numerical_tolerance'),None


