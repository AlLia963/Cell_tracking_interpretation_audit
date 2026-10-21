"""Controlled reference accounting; no natural A/B/C stage scoring.
Measurement functions never receive fault name/receipt/selected identities.
"""
import sys
sys.dont_write_bytecode=True
import io,json,hashlib,zipfile,itertools
from pathlib import Path
from fractions import Fraction
import numpy as np
import cv2
R=Path(__file__).resolve().parent
sys.path.insert(0,str(R/'analysis_framework_v0.8'))
sys.path.insert(0,str(R/'mask_ambiguity_v0.1'))
from mask_correspondence import MaskFrame
from exact_disjoint_envelope import envelope,edge_envelope
from stage_accounting import Graph,account_from_matches
sys.path.insert(0,str(R/'typed_pathway_adapter_v0.2'))
from typed_pathways import annotate_typed_pathways
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def oracle_domains(pred,ref):
    # Independent set/Fraction exhaustive assignment objective, not production envelope.
    ps=[set(np.flatnonzero(m)) for m in pred.masks];rs=[set(np.flatnonzero(m)) for m in ref.masks]
    costs={};choices=[]
    for i,r in enumerate(rs):
        options=[None]
        for j,p in enumerate(ps):
            u=len(r|p);q=Fraction(len(r&p),u) if u else Fraction(0)
            if q>Fraction(1,2):costs[i,j]=q;options.append(j)
        choices.append(options)
    best=(-1,Fraction(-1));optimal=[]
    for assignment in itertools.product(*choices):
        used=[j for j in assignment if j is not None]
        if len(used)!=len(set(used)):continue
        obj=(len(used),sum((costs[i,j] for i,j in enumerate(assignment) if j is not None),Fraction(0)))
        if obj>best:best=obj;optimal=[assignment]
        elif obj==best:optimal.append(assignment)
    return {int(ref.ids[i]):tuple(sorted({int(pred.ids[a[i]]) for a in optimal if a[i] is not None})) for i in range(len(rs))}

def frames(view,refs,method):
    domains={}
    for t in [0,1]:
        take=view['ids']//100000==t
        pred=MaskFrame(view['ids'][take],view['masks'][take],t,'actual D support or controlled overlay; registered pixels')
        domains.update(method(pred,refs[t]))
    return domains

