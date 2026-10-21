"""Join typed relation, actual native type flags, event-time and chain identities.

Relation/event/eligible-chain denominators remain separate. No biological repair.
"""
from pathlib import Path
from collections import Counter,defaultdict
import argparse, json, numpy as np, zipfile, io, shutil
from run_archive import HERE,read,write,sha,require,module

def relation_category(row):
    if row['event_link_status'] != 'linked':
        return 'no_unique_neighboring_reference_event'
    return ('exact' if row['exact_reference_event_matched'] else
            'one_frame_only' if row['one_frame_reference_event_matched'] else
            'unmatched_within_one_frame')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input-root',type=Path,default=HERE/'fixed_archive_root');ap.add_argument('--timing-root',type=Path,required=True);ap.add_argument('--chains-root',type=Path,required=True);ap.add_argument('--native-window-root',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    root=a.input_root.resolve();art=root/'article_strengthening_20261004_v1';out=a.output.resolve();require(not out.exists(),'Fresh output');out.mkdir(parents=True);shutil.copy2(__file__,out/'EXECUTED_ADAPTER.py')
    pins={};wrong=[];events={};pair_routes=[]
    for i in range(1,30):
        film=f'{i:02d}';ep=a.timing_root/(film+'_EVENTS.json');pins[str(ep)]=sha(ep);records=read(ep);rr=[r for r in records if r['arm']=='baseline'];require(len(rr)==2,'Exact baseline two tolerances');by_t={r['tolerance_frames']:r for r in rr};events[film]=by_t
        with zipfile.ZipFile(root/'external_validation_v0.1/CTC.zip') as z:trackbytes=z.read(f'CTC/test/{film}_GT/TRA/man_track.txt')
        tracks={int(i):(int(s),int(e),int(p)) for i,s,e,p in np.loadtxt(io.BytesIO(trackbytes),dtype=int,ndmin=2)}
        children=defaultdict(list)
        for ident,(start,end,parent) in tracks.items():
            if parent:children[parent].append(ident)
        natural=art/'external_natural_support_actual_v0.1'/(film+'_edge_records.jsonl');pins[str(natural)]=sha(natural)
        for line in natural.open(encoding='utf-8'):
            r=json.loads(line)
            if r['untyped_bounds'][3]==[True,True] and r['bounds'][3]==[False,False]:
                x,y=r['reference_edge'];t=r['current_frame']-1;mother=x%100000;daughter=y%100000;k=int(r['kind']=='division');key=[film,t,mother,t+1,daughter,k]
                maps=by_t[0]['per_frame_correspondence'];forward={j:dict(row) for j,row in enumerate(maps)};p=forward[t].get(mother);q=forward[t+1].get(daughter)
                require(p is not None and q is not None,'Wrong-type relation endpoints need actual full-policy maps')
                if k:
                    candidates=[mother];rule='reference division-daughter relation supplies the mother and exact reference division boundary'
                else:
                    start,end,parent=tracks[mother];candidates=[]
                    if end==t+1 and len(children[mother])>1:candidates.append(mother)
                    if start==t and parent and len(children[parent])>1:candidates.append(parent)
                    rule='reference continuation spans an early outgoing or late incoming candidate division boundary within one frame'
                matched={}
                for tol in (0,1):
                    hits=[e for e in by_t[tol]['matched_pairs'] if e['reference_mother'] in candidates and (k or (e['prediction_mother']==p and q in e['prediction_daughters_corresponding']))]
                    require(len(hits)<=1,'Ambiguous candidate-event mapping; do not choose a tie-break');matched[tol]=hits[0] if hits else None
                selected=matched[1]['reference_mother'] if matched[1] else candidates[0] if len(candidates)==1 else None
                wrong.append({'reference_relation':key,'reference_relation_type':'division_daughter' if k else 'continuation','candidate_reference_events':[[film,m] for m in candidates],'event_link_rule':rule,'reference_event':None if selected is None else [film,selected],'event_link_status':'linked' if selected is not None else 'no_unique_neighboring_reference_event','original_typed_history':r['visibility'],'raw_pair_history':[int(lo) if lo==hi else None for lo,hi in r['untyped_bounds']],'predicted_endpoint_ids_at_exact_frames':[p,q],'prediction_raw_pair_type':0 if p==q else 1,'exact_reference_event_matched':matched[0] is not None,'one_frame_reference_event_matched':matched[1] is not None,'one_frame_match':matched[1],'reference_event_counts_as_one_unit_not_two_daughters':True})
    require(len(wrong)==123,'Complete wrong-type baseline denominator')
    grouped=defaultdict(list)
    for row in wrong:
        if row['reference_event']:grouped[tuple(row['reference_event'])].append(row)
    eventrows=[{'reference_event':list(key),'wrong_type_relation_count':len(rows),'wrong_type_relations':[r['reference_relation'] for r in rows],'exact_match':any(r['exact_reference_event_matched'] for r in rows),'one_frame_match':any(r['one_frame_reference_event_matched'] for r in rows),'match_record':next((r['one_frame_match'] for r in rows if r['one_frame_match']),None)} for key,rows in sorted(grouped.items())]
    write(out/'ALL123_WRONG_TYPE_RELATION_EVENT_CROSSWALK.json',wrong);write(out/'EVENT_UNITS.json',eventrows)
    chain_result=read(a.chains_root/'RESULT.json');chainids=chain_result['birth_to_division_chains']['untyped_complete_but_typed_incomplete_baseline'];chainrows=[]
    for film,track in chainids:
        lp=a.chains_root/(film+'_RECORDS.json');pins[str(lp)]=sha(lp);chain=next(r for r in read(lp)['birth_to_division_chains'] if r['track']==track);incoming=next(e for e in chain['required_edges'] if e[4]==1 and e[3]==track and e[2]==chain['start']);mother=incoming[1];matched={tol:next((r for r in events[film][tol]['matched_pairs'] if r['reference_mother']==mother),None) for tol in (0,1)}
        chainrows.append({'chain_identity':[film,track],'strict_required_incoming':incoming,'strict_chain_recovered':chain['recovered']['baseline'],'failure_domains':chain['failure_domains']['baseline'],'incoming_complete_event_exact_match':matched[0] is not None,'incoming_complete_event_one_frame_match':matched[1] is not None,'one_frame_match':matched[1],'strict_chain_certificate_after_join':chain['recovered']['baseline']})
    require(len(chainrows)==30,'Complete30 chain type-only cases');write(out/'ALL30_STRICT_CHAIN_INCOMING_EVENT_CROSSWALK.json',chainrows)
    # Machine-readable exact specimen plus companion daughter; pixels are in NPZ.
    sp=a.native_window_root/'FIGURE4_SOURCE_TYPE_FLAG_TABLE.json';wp=a.native_window_root/'29_WW_041_WINDOW.json';pix=a.native_window_root/'FIGURE4_29_040_041_SUPPORT_PIXELS.npz';pins.update({str(p):sha(p) for p in [sp,wp,pix]});source=read(sp)[0];win=read(wp);table=[]
    with np.load(pix,allow_pickle=False) as pixels:
        left=list(source['reference_previous_ids']);right=list(source['reference_current_ids'])
        for relation in [(40,58,1),(40,59,1)]:
            e=next(e for e in win['matching']['edges'] if tuple(e['reference_edge'])==relation);mother,daughter,k=relation;lr=left.index(mother);rr=right.index(daughter)
            for s in 'ABCD':
                st=source['projection']['stages'][s];options=e['stages'][s];edges=st['incoming_edges_previous_entryrow_current_entryrow_type'];pair_types=[{'source_entry_row':x,'target_entry_row':y,'actual_type':kk} for x,y,kk in edges if x in options['source_options'] and y in options['target_options']];row_ids=st['entry_rows'];mapped=[]
                for q in options['target_options']:
                    ix=row_ids.index(q);mask=pixels[s][ix];ref=pixels['reference_current'][rr];intersection=int((mask&ref).sum());union=int((mask|ref).sum());mapped.append({'entry_row':q,'native_cell':st['native_cells'][ix],'division_flag':st['division_flags'][ix],'query_index':st['query_all_indices'][ix],'support_area_pixels':int(mask.sum()),'reference_area_pixels':int(ref.sum()),'intersection':intersection,'union':union,'strict_integer_IoU_eligibility':2*intersection>union})
                table.append({'single_reference_relation':['29',40,mother,41,daughter,k],'stage':s,'reference_type':1,'actual_mapped_pair_types':pair_types,'raw_pair_visible':bool(pair_types),'typed_visible':options['certain'],'source_options':options['source_options'],'target_options':options['target_options'],'mapped_target_rows':mapped,'all_native_stage_rows':[{'entry_row':q,'native_cell':st['native_cells'][ix],'division_flag':st['division_flags'][ix],'query_index':st['query_all_indices'][ix],'support_area_pixels':int(pixels[s][ix].sum())} for ix,q in enumerate(row_ids)],'single_relation_scope':daughter==58,'companion_daughter_scope':daughter==59})
    shutil.copy2(pix,out/pix.name)
    write(out/'FIGURE4_EXACT_SINGLE_RELATION_AND_COMPANION_TYPE_TABLE.json',{'primary_single_relation':['29',40,40,41,58,1],'companion_reference_daughter':['29',40,40,41,59,1],'primary_raw_history':'1111','primary_typed_history':'1100','companion_typed_history':'0000','pixels_file':pix.name,'pixels_sha256':sha(pix),'stages':table,'event_not_certified_from_primary_single_relation':True})
    counts=Counter(relation_category(x) for x in wrong);ec=Counter(('exact' if x['exact_match'] else 'one_frame_only' if x['one_frame_match'] else 'unmatched_within_one_frame') for x in eventrows)
    summary={'operation':'complete relation/event/chain identity crosswalk','baseline_wrong_type_relations':len(wrong),'relation_type_counts':dict(Counter(x['reference_relation_type'] for x in wrong)),'relation_level_event_match_categories':dict(counts),'distinct_linked_reference_event_units':len(eventrows),'relations_without_unique_neighbor_event':sum(x['reference_event'] is None for x in wrong),'event_level_match_categories':dict(ec),'event_mother_end_shift_counts_by_relation':dict(Counter(str(x['one_frame_match']['mother_end_shift']) for x in wrong if x['one_frame_match'])),'eligible_chain_type_only_cases':len(chainrows),'chain_incoming_event_matched_exact':sum(x['incoming_complete_event_exact_match'] for x in chainrows),'chain_incoming_event_matched_tolerance1':sum(x['incoming_complete_event_one_frame_match'] for x in chainrows),'denominators_not_pooled':True,'scope':'Retrospective crosswalk of fixed archives. Relaxed event-time match never alters strict typed relation/whole-chain certification or identifies biological division truth.'}
    write(out/'RESULT.json',summary);write(out/'CONSUMED_BINDINGS.json',pins);write(out/'NEW_OUTPUT_FREEZE.json',{'files':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in out.iterdir() if p.is_file()}});print(json.dumps(summary))
if __name__=='__main__':main()
