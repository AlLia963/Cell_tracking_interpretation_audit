"""Retain v02 partial output; convert NumPy's tolerance comparison to JSON bool."""
from pathlib import Path
D=Path(__file__).resolve().parent
prior=D/'run_general_numerical_family_v02.py'
s=prior.read_text(encoding='utf-8')
before='keep=one_to_one and cardinality and abs(gap)<=tol(total,baseline)'
assert s.count(before)==1
s=s.replace(before,'keep=bool(one_to_one and cardinality and abs(gap)<=tol(total,baseline))')
s=s.replace("O=D/'gate_08/numerical_family_v0.2'", "O=D/'gate_08/numerical_family_v0.3'")
s=s.replace('inputs=[Path(__file__),',"inputs=[Path(__file__),D/'run_general_numerical_family_v02.py',")
exec(compile(s,str(Path(__file__)),'exec'),globals())
