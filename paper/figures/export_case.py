"""Extract an explicitly selected case from real images and saved predictions.

No inference, manual tracing, label editing, or result-dependent case selection.
JSON input paths are resolved relative to the configuration file.
"""
from pathlib import Path
import argparse, gzip, hashlib, io, json, zipfile
import numpy as np
from PIL import Image


def read(path):
    if str(path).endswith('.gz'):
        with gzip.open(path, 'rt', encoding='utf8') as f: return json.load(f)
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def npz(path):
    with np.load(path, allow_pickle=False) as z: return {k: z[k].copy() for k in z.files}


def digest_array(a):
    a = np.ascontiguousarray(a)
    return hashlib.sha256(str((a.dtype.str, a.shape)).encode()+a.tobytes()).hexdigest()


def overlap(reference, masks, ids):
    """Literal strict IoU > 1/2; retain all candidates, never break a tie."""
    hits=[]
    for mask, identity in zip(masks, ids):
        mask=np.asarray(mask, bool)
        intersection=int(np.count_nonzero(reference & mask))
        union=int(np.count_nonzero(reference | mask))
        if 2*intersection > union:
            hits.append({'id':int(identity),'intersection':intersection,'union':union})
    return hits


def label_matches(reference, labels):
    ids=np.unique(labels); ids=ids[ids!=0]
    return overlap(reference, (labels==i for i in ids), ids)


def single(hits):
    if len(hits)>1: raise ValueError('Ambiguous mask correspondence: singleton renderer withheld')
    return hits[0]['id'] if hits else None


def tiff_time_channels(filename, frames):
    """Read explicit temporal/channel axes, returning selected TCYX pixels."""
    import tifffile
    with tifffile.TiffFile(filename) as tif:
        series=tif.series[0]; axes=series.axes; shape=series.shape
        if axes not in ('TYX','TCYX'):
            raise ValueError('Unsupported temporal TIFF axes: '+axes)
        if any(type(t) is not int or t<0 or t>=shape[0] for t in frames):
            raise ValueError('Requested acquisition frame outside TIFF time axis')
        a=series.asarray()
    channels=a[frames,None,:,:] if axes=='TYX' else a[frames,:,:,:]
    return channels,{'axes':axes,'shape':list(shape),'selected_frames':frames,'channels_per_frame':int(channels.shape[1]),'selected_channel_array_sha256':{f'{t}:{k}':digest_array(channels[i,k]) for i,t in enumerate(frames) for k in range(channels.shape[1])}}


def ctc_arrays(archive, movie, frames, labels):
    raws=[]; refs=[]; sources=[]
    with zipfile.ZipFile(archive) as z:
        if frames[1] != frames[0]+1:raise ValueError('CTC case must use adjacent frames')
        lineage_name=f'CTC/test/{movie}_GT/TRA/man_track.txt'
        lineage_bytes=z.read(lineage_name)
        tracks={int(parts[0]):list(map(int,parts[1:])) for line in lineage_bytes.decode().splitlines() if (parts:=line.split())}
        for t,label in zip(frames,labels):
            if label not in tracks or not tracks[label][0]<=t<=tracks[label][1]:raise ValueError('Reference label outside annotated lifetime')
        if labels[0]==labels[1]:reference_type='continuation'
        elif tracks[labels[1]][2]==labels[0] and tracks[labels[1]][0]==frames[1] and tracks[labels[0]][1]==frames[0]:reference_type='division'
        else:raise ValueError('Selected reference pair is not an annotated adjacent relation')
        sources.append({'member':lineage_name,'sha256':hashlib.sha256(lineage_bytes).hexdigest()})
        for t, label in zip(frames, labels):
            names=[f'CTC/test/{movie}/t{t:03d}.tif',f'CTC/test/{movie}_GT/TRA/man_track{t:03d}.tif']
            data=[z.read(n) for n in names]
            arrays=[np.asarray(Image.open(io.BytesIO(b))) for b in data]
            raw=arrays[0]
            if raw.ndim==3:
                if raw.shape[2]!=3 or not np.array_equal(raw[...,0],raw[...,1]) or not np.array_equal(raw[...,0],raw[...,2]):
                    raise ValueError('Expected identical grayscale RGB channels')
                raw=raw[...,0]
            if not np.any(arrays[1]==label): raise ValueError('Selected reference label absent')
            raws.append(raw); refs.append(arrays[1]==label)
            sources.extend({'member':n,'sha256':hashlib.sha256(b).hexdigest()} for n,b in zip(names,data))
    return raws, refs, sources, reference_type


