from pathlib import Path
from collections import Counter,defaultdict
import csv,json
import numpy as np
import audit_engine as E
from orientation import reverse_pair_record
R=Path(__file__).resolve().parents[1];O=R/'04_统一重分析';D=R/'06_结果与交付'
def jl(p):return [json.loads(s)for s in p.read_text(encoding='utf8').splitlines()]
assets={x['asset_id']:x for x in jl(O/'ASSET_ADMISSION.jsonl')};index={x['graph_id']:x for x in jl(O/'GRAPH_INDEX.jsonl')};summ={x['graph_id']:x for x in jl(O/'GRAPH_AUDIT_SUMMARIES.jsonl')}
pairs=list(csv.DictReader((O/'paired/ALL_WITHIN_MOVIE_PAIRS.csv').open(encoding='utf-8-sig')));bykey={(r['film'],r['before_graph'],r['after_graph']):r for r in pairs}
metrics=['before_TP','after_TP','gains','losses','net']
def graph(g):return E.load_graph(O/index[g]['path'])
def vis(g):
    with np.load(O/'visibility'/(g+'.npz'),allow_pickle=False)as z:return {k:z[k].copy()for k in z.files}
def aligned(film,a,b):
    if a==b:
        s=E.read_json_gz(O/'graph_reports'/(a+'.json.gz'));v=vis(a)
        result=E.coupled_contrast(graph(a),graph(b),E.load_graph(O/'references'/(film+'.npz')),s,s,v,v,O/'frame_cache')
        r={'film':film,'before_graph':a,'after_graph':b,'status':result['status'],'canonical_gains':0,'canonical_losses':0,'canonical_net':0,'canonical_before_TP':summ[a]['canonical_TP'],'canonical_after_TP':summ[b]['canonical_TP'],'identical_saved_graph':True,'witness_record':'same_identity/'+a+'.json.gz'}
        E.save_json_gz(D/r['witness_record'],result)
        if result.get('bounds'):
            for k,x in result['bounds'].items():
                for s,v in x.items():r[k+'_'+s]=v
        return r
    x,y=sorted([a,b]);r=dict(bykey[(film,x,y)]);r['identical_saved_graph']=False
    if a==y:
        r=reverse_pair_record(r)
    return r
designs=[('division_threshold_060_to_078','F11588','F11794'),('division_threshold_078_to_090','F11794','F11847'),('division_threshold_060_to_090','F11588','F11847'),('two_postlink_policies_disabled','F12397','F12555'),('structural_refactor','F15014','F16880'),('measurement_pipeline_change_80films','F15190','F16103')]
outputs=[]
for name,a,b in designs:
    aa={x['film']:x['graph_id']for x in assets[a]['accepted']};bb={x['film']:x['graph_id']for x in assets[b]['accepted']};common=sorted(set(aa)&set(bb));rs=[aligned(f,aa[f],bb[f])for f in common]
    totals={k:sum(int(x[k])for x in rs)for k in ['canonical_before_TP','canonical_after_TP','canonical_gains','canonical_losses','canonical_net']}
    complete=all(x['status'].startswith('COMPLETE')for x in rs)
    if complete:
        totals['joint_bounds_sum_over_distinct_movies']={m:{side:sum(int(x[m+'_'+side])for x in rs)for side in ['minimum','maximum']}for m in metrics}
    outputs.append({'design':name,'before_asset':a,'after_asset':b,'before_source':assets[a]['original_locator'],'after_source':assets[b]['original_locator'],'before_cohort':len(aa),'after_cohort':len(bb),'common_movies':len(common),'before_only':sorted(set(aa)-set(bb)),'after_only':sorted(set(bb)-set(aa)),
        'identical_graph_movies':sum(x['identical_saved_graph']for x in rs),'canonical_positive_movies':sum(int(x['canonical_net'])>0 for x in rs),'canonical_negative_movies':sum(int(x['canonical_net'])<0 for x in rs),'canonical_zero_movies':sum(int(x['canonical_net'])==0 for x in rs),'same_TP_turnover_movies':sum(int(x['canonical_net'])==0 and int(x['canonical_gains'])>0 for x in rs),'totals':totals,'per_movie':rs,'causal_single_factor_not_asserted':True,'static_single_threshold_difference':name.startswith('division_threshold'),'reference_train_overlap_not_heldout_validation':True})
(D/'FOCUSED_COHORT_CONTRASTS.json').write_text(json.dumps(outputs,ensure_ascii=False,indent=2),encoding='utf8')
# Complete cohort summaries for every admitted saved asset, including zeros/losses upstream.
cohorts=[]
for a in assets.values():
    rr=[summ[x['graph_id']]for x in a.get('accepted',[])]
    if not rr:continue
    cohorts.append({'asset_id':a['asset_id'],'kind':a['kind'],'source':a['original_locator'],'film_count':len(rr),'canonical_TP':sum(x['canonical_TP']for x in rr),'canonical_FN':sum(x['canonical_FN']for x in rr),'canonical_FP_sparse_contract':sum(x['canonical_FP']for x in rr),'reference_edge_queries':sum(x['reference_edges']for x in rr),'ambiguous_relations':sum(x['ambiguous_relations']for x in rr),'path_strict_reports':sum(x['path']['strict_relaxation_differences']for x in rr),'fork_strict_reports':sum(x['fork']['strict_relaxation_differences']for x in rr),'scope':'Repeated views of TRAIN films; not independent samples or official competition scores'})
with (D/'ALL_ASSET_COHORT_RESULTS.csv').open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fieldnames=list(cohorts[0]));w.writeheader();w.writerows(cohorts)
global_summary={'pairs':len(pairs),'statuses':dict(Counter(x['status']for x in pairs)),'same_canonical_TP_but_turnover_pairs':sum(x['same_TP_with_identity_turnover']=='True'for x in pairs),'strict_coupled_narrowing_pairs':sum(x['strict_coupling_narrowing']=='True'for x in pairs),'withholds':[x for x in pairs if not x['status'].startswith('COMPLETE')],'examples_turnover':[x for x in pairs if x['same_TP_with_identity_turnover']=='True'][:20],'no_pair_count_is_independent_N':True}
(D/'PAIRED_COVERAGE_SUMMARY.json').write_text(json.dumps(global_summary,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps([{k:v for k,v in x.items()if k not in ['per_movie','before_only','after_only']}for x in outputs],ensure_ascii=False,indent=2))
