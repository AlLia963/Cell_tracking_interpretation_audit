from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict
from fractions import Fraction
import ast
import csv
import hashlib
import json
import zipfile
import numpy as np

P=Path(__file__).resolve().parent
A=P.parent
R=A.parent
B=A/'reproduction_LOCAL_ONLY_v0.1'/'external_full'
S=A/'closest_prior_lineage_definitions_v0.1'
O=P/'actual_v0.1'
ARMS=('baseline','max_area','all_components')

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,d):
    with p.open('x',encoding='utf-8') as f:json.dump(d,f,ensure_ascii=False,indent=2)
def require(c,m):
    if not c:raise RuntimeError(m)
def parse(data,frames,name):
    rows=[]
    for line in data.decode('utf-8-sig').splitlines():
        if line.strip():
            row=tuple(map(int,line.split()))
            require(len(row)==4,'Invalid track width '+name)
            rows.append(row)
    ids=[x[0] for x in rows]
    require(len(ids)==len(set(ids)) and all(i>0 for i in ids),'Nonunique/nonpositive IDs '+name)
    table={i:(s,e,p) for i,s,e,p in rows}
    for i,(s,e,p) in table.items():
        require(0<=s<=e<frames and p>=0,'Interval bound '+name)
        if p:
            require(p in table and p!=i and table[p][1]==s-1,'Parent timing '+name)
    return rows,table
def cycle_lengths(table):
    children=defaultdict(list)
    for i,(_,_,p) in table.items():
        if p:children[p].append(i)
    split={i for i,v in children.items() if len(v)>1}
    valid={i: e-s for i,(s,e,p) in table.items() if i in split and p in split}
    return valid
def independent_cca(ref,comp):
    if not ref:return None
    if not comp:return Fraction(0)
    rh=Counter(ref.values());ch=Counter(comp.values())
    rc=cc=0;gap=Fraction(0)
    for length in sorted(set(rh)|set(ch)):
        rc+=rh[length];cc+=ch[length]
        gap=max(gap,abs(Fraction(rc,len(ref))-Fraction(cc,len(comp))))
    return 1-gap
def original_functions():
    expected={'cca.py':'63fdc447afcbeae350a1cb5f8df301ed62cb96089d81d8d2f399f50785873b62',
              'bc.py':'cab0b299382ca6d1c041a7a142261f1c1813f5c03bbf27758576cd3a8581c56d'}
    namespace={'np':np}
    for n,names in [('bc.py',{'get_ids_that_ends_with_split'}),('cca.py',{'is_valid_track','cca'})]:
        require(sha(S/n)==expected[n],'Primary source changed')
        tree=ast.parse((S/n).read_text(encoding='utf-8'))
        funcs=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name in names]
        require({x.name for x in funcs}==names,'Primary function missing')
        # Execute unchanged original function bodies, removing only package imports.
        exec(compile(ast.Module(body=funcs,type_ignores=[]),str(S/n),'exec'),namespace)
    return namespace