def pulse(c, path):
    frames=c['frames']; labels=c['reference_labels']
    raws,refs,sources,reference_type=ctc_arrays(path(c['archive']),c['movie'],frames,labels)
    if c['reference_type']!=reference_type:raise ValueError('Declared reference type differs from annotated lineage')
    pixels={f'raw_{i}':a for i,a in enumerate(raws)}
    pixels.update({f'reference_{i}':a for i,a in enumerate(refs)})
    rows=[]
    for arm, loc in c['predictions'].items():
        g=npz(path(loc)); masks=[g[f'frame_{t:04d}'] for t in frames]
        candidates=[label_matches(r,m) for r,m in zip(refs,masks)]
        mapped=[single(x) for x in candidates]
        e=g['typed_edges']; selected=[r.tolist() for r in e if int(r[0])==frames[0] and int(r[2])==frames[1] and int(r[1])==mapped[0] and int(r[3])==mapped[1]]
        actual_types=sorted({('continuation' if int(x[4])==0 else 'division') for x in selected})
        rows.append({'arm':arm,'matches':candidates,'mapped_pair':mapped,'raw_visible':bool(selected),'types':actual_types,'typed_visible':c['reference_type'] in actual_types})
        for i,(mask,pid) in enumerate(zip(masks,mapped)):
            pixels[f'{arm}_{i}']=(mask==pid) if pid is not None else np.zeros(mask.shape,bool)
    return {'domain':'bacterial_pulse','rows':rows,'pixel_sources':sources},pixels


def native(c, path):
    frames=c['frames']; raws,refs,sources,reference_type=ctc_arrays(path(c['archive']),c['movie'],frames,c['reference_labels'])
    if c['reference_type']!=reference_type:raise ValueError('Declared reference type differs from annotated lineage')
    prev=npz(path(c['states'][0])); cur=npz(path(c['states'][1]))
    graph=read(path(c['graph']))[frames[1]]
    prev_hits=overlap(refs[0],prev['return_masks'],range(len(prev['return_masks'])))
    anchor=single(prev_hits)
    arrays={'A':cur['resized_probabilities']>.5,'B':cur['winner_threshold_binary'].astype(bool),'C':cur['component_retained_binary'].astype(bool),'D':cur['return_masks'].astype(bool)}
    pixels={'raw_previous':raws[0],'raw_current':raws[1],'reference_previous':refs[0],'reference_current':refs[1], 'prediction_previous':prev['return_masks'][anchor].astype(bool) if anchor is not None else np.zeros(refs[0].shape,bool)}
    rows=[]
    for stage,masks in arrays.items():
        hits=overlap(refs[1],masks,range(len(masks))); target=single(hits)
        pair=[frames[0]*100000+anchor,frames[1]*100000+target] if anchor is not None and target is not None else [None,None]
        types=sorted({e[2] for e in graph['stages'][stage]['edges'] if e[:2]==pair})
        rows.append({'stage':stage,'anchor_matches':prev_hits,'current_matches':hits,'mapped_pair':pair,'types':types,'raw_visible':bool(types),'typed_visible':c['reference_type'] in types})
        pixels[stage]=masks[target] if target is not None else np.zeros(refs[1].shape,bool)
    result={'domain':'native_bacterial_stages','rows':rows,'typed_history':''.join(str(int(r['typed_visible'])) for r in rows),'raw_history':''.join(str(int(r['raw_visible'])) for r in rows),'pixel_sources':sources}
    if 'expected_typed_history' in c:
        if result['typed_history']!=c['expected_typed_history']: raise ValueError('Recomputed history differs from retained identity record')
        result['retained_history_equal']=True
    return result,pixels


