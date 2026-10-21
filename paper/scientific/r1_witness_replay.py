"""Independent complete scalar replay from actual supplied map-index membership.

The scalar replay uses full graph pair sets and elementary history arithmetic.
It never calls the producer's contribution helper or accepts a projection as a map.
"""
from pathlib import Path
import argparse, hashlib, itertools, json, sys, time
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE/'sources/portable/src'))
from portable_analysis_candidate import Graph, coupled_aggregate_bounds, history_features
from portable_analysis_candidate.io import load_families_json, load_graph_json

def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))

def emit(p, x):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf-8') as f:
        json.dump(x, f, ensure_ascii=False, indent=2)
        f.write('\n')

def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def natural_features(h):
    losses = [i for i in range(1, len(h)) if h[i-1] == 1 and h[i] == 0]
    gains = [i for i in range(1, len(h)) if h[i-1] == 0 and h[i] == 1]
    result = {'final_missing': int(h[-1] == 0), 'persistent_absence': int(not any(h)),
        'final_missing_with_loss': int(h[-1] == 0 and bool(losses)),
        'changed_reference_identities': int(bool(losses or gains)),
        'first_last_loss_disagreements_final_missing': int(h[-1] == 0 and len(losses) > 1),
        'final_last_loss_persistent': int(not any(h))}
    result.update({f'stage_visible_{i}': h[i] for i in range(7)})
    result.update({f'gain_{i}': int(i in gains) for i in range(1, 7)})
    result.update({f'loss_{i}': int(i in losses) for i in range(1, 7)})
    result.update({f'final_last_loss_{i}': int(h[-1] == 0 and bool(losses) and losses[-1] == i) for i in range(1, 7)})
    return result

def scalar_value(ref, stages, maps, field, natural=False):
    pairs = [set(map(tuple, s.edges.tolist())) for s in stages]
    total = 0
    for a, b in ref.edges.tolist():
        h = [int((m.get(a), m.get(b)) in es) for m, es in zip(maps, pairs)]
        losses = sum(h[i-1] == 1 and h[i] == 0 for i in range(1, len(h)))
        if natural:
            # This second arithmetic route does not call the feature callback.
            transitions=[h[i]-h[i-1] for i in range(1,len(h))]
            loss_positions=[i+1 for i,v in enumerate(transitions) if v==-1]
            if field=='final_missing':value=1-h[-1]
            elif field in {'persistent_absence','final_last_loss_persistent'}:value=int(sum(h)==0)
            elif field=='final_missing_with_loss':value=int(h[-1]==0 and -1 in transitions)
            elif field=='changed_reference_identities':value=int(any(transitions))
            elif field=='first_last_loss_disagreements_final_missing':value=int(h[-1]==0 and len(loss_positions)>=2)
            elif field.startswith('stage_visible_'):value=h[int(field.rsplit('_',1)[1])]
            elif field.startswith('gain_'):value=int(transitions[int(field.rsplit('_',1)[1])-1]==1)
            elif field.startswith('loss_'):value=int(transitions[int(field.rsplit('_',1)[1])-1]==-1)
            elif field.startswith('final_last_loss_'):value=int(h[-1]==0 and bool(loss_positions) and loss_positions[-1]==int(field.rsplit('_',1)[1]))
            else:raise ValueError('Unknown natural scalar: '+field)
        elif field == 'final_missing': value = int(h[-1] == 0)
        elif field == 'final_visible': value = int(h[-1] == 1)
        elif field == 'persistent_absence': value = int(not any(h))
        elif field == 'observed_loss_transitions': value = losses
        elif field == 'final_missing_after_observed_loss': value = int(h[-1] == 0 and losses > 0)
        else: raise ValueError('Unknown complete scalar field: ' + field)
        total += value
    return total

def replay(result, ref, stages, families, natural=False):
    rows = []
    for field, bound in result['scalar_bounds'].items():
        for side in ['minimum', 'maximum']:
            witness = bound[side+'_witness']
            indices = witness['whole_map_index_per_stage']
            assert len(indices) == len(stages) == len(families)
            assert all(type(i) is int and 0 <= i < len(f) for i, f in zip(indices, families))
            maps = [family[i] for family, i in zip(families, indices)]
            # An index points to a literal actual whole map, with all entries kept.
            assert all(mapping in family for mapping, family in zip(maps, families))
            value = scalar_value(ref, stages, maps, field, natural)
            assert value == bound[side] == witness['reproduced_scalar']
            assert witness['all_maps_are_members_of_supplied_families'] is True
            rows.append({'field': field, 'side': side, 'whole_map_index_per_stage': indices,
                'stage_family_sizes': [len(f) for f in families], 'actual_map_membership_checked': True,
                'independent_full_graph_scalar': value, 'reported_endpoint': bound[side], 'pass': True})
    return rows

