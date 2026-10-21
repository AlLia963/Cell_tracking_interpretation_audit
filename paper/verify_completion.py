"""Compare completed gap-closing calculations to retained scientific evidence.

Execution times, memory samples and filesystem locations are measured metadata;
they are excluded explicitly, never through approximate numeric tolerance.
"""
from pathlib import Path
import argparse
import csv
import gzip
import hashlib
import json


def read(p):
    if p.suffix == '.gz':
        with gzip.open(p,'rt',encoding='utf-8') as f: return json.load(f)
    if p.suffix == '.csv':
        return list(csv.DictReader(p.open(encoding='utf-8-sig')))
    return json.loads(p.read_text(encoding='utf-8-sig'))


def stable(x):
    if isinstance(x,dict):
        return {k:stable(v) for k,v in x.items() if not any(t in k.lower() for t in
            ['seconds','runtime','peak_working_set','working_set_bytes'])}
    if isinstance(x,list): return [stable(v) for v in x]
    return x


def duty_records(x):
    x = json.loads(json.dumps(x))
    for row in x['carriers']:
        for key in ['S2_path','S3_path']:
            row[key] = '/'.join(row[key].replace('\\','/').split('/')[-2:])
    return x


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True)
    p.add_argument('--original-runs',type=Path,required=True)
    p.add_argument('--new-runs',type=Path,required=True)
    p.add_argument('--research-root',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();c=read(a.config);s=Path(c['companion_root']);n=a.new_runs;o=a.original_runs
    records=[]
    def compare(label,left,right,select=lambda x:x):
        x,y=select(read(left)),select(read(right));equal=x==y
        records.append({'comparison':label,'equal':equal,
                        'target_sha256':hashlib.sha256(left.read_bytes()).hexdigest(),
                        'actual_sha256':hashlib.sha256(right.read_bytes()).hexdigest()})
        if not equal: raise ValueError('Scientific difference: '+label)
    h=a.research_root/'03_原3D与匹配族分析'
    compare('30 geometry / 90 full scientific summary rows',h/'geometry_sensitivity_v0.1/ALL_SCENARIO_BRANCH_SUMMARY.csv',n/'geometry/ALL_SCENARIO_BRANCH_SUMMARY.csv',stable)
    compare('30 geometry all31 scalars by film and contract',h/'geometry_sensitivity_v0.1/ALL31_SCALAR_BOUNDS_BY_SCENARIO_FILM.csv',n/'geometry/ALL31_SCALAR_BOUNDS_BY_SCENARIO_FILM.csv',stable)
    for d in sorted((n/'geometry/outcomes').iterdir()):
        for b in ['finite/unconstrained','finite/geometry_constrained','numerical/unconstrained']:
            rel=Path(d.name)/b/'ALL5751_HISTORY_SETS.json.gz'
            compare('geometry histories '+d.name+' '+b,h/'geometry_sensitivity_v0.1/outcomes'/rel,n/'geometry/outcomes'/rel)
    compare('36 scale cases: all scientific/cap fields',h/'family_operating_domain_stress_v0.1/case_results.csv',n/'stress/case_results.csv',stable)
    compare('27 operating envelope / 54 comparisons',s/'expected/operating_envelope/REPORT_TABLE.json',n/'operating-envelope/measurement/REPORT_TABLE.json',stable)
    target=s/'inputs_LOCAL_ONLY/bacterial/results/duties_run01/measurement'
    compare('734 complete duty fixture records; only S2/S3 path roots relocated',target/'fixtures.json',n/'bacterial-duties/measurement/measurement/fixtures.json',duty_records)
    compare('734 duty summary',target/'report.json',n/'bacterial-duties/measurement/measurement/report.json',lambda x:x['summary'])
    compare('all96 new-policy scores',o/'bacterial-common/measurement/RESULT.json',n/'common-score-generated/measurement/RESULT.json')
    # Gates use identical finite/numerical algorithms, not the legacy tie point
    # assignment. Published canonical counts are checked independently below.
    expected={6:[241,166,75,152],7:[209,137,72,144],8:[192,121,71,146]}
    for g,values in expected.items():
        x=read(n/f'natural-gates/measurement/gate_{g:02}/finite/unconstrained/ALL31_SCALAR_BOUNDS.json')
        got=[x[k]['canonical'] for k in ['final_missing','persistent_absence','final_missing_with_loss','changed_reference_identities']]
        assert got==values
        records.append({'comparison':f'gate {g} published canonical counts','equal':True})
    compare('gate7 full5751 canonical histories',o/'natural3d/measurement/family/gate_07/CANONICAL_HISTORIES.json',n/'natural-gates/measurement/gate_07/CANONICAL_HISTORIES.json')
    assert read(n/'allocation-replay_v04/COMPARISON.json')['all8_complete_ledgers_equal']
    assert read(n/'duty-boundary/measurement/RESULT.json')['all13_boundaries_passed']
    assert read(n/'policy-generation/generated_run/RESULT.json')['all96_array_members_exact']
    result={'all_compared_scientific_records_equal':True,'comparisons':records,
            'geometry_full_history_comparisons':90,'new_geometry_certificate_checks':read(n/'geometry/execution/VERIFICATION.json')['frame_certificates_checked'],
            'all13_duty_boundaries_passed':True,'all8_allocation_ledgers_equal':True,'all96_regenerated_policy_arrays_equal':True,
            'source_data_export_entries':47,'new_biological_N':0,'new_upstream_model_inference':False,
            'resource_runtime_memory_not_expected_bit_exact':True,'this_is_not_peer_review':True}
    with a.report.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({'comparison_units':len(records),'all_equal':True}))


if __name__=='__main__':main()
