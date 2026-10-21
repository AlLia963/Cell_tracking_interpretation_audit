"""Actual local A–D reconstruction using bound supports, not expected records."""
from pathlib import Path
import sys,argparse,json,hashlib,zipfile,io,collections,datetime
import numpy as np,cv2
sys.dont_write_bytecode=True
P=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(P))
from run_native_noisy_validation_v03 import measure,MaskFrame,edge_envelope,independent_diff_baseline
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,v):
 with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,allow_nan=False)
def main():
 a=argparse.ArgumentParser();a.add_argument('--resources',type=Path,required=True);a.add_argument('--output',type=Path,required=True);args=a.parse_args()
 cfg=read(args.resources);root=args.resources.resolve().parent;O=args.output;O.mkdir(exist_ok=False)
 archive=Path(cfg['archive_path']);assert sha(archive)==cfg['archive_sha256']
 metadata={};graph_by={};side_by={}
 for r in cfg['films']:
  sp=root/r['sidecar_relative'];gp=root/r['graph_relative'];assert sha(sp)==r['sidecar_sha256'] and sha(gp)==r['graph_sha256']
  side_by[r['film']]=read(sp);graph_by[r['film']]=read(gp);metadata[str(sp)]=sha(sp);metadata[str(gp)]=sha(gp)
  assert len(side_by[r['film']]['records'])==len(graph_by[r['film']])==r['frames']
 assert len(cfg['films'])==29 and sum(r['frames'] for r in cfg['films'])==5340
 write(O/'BEFORE_REFERENCE.json',{'metadata':metadata,'archive_sha256':cfg['archive_sha256'],'resources_sha256':sha(args.resources),'actual_support_bytes':'verified at use before NPZ member decode; outputs and sidecars already frozen prior to reference access','source_code_sha256':sha(Path(__file__))})
 totals=collections.Counter();allloss=[];inputbindings=[];perfilm=[]
 with zipfile.ZipFile(archive) as z:
  for r in cfg['films']:
   film=r['film'];graphs=graph_by[film];states=side_by[film]['records'];c=collections.Counter();previous=None;prevref=None;prevlabels=None
   names=sorted(n for n in z.namelist() if n.startswith(f'CTC/test/{film}_GT/TRA/man_track') and n.endswith('.tif'))
   assert len(names)==len(graphs)==len(states)
   lineage=np.loadtxt(io.BytesIO(z.read(f'CTC/test/{film}_GT/TRA/man_track.txt')),dtype=int,ndmin=2)
   with (O/(film+'_edge_records.jsonl')).open('x',encoding='utf-8') as log:
    for f,(g,loc,name) in enumerate(zip(graphs,states,names)):
     p=Path(r['support_paths_resolve_under'])/loc['state_path_relative_to_root'];digest=sha(p);assert digest==loc['state_sha256'] and g['frame']==f
     before=p.stat()
     with np.load(p,allow_pickle=False) as a:
      supports={'A':a['resized_probabilities']>.5,'B':a['winner_threshold_binary'].astype(bool),'C':a['component_retained_binary'].astype(bool),'D':a['return_masks'].astype(bool)}
     after=p.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
     raw=z.read(name);im=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_UNCHANGED);assert im is not None
     labels=set(map(int,np.unique(im[im>0])));ids=np.array(sorted(labels),dtype=np.int64)
     refmasks=np.array([im==i for i in ids],dtype=bool).reshape((-1,*im.shape))
     ref=MaskFrame((1 if f else 0)*100000+ids,refmasks,1 if f else 0,'public same-frame disjoint TRA reference')
     c['frames']+=1;inputbindings.append({'film':film,'frame':f,'support_path':str(p),'support_sha256':digest,'reference_member':name,'reference_sha256':hashlib.sha256(raw).hexdigest()})
     if f:
      refs=[MaskFrame(prevref.ids%100000,prevref.masks,0,prevref.support_definition),ref]
      refedges={(i,100000+i):'continuation' for i in prevlabels&labels}
      for i,s,e,parent in lineage:
       if s==f and parent and int(parent) in prevlabels and int(i) in labels:refedges[int(parent),100000+int(i)]='division'
      views=[]
      for stage in 'ABCD':
       cur=g['stages'][stage];delta=(f-1)*100000
       vi=np.concatenate([np.asarray(previous['ids'],dtype=np.int64)%100000,np.asarray(cur['nodes'],dtype=np.int64)-delta])
       masks=np.concatenate([previous['masks'],supports[stage]])
       edges={(int(x)-delta,int(y)-delta) for x,y,k in cur['edges']}
       div={(int(x)-delta,int(y)-delta) for x,y,k in cur['edges'] if k=='division'}
       assert len(vi)==len(masks) and all(x in vi and y in vi for x,y in edges)
       views.append({'ids':vi,'masks':masks,'edges':edges,'division':div})
      records,domains=measure(views,refs,refedges)
      assert len(records)==len(refedges)
      for rec in records:
       x,y=rec['reference_edge'];rec['video']=film;rec['current_frame']=f
       rec['untyped_bounds']=[edge_envelope(d[x],d[y],v['edges']) for d,v in zip(domains,views)]
       rec['equal_information_last_loss']=independent_diff_baseline(views,domains,(x,y),rec['kind'])
       assert rec['equal_information_last_loss']==rec['unique_boundary']
       c['reference_edges']+=1;c['determinate_visibility']+=int(not rec['ambiguous_visibility']);c['ambiguous_visibility']+=int(rec['ambiguous_visibility']);c['ambiguous_correspondence']+=int(rec['ambiguous_correspondence'])
       for k,stage in enumerate('ABCD'):
        c[stage+'_certain_visible']+=int(rec['bounds'][k][0]);c[stage+'_possible_visible']+=int(rec['bounds'][k][1])
       if rec['final_missing']:
        c['D_missing']+=1
        if rec['unique_boundary']=='withheld-ambiguity':c['withheld_last_loss']+=1
        elif rec['unique_boundary'] is None:c['persistent_absence']+=1
        else:
         c['observed_last_loss']+=1;allloss.append(rec)
       log.write(json.dumps(rec,separators=(',',':'))+'\n')
      c['windows']+=1
     previous={'ids':g['stages']['D']['nodes'],'masks':supports['D'].copy()};prevref=ref;prevlabels=labels
   perf={'film':film,'counts':dict(c),'records_sha256':sha(O/(film+'_edge_records.jsonl'))};perfilm.append(perf);totals.update(c)
   write(O/(film+'_summary.json'),perf);print('RECONSTRUCTED_NATURAL',film,dict(c),flush=True)
 assert totals['frames']==5340 and totals['windows']==5311 and totals['reference_edges']==31093
 write(O/'INPUT_BINDINGS.json',inputbindings)
 write(O/'RESULT.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'totals':dict(totals),'films':perfilm,'actual_losses':allloss,'input_bindings_sha256':sha(O/'INPUT_BINDINGS.json'),'scope':'fresh actual support/typed graph accounting using supplied production envelope; all-record same-information differential comparison; NOT new inference, independent full matcher oracle, biological causal responsibility or utility'})
 print(json.dumps(dict(totals)),flush=True)
if __name__=='__main__':main()
