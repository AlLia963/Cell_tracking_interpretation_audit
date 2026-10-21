"""Check every executed certificate, whole-map admission and joint witness.
Uses frozen supplied costs; does not rerun baseline or raw model inference.
"""
import collections, itertools, json, math, time
from fractions import Fraction
import numpy as np
import sensitivity as S

def verify_frame(cert):
    rids=cert['reference_ids'];pids=cert['prediction_ids'];rix={q:i for i,q in enumerate(rids)};pix={p:i for i,p in enumerate(pids)}
    allowed=np.zeros((len(rids),len(pids)),dtype=bool);ci={};dist={};den=int(cert['exact_cost_denominator'])
    for q,p,h,c in cert['allowed_costs']:
        r,v=rix[q],pix[p];allowed[r,v]=True;ci[r,v]=int(c);dist[r,v]=float.fromhex(h)
        assert Fraction(ci[r,v],den)==Fraction.from_float(dist[r,v]) and dist[r,v]<=7
    base={rix[q]:pix[p] for q,p in cert['canonical_pairs']};assert len(base)==cert['max_cardinality'] and len(set(base.values()))==len(base)
    assert sum(ci[x] for x in base.items())==int(cert['canonical_exact_integer_sum'])
    assert math.fsum(dist[x] for x in base.items())==cert['canonical_native_fsum_um']
    cover=set((kind,q) for kind,q in cert['minimum_vertex_cover']);assert len(cover)==len(base)
    assert all(('reference',rids[r]) in cover or ('prediction',pids[c]) in cover for r,c in ci)
    source,sink,arcs=S.R.residual(len(rids),len(pids),allowed,ci,base)
    assert sink not in S.R.reachable(sink+1,arcs,source)
    pot=list(map(int,cert['residual_potentials']));assert all(c+pot[u]-pot[v]>=0 for u,v,c in arcs)
    adj=[[] for _ in pot]
    for u,v,c in arcs:adj[u].append((v,c+pot[u]-pot[v]))
    source_dist,_=S.R.dijkstra(len(pot),adj,source);cache={}
    forced={};screen=Fraction(cert['support_screen_exact_um']);screenint=math.ceil(screen*den)
    for q,p,gap,keep in cert['forced_options']:
        r=rix[q]
        if p is None:
            actual=0 if r not in base else None if source_dist[r] is None else pot[r]-pot[source]+source_dist[r]
        else:
            c=pix[p]
            if base.get(r)==c:actual=0
            else:
                if c not in cache:cache[c]=S.R.dijkstra(len(pot),adj,len(rids)+c)[0]
                back=cache[c][r];actual=None if back is None else ci[r,c]+pot[r]-pot[len(rids)+c]+back
        assert gap==(None if actual is None else str(Fraction(actual,den)))
        assert keep==(actual is not None and actual<=screenint)
        forced[q,p]=keep
    assert len(forced)==len(ci)+len(rids)
    support={q:opts for q,opts in cert['support_options']}
    assert all(set(opts)=={p for (r,p),keep in forced.items() if r==q and keep} for q,opts in support.items())
    variable=[q for q,opts in support.items() if len(opts)>1];combinations=math.prod(len(support[q]) for q in variable)
    assert combinations==cert['screened_combinations']
    if combinations>S.CAP:assert 'whole_map_checks' not in cert;return
    checks=cert['whole_map_checks'];assert len(checks)==combinations
    for choices,c in zip(itertools.product(*(support[q] for q in variable)),checks):
        assert list(choices)==c['choices'];m={rids[r]:pids[p] for r,p in base.items()}
        for q,p in zip(variable,choices):
            m.pop(q,None)
            if p is not None:m[q]=p
        injective=len(set(m.values()))==len(m);cardinal=len(m)==len(base)
        assert c['one_to_one']==injective and c['maximum_cardinality']==cardinal
        if not injective or not cardinal:assert not c['finite_admitted'] and not c['numerical_admitted'];continue
        cost=sum(ci[rix[q],pix[p]] for q,p in m.items());gap=cost-int(cert['canonical_exact_integer_sum']);assert gap>=0
        fs=math.fsum(dist[rix[q],pix[p]] for q,p in m.items());tol=64*np.finfo(float).eps*max(1,abs(fs),abs(cert['canonical_native_fsum_um']))
        assert c['finite_admitted']==(gap==0) and c['numerical_admitted']==(abs(fs-cert['canonical_native_fsum_um'])<=tol)
        assert c['exact_calculated_double_sum_gap']==str(Fraction(gap,den))

