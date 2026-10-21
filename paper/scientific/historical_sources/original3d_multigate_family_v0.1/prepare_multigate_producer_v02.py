"""Retain v01 preparation failure; both uses of the margin RESULT must be adapted."""
from pathlib import Path
D=Path(__file__).resolve().parent
s=(D/'prepare_multigate_producer_v01.py').read_text(encoding='utf-8')
before='family=swap(family,"D/\'actual_v0.1/"+name+"\'", "M/\'"+name+"\'")'
after='family=swap(family,"D/\'actual_v0.1/"+name+"\'", "M/\'"+name+"\'", count=2 if name=="RESULT.json" else 1)'
assert s.count(before)==1
s=s.replace(before,after).replace('PRODUCER_PREPARATION.json','PRODUCER_PREPARATION_v02.json')
exec(compile(s,str(Path(__file__)),'exec'),globals())
