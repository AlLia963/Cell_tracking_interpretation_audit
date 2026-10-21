"""Verify a supplied local input bundle and write a location-specific config."""
from pathlib import Path
import argparse
import hashlib
import json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle', type=Path, required=True)
    p.add_argument('--runtime', type=Path, required=True)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--runs', type=Path, required=True)
    a = p.parse_args(); b = a.bundle.resolve(); runs = a.runs.resolve()
    manifest = next(b / name for name in ['INPUT_MANIFEST_v3.json', 'INPUT_MANIFEST_v2.json', 'INPUT_MANIFEST.json'] if (b / name).exists())
    m = json.loads(manifest.read_text(encoding='utf-8'))
    for row in m['files']:
        f = b / row['path']
        if not f.resolve().is_relative_to(b) or f.stat().st_size != row['bytes']:
            raise ValueError('Input path/size mismatch: ' + row['path'])
        with f.open('rb') as h:
            if hashlib.file_digest(h, 'sha256').hexdigest() != row['sha256']:
                raise ValueError('Input hash mismatch: ' + row['path'])
    c = b / 'companion'
    cfg = {'companion_root': str(c), 'runtime_root': str(a.runtime.resolve()),
           'natural_input_root': str(c / 'inputs_LOCAL_ONLY/natural/coordinate_all8'),
           'bacterial_input_root': str(c / 'inputs_LOCAL_ONLY/bacterial/fixed_archive_root'),
           'common_carrier_root': str(c / 'inputs_LOCAL_ONLY/bacterial/inputs_LOCAL_ONLY/common_carrier96'),
           'epithelial_archive': str(c / 'inputs/public/MovieEpitheliumFigure5.zip'),
           'native_map_patch': str(c / 'inputs_LOCAL_ONLY/bacterial/SELECTED_NATIVE_ROOT_MAP.json'),
           'natural_measurement_root': str(runs / 'natural3d/measurement'),
           'timing_measurement_root': str(runs / 'bacterial-timing/measurement/measurement'),
           'chains_measurement_root': str(runs / 'bacterial-chains/measurement/measurement'),
           'native_window_root': str(runs / 'native16/measurement'),
           'common_generation_root': str(b / 'common_generation'),
           'generated_common_root': str(runs / 'common-generate/measurement/generated_run/generated'),
           'iws_root': str(b / 'iws_carriers'), 'allocation_scores': str(b / 'allocation_scores.json'),
           'duty_authority': str(runs / 'bacterial-duties/measurement/authority.json'),
           'article_root': str(b / 'article'), 'extra_input_root': str(b / 'extras'), 'input_manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest()}
    with a.config.open('x', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(json.dumps({'verified_files': len(m['files']), 'bytes': m['total_bytes'], 'config_written': True}))


if __name__ == '__main__':
    main()