def verify_branch(sd,branch,films,records):
    bd=sd/branch;res=S.read(bd/'RESULT.json')
    if res['status'].startswith('WITHHELD'):return {'status':res['status'],'branch':branch}
    doc=S.read(bd/'JOINT_INPUT.LOCAL_ONLY.json.gz');witness=S.read(bd/'COMPLETE_MAPPING_CONFIGURATION_WITNESSES.json.gz')
    histories=S.read(bd/'ALL5751_HISTORY_SETS.json.gz');bounds=S.read(bd/'ALL31_SCALAR_BOUNDS.json')
    blocks=S.read(sd/branch.split('/')[0]/'WHOLE_FRAME_FAMILIES.json.gz')
    ls=S.read(sd/branch.split('/')[0]/'GEOMETRY_LINKS_AND_REJECTIONS.json.gz');links=ls['links'] if branch.endswith('geometry_constrained') else []
    for l in ls['links']:
        assert l['left_domain']==l['right_domain']
        assert all(l['left_candidate_coordinates'][str(p)]==l['right_candidate_coordinates'][str(p)] for p in l['left_domain'] if p is not None)
    allkeys=set(tuple(x) for x in doc['reference_edge_ids']);assert len(allkeys)==5751
    fixed={tuple(x['reference_edge_id']):x['history'] for x in doc['fixed_histories']};represented=dict((key,{h}) for key,h in fixed.items())
    fixedstats=S.R.total_features(fixed.values());mins=dict(fixedstats);maxs=dict(fixedstats);blockowners={};nodeowners={};components=0;configurations=0
    for cw,component in zip(witness,doc['components']):
        film=cw['film'];keys=[tuple(x) for x in component['reference_edge_ids']];assert not set(keys)&set(represented)
        inds=cw['block_indices'];count=math.prod(len(blocks[i]['assignments']) for i in inds)
        assert count==cw['raw_product_configurations_before_links'] and count<=S.CAP
        for i in inds:assert i not in blockowners;blockowners[i]=cw['component']
        for q in cw['references']:
            key=film,q;assert key not in nodeowners or nodeowners[key]==cw['component'];nodeowners[key]=cw['component']
        local=S.read(sd/(film+'.json.gz'));maps=[dict(m) for m in local['certified_canonical_maps']]
        states=films[film];edges=[set(map(tuple,s.edges.tolist())) for s in states]
        accepted=[]
        for values in itertools.product(*(blocks[i]['assignments'] for i in inds)):
            choices={(blocks[i]['stage'],int(q)):p for i,a in zip(inds,values) for q,p in a.items()}
            applicable=[l for l in links if l['film']==film and l['reference_id'] in cw['references']]
            if any(choices.get((l['from_stage'],l['reference_id']),maps[l['from_stage']].get(l['reference_id']))!=choices.get((l['to_stage'],l['reference_id']),maps[l['to_stage']].get(l['reference_id'])) for l in applicable):continue
            accepted.append(choices)
        assert len(accepted)==cw['feasible_configurations']==len(component['configurations'])==len(cw['mapping_choices'])
        stats=[]
        for choices,saved,hs in zip(accepted,cw['mapping_choices'],component['configurations']):
            assert saved==[[k,q,p] for (k,q),p in sorted(choices.items())]
            actual=[]
            for _,a,b in keys:
                h=''.join(str(int((choices.get((k,a),maps[k].get(a)),choices.get((k,b),maps[k].get(b))) in edges[k])) for k in range(7));actual.append(h)
            assert actual==hs;stats.append(S.R.total_features(hs))
        for scalar in mins:
            lo=min(x[scalar] for x in stats);hi=max(x[scalar] for x in stats)
            assert lo==cw['minimum'][scalar] and hi==cw['maximum'][scalar]
            assert stats[cw['minimum_witness_config_index'][scalar]][scalar]==lo
            assert stats[cw['maximum_witness_config_index'][scalar]][scalar]==hi
            mins[scalar]+=lo;maxs[scalar]+=hi
        for i,key in enumerate(keys):represented[key]={hs[i] for hs in component['configurations']}
        components+=1;configurations+=len(accepted)
    assert len(blockowners)==len(blocks);assert set(represented)==allkeys
    canonical=S.R.total_features(x['history'] for x in records)
    for scalar,b in bounds.items():assert b=={'canonical':canonical[scalar],'minimum':mins[scalar],'maximum':maxs[scalar]}
    assert len(bounds)==31
    for x in histories:
        key=x['film'],*x['reference_edge'];assert set(x['admissible_visibility_strings'])==represented[key]
        assert x['categories']==S.R.categories(x['admissible_visibility_strings'])
    S.partition(histories)
    return {'status':'PASS','branch':branch,'reference_relations':5751,'scalar_bounds_checked':31,'components':components,'complete_configurations_checked':configurations,'whole_frame_blocks':len(blocks)}

def main():
    beg=time.perf_counter();S.verify_freeze();manifest=S.read(S.ROOT/'INPUT_CONSUMPTION_MANIFEST.json')
    films={film:[S.load_npz(S.INPUT/film/f'stage_{k}.npz') for k in range(7)] for film in manifest['films']}
    checks=[];frames=0;repairs=0
    for scenario in S.read(S.ROOT/'SCENARIOS.json'):
        sid=scenario['scenario_id'];sd=S.ROOT/'outcomes'/sid
        for film in manifest['films']:
            local=S.read(sd/(film+'.json.gz'))
            for cert in local['frame_certificates']:verify_frame(cert);frames+=1
            for failed in local['original_matcher_failure_and_exact_repairs']:
                assert failed['objective_changed'] is False
                assert failed['negative_cycle_evidence'] is not None or failed['sink_reachable_from_source']
                if failed['negative_cycle_evidence']:assert int(failed['negative_cycle_evidence']['scaled_integer_sum'])<0
                repairs+=1
        records=S.read(sd/'CANONICAL_HISTORIES.json.gz')
        for branch in ['finite/unconstrained','finite/geometry_constrained','numerical/unconstrained']:
            checks.append({'scenario_id':sid,**verify_branch(sd,branch,films,records)})
        print(json.dumps({'verified':sid,'certificates':frames,'seconds':time.perf_counter()-beg}),flush=True)
    result={'UTC':S.now(),'status':'PASS_COMPLETE_EXECUTED_EVIDENCE','scenario_count':30,'frame_certificates_checked':frames,
      'branch_checks':checks,'actual_original_matcher_failure_repairs_checked':repairs,'elapsed_seconds':time.perf_counter()-beg,
      'raw_npz_rehashed':False,'baseline_recomputed':False,'residual_cover_potential_forced_support_and_all_whole_map_admission_checked':True,
      'complete_component_products_history_vectors_and_all31_scalar_witness_indices_checked':True}
    S.write(S.ROOT/'execution'/'VERIFICATION.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='branch_checks'}))

if __name__=='__main__':main()
