"""Distinct adaptive finite-calculated-double family; preserve numerical/failed runs."""
from pathlib import Path
D=Path(__file__).resolve().parent
prior=D/'run_general_numerical_family_v02.py'
s=prior.read_text(encoding='utf-8')
before='keep=one_to_one and cardinality and abs(gap)<=tol(total,baseline)'
assert s.count(before)==1
s=s.replace(before,"if exact_gap < 0:failures.append({'film':film,'stage':stage,'frame':frame,'negative_exact_gap':str(exact_gap)})\n            keep=bool(one_to_one and cardinality and exact_gap==0)")
s=s.replace("O=D/'gate_08/numerical_family_v0.2'", "O=D/'gate_08/finite_objective_family_v0.4'")
s=s.replace('inputs=[Path(__file__),',"inputs=[Path(__file__),D/'run_general_numerical_family_v02.py',D/'PROTOCOL_FINITE_OBJECTIVE_COMPARISON_v03.md',")
s=s.replace('ACTUAL_ADAPTIVE_WHOLE_FRAME_NUMERICAL_FAMILY_COMPLETE_PENDING_INDEPENDENT_AUDIT',
    'ACTUAL_ADAPTIVE_FINITE_CALCULATED_DOUBLE_FAMILY_COMPLETE_PENDING_INDEPENDENT_AUDIT')
s=s.replace('Retained strict geometric-equality failure; this is a newly explicit per-frame numerical-tolerance family',
    'Retained strict geometric-equality failure and broader numerical family; this branch requires exact equality of calculated-double distance sums')
exec(compile(s,str(Path(__file__)),'exec'),globals())
