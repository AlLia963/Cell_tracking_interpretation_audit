"""Denominators and compact complete cohort tables from actual bound records."""
from pathlib import Path
import argparse, collections, json, numpy as np
from run_archive import HERE, sha, read, write, require
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();out=a.output.resolve();require(not out.exists(),'Output must be absent');out.mkdir(parents=True)
    pm=read(HERE/'sources/legacy/common_carrier96/prediction_manifest.json');by={r['stem']:r for r in pm['predictions'] if r['arm']=='unchanged'};rows=[];totals=collections.defaultdict(collections.Counter)
    for film in sorted(by):
        p=HERE/'inputs_LOCAL_ONLY/common_carrier96'/f'{film}_reference_pixel.npz'
        with np.load(p,allow_pickle=False) as z:
            n=len(z['ids']);e=len(z['edges']);require(len(set(map(int,z['ids'])))==n,'Reference node IDs');require(len(set(map(tuple,z['edges'].tolist())))==e,'Reference unique edges')
        row={'film':film,'split':by[film]['split'],'reference_nodes':n,'reference_edges':e,'reference_npz_sha256':sha(p)};rows.append(row);totals[row['split']].update({'films':1,'reference_nodes':n,'reference_edges':e});totals['all'].update({'films':1,'reference_nodes':n,'reference_edges':e})
    write(out/'COMMON_CARRIER16_DENOMINATORS.json',{'records':rows,'totals':{k:dict(v) for k,v in totals.items()},'selection_provenance':'All16 already defined native_consensus_B films in original SVM_topology_replay_v0.2 prediction_manifest,8 development+8 transfer; no outcome selection. Exact saved B restored before-gate carrier used for all6 policies; correlated E predictions supplied prior completed runs. Fixed retrospective reused material; no independent prospective biological validation. Sparse source-relative reference, not all unannotated graph edges as negatives.','source_prediction_manifest_sha256':sha(HERE/'sources/legacy/common_carrier96/prediction_manifest.json')})
    x=read(HERE/'results/identity_crosswalk_run03/ALL123_WRONG_TYPE_RELATION_EVENT_CROSSWALK.json');write(out/'CROSSWALK_RECORD_SCHEMA_SAMPLE.json',{'top_type':type(x).__name__,'first':x[0] if isinstance(x,list) else {k:(v[0] if isinstance(v,list) else v) for k,v in x.items()}})
    table=[]
    for typ in ['continuation','division_daughter']:
        rowsx=[r for r in x if r['reference_relation_type']==typ];table.append({'relation_type':typ,'relations':len(rowsx),'exact_event_match':sum(r['exact_reference_event_matched'] for r in rowsx),'tolerance_only':sum(r['one_frame_reference_event_matched'] and not r['exact_reference_event_matched'] for r in rowsx),'linked_event_unmatched_within1':sum(r['reference_event'] is not None and not r['one_frame_reference_event_matched'] for r in rowsx),'no_unique_neighboring_event':sum(r['reference_event'] is None for r in rowsx)})
    events=read(HERE/'results/identity_crosswalk_run03/EVENT_UNITS.json');chains=read(HERE/'results/identity_crosswalk_run03/ALL30_STRICT_CHAIN_INCOMING_EVENT_CROSSWALK.json')
    write(out/'CROSSWALK_DENOMINATORS.json',{'relation_table':table,'event_units':len(events),'event_relation_multiplicity_by_match':{str(k):dict(collections.Counter(r['wrong_type_relation_count'] for r in events if r['one_frame_match']==k)) for k in [True,False]},'mother_end_shift_by_event':dict(collections.Counter(str(r['match_record']['mother_end_shift']) for r in events if r['match_record'])),'mother_end_shift_for30_chain_birth_events':dict(collections.Counter(str(r['one_frame_match']['mother_end_shift']) for r in chains if r['one_frame_match'])),'scope':'123 strict typed-D failures with raw-D present: relation-level join to neighboring CTC reference division events and actual one-to-one BC event records. There are115 linked relations belonging to64 distinct reference events, and8 continuations without a unique neighboring actual event. Neither123 nor64 is the full2496 reference-event denominator. Tolerance matching does not change strict typed relation or eligible-chain certification.'})
    write(out/'OUTPUT_FREEZE.json',{'files':{p.name:sha(p) for p in out.iterdir() if p.is_file()}})
    print(json.dumps({k:dict(v) for k,v in totals.items()}))
if __name__=='__main__':main()
