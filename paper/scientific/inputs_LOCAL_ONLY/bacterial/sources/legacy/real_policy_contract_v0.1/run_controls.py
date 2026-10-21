import sys
sys.dont_write_bytecode=True
from pathlib import Path
import hashlib,json,time,traceback
from collections import Counter,defaultdict
import numpy as np
HERE=Path(__file__).resolve().parent;R=HERE.parent;OUT=HERE/'results'
sys.path.insert(0,str(R/'reusable_analysis_package_v0.1'))
from stage_accounting import Graph
from contract_accounting import check,stamp
GRAPHS=R/'3d_original_pixel_stage_exports'
LEDGER=R/'S3_image_policy_independent_audit_v0.2/decision_ledger.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(path):
    with np.load(path,allow_pickle=False) as d:ids=d['node_ids'];coords=d['coords'];edges=ids[d['edges']]
    return Graph(ids,coords,edges,'pixel')
def changed(g,removed=(),added=(),input_shift=False):
    edges=(set(map(tuple,g.edges.tolist()))-set(removed))|set(added);coords=g.coords.copy()
    if input_shift:coords[0,1]+=0.125
    return Graph(g.ids,coords,np.array(sorted(edges),dtype=np.int64).reshape(-1,2),g.unit)
def last_loss(states):
    losses=[i for i in range(1,len(states)) if states[i-1] and not states[i]]
    return losses[-1] if losses and not states[-1] else None
def independent_equal_information(states,contract_available,binding_valid,required,source_present):
    if not contract_available or not binding_valid:return None
    if required and not source_present:return 'S3_sink'
    hits=np.flatnonzero(np.logical_and(np.array(states[:-1],bool),np.logical_not(states[1:])))
    return 'S4_delete' if not states[-1] and len(hits) and int(hits[-1])+1==2 else None
def main():
    OUT.mkdir(exist_ok=False);start=time.monotonic();ledger=json.loads(LEDGER.read_text(encoding='utf-8'));rows=[];bindings={str(LEDGER):sha(LEDGER)};carrier_records=[]
    for film in ledger['result_rows']:
        name=film['film'];p2=GRAPHS/name/'S2_gap_closing.npz';p3=GRAPHS/name/'S3_safe_divisions.npz';g2=load(p2);g3=load(p3)
        bindings.update({str(p):sha(p) for p in [p2,p3]});assert np.array_equal(g2.ids,g3.ids) and np.array_equal(g2.coords,g3.coords)
        proposals=film['proposal_decision_ledger'];domain=[(p['source'],p['target']) for p in proposals];assert len(domain)==len(set(domain))
        winners=set(map(tuple,film['independent_expected_winners']));old=set(map(tuple,g2.edges.tolist()));actual=set(map(tuple,g3.edges.tolist()));assert actual-old==winners and old<=actual
        contract=dict(schema='certified-append-domain-v1',authority_sha256=sha(LEDGER),input_stamp=stamp(g2),candidate_domain=domain,required_additions=sorted(winners))
        carrier_records.append(dict(film=name,contract=contract,S2_path=str(p2),S3_path=str(p3)))
        for pair in sorted(set(domain)):
            required=pair in winners
            arms=['intact','S3_dropped_emission','S4_delete','unknown_contract','stale_contract_input'] if required else ['policy_excluded']
            for arm in arms:
                before=g2;source_output=g3;final=g3;certificate=contract;origin=None;oracle='satisfied' if required else 'not-required-by-contract';delta=[]
                if arm in ['S3_dropped_emission','unknown_contract']:
                    source_output=changed(g3,removed=[pair]);final=source_output;delta=[dict(stage='S3',operation='drop_emission',edge=pair)];oracle='violated';origin='S3_sink'
                if arm=='S4_delete':final=changed(g3,removed=[pair]);origin='S4_delete';delta=[dict(stage='S4',operation='delete_emitted_pair',edge=pair)]
                if arm=='unknown_contract':certificate=None;oracle='withheld';origin=None
                if arm=='stale_contract_input':before=changed(g2,input_shift=True);oracle='withheld';delta=[dict(stage='S2',operation='shift_first_coordinate_z',amount=.125)];origin=None
                result=check(before,source_output,pair,certificate)
                states=[pair in set(map(tuple,g.edges.tolist())) for g in [before,source_output,final]]
                predicted_origin=None
                if result['decision']=='violated':predicted_origin='S3_sink'
                elif result['decision']!='withheld' and last_loss(states)==2:predicted_origin='S4_delete'
                baseline=independent_equal_information(states,certificate is not None,stamp(before)==contract['input_stamp'],required,states[1])
                rows.append(dict(film=name,arm=arm,candidate=list(pair),required_by_audited_policy=required,input_stamp=stamp(before),fixture_delta=delta,states=states,oracle_contract_decision=oracle,framework_contract=result,oracle_known_fault_site=origin,combined_origin=predicted_origin,equal_information_origin=baseline,final_only_origin=None,first_missing_export=next((i for i,v in enumerate(states) if not v),None),observed_last_loss=last_loss(states)))
        print(name,'fixtures',sum(r['film']==name for r in rows),flush=True)
    assert len(rows)==734
    summary=dict(fixtures=len(rows),carriers=8,arm_counts=dict(Counter(r['arm'] for r in rows)),contract_agreement=sum(r['framework_contract']['decision']==r['oracle_contract_decision'] for r in rows),contract_status_counts=dict(Counter(r['framework_contract']['decision'] for r in rows)),known_fault_trials=sum(r['oracle_known_fault_site'] is not None for r in rows),combined_origin_correct=sum(r['oracle_known_fault_site'] is not None and r['combined_origin']==r['oracle_known_fault_site'] for r in rows),equal_information_correct=sum(r['oracle_known_fault_site'] is not None and r['equal_information_origin']==r['oracle_known_fault_site'] for r in rows),final_only_withheld_known_faults=sum(r['oracle_known_fault_site'] is not None and r['final_only_origin'] is None for r in rows),first_missing_estimand='Export0 for all candidates;not a source duty/causal origin estimator',scope='Artificial raw-ID producer-contract fixtures on real source graphs;not biological reference visibility;not natural causal accuracy')
    (OUT/'fixtures.json').write_text(json.dumps(dict(carriers=carrier_records,trials=rows),indent=2),encoding='utf-8')
    for p in [Path(__file__),HERE/'contract_accounting.py',HERE/'PROTOCOL.md',R/'reusable_analysis_package_v0.1/stage_accounting.py']:bindings[str(p)]=sha(p)
    (OUT/'report.json').write_text(json.dumps(dict(summary=summary,bindings=bindings,runtime_seconds=time.monotonic()-start),indent=2),encoding='utf-8');print(summary,flush=True)
if __name__=='__main__':
    try:main()
    except Exception:
        if OUT.exists():(OUT/'failure.json').write_text(json.dumps(dict(traceback=traceback.format_exc())),encoding='utf-8')
        raise