def epithelial(c, path):
    import tifffile
    frames=c['frames']; label=c['reference_label']
    channels,raw_axes=tiff_time_channels(path(c['raw']),frames)
    with tifffile.TiffFile(path(c['reference'])) as z: refs=[z.pages[t].asarray()==label for t in frames]
    if not all(np.any(r) for r in refs): raise ValueError('Selected reference continuation absent')
    if any(r.shape!=channels.shape[-2:] for r in refs):raise ValueError('Raw/reference pixel grids differ')
    displays=[]; limits=[]
    for k in range(channels.shape[1]):
        lo,hi=np.quantile(channels[:,k].astype(float),[.01,.99]); limits.append([float(lo),float(hi)])
        displays.append(np.clip((channels[:,k]-lo)/(hi-lo),0,1) if hi>lo else np.zeros_like(channels[:,k],float))
    display=np.mean(displays,axis=0); pixels={f'raw_{i}':v for i,v in enumerate(display)}
    pixels.update({f'reference_{i}':v for i,v in enumerate(refs)});rows=[]
    for stage,locations in c['stages'].items():
        with tifffile.TiffFile(path(locations['masks'])) as z: masks=[z.pages[t].asarray() for t in frames]
        hits=[label_matches(r,m) for r,m in zip(refs,masks)]; mapped=[single(h) for h in hits]
        pair=[t*100000+v if v is not None else None for t,v in zip(frames,mapped)]
        edges={tuple(e) for e in read(path(locations['graph']))['edges']}
        rows.append({'stage':stage,'matches':hits,'mapped_pair':pair,'visible':tuple(pair) in edges})
        for i,(m,v) in enumerate(zip(masks,mapped)):pixels[f'{stage}_{i}']=(m==v) if v is not None else np.zeros(m.shape,bool)
    result={'domain':'epithelial','rows':rows,'history':''.join(str(int(r['visible'])) for r in rows),'raw_axis_selection':raw_axes,'common_channel_display_limits':limits}
    if 'expected_history' in c:
        if result['history']!=c['expected_history']:raise ValueError('Recomputed history differs from retained identity record')
        result['retained_history_equal']=True
    return result,pixels


