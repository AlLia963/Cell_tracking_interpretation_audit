"""Prediction-only historical anchor binding and replay comparison; no GT."""
import hashlib,json
from pathlib import Path
import numpy as np
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify_anchors(preparation):
    r=Path(preparation).parent.parent
    roots={'WW':r/'external_trajectory_intervention_v0.1/baseline','AA':r/'single_pulse_interventions_v0.1/pulse_all_components'}
    films={f'{i:02d}' for i in range(1,30)};assets={};rows={}
    for arm,root in roots.items():
        manifest=root/'manifest.json';data=json.loads(manifest.read_text(encoding='utf-8'))
        reports=data['all_video_reports'];assert len(reports)==29 and {row['video'] for row in reports}==films
        assets[str(manifest)]=sha(manifest)
        prov=root/'provenance_before_inference.json';assets[str(prov)]=sha(prov)
        rows[arm]={}
        for row in reports:
            video=row['video'];folder=root/'native'/video;assert row['status']=='completed'
            final=list(folder.glob('mask*.tif'))+[folder/'res_track.txt']
            assert {f.name for f in final}==set(row['output_hashes'])
            for f in final:
                assert sha(f)==row['output_hashes'][f.name];assets[str(f)]=sha(f)
            states=folder/'operator_states';protocol=states/'observer_protocol.json';assets[str(protocol)]=sha(protocol)
            records=json.loads(protocol.read_text(encoding='utf-8'))['records']
            expected={f"frame{record['frame']:03d}.npz":record['state_sha256'] for record in records}
            assert len(expected)==len(records) and {p.name for p in states.glob('frame*.npz')}==set(expected)
            for name,digest in expected.items():
                f=states/name;assert sha(f)==digest;assets[str(f)]=digest
                with np.load(f,allow_pickle=False) as data:assert len(data.files)==49
            journal=states/'frame_journal.jsonl';assert journal.exists();assets[str(journal)]=sha(journal)
            rows[arm][video]={'root':str(folder),'input_frames':row['input_frames'],'output_hashes':row['output_hashes'],'capture_hashes':expected}
    return {'scope':'Prediction-only actual bound historical WW/AA full29 anchors; no GT','files':assets,'rows':rows}
def equal(a,b):
    if a.dtype!=b.dtype or a.shape!=b.shape:return False
    if a.dtype.kind=='O':
        return all(x is None and y is None for x,y in zip(a.flat,b.flat))
    if a.dtype.kind in 'fc' and (not np.isfinite(a).all() or not np.isfinite(b).all()):return False
    return a.tobytes(order='C')==b.tobytes(order='C')
def compare_replay(preparation,anchors,arm,video,folder):
    assert arm in ('WW','AA');row=anchors['rows'][arm][video];historical=Path(row['root']);folder=Path(folder)
    # Reverify bound assets at consumption; no silent drift since pre-model binding.
    for path,digest in anchors['files'].items():
        if Path(path).is_relative_to(historical):assert sha(Path(path))==digest
    actual=list(folder.glob('mask*.tif'))+[folder/'res_track.txt']
    finals={p.name:sha(p) for p in actual};output_ok=finals==row['output_hashes']
    expected=set(row['capture_hashes']);states=folder/'operator_states'
    capture_ok={p.name for p in states.glob('frame*.npz')}==expected;differences=[]
    if capture_ok:
        for name in sorted(expected):
            with np.load(historical/'operator_states'/name,allow_pickle=True) as h,np.load(states/name,allow_pickle=True) as n:
                if len(n.files)!=49 or set(h.files)!=set(n.files):differences.append({'capture':name,'reason':'field inventory'})
                else:
                    bad=[key for key in h.files if not equal(h[key],n[key])]
                    if bad:differences.append({'capture':name,'fields':bad})
    def applicability(path):
        events=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        return [{k:e[k] for k in ('frame','operator_applicable','mask_saved') if k in e} for e in events if e['event']=='frame_complete']
    applicable_ok=applicability(historical/'operator_states/frame_journal.jsonl')==applicability(states/'frame_journal.jsonl')
    return {'PASS':output_ok and capture_ok and not differences and applicable_ok,'historical_arm':arm,'video':video,'final_outputs_exact':output_ok,'capture_exact_inventory':capture_ok,'all49_values_differences':differences,'journal_no_candidate_applicability_exact':applicable_ok,'capture_count':len(expected)}
