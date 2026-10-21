"""Explicit input/output replay of already known epithelial results.
The supplement bundles its pinned public archive and known comparison targets.
This reader performs no upload or acquisition; producers do not read targets.
"""
from pathlib import Path
import argparse, hashlib, json, zipfile, importlib.util, sys, platform, datetime, traceback, time

HERE=Path(__file__).resolve().parent
def sha(path):
    with path.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def save(path,obj):
    assert not path.exists(),str(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--archive',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args(); archive=args.archive.resolve(); out=args.output.resolve()
    if out.exists(): raise FileExistsError('Output must be absent; previous runs are retained: '+str(out))
    manifest=json.loads((HERE/'PUBLIC_INPUT_MANIFEST.json').read_text(encoding='utf-8'))
    if archive.stat().st_size!=manifest['archive_bytes'] or sha(archive)!=manifest['archive_sha256']:
        raise ValueError('Archive fails exact frozen public-input bytes/SHA256 contract')
    with archive.open('rb') as f:
        if hashlib.file_digest(f,'md5').hexdigest()!=manifest['archive_md5']:
            raise ValueError('Archive fails source record MD5 contract')
    out.mkdir(); started=time.monotonic()
    save(out/'REPLAY_START.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'archive_sha256':sha(archive),'manifest_sha256':sha(HERE/'PUBLIC_INPUT_MANIFEST.json'),
        'replay_sha256':sha(Path(__file__)),'prior_results_known':True,'new_validation_claim':False,
        'python':sys.version,'platform':platform.platform()})
    try:
        # Read exactly eight named TIFF members. Never load pickle or extract arbitrary paths.
        records=[]
        with zipfile.ZipFile(archive) as z:
            for record in manifest['records']:
                data=z.read(record['archive_member'])
                if len(data)!=record['bytes'] or hashlib.sha256(data).hexdigest()!=record['sha256']:
                    raise ValueError('Selected TIFF fails frozen input contract: '+record['archive_member'])
                basename='raw.tif' if record['role']=='raw' else 'curated_labels.tif'
                path=out/'inputs'/record['movie']/basename
                path.parent.mkdir(parents=True,exist_ok=True)
                with path.open('xb') as f: f.write(data)
                records.append({**record,'local_path':str(path)})
        bound=out/'RUN_INPUT_BINDING.json'
        save(bound,{'records':records,'public_source':manifest['doi'],'prior_results_known':True})
        base=HERE/'additional_public_tracking_domain_v0.1'
        producer=load_module('raw_epithelial_replay',base/'generate_raw_stages_v0_1.py')
        producer.DESIGN=bound; producer.OUT=out/'raw_stages'
        producer.main()
        # Raw-only outputs are fully frozen before this execution opens reference arrays.
        measurement=load_module('measured_epithelial_replay',base/'measure_reference_graph_v0_1.py')
        measurement.P=out; measurement.STAGES=out/'raw_stages'; measurement.OUT=out/'reference_measurement'
        # The original measurement function expects this filename, not a historical root.
        save(out/'RAW_EXPERIMENT_DESIGN_v0.1.json',json.loads(bound.read_text(encoding='utf-8')))
        # P is rebound for inputs but its source-pin locator is kept source-relative.
        original_sha=measurement.sha
        source_core=HERE/'generic_raw_local_workflow_v0.1/local_graph_core.py'
        obsolete_pin=out.parent/'generic_raw_local_workflow_v0.1/local_graph_core.py'
        def source_pin(path):
            return original_sha(source_core if path==obsolete_pin else path)
        measurement.sha=source_pin
        measurement.main()
        save(out/'REPLAY_COMPLETE.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'status':'ACTUAL_EXPLICIT_PATH_PUBLIC_REPLAY_COMPLETE_NOT_NEW_SCIENCE_OR_PUBLIC_RELEASE',
            'elapsed_seconds':time.monotonic()-started,'prior_results_known':True,
            'same_host_existing_environment':True,'clean_machine_claim':False,
            'source_manifest_sha256':sha(HERE/'SOURCE_MANIFEST.json')})
    except Exception as e:
        save(out/'REPLAY_FAILURE.json',{'error':repr(e),'traceback':traceback.format_exc(),'partial_outputs_preserved':True})
        raise
if __name__=='__main__': main()