def coordinates(c, path):
    import zarr
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'expanded'))
    import audit_engine as engine
    ref=npz(path(c['reference'])); ids=c['reference_ids']; pos={int(q):v for q,v in zip(ref['ids'],ref['coords'])}
    ref_graph=engine.load_graph(path(c['reference']))
    if any(tuple(e) not in set(map(tuple,ref['edges'])) for e in zip(ids,ids[1:])): raise ValueError('Selected reference path absent')
    rc=np.array([pos[q] for q in ids]); frames=[int(t) for t in rc[:,0]]; scale=np.array(c['scale_um_zyx'])
    allcoords=[rc[:,1:]/scale];rows=[]
    for side in ['before','after']:
        g=npz(path(c[side]['graph'])); report=read(path(c[side]['report'])); mapping={int(k):v for k,v in report['canonical_map'].items()}
        prediction=engine.load_graph(path(c[side]['graph'])); frame_checks=[]
        for t in sorted(set(frames)):
            fresh=engine.frame_result(engine.framed(ref_graph,t),engine.framed(prediction,t),t)
            if fresh['status']!='COMPLETE' or fresh['ordinary'].get('status')!='EXACT_COMPLETE_FAMILY_EQUAL':
                raise ValueError('Selected frame reconstruction did not complete')
            saved={q:mapping[q] for q in fresh['reference_ids'] if q in mapping}
            if fresh['canonical']!=saved:raise ValueError('Reconstructed correspondence differs from archived canonical map')
            frame_checks.append({'frame':t,'family_size':len(fresh['worlds']),'independent_family_equal':True,'canonical_map_equal':True})
        mapped=[mapping.get(q) for q in ids]; positions={int(q):v for q,v in zip(g['ids'],g['coords'])}
        coords=[positions[q].tolist() if q is not None else None for q in mapped]
        allcoords.append(np.array([v[1:] for v in coords if v is not None])/scale)
        pairs=set(map(tuple,g['edges']));bits=[int(tuple(e) in pairs) for e in zip(mapped,mapped[1:])]
        rows.append({'side':side,'mapped_ids':mapped,'coordinates_um':coords,'pair_visibility':bits,'fresh_frame_checks':frame_checks})
    allcoords=np.concatenate([a for a in allcoords if len(a)])
    if str(c['raw']).endswith('.npz'):
        captured=npz(path(c['raw']))
        if any(f'frame_{t}' not in captured for t in frames):raise ValueError('Requested real frame absent from supplied subset')
        shapes={captured[f'frame_{t}'].shape for t in frames}
        if len(shapes)!=1 or len(next(iter(shapes)))!=3:raise ValueError('Expected equal original ZYX frame grids')
        shape=next(iter(shapes));frame=lambda t:captured[f'frame_{t}']
    else:
        raw=zarr.open_group(str(path(c['raw'])), mode='r')['0'];shape=raw.shape[1:];frame=lambda t:raw[t]
    low=np.maximum(0,np.floor(allcoords.min(axis=0)).astype(int)-[2,13,13]); high=np.minimum(shape,np.ceil(allcoords.max(axis=0)).astype(int)+[3,14,14])
    pixels={f'raw_{t}':np.asarray(frame(t)[low[0]:high[0],low[1]:high[1],low[2]:high[2]]).max(axis=0) for t in frames}
    return {'domain':'coordinates','frames':frames,'reference_ids':ids,'reference_um':rc.tolist(),'scale_um_zyx':scale.tolist(),'rows':rows,'crop_zyx_start':low.tolist(),'crop_zyx_stop':high.tolist(),'readout':'canonical pair visibility; not an invariant-family claim'},pixels


def export(config, output):
    config=Path(config).resolve(); c=read(config); output=Path(output)
    if output.exists(): raise FileExistsError('Use a new output directory')
    path=lambda s:(config.parent/Path(s)).resolve()
    operations={'coordinates':coordinates,'pulse':pulse,'native':native,'epithelial':epithelial}
    result,pixels=operations[c['kind']](c,path)
    output.mkdir(parents=True)
    # Native arrays are retained; the PNG is a preview, never the measurement input.
    np.savez_compressed(output/'PIXELS.npz',**pixels)
    result.update(case=c, pixel_array_sha256={k:digest_array(v) for k,v in pixels.items()}, producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), inference_run=False)
    (output/'RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rawkeys=[k for k in pixels if k.startswith('raw_')]
    vals=np.concatenate([pixels[k].ravel() for k in rawkeys]); lo,hi=np.quantile(vals,[.01,.99])
    for k in rawkeys:
        fig,ax=plt.subplots(figsize=(4,4)); ax.imshow(pixels[k],cmap='gray',vmin=lo,vmax=hi,interpolation='nearest');ax.axis('off');ax.set_title(c['case_id']+' / '+k,fontsize=8)
        fig.savefig(output/(k+'.png'),dpi=120,bbox_inches='tight');plt.close(fig)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    r=export(a.config,a.output); print(json.dumps({'domain':r['domain'],'case_id':r['case']['case_id'],'status':'EXTRACTED_AND_MEASURED'}))
