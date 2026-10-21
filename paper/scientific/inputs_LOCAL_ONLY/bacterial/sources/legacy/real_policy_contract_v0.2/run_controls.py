import sys
sys.dont_write_bytecode=True
from pathlib import Path
import importlib.util,json,hashlib,traceback
HERE=Path(__file__).resolve().parent;R=HERE.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    spec=importlib.util.spec_from_file_location('old_fixture_runner',R/'real_policy_contract_v0.1/run_controls.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    # The old fixture selection/injector is unchanged; new checker is loaded here.
    spec2=importlib.util.spec_from_file_location('new_contract_checker',HERE/'contract_accounting.py');new=importlib.util.module_from_spec(spec2);sys.modules[spec2.name]=new;spec2.loader.exec_module(new)
    ledger=json.loads(m.LEDGER.read_text(encoding='utf-8'));records=[]
    source_replay=json.loads((R/'S3_image_veto_replay_v0.1/report.json').read_text(encoding='utf-8'))
    original_bindings={'/'.join(k.replace(chr(92),'/').split('/')[-2:]):v for k,v in source_replay['input_hashes'].items()}
    for film in ledger['result_rows']:
        path=m.GRAPHS/film['film']/'S2_gap_closing.npz';assert sha(path)==original_bindings[film['film']+'/S2_gap_closing.npz']
        g=m.load(path);domain=[(p['source'],p['target']) for p in film['proposal_decision_ledger']]
        contract=dict(schema='certified-append-domain-v1',authority_sha256=sha(m.LEDGER),input_stamp=new.stamp(g),candidate_domain=domain,required_additions=sorted(set(map(tuple,film['independent_expected_winners']))))
        records.append(dict(film=film['film'],contract=contract,input_file_sha256=sha(path)))
    authority_path=HERE/'authority.json'
    with authority_path.open('x',encoding='utf-8') as f:json.dump(dict(schema='pinned-append-authority-v1',contracts=records,independent_ledger_sha256=sha(m.LEDGER),source_replay_sha256=sha(R/'S3_image_veto_replay_v0.1/report.json')),f,indent=2)
    authority=new.load_authority(authority_path,sha(authority_path))
    # Original runner uses Python tuples; serialize candidate domains into the
    # canonical JSON representation of the detached, pinned authority.
    def wrapped(before,after,candidate,contract):
        if contract is not None:contract=json.loads(json.dumps(contract))
        hits=[r['film'] for r in records if r['contract']['input_stamp']==(contract['input_stamp'] if contract else new.stamp(before))]
        if len(hits)!=1:raise ValueError('Cannot bind fixture carrier')
        return new.check(before,after,candidate,contract,authority=authority,film=hits[0])
    m.check=wrapped;m.stamp=new.stamp;m.OUT=HERE/'results';m.HERE=HERE;m.main()
    report_path=HERE/'results/report.json';report=json.loads(report_path.read_text(encoding='utf-8'))
    bindings={str(p):sha(p) for p in [Path(__file__),HERE/'contract_accounting.py',HERE/'PROTOCOL.md',authority_path,R/'real_policy_contract_v0.1/run_controls.py',R/'reusable_analysis_package_v0.1/stage_accounting.py']}
    # Add a separate immutable release/provenance record, preserving runner output.
    with (HERE/'results/new_checker_bindings.json').open('x',encoding='utf-8') as f:json.dump(dict(bindings=bindings,original_fixture_definition_unchanged=True,count_is_same734not_additional_replicates=True),f,indent=2)
if __name__=='__main__':
    try:main()
    except Exception:
        p=HERE/'failure.json'
        if not p.exists():p.write_text(json.dumps(dict(traceback=traceback.format_exc())),encoding='utf-8')
        raise
