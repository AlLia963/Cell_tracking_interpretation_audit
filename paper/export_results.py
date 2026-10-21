"""Export scientific result data for all 47 Source Data entries, without plotting.

Computed CSV/JSON files come from new measurement artifacts. Documentary entries
are labeled documentary; they are never counted as executed experiments. The
article text supplies titles and definitions, never numeric calculation answers.
"""
from pathlib import Path
import argparse
import collections
import csv
import hashlib
import json
import re
import shutil


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runs', type=Path, required=True)
    p.add_argument('--extra-runs', type=Path)
    p.add_argument('--article-root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); a.output.mkdir(parents=True, exist_ok=False)
    roots = ([a.extra_runs] if a.extra_runs else []) + [a.runs]
    aliases = {'bacterial-pulse-endpoint': 'pulse', 'bacterial-initial-overlays': 'initial',
               'historical-geometry': 'geometry', 'historical-stress': 'stress',
               'allocation-replay': 'allocation-replay_v04', 'common-generate': 'policy-generation', 'historical-negative': 'historical-negative_v02', 'common-family-census': 'common-family-census_v02'}
    def route(name):
        for root in roots:
            for key in [aliases.get(name, name), name]:
                d = root / key
                if d.is_dir() and any(d.iterdir()) and not (d / 'FAILED.json').exists():
                    return d
        raise FileNotFoundError('Missing executed route: ' + name)
    def files(name, patterns, prefix='measurement'):
        d = route(name) / prefix
        if not d.exists(): d = route(name)
        result = []
        for pat in patterns:
            result.extend(sorted(d.glob(pat)))
        return list(dict.fromkeys(result))
    spec = {}
    def bind(ids, name, pats, prefix='measurement'):
        for n in ids: spec[n] = (name, pats, prefix)
    bind([3,8,40,41,42], 'natural3d', ['ALL31_FIELD_DEFINITIONS_BOUNDS.json','ALL62_ENDPOINT_ADMISSIONS.json','REPORT_DECISION_YIELD.json','ALL8_FILM_YIELD.json','local/**/REPORTS.jsonl'])
    bind([4,5,6,7], 'natural-gates', ['gate_*/CANONICAL_HISTORIES.json','gate_*/**/ALL31_SCALAR_BOUNDS.json','gate_*/**/RESULT.json'])
    bind([9], 'historical-geometry', ['ALL_SCENARIO_BRANCH_SUMMARY.csv','ALL31_SCALAR_BOUNDS_BY_SCENARIO_FILM.csv','REPORT.json'], '')
    bind([10,11], 'historical-stress', ['case_results.csv','all_frame_results.csv','resource_profiles.csv','RUN_COMPLETE.json'], '')
    bind([12], 'bacterial-initial-overlays', ['work/native_noisy_validation_v0.3/case_records.json'])
    bind([13], 'bacterial-initial-overlays', ['final_observation_classes/RESULT.json','final_observation_classes/known_last_loss_130.json','final_observation_classes/all_determinate_final_missing.json'])
    bind([14,15], 'bacterial-division-overlays', ['measurement/CASE_RECORDS.json','measurement/TARGET_ELIGIBILITY.json'])
    bind([16,17], 'bacterial-duties', ['measurement/fixtures.json','measurement/report.json','authority.json'])
    bind([18], 'allocation-replay', ['decision_ledger.json','COMPARISON.json'], '')
    bind([19,20], 'common-score-generated', ['RESULT.json'])
    bind([21], 'common-generate', ['PREDICTIONS_BEFORE_REFERENCE.json','RESULT.json','COMPARISON_AFTER_PREDICTION_FREEZE.json'], 'generated_run')
    bind([22], 'bacterial-full', ['measurement/RESULT.json','measurement/*_results.json'])
    bind([23,24], 'bacterial-natural', ['measurement/RESULT.json','measurement/*_edge_records.jsonl'])
    bind([25], 'projection', ['RESULT.json','COMPARISON.json'])
    bind([26], 'bacterial-pulse-endpoint', ['RESULT.json','*_ENDPOINT.json'])
    bind([27,28], 'bacterial-stage-archive', ['RESULT.json','IDENTITIES.json','PULSE_LOSS_IDENTITIES.json','WITHHELD.json'])
    bind([29,30,31], 'bacterial-chains', ['measurement/RESULT.json','measurement/*_RECORDS.json'])
    bind([32,34], 'bacterial-timing', ['measurement/RESULT.json','measurement/*_EVENTS.json'])
    bind([33], 'bacterial-cca', ['measurement/RESULT.json','measurement/PER_MOVIE.csv','measurement/IDENTITIES_AND_LENGTHS.json'])
    bind([35], 'epithelial', ['reference_measurement/*complete_result.json'])
    bind([39], 'typed-constructed', ['*/RESULT.json'], '')
    bind([43], 'operating-envelope', ['REPORT_TABLE.json','NEGATIVE_CONTROLS.json','RUN_COMPLETE.json'])
    bind([44], 'identity-crosswalk', ['ALL123_WRONG_TYPE_RELATION_EVENT_CROSSWALK.json','EVENT_UNITS.json','ALL30_STRICT_CHAIN_INCOMING_EVENT_CROSSWALK.json','FIGURE4_EXACT_SINGLE_RELATION_AND_COMPANION_TYPE_TABLE.json','RESULT.json'])
    bind([45,46], 'common-family-census', ['ALL96_FILM_ARM_CENSUS.json','ALL_FRAME_CERTIFICATES.json','ALL_PATH_REPORTS.json','RESULT.json'])
    bind([47], 'analyst-path', ['REPORT.json','COMPLETE_FRAME_FAMILIES.json'])
    article = (a.article_root / 'SourceData.md').read_text(encoding='utf-8')
    sections = {int(re.match(r'D(\d+)', s).group(1)): s for s in re.split(r'\n## ', article)[1:]}
    assert set(sections) == set(range(1,48))
    documentary = {1,2,36,37,38}; index = []
    def csv_records(path, value):
        # Nested records retain their complete JSON value and identity. No
        # cross-domain denominator pooling or token-presence numerical test.
        rows = value if isinstance(value,list) else [{'field':k,'value':v} for k,v in value.items()]
        if rows and not all(isinstance(r,dict) for r in rows):
            rows = [{'index':i,'value':v} for i,v in enumerate(rows)]
        fields = list(dict.fromkeys(k for r in rows for k in r))
        with path.open('x',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
            for r in rows:
                w.writerow({k:json.dumps(v,ensure_ascii=False,separators=(',',':')) if isinstance(v,(dict,list)) else v for k,v in r.items()})
    for n in range(1,48):
        d=a.output/f'D{n:02}';d.mkdir();sources=[]
        if n in documentary:
            (d/'DOCUMENTARY.md').write_text('## '+sections[n],encoding='utf-8')
            kind='documentary: definition, provenance, literature or historical execution scope'
        else:
            name,pats,prefix=spec[n]; ff=files(name,pats,prefix)
            if name=='common-generate' and not ff:
                ff=files(name,pats,'measurement/generated_run')
            if name in ('historical-geometry','historical-stress','allocation-replay') and not ff:
                ff=files(name,pats,'measurement')
            if not ff: raise ValueError('No actual scientific result for D%02d'%n)
            for i,f in enumerate(ff):
                dest=d/(f'{i:03}_'+f.name)
                shutil.copy2(f,dest)
                if f.suffix in ('.json','.jsonl'):
                    val=read(f) if f.suffix=='.json' else [json.loads(x) for x in f.read_text(encoding='utf-8').splitlines()]
                    csv_records(dest.with_suffix('.csv'),val)
                sources.append({'route':name,'artifact':f.relative_to(route(name)).as_posix(),'sha256':sha(f)})
            kind='computed scientific data (CSV plus complete original JSON/JSONL); not figure rendering'
        index.append({'source_data':f'D{n:02}','kind':kind,'sources':sources,
                      'fresh_resource_values_need_not_equal_historical_wall_time':n==11})
    (a.output/'SOURCE_DATA_EXPORT_INDEX.json').write_text(json.dumps({'source_data_sha256':sha(a.article_root/'SourceData.md'),
        'all47_entries_present':True,'computed_entries':42,'documentary_entries':5,'rows':index,
        'export_is_not_itself_full_prose_numeric_QC':True},ensure_ascii=False,indent=2),encoding='utf-8')
    # S4 historical adverse/null controls were not assigned separate D numbers.
    negative = files('historical-negative', ['RESULT.json','COMPARISON.json'])
    extra = a.output/'S4_HISTORICAL_NEGATIVE';extra.mkdir()
    for f in negative:
        shutil.copy2(f,extra/f.name)
        if f.name=='RESULT.json':
            for key,value in read(f).items():
                if isinstance(value,list):csv_records(extra/(key+'.csv'),value)
    print(json.dumps({'entries':len(index),'computed':42,'documentary':5,'additional_S4_negative_files':len(negative)}))


if __name__=='__main__': main()
