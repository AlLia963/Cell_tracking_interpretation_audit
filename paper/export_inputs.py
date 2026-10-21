"""Export an authorized LOCAL ONLY scientific input companion to a new path.

This never uploads data. Actual copies, rather than workspace junctions, make
the companion independent of the author's historical directory tree. Code is
supplied separately by this repository. Frozen outputs used for comparisons and
source certificates are labeled inputs, not generated experimental evidence.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil

HERE = Path(__file__).resolve().parent


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--article-root', type=Path)
    a = p.parse_args(); c = read(a.config)
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    excluded = {'__pycache__', '.git', 'records', 'results', 'recipes_prepared_unexecuted'}
    def copy_tree(source, target, omit_code=False):
        for base, dirs, files in os.walk(source, followlinks=True):
            dirs[:] = [x for x in dirs if x not in excluded]
            d = target / Path(base).relative_to(source); d.mkdir(parents=True, exist_ok=True)
            for name in files:
                f = Path(base) / name
                if f.suffix == '.pyc' or (omit_code and f.suffix == '.py'):
                    continue
                shutil.copy2(f, d / name)
    # Metadata, supplied scientific arrays, and comparison targets. No code is
    # invisibly imported from the old workspace by the new runtime assembler.
    companion = out / 'companion'
    copy_tree(Path(c['runtime_root']), companion, omit_code=True)
    # A few historical checkers pin non-executable authority/fixture JSON under
    # a directory called results. Preserve these declared contract inputs even
    # though old measurement runs are excluded from the companion.
    bacterial = Path(c['runtime_root']) / 'inputs_LOCAL_ONLY/bacterial'
    for row in read(bacterial / 'CONFIG_LOCAL_ONLY.json')['source_files']:
        source = bacterial / row['package']
        if source.is_file() and source.suffix != '.py':
            target = companion / 'inputs_LOCAL_ONLY/bacterial' / row['package']
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, target)
    # Native grid registration validates a small set of original source bytes.
    # These inert provenance copies are never executed/imported as dependency code.
    cfg = read(bacterial / 'CONFIG_LOCAL_ONLY.json')
    registration = read(bacterial / 'provenance/pulse/coordinate_registration.json')
    original_prefix = cfg['input_root'].replace('\\', '/').rstrip('/') + '/'
    for record in registration.values():
        for name, expected in record['upstream_source_evidence_bindings'].items():
            rel = name.replace('\\', '/').removeprefix(original_prefix)
            source = Path(c['bacterial_input_root']) / rel
            if sha(source) != expected:
                raise ValueError('Original registration provenance changed')
            target = companion / 'inputs_LOCAL_ONLY/bacterial/fixed_archive_root' / rel
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, target)
    if c.get('extra_input_root'):
        copy_tree(Path(c['extra_input_root']), out / 'extras')
    old_composition = companion / 'LOCAL_COMPOSITION.json'
    if old_composition.exists():
        old_composition.unlink()  # our copied record, not an original/hardlink
    copy_tree(Path(c['common_generation_root']), out / 'common_generation', omit_code=True)
    # Only the graph carriers actually consumed by the 96-output generation.
    generation = Path(c['generated_common_root']).parent
    pins = read(generation / 'PREDICTIONS_BEFORE_REFERENCE.json')['input_bindings']
    iws = Path(c['iws_root']).resolve()
    for name in pins:
        f = Path(name).resolve()
        if f.is_relative_to(iws):
            dest = out / 'iws_carriers' / f.relative_to(iws)
            if f.is_dir():
                copy_tree(f, dest)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(f, dest)
    shutil.copy2(c['allocation_scores'], out / 'allocation_scores.json')
    if a.article_root:
        d = out / 'article'; d.mkdir()
        for name in ['manuscript_v1.0.md', 'supplement_v1.0_proofread.md', 'SourceData.md']:
            shutil.copy2(a.article_root / name, d / name)
    files = [{'path': f.relative_to(out).as_posix(), 'bytes': f.stat().st_size, 'sha256': sha(f)}
             for f in sorted(out.rglob('*')) if f.is_file()]
    manifest = {'schema': 'paper-input-companion-v1', 'local_only': True,
                'publication_permission': False, 'files': files,
                'total_bytes': sum(x['bytes'] for x in files),
                'code_in_repository': True, 'contains_fixed_predictions_and_stage_certificates': True,
                'contains_historical_comparison_answers': True,
                'upstream_training_reproduced': False}
    (out / 'INPUT_MANIFEST.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({'files': len(files), 'bytes': manifest['total_bytes'], 'local_only': True}))


if __name__ == '__main__':
    main()
