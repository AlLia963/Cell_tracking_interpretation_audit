"""Constructed inputs through build, comparison, witness verification and refusal."""
from pathlib import Path
import argparse,json,subprocess,sys
import numpy as np
P=Path(__file__).resolve().parent
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);a=parser.parse_args();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False)
    def save(name,ids,coords,edges):np.savez_compressed(out/(name+'.npz'),ids=np.array(ids,np.int64),coords=np.array(coords,float),edges=np.array(edges,np.int64),unit=np.array('um'))
    save('reference',[1,2,3],[[0,0,0,0],[1,0,0,0],[2,0,0,0]],[(1,2),(2,3)])
    coords=[[0,0,0,0],[1,0,0,-1],[1,0,0,1],[2,0,0,0]]
    save('prediction',[10,20,21,30],coords,[(10,20),(21,30)])
    records=[]
    for name,contract,cap,expected in [('linked','identical-input',1048576,0),('product','independent',1048576,0),('cap_refusal','identical-input',1,2)]:
        cmd=[sys.executable,str(P/'compare.py'),'--reference',str(out/'reference.npz'),'--before',str(out/'prediction.npz'),'--after',str(out/'prediction.npz'),'--output',str(out/name),'--contract',contract,'--cap',str(cap)]
        run=subprocess.run(cmd,capture_output=True,text=True);records.append({'task':name,'returncode':run.returncode,'stdout':run.stdout,'stderr':run.stderr})
        if run.returncode!=expected:raise RuntimeError(records[-1])
        r=json.loads((out/name/'REPORT.json').read_text(encoding='utf8'))
        if expected==2:
            if r['status']!='WITHHELD_COMPONENT_CAP' or r['bounds'] is not None:raise RuntimeError('Not a real refusal')
        else:
            check=subprocess.run([sys.executable,str(P/'verify_endpoints.py'),'--task',str(out/name),'--reference',str(out/'reference.npz'),'--before',str(out/'prediction.npz'),'--after',str(out/'prediction.npz')],capture_output=True,text=True)
            if check.returncode:raise RuntimeError(check.stderr)
            if name=='linked' and any(r['bounds'][m]!={'minimum':0,'maximum':0}for m in ['gains','losses','net']):raise RuntimeError('Identity comparison must be zero')
            if name=='product' and r['bounds']['gains']['maximum']!=1:raise RuntimeError('Product allows the 01 to 10 matching turnover')
    (out/'SUMMARY.json').write_text(json.dumps({'status':'EXPANDED_EXAMPLE_PASS','records':records},indent=2),encoding='utf8');print('EXPANDED_EXAMPLE_PASS')
if __name__=='__main__':main()
