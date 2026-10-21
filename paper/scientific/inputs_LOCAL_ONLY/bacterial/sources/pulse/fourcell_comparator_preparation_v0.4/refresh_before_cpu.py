from pathlib import Path
import hashlib,json,ast,difflib,datetime
O=Path(__file__).resolve().parent;old=O.parent/'fourcell_comparator_preparation_v0.3'
a=(old/'analysis_v0_5.py').read_text();b=(O/'analysis_v0_6.py').read_text()
(O/'comparator03_to04.diff').write_text(''.join(difflib.unified_diff(a.splitlines(True),b.splitlines(True),fromfile='frozen03/analysis_v0_5.py',tofile='NEW04/analysis_v0_6.py')),encoding='utf-8')
functions=lambda s:{n.name:ast.dump(n,include_attributes=False) for n in ast.parse(s).body if isinstance(n,ast.FunctionDef)}
aa,bb=functions(a),functions(b);changed=[n for n in aa if aa[n]!=bb[n]];assert set(changed)=={'validate_history','verified_array_digest'}
payload={'saved_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'actual_selected_SHA256':hashlib.sha256((O/'analysis_v0_6.py').read_bytes()).hexdigest(),'changed_existing_functions':changed,'new_functions':sorted(set(bb)-set(aa)),'all_other_functions_unchanged':[n for n in aa if aa[n]==bb[n]],'initial_preparation_record_is_intermediate':True,'first_shell_candidate_update_failed':'PowerShell quoting rejected inline command before Python start; actual source changed via explicit apply_patch, no old source/data modified'}
with (O/'PRE_CPU_SOURCE_FREEZE.json').open('x',encoding='utf-8') as f:json.dump(payload,f,indent=2)
print(json.dumps(payload))
