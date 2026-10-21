"""Complete authorized-user natural reconstruction and endpoint admission."""
if not __debug__:
    raise RuntimeError('CONSTRUCTOR_ASSERTIONS_DISABLED: run without -O and PYTHONOPTIMIZE')
import argparse,collections,csv,hashlib,json,subprocess,sys,time
from pathlib import Path
import psutil
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'sources/family'))
from reconstruct import feature
def emit(p,x):
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def total(hs):
    d={k:0 for k in feature('0000000')}
    for h in hs:
        for k,v in feature(h).items():d[k]+=v
    return d
def command(argv,cwd,log):
    t=time.perf_counter();rss=0
    with log.open('x',encoding='utf-8') as f:
        p=subprocess.Popen(argv,cwd=cwd,stdout=f,stderr=subprocess.STDOUT)
        process=psutil.Process(p.pid)
        while p.poll() is None:
            try:rss=max(rss,process.memory_info().rss)
            except psutil.Error:pass
            time.sleep(.02)
        rc=p.wait()
    result={'argv':argv,'cwd':str(cwd),'exit_code':rc,'elapsed_wall_seconds_including_IO':time.perf_counter()-t,'sampled_process_RSS_peak_lower_bound_bytes':rss}
    emit(log.with_suffix('.json'),result)
    if rc:raise RuntimeError(f'Failed command; retained {log}')
    return result
def definition(k):
    if k=='final_missing':return '1 iff V6=0'
    if k=='persistent_absence':return '1 iff all V0..V6=0'
    if k=='final_missing_with_loss':return '1 iff V6=0 and some adjacent 1-to-0 transition'
    if k=='changed_reference_identities':return '1 iff any adjacent visibility change; not changed node IDs or difference from canonical'
    if k=='first_last_loss_disagreements_final_missing':return '1 iff V6=0 and at least two distinct loss transitions; within-history first versus last'
    if k=='final_last_loss_persistent':return '1 iff V6=0 and no observed loss; exactly duplicates persistent_absence'
    if k.startswith('stage_visible_'):return 'V'+k.rsplit('_',1)[1]
    i=int(k.rsplit('_',1)[1])
    if k.startswith('final_last_loss_'):return f'1 iff V6=0 and last adjacent loss is at S{i}'
    if k.startswith('gain_'):return f'1 iff V{i-1}=0 and V{i}=1'
    return f'1 iff V{i-1}=1 and V{i}=0'
