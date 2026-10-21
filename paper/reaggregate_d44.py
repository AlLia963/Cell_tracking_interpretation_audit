"""Reaggregate the saved D44 identities without rerunning event matching.

Historical results remain unchanged. Current categories keep unlinked
relations separate from linked events that remain unmatched at tolerance one.
"""
from pathlib import Path
from collections import Counter
import argparse,json

def require(ok,message):
    if not ok:raise ValueError(message)

def summarize(relations,events,chains):
    require(len(relations)==123 and len(events)==64 and len(chains)==30,'Unexpected retained D44 denominators')
    require(len({tuple(x['reference_relation'])for x in relations})==123,'Repeated relation identity')
    require(len({tuple(x['reference_event'])for x in events})==64,'Repeated event identity')
    require(len({tuple(x['chain_identity'])for x in chains})==30,'Repeated chain identity')
    groups=Counter()
    for row in relations:
        linked=row['reference_event'] is not None
        require(linked==(row['event_link_status']=='linked'),'Inconsistent event-link identity')
        if not linked:
            require(not row['exact_reference_event_matched'] and not row['one_frame_reference_event_matched'],'Unlinked relation has event match')
            category='no_unique_neighboring_reference_event'
        elif row['exact_reference_event_matched']:category='exact'
        elif row['one_frame_reference_event_matched']:category='one_frame_only'
        else:category='unmatched_within_one_frame'
        groups[category]+=1
    eg=Counter('exact'if x['exact_match']else'one_frame_only'if x['one_frame_match']else'unmatched_within_one_frame'for x in events)
    require(set(tuple(x['reference_event'])for x in relations if x['reference_event'])==set(tuple(x['reference_event'])for x in events),'Linked event domains differ')
    require([groups['one_frame_only'],groups['unmatched_within_one_frame'],groups['no_unique_neighboring_reference_event']]==[102,13,8],'Current relation groups differ from manuscript')
    require([eg['one_frame_only'],eg['unmatched_within_one_frame']]==[51,13],'Current event groups differ from manuscript')
    return {'status':'D44_CURRENT_DENOMINATORS_CHECKED','relation_identities':123,
        'relation_level_event_match_categories':dict(groups),'distinct_linked_events':64,
        'event_level_match_categories':dict(eg),'chain_incoming_timing_discrepancies':30,
        'legacy_unmatched_category_21_means_linked_unmatched_13_plus_unlinked_8':True,
        'historical_result_bytes_changed':False,'event_matching_rerun':False,'denominators_not_pooled':True}

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--relations',type=Path,required=True)
    ap.add_argument('--events',type=Path,required=True);ap.add_argument('--chains',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    result=summarize(*[json.loads(p.read_text(encoding='utf8'))for p in (a.relations,a.events,a.chains)])
    with a.output.open('x',encoding='utf8')as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result))
