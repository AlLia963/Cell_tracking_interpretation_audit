"""Read-only post-execution audit, implemented without importing generation/readout modules."""
import csv, fractions, gzip, hashlib, json, math
from pathlib import Path

ROOT=Path(__file__).resolve().parent
def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def gzread(p):
    with gzip.open(p,'rt',encoding='utf-8') as f: return json.load(f)
def csvread(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
def features(hs):
    total={'final_missing':0,'persistent_absence':0,'final_missing_with_loss':0,'visibility_transition_edges':0,
           'first_last_loss_disagreements_final_missing':0,'final_last_loss_persistent':0,'stage_visible_0':0,
           'stage_visible_1':0,'gain_1':0,'loss_1':0,'final_last_loss_1':0}
    for h in hs:
        a,b=(int(v) for v in h)
        total['final_missing']+=1-b; total['persistent_absence']+=int(a+b==0)
        total['final_last_loss_persistent']+=int(a+b==0)
        total['stage_visible_0']+=a; total['stage_visible_1']+=b
        total['visibility_transition_edges']+=abs(b-a)
        if a>b:
            total['loss_1']+=1; total['final_last_loss_1']+=1; total['final_missing_with_loss']+=1
        elif b>a: total['gain_1']+=1
    return total
def audit():
    checked=0
    for manifest in ('INPUT_SOURCE_FREEZE.json','OUTPUT_FREEZE.json'):
        for row in read(ROOT/manifest)['files']:
            p=ROOT/row['path']; assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']; checked+=1
    design=read(ROOT/'DESIGN_FREEZE.json'); run=read(ROOT/'RUN_COMPLETE.json')
    assert design['cases']==36 and design['frame_cap']==design['component_cap']==65536
    assert not run['unexpected_worker_failures']
    counts={'cases':0,'certificates':0,'complete_frame_family_blocks':0,'finite_members_checked':0,
            'actual_joint_configuration_members_checked':0,'separate_scalar_endpoint_witnesses_checked':0,
            'literal_validated_cases':0,'analytical_only_cases':0,'scalar_report_cases':0,'withheld_cases':0}
    summary=[]
    for fixed in design['fixed_cases']:
        case=read(ROOT/fixed['path']); out=ROOT/'results'/fixed['case_id']; counts['cases']+=1
        frames=gzread(out/'frame_members.json.gz')['frames']; n=case['n_per_frame']
        for frame in frames:
            cert=gzread(out/frame['certificate_file']); counts['certificates']+=1
            rids=cert['reference_ids']; pids=cert['prediction_ids']; nr=len(rids); npred=len(pids)
            assert nr==npred==n and cert['max_cardinality']==n
            base=dict(cert['canonical_pairs']); den=int(cert['exact_cost_denominator']); ci={}
            for r,p,h,v in cert['allowed_costs']:
                value=float.fromhex(h); assert value<=case['gate_um']
                assert fractions.Fraction(int(v),den)==fractions.Fraction.from_float(value)
                ci[r,p]=int(v)
            cover=set(map(tuple,cert['minimum_vertex_cover'])); assert len(cover)==n
            assert all(('reference',r) in cover or ('prediction',p) in cover for r,p in ci)
            ridx={v:i for i,v in enumerate(rids)}; pidx={v:i+nr for i,v in enumerate(pids)}
            source=nr+npred; sink=source+1; pot=list(map(int,cert['residual_potentials']))
            arcs=[]
            for r in rids: arcs.append((ridx[r],source,0) if r in base else (source,ridx[r],0))
            matched=set(base.values())
            for p in pids: arcs.append((sink,pidx[p],0) if p in matched else (pidx[p],sink,0))
            for (r,p),v in ci.items(): arcs.append((pidx[p],ridx[r],-v) if base.get(r)==p else (ridx[r],pidx[p],v))
            assert all(v+pot[a]-pot[b]>=0 for a,b,v in arcs)
            reached={source}
            while True:
                new={b for a,b,v in arcs if a in reached}-reached
                if not new: break
                reached|=new
            assert sink not in reached
            assert sum(ci[r,p] for r,p in base.items())==int(cert['canonical_exact_integer_sum'])
            if frame['complete']:
                counts['complete_frame_family_blocks']+=1; assert frame['members'] and not frame['cap']
                assert len(frame['members'])==int(case['expected_frame_finite_count_analytic'])
                for m in frame['members']:
                    m={int(r):p for r,p in m.items()}
                    assert set(m)==set(rids) and len(set(m.values()))==n
                    assert sum(ci[r,p] for r,p in m.items())==int(cert['canonical_exact_integer_sum'])
                    counts['finite_members_checked']+=1
                assert sum(c['finite_admitted'] for c in cert['whole_map_checks'])==len(frame['members'])
            else:
                assert frame['members'] is None and cert['screened_combinations']>65536
                assert frame['cap']['status']=='WITHHELD_WHOLE_FRAME_CAP'
        literal=read(out/'literal_validation.json')
        if n<=8:
            counts['literal_validated_cases']+=1; assert literal['status']=='PASS_INDEPENDENT_LITERAL_PERMUTATION_CHECK'
            for f in literal['frame_checks']:
                assert f['literal_permutations_checked']==math.factorial(n)
                assert f['literal_optimum_count']==int(case['expected_frame_finite_count_analytic'])
                assert f['independent_math_dist_equals_calculated_source_costs']
                if f['production_family_complete']: assert f['literal_member_set_equals_generated_finite_family']
                else: assert f['literal_member_set_equals_generated_finite_family'] is None
            for claims in literal['shared_endpoint_claim_checks']:
                assert claims['joint_visible_count_values']==[1]
                assert not claims['claims_edge0_visible_and_edge1_visible_jointly_possible']
                if case['kind']=='exact_degenerate': assert all(claims['each_edge_separately_visible_possible'])
        else:
            counts['analytical_only_cases']+=1; assert literal['status']=='ANALYTIC_ONLY_NOT_ENUMERATED'
        js=read(out/'joint_construction_status.json'); reportfile=out/'generic_joint_readout.json'
        if reportfile.exists():
            counts['scalar_report_cases']+=1; assert js['status']=='COMPLETE_ACTUAL_JOINT_CONFIGURATIONS'
            doc=read(out/'joint_input.json'); report=read(reportfile); rows=csvread(out/'joint_member_report.csv')
            assert len(rows)==js['actual_joint_configurations']<=65536
            totals=[]; observed=[]
            es=[set(map(tuple,s['edges'])) for s in case['stages']]
            for row in rows:
                maps=[{},{}]; indices=json.loads(row['frame_member_indices'])
                for frame,i in zip(frames,indices): maps[frame['stage']].update({int(r):p for r,p in frame['members'][i].items()})
                hs=[''.join(str(int((m[a],m[b]) in edges)) for m,edges in zip(maps,es)) for a,b in case['reference']['edges']]
                assert hs==json.loads(row['histories']); vals=features(hs)
                assert all(vals[k]==int(row[k]) for k in vals)
                if case['kind']=='exact_degenerate': assert all(sum(int(h[k]) for h in hs)==1 for k in range(2))
                totals.append(vals); observed.append(hs); counts['actual_joint_configuration_members_checked']+=1
            if doc['components']: assert observed==doc['components'][0]['configurations']
            else: assert observed==[[r['history'] for r in doc['fixed_histories']]]
            for e in csvread(out/'scalar_endpoint_witnesses.csv'):
                field=e['field']; lo=int(e['minimum']); hi=int(e['maximum'])
                assert lo==min(t[field] for t in totals) and hi==max(t[field] for t in totals)
                assert totals[int(e['minimum_witness_configuration_index'])][field]==lo
                assert totals[int(e['maximum_witness_configuration_index'])][field]==hi
                assert report['scalar_bounds'][field]=={'minimum':lo,'maximum':hi}
                counts['separate_scalar_endpoint_witnesses_checked']+=2
            if case['kind']=='exact_degenerate':
                assert not any(t['persistent_absence']==n-1 and t['visibility_transition_edges']==2 for t in totals)
                assert set(t['visibility_transition_edges'] for t in totals)=={0,2}
        else:
            counts['withheld_cases']+=1; assert js['scalar_bounds'] is None
            assert read(out/'given_family_readout_profile.json')['runtime_seconds'] is None
        summary.append({'case_id':fixed['case_id'],'audit':'PASS','production_family_complete':all(f['complete'] for f in frames),
                        'complete_scalar_report':reportfile.exists(),'literal_validation':literal['status']})
    assert counts['cases']==36 and counts['certificates']==144 and counts['scalar_report_cases']==29 and counts['withheld_cases']==7
    payload={'status':'PASS','frozen_artifact_hashes_checked':checked,'counts':counts,
             'audit_independent_of_generation_and_generic_readout_functions':True,
             'certificate_checks':'allowed exact costs, equal-size cover, no augmenting path, nonnegative reduced residual costs, all finite member costs and injectivity',
             'joint_member_checks':'every saved configuration row rebuilt from four actual frame member indices and raw stage edges; independent two-stage feature arithmetic and all scalar endpoint witnesses',
             'cap_refusals_preserved':True,'biological_N':0,'case_audits':summary}
    with (ROOT/'POST_RUN_AUDIT.json').open('x',encoding='utf-8') as f: json.dump(payload,f,ensure_ascii=False,indent=2)
    print(json.dumps({'status':'PASS',**counts},ensure_ascii=False))
if __name__=='__main__': audit()
