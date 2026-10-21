"""Explicit-input entry for the existing certified saved-graph path task.

This wrapper retains the scientific constructor and creates a hash binding for
later witness replay. It is an audit of fixed outputs, not tracker inference.
"""
from pathlib import Path
import hashlib, json, subprocess, sys

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    if not __debug__:
        raise RuntimeError('CONSTRUCTOR_ASSERTIONS_DISABLED: run without -O and PYTHONOPTIMIZE')
    argv=sys.argv[1:]
    if '--output' not in argv:raise SystemExit('--output <absent-directory> is required')
    out=Path(argv[argv.index('--output')+1]).resolve()
    if out.exists():raise SystemExit('Existing output refused')
    frontend=Path(__file__).resolve().parent/'scientific/extras/analyst/audit_path_statement.py'
    p=subprocess.run([sys.executable,'-X','utf8',str(frontend),*argv])
    if p.returncode:raise SystemExit(p.returncode)
    names=['INPUT_AND_QUERY_CONTRACT.json','REPORT.json']
    if (out/'COMPLETE_FRAME_FAMILIES.json').is_file():names.append('COMPLETE_FRAME_FAMILIES.json')
    record={'schema':'bound-path-audit/1.2','files':{n:sha(out/n) for n in names},
            'wrapper_sha256':sha(Path(__file__).resolve()),
            'binding_is_integrity_not_independent_completeness_proof':True}
    with (out/'REPORT_BINDING.json').open('x',encoding='utf8') as f:json.dump(record,f,indent=2)
if __name__=='__main__':main()
