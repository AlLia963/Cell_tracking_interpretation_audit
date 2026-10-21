"""Recompute native49 stage support/typed matching on explicit windows or all116.

Uses exact copied projection, serialization bridge and two distinct matchers.
Never calls model inference, normalization or the historical ROOT gates.
"""
from pathlib import Path
from types import SimpleNamespace
import argparse, hashlib, io, json, shutil, sys, zipfile
import numpy as np, tifffile
from run_archive import HERE, CELLS, sha, read, write, require, module, source_bindings
sys.dont_write_bytecode=True

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input-root',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--windows',default='21:57,21:61,21:62,29:41',help='all or comma-separated film:currentframe');ap.add_argument('--native-root-map',type=Path,help='Optional JSON mapping old absolute native roots to supplied new roots');ap.add_argument('--registration',type=Path,default=HERE/'provenance/pulse/coordinate_registration.json');a=ap.parse_args()
    cfg=source_bindings();root=a.input_root.resolve();out=a.output.resolve();require(not out.exists(),'Absent output required');out.mkdir(parents=True);shutil.copy2(__file__,out/'EXECUTED_ADAPTER.py')
    work=root/cfg['pulse_cohort_relative'];reg=read(a.registration);native_map=read(a.native_root_map) if a.native_root_map else {}
    stage=module(HERE/'sources/pulse/fourcell_stage_exposure_preparation_v0.3/stage_exposure_v0_3.py')
    match=module(HERE/'sources/pulse/reference_stage_matcher_preparation_v0.2/stage_matcher_v0_3.py');match['ENVELOPE']=HERE/'sources/legacy/mask_ambiguity_v0.1/exact_disjoint_envelope.py'
    env=module(HERE/'sources/pulse/fourcell_cohort_adapter_preparation_v0.6/raw_adapters_v0_4.py')
    me=module(HERE/'sources/pulse/fourcell_scientific_measurement_preparation_v0.3/measurement_driver_v0_9.py')
    if a.windows=='all':windows=[(f'{i:02d}',None) for i in range(1,30)]
    else:windows=[(x.split(':')[0],int(x.split(':')[1])) for x in a.windows.split(',')]
    pins={};rows=[];bridges=[];withheld=[];specimen=[]
    def resolve(p):
        original=str(p)
        def under_prefix(path,prefix):
            return path==prefix or path.startswith(prefix.rstrip('\\/')+'\\') or path.startswith(prefix.rstrip('\\/')+'/')
        mapped=None
        for old,new in native_map.items():
            if under_prefix(original,old):
                # New targets are relative to the caller's declared input root.
                suffix=original[len(old):].lstrip('\\/').replace('\\','/')
                target=Path(new)
                mapped=(target if target.is_absolute() else root/target)/suffix
                break
        if mapped is None:
            old=cfg['input_root']
            if under_prefix(original,old):
                mapped=root/original[len(old):].lstrip('\\/').replace('\\','/')
            else:
                target=Path(original)
                mapped=target if target.is_absolute() else root/target
        resolved=mapped.resolve()
        require(resolved.is_relative_to(root),'Scientific source escapes explicit --input-root: '+original)
        return resolved
    with zipfile.ZipFile(root/cfg['reference_archive_relative']) as z:
        for film,selected in windows:
            for arm in CELLS:
                fp=work/arm/film;idx=read(fp/'FILM_COMPLETE.json');n=idx['frames'];tau=idx['tau'];source=read(fp/'array_sources.json')['sources'];receipt=read(fp/'CONSUMED_RECEIPT.json');expected={p:x['sha256'] for p,x in receipt['actual_files'].items()}
                original={int(Path(x['source_path']).stem.removeprefix('frame')):x['source_path'] for x in source.values() if x['format']=='npz' and Path(x['source_path']).parent.name=='operator_states'}
                times=range(1,n) if selected is None else [selected]
                binding={k.replace('\\','/'):v for k,v in idx['output_bindings'].items()};predp=fp/'prediction/prediction.npz';require(sha(predp)==binding['prediction/prediction.npz'],'Compact endpoint pin');pins[str(predp)]=sha(predp)
                with np.load(predp,allow_pickle=False) as a_pred:final_edges=set(map(tuple,a_pred['typed_edges'].tolist()))
                require(reg[film]['transform']=='identity_yx' and reg[film]['upstream_source_evidence_bindings'],'Source-defined registration evidence required')
                for p,h in reg[film]['upstream_source_evidence_bindings'].items():require(sha(resolve(p))==h,'Source registration identity');pins[str(resolve(p))]=h
                for t in times:
                    require(0<t<n,'Frame window bound')
                    if t not in original or t-1 not in original:withheld.append({'film':film,'arm':arm,'frame':t,'status':'UNSUPPORTED_NATIVE_OPERATOR_OR_PRIOR_ANCHOR'});continue
                    decoded=[];images=[];anchors=[];record=None;supports=None
                    for frame in [t-1,t]:
                        oldp=original[frame];p=resolve(oldp);require(sha(p)==expected[oldp],'Native49 exact byte pin');pins[str(p)]=sha(p);payload=env['read_arrays'](p,native=True);require(set(payload)==env['NATIVE49'],'Exact native49 field domain')
                        oldmask=str(Path(oldp).parent.parent/f'mask{frame:03d}.tif');mask=resolve(oldmask);require(sha(mask)==expected[oldmask],'Own-arm CTC mask pin');pins[str(mask)]=sha(mask);image=tifffile.imread(mask)
                        record,supports,anchor=stage['project_native_frame'](payload,image,None if frame==t-1 else anchors[-1]);anchor['frame']=frame;record['frame']=frame;anchors.append(anchor);decoded.append(payload);images.append(image)
                    bridge=stage['typed_serialization_bridge'](t,record,anchors[0],anchors[1],final_edges);bridges.append({'film':film,'arm':arm,**bridge});require(bridge['status']=='EXACT_D_TYPED_SERIALIZATION_BRIDGE','Typed bridge mismatch retained; cannot classify')
                    refs=[]
                    for frame in [t-1,t]:
                        name=f'CTC/test/{film}_GT/TRA/man_track{frame:03d}.tif';raw=z.read(name);im=tifffile.imread(io.BytesIO(raw));ids=tuple(int(i) for i in np.unique(im) if i);refs.append(SimpleNamespace(frame=frame,ids=ids,masks=np.stack([im==i for i in ids]) if ids else np.zeros((0,*im.shape),bool)));pins[name]=hashlib.sha256(raw).hexdigest()
                    trackname=f'CTC/test/{film}_GT/TRA/man_track.txt';trackraw=z.read(trackname);pins[trackname]=hashlib.sha256(trackraw).hexdigest();tracks=np.loadtxt(io.BytesIO(trackraw),dtype=int,ndmin=2)
                    local=[(i,i,0) for i in set(refs[0].ids)&set(refs[1].ids)]+[(int(p),int(i),1) for i,s,e,p in tracks if s==t and p and int(p) in refs[0].ids and int(i) in refs[1].ids]
                    anchor=SimpleNamespace(frame=t-1,ids=tuple(anchors[0]['rows']),masks=anchors[0]['masks']);log={'stage':'C','frame':tau}
                    proposed=match['match_window'](t,anchor,supports,record,refs[0],refs[1],local,supplied_log=log);baseline=match['match_window'](t,anchor,supports,record,refs[0],refs[1],local,supplied_log=log,baseline=True)
                    p=dict(proposed);b=dict(baseline);p.pop('baseline');b.pop('baseline');require(p==b,'Same-information mismatch preserved')
                    row={'film':film,'arm':arm,'frame':t,'projection':record,'matching':proposed,'literal_same_information':baseline,'same_information_equal':True};rows.append(row);write(out/f'{film}_{arm}_{t:03d}_WINDOW.json',row)
                    if film=='29' and t==41 and arm=='WW':
                        # Source flags are actual native producer values; exact pixels preserved.
                        masks={'previous_D':anchors[0]['masks'],**supports,'reference_previous':refs[0].masks,'reference_current':refs[1].masks}
                        np.savez_compressed(out/'FIGURE4_29_040_041_SUPPORT_PIXELS.npz',**masks)
                        specimen.append({'film':film,'arm':arm,'frame':t,'projection':record,'previous_D_rows':anchors[0]['rows'].tolist(),'previous_D_ctc_labels':anchors[0]['ctc'],'current_D_ctc_labels':anchors[1]['ctc'],'reference_previous_ids':list(refs[0].ids),'reference_current_ids':list(refs[1].ids),'actual_reference_lineage_rows':[r.tolist() for r in tracks if r[0] in (40,58,59)],'reference_mother40_daughters':[[int(p),int(i),1] for i,s,e,p in tracks if s==41 and p==40],'pixel_file':'FIGURE4_29_040_041_SUPPORT_PIXELS.npz','actual_native_fields':{k:decoded[1][k].tolist() for k in decoded[1] if any(x in k for x in ['cells','div_track','all_indices'])}})
                    print('REMATCHED_NATIVE',film,arm,t,flush=True)
    write(out/'FIGURE4_SOURCE_TYPE_FLAG_TABLE.json',specimen);write(out/'CONSUMED_BINDINGS.json',pins);write(out/'D_TYPED_SERIALIZATION_BRIDGES.json',bridges);write(out/'WITHHELD.json',withheld)
    write(out/'RESULT.json',{'operation':'new exact native49 projection and proposed/literal matching','windows_requested':a.windows,'arm_windows_completed':len(rows),'reference_relations_measured':sum(len(x['matching']['edges']) for x in rows),'same_information_equal_all':True,'unsupported_windows':len(withheld),'new_model_forward':False,'new_normalization':False,'causal_source':'unidentifiable','full116_recomputed':a.windows=='all'})
    write(out/'NEW_OUTPUT_FREEZE.json',{'files':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in out.iterdir() if p.is_file()}})
if __name__=='__main__':main()