def main():
    O.mkdir(exist_ok=False)
    resource=read(B/'RESOURCE_MANIFEST.json')
    pins={str(P/'PROTOCOL.md'):sha(P/'PROTOCOL.md'),str(P/'analyze.py'):sha(P/'analyze.py'),
          str(B/'RESOURCE_MANIFEST.json'):sha(B/'RESOURCE_MANIFEST.json'),
          str(S/'cca.py'):sha(S/'cca.py'),str(S/'bc.py'):sha(S/'bc.py')}
    originals=original_functions()
    roots={x['arm']:x for x in resource['arms']}
    manifests={}
    for arm in ARMS:
        entry=roots[arm];path=B/entry['manifest_relative']
        require(sha(path)==entry['manifest_sha256'],'Prediction manifest changed')
        pins[str(path)]=sha(path)
        manifests[arm]={x['video']:x for x in read(path)['all_video_reports']}
        require(set(manifests[arm])=={f'{i:02d}' for i in range(1,30)},'Not full29')
        for film,m in manifests[arm].items():
            path=Path(entry['native_root'])/film/'res_track.txt'
            require(sha(path)==m['output_hashes']['res_track.txt'],'Prediction track file changed '+str(path))
            pins[str(path)]=sha(path)
    inputs=[]
    # Public archive hash is already admitted and repeatedly independently verified.
    # Bind exact reference member content used here, not another bulk zip hash pass.
    with zipfile.ZipFile(resource['archive_path']) as z:
        for i in range(1,30):
            film=f'{i:02d}';frames=manifests['baseline'][film]['input_frames']
            name=f'CTC/test/{film}_GT/TRA/man_track.txt'
            refbytes=z.read(name)
            refrows,reftable=parse(refbytes,frames,name)
            rec={'film':film,'frames':frames,'reference_member':name,'reference_content_sha256':hashlib.sha256(refbytes).hexdigest(),
                 'reference_rows':refrows,'reference_table':reftable,'predictions':{}}
            for arm in ARMS:
                require(manifests[arm][film]['input_frames']==frames,'Frame domain differs')
                path=Path(roots[arm]['native_root'])/film/'res_track.txt'
                rows,table=parse(path.read_bytes(),frames,str(path))
                rec['predictions'][arm]={'rows':rows,'table':table,'path':str(path)}
            inputs.append(rec)
    write(O/'START_INPUTS.json',{'UTC':datetime.now(timezone.utc).isoformat(),'local_files':pins,
          'reference_archive':resource['archive_path'],'archive_previous_admitted_sha256':resource['archive_sha256'],
          'reference_members':[{k:x[k] for k in ['film','frames','reference_member','reference_content_sha256']} for x in inputs],
          'prospective_preregistration':False,'outcomes_not_computed_at_this_input_freeze':True})
    records=[]
    for movie in inputs:
        film=movie['film'];ref=cycle_lengths(movie['reference_table'])
        arr_ref=np.asarray(movie['reference_rows'],dtype=np.int64).reshape(-1,4)
        true_ref=originals['is_valid_track'](arr_ref)
        require(set(arr_ref[true_ref,0].tolist())==set(ref),'Reference cycle eligibility mismatch')
        for arm in ARMS:
            entry=movie['predictions'][arm];pred=cycle_lengths(entry['table'])
            arr=np.asarray(entry['rows'],dtype=np.int64).reshape(-1,4)
            true_pred=originals['is_valid_track'](arr)
            require(set(arr[true_pred,0].tolist())==set(pred),'Prediction cycle eligibility mismatch')
            exact=independent_cca(ref,pred);original=originals['cca'](arr,arr_ref)
            require((exact is None)==(original is None),'Undefined scope differs')
            if exact is not None:require(abs(float(exact)-original)<=1e-12,'Original CCA differs')
            records.append({'film':film,'arm':arm,'reference_tracks':len(movie['reference_table']),
                'predicted_tracks':len(entry['table']),'reference_complete_cycles':len(ref),'prediction_complete_cycles':len(pred),
                'CCA_exact_numerator':None if exact is None else exact.numerator,
                'CCA_exact_denominator':None if exact is None else exact.denominator,
                'CCA':None if exact is None else float(exact),'pinned_original_CCA':original,
                'reference_cycle_ids_lengths':ref,'prediction_cycle_ids_lengths':pred,
                'prediction_track_path':entry['path']})
    table={(x['film'],x['arm']):x for x in records}
    domain=[f'{i:02d}' for i in range(1,30) if table[(f'{i:02d}','baseline')]['CCA'] is not None]
    summaries={}
    def frac(x):return Fraction(x['CCA_exact_numerator'],x['CCA_exact_denominator'])
    for arm in ARMS:
        values=[frac(table[(film,arm)]) for film in domain]
        macro=sum(values,Fraction(0))/len(values) if values else None
        signs={'positive':[],'null':[],'negative':[]}
        for film in domain:
            delta=frac(table[(film,arm)])-frac(table[(film,'baseline')])
            signs['positive' if delta>0 else 'negative' if delta<0 else 'null'].append(film)
        summaries[arm]={'defined_movies':len(domain),'macro_CCA':float(macro) if macro is not None else None,
                        'macro_exact':str(macro),'paired_movie_directions':signs}
    # Current source pins must still match after the complete87 calculations.
    require(all(sha(path)==v for path,v in pins.items()),'Input changed during experiment')
    with (O/'PER_MOVIE.csv').open('x',encoding='utf-8',newline='') as f:
        keys=['film','arm','reference_tracks','predicted_tracks','reference_complete_cycles','prediction_complete_cycles','CCA_exact_numerator','CCA_exact_denominator','CCA','pinned_original_CCA']
        writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader()
        for x in records:writer.writerow({k:x[k] for k in keys})
    write(O/'IDENTITIES_AND_LENGTHS.json',records)
    result={'UTC':datetime.now(timezone.utc).isoformat(),'status':'ACTUAL_EXISTING29_THREE_POLICY_CCA_DEFINITION_ALIGNED_DUAL_ROUTE_COMPLETE',
            'all87_primary_function_and_independent_exact_routes_agree':True,'all_input_file_pins_unchanged':True,
            'reference_cycle_total':sum(table[(f'{i:02d}','baseline')]['reference_complete_cycles'] for i in range(1,30)),
            'per_arm':summaries,'source_revision':'59481c48a62d4376fe34bed3e3606b4ec4d60972',
            'scope':'CCA definition calculation from already executed three-policy CTC track files; not complete official evaluation-package execution/certification, identity-chain accuracy, new inference/biological N, or fourarm GT admission',
            'retrospective':True,'new_biological_N':0,'fourarm_admission':False,'SF_M1':'MAJOR_OPEN'}
    write(O/'RESULT.json',result)
    print(json.dumps(result,ensure_ascii=False))

try:main()
except Exception as e:
    if O.exists() and not (O/'FAILED.json').exists():write(O/'FAILED.json',{'UTC':datetime.now(timezone.utc).isoformat(),'status':'FAILED','error':repr(e),'results_must_not_be_claimed':True})
    raise