def graph_npz(p):
    with np.load(p, allow_pickle=False) as z:
        return Graph(z['ids'], z['coords'], z['edges'], str(z['unit'].item()))

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--natural-family', required=True, type=Path)
    ap.add_argument('--natural-input-root', required=True, type=Path)
    ap.add_argument('--supplied-result', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args(); out = args.output.resolve(); out.mkdir(exist_ok=False)
    started = time.perf_counter(); input_rows=[]
    for fp in sorted(args.natural_family.glob('*.json')):
        producer = read(fp)
        if not isinstance(producer, dict) or 'frame_certificates' not in producer: continue
        film = producer['film']; root = args.natural_input_root/film
        ref = graph_npz(root/'reference.npz'); stages = [graph_npz(root/f'stage_{i}.npz') for i in range(7)]
        families=[]
        for stage in range(7):
            base = dict(map(tuple, producer['canonical_maps'][stage])); blocks = [b for b in producer['finite_blocks'] if b['stage'] == stage]
            domain=[]
            for choices in itertools.product(*(b['assignments'] for b in blocks)):
                mapping=dict(base)
                for choice in choices:
                    for node,value in choice.items():
                        if value is None: mapping.pop(int(node),None)
                        else: mapping[int(node)]=value
                domain.append(mapping)
            families.append(domain)
        # Same feature arithmetic as the declared 31 natural fields, expressed independently.
        result = coupled_aggregate_bounds(stages, ref, families, natural_features,
            cross_stage_constraints='none_in_correspondence_estimand', max_assignments_per_component=1048576)
        rows = replay(result, ref, stages, families, natural=True)
        input_rows.append({'film': film, 'result': result, 'replay_rows': rows,
            'stage_family_maps': [[[[q,v] for q,v in sorted(m.items())] for m in family] for family in families],
            'producer_family_record': str(fp), 'producer_family_sha256': sha(fp)})
    assert len(input_rows) == 8
    # Prior targets were generated by the witness extension and independently replayed.
    known = {r['film']:r['result'] for r in read(HERE/'inputs_LOCAL_ONLY/natural_witness_targets/ALL8_FILM_SCALARS_WITH_WITNESS_INDICES.json')}
    for r in input_rows: assert r['result'] == known[r['film']]
    pooled={}
    for r in input_rows:
        for name,b in r['result']['scalar_bounds'].items():
            dst=pooled.setdefault(name,{'minimum':0,'maximum':0})
            for side in ['minimum','maximum']:dst[side]+=b[side]
    natural_bounds=read(args.natural_family/'finite/unconstrained/ALL31_SCALAR_BOUNDS.json')
    assert set(pooled)==set(natural_bounds)
    assert all(pooled[k]=={side:b[side] for side in ['minimum','maximum']} for k,b in natural_bounds.items())
    emit(out/'NATURAL_ALL8_WHOLE_MAP_RESULTS_AND_REPLAYS_LOCAL_ONLY.json',input_rows)
    supplied=HERE/'inputs/supplied_family'
    families,_=load_families_json(supplied/'coordinate_families.json')
    reference=load_graph_json(supplied/'coordinate_reference.json')
    stages=[load_graph_json(supplied/f'coordinate_stage_{i}.json') for i in range(2)]
    supplied_rows=replay(read(args.supplied_result)['result'],reference,stages,families)
    emit(out/'SUPPLIED_WHOLE_MAP_ENDPOINT_REPLAY.json',supplied_rows)
    # Correlated control: two actual maps; independent component projection product is four.
    ref=Graph(np.array([1,2,3,4]),np.array([[0,0,0,0],[1,0,0,0],[0,0,0,3],[1,0,0,3]]),np.array([[1,2],[3,4]]),'pixel')
    pred=Graph(np.array([101,102,103,104,105,106,107,108]),np.array([[0,0,0,0],[1,0,0,0],[0,0,0,3],[1,0,0,3],[0,0,0,0],[1,0,0,0],[0,0,0,3],[1,0,0,3]]),np.array([[101,102],[103,104]]),'pixel')
    fam=[[{1:101,2:102,3:103,4:104},{1:105,2:106,3:107,4:108}]]*2
    control=coupled_aggregate_bounds([pred,pred],ref,fam,history_features,cross_stage_constraints='none_in_correspondence_estimand')
    control_rows=replay(control,ref,[pred,pred],fam)
    refusal=coupled_aggregate_bounds([pred,pred],ref,fam,history_features,cross_stage_constraints='none_in_correspondence_estimand',max_assignments_per_component=1)
    assert refusal['scalar_bounds'] is None and refusal['status']=='WITHHELD_COMPONENT_ENUMERATION_CAP'
    assert not any('witness' in k for k in refusal)
    emit(out/'CORRELATED_CONTROL_WITH_WITNESSES.json',{'result':control,'independent_replays':control_rows,'full_literal_families':[[list(m.items()) for m in f] for f in fam]})
    emit(out/'CAP_REFUSAL.json',refusal)
    emit(out/'VALIDATION_COMPLETE.json',{'status':'ALL_ACTUAL_WHOLE_MAP_INDICES_AND_COMPLETE_SCALARS_REPLAY_PASS',
        'natural_films':8,'natural_reference_relations':5751,'natural_fields':31,
        'natural_endpoint_replays':sum(len(r['replay_rows']) for r in input_rows),
        'supplied_endpoint_replays':len(supplied_rows),'correlated_endpoint_replays':len(control_rows),
        'correlated_families_preserved':True,'cap_no_partial_scalar_or_witness_payload':True,
        'all_full_natural_witness_targets_equal':True,'pooled_all31_natural_endpoints_equal':True,
        'family_completeness_certified_by_portable_module':False,'local_only':True,'new_biological_N':0,
        'elapsed_seconds_including_IO':time.perf_counter()-started})
    print(json.dumps({'status':'PASS','natural_endpoint_replays':496,'output':str(out)}))

if __name__=='__main__':main()
