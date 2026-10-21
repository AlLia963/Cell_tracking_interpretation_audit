"""Build and compare two normalized saved graphs from explicit primitive inputs."""
from pathlib import Path
import argparse,json,sys
import numpy as np
import audit_engine as E
from linked_contrast import linked_contrast

def validate(g,label):
    if g.unit!='um':raise ValueError(label+': explicit normalized um required')
    if g.coords.shape!=(len(g.ids),4) or not np.isfinite(g.coords).all():raise ValueError(label+': finite tzyx coordinates required')
    if len(set(map(int,g.ids)))!=len(g.ids):raise ValueError(label+': duplicate node IDs')
    if not np.equal(g.coords[:,0],np.floor(g.coords[:,0])).all():raise ValueError(label+': noninteger acquisition indices')
    times=dict(zip(map(int,g.ids),g.coords[:,0]))
    if g.edges.ndim!=2 or g.edges.shape[1]!=2:raise ValueError(label+': Nx2 relations required')
    if len(set(map(tuple,g.edges.tolist())))!=len(g.edges):raise ValueError(label+': duplicate relations')
    for a,b in g.edges:
        if int(a) not in times or int(b) not in times:raise ValueError(label+': edge endpoint missing')
        if times[int(a)]>=times[int(b)]:raise ValueError(label+': relations must advance acquisition time')

def run(reference,before,after,output,contract='identical-input',cap=1048576):
    if contract not in ('independent','identical-input'):
        raise ValueError('Unknown comparison contract')
    if type(cap) is not int or cap < 1:
        raise ValueError('cap must be a positive integer')
    output=Path(output)
    if output.exists():raise FileExistsError('Use a new output directory')
    inputs=[Path(x).resolve()for x in [reference,before,after]]
    ref,gb,ga=[E.load_graph(x)for x in inputs]
    for label,g in zip(['reference','before','after'],[ref,gb,ga]):validate(g,label)
    output.mkdir(parents=True);cache=output/'frame_cache'
    primitive_inputs={label:{'path':str(p),'sha256':E.hashlib.sha256(p.read_bytes()).hexdigest()}for label,p in zip(['reference','before','after'],inputs)}
    input_contract={'unit':'um','inclusive_gate_um':7,'objective':'maximum cardinality then exact sum of calculated float64 hypot distances','types':'untyped directed relations','component_cap':cap,'matching_identity':'same reference and full predicted IDs and coordinates at a frame; same object-ID namespace required'}
    declaration={'contract':contract,'primitive_inputs':primitive_inputs,'input_contract':input_contract}
    (output/'COMPARISON_CONTRACT.json').write_text(json.dumps(declaration,ensure_ascii=False,indent=2),encoding='utf8')
    built=[E.audit_graph(g,ref,'declared-comparison',cache)for g in [gb,ga]]
    ss=[x[0]for x in built];vs=[x[1]for x in built]
    fs=[{int(t):E.read_json_gz(cache/loc)for t,loc in s['frame_locators'].items()}for s in ss]
    result=linked_contrast([gb,ga],ref,ss,vs,fs,cap=cap,enable_links=contract=='identical-input')
    result['contract']=contract
    result['primitive_inputs']=primitive_inputs
    result['input_contract']=input_contract
    for i,s in enumerate(ss):E.save_json_gz(output/('graph_'+str(i)+'.json.gz'),s)
    bound=[output/'COMPARISON_CONTRACT.json']+[output/('graph_'+str(i)+'.json.gz')for i in range(2)]+sorted(cache.rglob('*.json.gz'))
    result['artifact_bindings']={str(p.relative_to(output)).replace('\\','/'):E.hashlib.sha256(p.read_bytes()).hexdigest()for p in bound}
    (output/'REPORT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['reference','before','after','output']:p.add_argument('--'+key,required=True)
    p.add_argument('--contract',choices=['independent','identical-input'],default='identical-input');p.add_argument('--cap',type=int,default=1048576)
    a=p.parse_args();r=run(**vars(a));print(r['status']);sys.exit(0 if r['status']=='COMPLETE'else 2)