def graph(view,edges):
    coords=[]
    for ident,m in zip(view['ids'],view['masks']):
        yx=np.argwhere(m).mean(axis=0) if m.any() else [0.,0.]
        coords.append([int(ident)//100000,0.,float(yx[0]),float(yx[1])])
    return Graph(view['ids'],np.array(coords).reshape(-1,4),np.array(sorted(edges),dtype=np.int64).reshape(-1,2),'pixel')

def measure(views,refs,reference_edges):
    domains=[frames(v,refs,envelope) for v in views]
    allids=np.concatenate([f.ids for f in refs]);masks=np.concatenate([f.masks for f in refs])
    refview={'ids':allids,'masks':masks}
    records=[]
    for kind in ['continuation','division']:
        re={e for e,k in reference_edges.items() if k==kind}
        edge_sets=[v['division'] if kind=='division' else v['edges']-v['division'] for v in views]
        gs=[graph(v,e) for v,e in zip(views,edge_sets)]
        reference=graph(refview,re)
        canonical=[{r:opts[0] for r,opts in d.items() if opts} for d in domains]
        accounted=account_from_matches(gs,reference,canonical)
        for record in accounted:
            a,b=record['reference_edge'];bounds=[edge_envelope(d[a],d[b],es) for d,es in zip(domains,edge_sets)]
            record.update(kind=kind,bounds=bounds,ambiguous_visibility=any(lo!=hi for lo,hi in bounds),ambiguous_correspondence=any(len(d[a])>1 or len(d[b])>1 for d in domains))
            if record['ambiguous_visibility']:record['unique_boundary']='withheld-ambiguity'
            else:record['unique_boundary']=record['loss_stages'][-1] if record['final_missing'] and record['loss_stages'] else None
            records.append(record)
    return annotate_typed_pathways(records,views),domains


def independent_diff_baseline(views,domains,edge,kind):
    # Equal-information baseline uses supplied production correspondence plus
    # its own explicit adjacency difference. Never receives oracle path/receipt.
    history=[]
    for view,d in zip(views,domains):
        es=view['division'] if kind=='division' else view['edges']-view['division']
        possible=[(a,b) in es for a in d[edge[0]] for b in d[edge[1]]]
        if possible and any(possible)!=all(possible):return 'withheld-ambiguity'
        history.append(int(bool(possible) and all(possible)))
    if history[-1]:return None
    last=None
    for k in range(1,len(history)):
        if history[k-1] and not history[k]:last=k
    return last

def main():
    O=R/'native_noisy_validation_v0.3';O.mkdir(exist_ok=False)
    G=R/'native_noisy_controls_v0.2';receipts=json.loads((G/'generator_receipts.json').read_text())
    archivepath=R/'external_validation_v0.1/CTC.zip'
    binding={'runner_sha256':sha(Path(__file__)),'protocol_sha256':sha(R/'native_noisy_control_protocol_v0.1.md'),'fixtures_receipts_sha256':sha(G/'generator_receipts.json'),'archive_sha256':sha(archivepath),'envelope_sha256':sha(R/'mask_ambiguity_v0.1/exact_disjoint_envelope.py'),'framework_sha256':sha(R/'analysis_framework_v0.8/stage_accounting.py')}
    (O/'before_execution.json').write_text(json.dumps(binding,indent=2))
    rows=[];inputbindings=[];baselinepaths={'unchanged':[1,1,1,1],'edge_delete':[1,0,0,0],'node_remove':[1,0,0,0],'support_zero':[1,0,0,0],'delete_recover_delete':[1,0,1,0],'delete_recover':[1,0,1,1],'prewindow_omission':[0,0,0,0],'absent_edge_noop':[1,1,1,1]}
    with zipfile.ZipFile(archivepath) as z:
        for video in receipts['videos']:
            v=video['video'];refs=[];labels=[]
            names=sorted(n for n in z.namelist() if n.startswith(f'CTC/test/{v}_GT/TRA/man_track') and n.endswith('.tif'))[:2]
            assert len(names)==2
            for t,name in enumerate(names):
                raw=z.read(name);im=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_UNCHANGED)
                ids=np.unique(im);ids=ids[ids>0];labels.append(set(map(int,ids)))
                refs.append(MaskFrame(t*100000+ids.astype(np.int64),np.array([im==i for i in ids],dtype=bool),t,'independent disjoint TRA annotation'))
                inputbindings.append({'video':v,'member':name,'sha256':hashlib.sha256(raw).hexdigest()})
            table=np.loadtxt(io.BytesIO(z.read(f'CTC/test/{v}_GT/TRA/man_track.txt')),dtype=int,ndmin=2)
            refedges={(n,100000+n):'continuation' for n in labels[0]&labels[1]}
            for label,start,end,parent in table:
                if start==1 and parent and parent in labels[0] and label in labels[1]:refedges[int(parent),100000+int(label)]='division'
            with np.load(G/f'{v}_unchanged.npz',allow_pickle=False) as a:
                baseline={'ids':a['ids0'],'masks':a['masks0'],'edges':set(map(tuple,a['edges0'])),'division':set(map(tuple,a['division0']))}
            bd=frames(baseline,refs,oracle_domains);inv={opts[0]:r for r,opts in bd.items() if len(opts)==1}
            pa,pb=video['selected'];target=(inv[pa],inv[pb]) if pa in inv and pb in inv else None
            kind='division' if (pa,pb) in baseline['division'] else 'continuation'
            eligible=target in refedges and refedges.get(target)==kind
            for case in video['cases']:
                p=G/case['fixture'];assert sha(p)==case['sha256']
                with np.load(p,allow_pickle=False) as a:
                    views=[{'ids':a[f'ids{k}'],'masks':a[f'masks{k}'],'edges':set(map(tuple,a[f'edges{k}'])),'division':set(map(tuple,a[f'division{k}']))} for k in range(4)]
                measured,domains=measure(views,refs,refedges)
                od=[frames(view,refs,oracle_domains) for view in views]
                assert domains==od,(v,case['arm'],'domain mismatch')
                entry={'video':v,'arm':case['arm'],'baseline_selected_edge_eligible':eligible,'reference_edge':target,'selected_predicted_edge':video['selected'],'measurement_records':measured}
                if not eligible:entry['status']='withheld-baseline-reference-ineligible';rows.append(entry);continue
                got=next(m for m in measured if tuple(m['reference_edge'])==target)
                es=[view['division'] if kind=='division' else view['edges']-view['division'] for view in views]
                oracle_bounds=[]
                for d,e in zip(od,es):
                    pairs=list(itertools.product(d[target[0]],d[target[1]]));vals=[pair in e for pair in pairs]
                    oracle_bounds.append((bool(vals) and all(vals),any(vals)))
                assert got['bounds']==oracle_bounds
                if any(lo!=hi for lo,hi in oracle_bounds):
                    entry.update(status='withheld-correspondence-ambiguity',oracle_bounds=oracle_bounds);rows.append(entry);continue
                truth=[int(lo) for lo,hi in oracle_bounds]
                # Execution-origin path for non-swapping arms is fixed independently of measurement.
                if case['arm'] in baselinepaths:assert truth==baselinepaths[case['arm']],(v,case['arm'],'executed oracle path mismatch')
                losses=[k for k in range(1,4) if truth[k-1]==1 and truth[k]==0]
                gains=[k for k in range(1,4) if truth[k-1]==0 and truth[k]==1]
                assert got['visibility']==truth and got['loss_stages']==losses and got['gain_stages']==gains
                lastloss=losses[-1] if not truth[-1] and losses else None
                firstmissing=next((k for k,val in enumerate(truth) if not val),None) if not truth[-1] else None
                entry.update(status='evaluated-controlled-path',oracle_visibility=truth,oracle_losses=losses,oracle_gains=gains,oracle_last_observed_loss_when_final_missing=lastloss,framework_boundary=got['unique_boundary'],equal_information_diff_boundary=independent_diff_baseline(views,domains,target,kind),first_missing_boundary=firstmissing,final_only_boundary=None,boundary_task_eligible=lastloss is not None)
                rows.append(entry)
            print(v,'baseline eligible',eligible,flush=True)
    summary={'cases':len(rows),'baseline_ineligible':sum(r['status']=='withheld-baseline-reference-ineligible' for r in rows),'ambiguous':sum(r['status']=='withheld-correspondence-ambiguity' for r in rows),'evaluated_paths':sum(r['status']=='evaluated-controlled-path' for r in rows),'boundary_task_eligible':sum(r.get('boundary_task_eligible',False) for r in rows)}
    eligible_rows=[r for r in rows if r.get('boundary_task_eligible')]
    for method in ['framework','equal_information_diff','first_missing','final_only']:
        summary[method]={'correct':sum(r[method+'_boundary']==r['oracle_last_observed_loss_when_final_missing'] for r in eligible_rows),'withheld':sum(r[method+'_boundary'] is None for r in eligible_rows),'denominator':len(eligible_rows)}
    summary['prewindow_false_firstmissing']=sum(r['arm']=='prewindow_omission' and r.get('first_missing_boundary')==0 for r in rows)
    (O/'case_records.json').write_text(json.dumps(rows,indent=2))
    (O/'reference_inputs.json').write_text(json.dumps(inputbindings,indent=2))
    (O/'summary.json').write_text(json.dumps({'binding':binding,'summary':summary,'scope':'Controlled overlay validation only;reference baseline ineligible retained;observed last-loss task,not causal source;independent review pending;natural stage scoring not allowed'},indent=2))
    print(summary)

if __name__=='__main__':main()