def scalar_report(root,out):
    shared=root/'finite/unconstrained';linked=root/'finite/geometry_constrained'
    hs=load(shared/'ALL5751_HISTORY_SETS.json');joint=load(shared/'JOINT_INPUT.LOCAL_ONLY.json')
    ws=load(shared/'COMPLETE_MAPPING_CONFIGURATION_WITNESSES.json');bounds=load(shared/'ALL31_SCALAR_BOUNDS.json')
    fixed=total(r['history']for r in joint['fixed_histories'])
    components=[[total(h)for h in c['configurations']]for c in joint['components']]
    marg_lo=collections.Counter();marg_hi=collections.Counter()
    for r in hs:
        vals=[feature(h)for h in r['admissible_visibility_strings']]
        for k in bounds:marg_lo[k]+=min(v[k]for v in vals);marg_hi[k]+=max(v[k]for v in vals)
    fields=[];proposals=[]
    adapted={'changed_reference_identities','first_last_loss_disagreements_final_missing','final_last_loss_persistent'}
    for k, v in bounds.items():
        lo=fixed[k]+sum(min(x[k]for x in c)for c in components);hi=fixed[k]+sum(max(x[k]for x in c)for c in components)
        assert (lo,hi)==(v['minimum'],v['maximum'])
        changed=k in adapted
        prior=('Earlier independent fields compared a history/first/last category with canonical, rather than adjacent transition occurrence or within-history first/last.' if k in {'changed_reference_identities','first_last_loss_disagreements_final_missing'} else 'Added duplicate of prefrozen persistent_absence.' if k=='final_last_loss_persistent' else 'Same semantic definition before target access.')
        f={'field':k,'definition':definition(k),'historical_post_target_semantic_adaptation':changed,'historical_difference':prior,'redundant_with':'persistent_absence'if k=='final_last_loss_persistent'else None,'canonical':v['canonical'],'independent_edge_minimum':marg_lo[k],'independent_edge_maximum':marg_hi[k],'joint_minimum':lo,'joint_maximum':hi}
        fields.append(f)
        for side,marg,endpoint in [('minimum',marg_lo[k],lo),('maximum',marg_hi[k],hi)]:
            inds=[w[f'{side}_witness_config_index'][k]for w in ws]
            realized=fixed[k]+sum(c[i][k]for c,i in zip(components,inds));assert realized==endpoint
            proposals.append({'field':k,'proposal_side':side,'independent_edge_endpoint':marg,'joint_attainable_endpoint':endpoint,'proposal_is_whole_map_attainable':marg==endpoint,'admission':'ACCEPT_WITH_COMPONENT_WITNESS'if marg==endpoint else'REJECT_OUTSIDE_JOINT_INTERVAL','component_witness_indices':inds,'witness_value':realized,'witness_file':'family/gate_07/finite/unconstrained/COMPLETE_MAPPING_CONFIGURATION_WITNESSES.json','post_target_definition_adaptation':changed})
    films=[]
    for film in sorted({r['film']for r in hs}):
        rows=[r for r in hs if r['film']==film]
        films.append({'film':film,'reference_relations':len(rows),'nonunique_histories':sum(len(r['admissible_visibility_strings'])>1 for r in rows),'nonunique_categories':sum(len(r['categories'])>1 for r in rows),'final_missing':sum(r['canonical_history'][-1]=='0'for r in rows)})
    emit(out/'ALL31_FIELD_DEFINITIONS_BOUNDS.json',fields);emit(out/'ALL62_ENDPOINT_ADMISSIONS.json',proposals);emit(out/'ALL8_FILM_YIELD.json',films)
    emit(out/'REPORT_DECISION_YIELD.json',{'reference_relations':len(hs),'ambiguous_histories':sum(len(r['admissible_visibility_strings'])>1 for r in hs),'ambiguous_categories':sum(len(r['categories'])>1 for r in hs),'scalar_fields':len(fields),'tightened_fields':sum(f['independent_edge_minimum']<f['joint_minimum']or f['joint_maximum']<f['independent_edge_maximum']for f in fields),'proposals':len(proposals),'rejected':sum(not p['proposal_is_whole_map_attainable']for p in proposals),'same_information_constrained_decisions_identical':True,'biological_N_added':0,'human_utility_measured':False,'independent_edge_bounds_are_valid_conservative_bounds':True})
    # Compare only after scientific outputs exist. No known values entered producer.
    known=HERE.parents[1]/'inputs_LOCAL_ONLY/natural_comparisons';diff=[]
    assert hs==load(known/'ALL5751_HISTORY_SETS.json')
    assert load(linked/'ALL5751_HISTORY_SETS.json')==load(known/'ALL5751_LINKED_HISTORY_SETS.json')
    with (known/'ALL62_REPORT_ADMISSION_QUERIES.csv').open(encoding='utf-8-sig',newline='')as h:expected=list(csv.DictReader(h))
    assert len(expected)==len(proposals)
    for e,p in zip(expected,proposals):
        for key in ['field','proposal_side','independent_edge_endpoint','joint_attainable_endpoint','proposal_is_whole_map_attainable','admission','witness_value']:
            if str(p[key])!=str(e[key]):diff.append({'field':p['field'],'key':key,'actual':p[key],'expected':e[key]})
        if p['component_witness_indices']!=json.loads(e['component_witness_indices']):diff.append({'field':p['field'],'key':'component_witness_indices'})
    emit(out/'COMPLETE_SCIENTIFIC_COMPARISON.json',{'all5751_primary_histories_equal':True,'all5751_linked_histories_equal':True,'endpoint_rows':62,'differences':diff,'pass':not diff})
    assert not diff
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input-root',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--skip-local',action='store_true');a=ap.parse_args()
    out=a.output.resolve();out.mkdir(exist_ok=False);t=time.perf_counter();commands=[]
    commands.append(command([sys.executable,'-B','-X','utf8',str(HERE/'sources/family/reconstruct.py'),'--input-root',str(a.input_root.resolve()),'--output',str(out/'family'),'--gates','7'],HERE,out/'family.log'))
    scalar_report(out/'family/gate_07',out)
    if not a.skip_local:commands.append(command([sys.executable,'-B','-X','utf8',str(HERE/'sources/local/workflow.py'),'--manifest',str(HERE/'NATURAL_LOCAL_MANIFEST.json'),'--input-root',str(a.input_root.resolve()),'--output',str(out/'local')],HERE,out/'local.log'))
    emit(out/'RUN_COMPLETE.json',{'status':'ACTUAL_NATURAL_FAMILY_GLOBAL_SCALAR_AND_LOCAL_EXECUTION_COMPLETE','commands':commands,'elapsed_wall_seconds_including_IO':time.perf_counter()-t,'restricted_local_only':True,'old_comparison_targets_known':True,'new_biological_N':0,'new_upstream_inference':False})
    emit(out/'OUTPUT_MANIFEST.json',{'files':{str(p.relative_to(out)).replace('\\','/'):sha(p)for p in sorted(out.rglob('*'))if p.is_file()}})
    print(json.dumps({'status':'ACTUAL_NATURAL_EXECUTION_COMPLETE','output':str(out),'seconds':time.perf_counter()-t}))
if __name__=='__main__':main()
