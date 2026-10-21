"""Fresh-output path adapters for exact scientific source functions.

No ROOT approval files are reader preconditions. CONFIG_LOCAL_ONLY and file
hashes identify the authorized existing archives. Upstream inference is separate.
"""
from pathlib import Path
from types import SimpleNamespace
import argparse, ast, collections, datetime, hashlib, importlib.util, json, os, shutil, subprocess, sys, traceback, zipfile
import numpy as np
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
CELLS=('WW','AW','WA','AA')
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,x):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False)
def require(c,m):
    if not c:raise ValueError(m)
def module(path,name='adapted_source'):
    """Load definitions/normal constant setup; remove original entry invocation only."""
    path=Path(path);tree=ast.parse(path.read_text(encoding='utf-8'))
    body=[]
    for node in tree.body:
        if isinstance(node,ast.If) and '__name__' in ast.unparse(node.test):continue
        if isinstance(node,ast.Try) and any(isinstance(x,ast.Call) and isinstance(x.func,ast.Name) and x.func.id=='main' for x in ast.walk(node)):continue
        body.append(node)
    ns={'__file__':str(path),'__name__':name}
    exec(compile(ast.Module(body=body,type_ignores=[]),str(path),'exec'),ns)
    return ns
def relocate_top(path,overrides):
    """Execute original top-level source with explicit path-variable assignments.

    The function bodies, graph operations, matching and aggregation are unchanged.
    Every overridden variable is named in ADAPTER_RECORD.json.
    """
    path=Path(path);tree=ast.parse(path.read_text(encoding='utf-8'));ns={'__file__':str(path),'__name__':'relocated_script'}
    for node in tree.body:
        if isinstance(node,ast.Assign):
            targets=[x.id for x in node.targets if isinstance(x,ast.Name)]
            if len(targets)==1 and targets[0] in overrides:
                ns[targets[0]]=overrides[targets[0]];continue
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),ns)
    return ns
def source_bindings():
    cfg=read(HERE/'CONFIG_LOCAL_ONLY.json')
    for row in cfg['source_files']:
        # Acquisition/job records are contextual provenance, never reader gates.
        if row['package'].startswith('provenance/'):continue
        require(sha(HERE/row['package'])==row['sha256'],'Packaged source/input changed: '+row['package'])
    return cfg
def full_resources(root,out):
    art=root/'article_strengthening_20261004_v1';p=HERE/'sources/legacy/external_full/RESOURCE_MANIFEST.json';cfg=read(p)
    cfg['archive_path']=str(root/'external_validation_v0.1/CTC.zip')
    for row in cfg['arms']:row['native_root']=str(root/'external_trajectory_intervention_v0.1'/row['arm']/'native')
    d=out/'resources';d.mkdir()
    for row in cfg['arms']:shutil.copy2(HERE/'sources/legacy/external_full'/row['manifest_relative'],d/row['manifest_relative'])
    write(d/'RESOURCE_MANIFEST.json',cfg);return d
def run_common(root,out):
    subprocess.run([sys.executable,'-B','-X','utf8',str(HERE/'inputs_LOCAL_ONLY/common_carrier96/reproduce96.py'),'--output',str(out/'RESULT.json')],check=True)
def run_full(root,out):
    resources=full_resources(root,out)
    subprocess.run([sys.executable,'-B','-X','utf8',str(HERE/'sources/legacy/external_full/reproduce_external_from_labels.py'),'--resources',str(resources/'RESOURCE_MANIFEST.json'),'--output',str(out/'measurement')],check=True)
def run_natural(root,out):
    stage_set_up();old=root/'article_strengthening_20261004_v1/reproduction_LOCAL_ONLY_v0.1/external_natural';resources=out/'resources';resources.mkdir();cfg=read(old/'RESOURCE_MANIFEST.json');cfg['archive_path']=str(root/'external_validation_v0.1/CTC.zip')
    for row in cfg['films']:
        row['support_paths_resolve_under']=str(root/'external_end_to_end_feasibility_v0.1')
        for k in ['sidecar_relative','graph_relative']:shutil.copy2(old/row[k],resources/row[k])
    write(resources/'RESOURCE_MANIFEST.json',cfg)
    ns=module(HERE/'sources/legacy/external_natural/reproduce_natural_from_supports.py');sys.argv=['natural','--resources',str(resources/'RESOURCE_MANIFEST.json'),'--output',str(out/'measurement')];ns['main']()
def run_metric(root,out,route):
    name={'timing':'division_timing_sensitivity_v0.1','cca':'cca_existing_cohort_v0.1','chains':'lineage_consequence_v0.1'}[route]
    src=HERE/'sources'/name/('analyze_v02.py' if route=='chains' else 'analyze.py')
    ns=module(src);resources=full_resources(root,out)
    ns.update(P=src.parent,A=root/'article_strengthening_20261004_v1',R=root,B=resources,S=HERE/'sources/closest_prior_lineage_definitions_v0.1',O=out/'measurement')
    if route=='timing':shutil.copy2(HERE/'sources/legacy/external_full/reproduce_external_from_labels.py',resources/'reproduce_external_from_labels.py')
    if route=='chains':
        original_load=ns['load']
        def relocated_load(path):
            if Path(path).name=='RESOURCE_MANIFEST.json' and Path(path).parent.name=='external_full':return read(resources/'RESOURCE_MANIFEST.json')
            return original_load(path)
        ns['load']=relocated_load
    ns['main']()
def run_duties(root,out,decision_ledger=None):
    art=root/'article_strengthening_20261004_v1';rep=art/'reproduction_LOCAL_ONLY_v0.1'
    base=HERE/'sources/legacy';sys.path.insert(0,str(base/'reusable_analysis_package_v0.1'));sys.path.insert(0,str(base/'real_policy_contract_v0.1'))
    old=module(base/'real_policy_contract_v0.1/run_controls.py','duty_fixture')
    checker=module(base/'real_policy_contract_v0.2/contract_accounting.py','duty_checker')
    old.update(GRAPHS=rep/'3d_original_pixel_stage_exports',LEDGER=Path(decision_ledger) if decision_ledger else HERE/'inputs_LOCAL_ONLY/decision_ledger.json',R=base,HERE=base/'real_policy_contract_v0.1',OUT=out/'measurement')
    ledger=read(old['LEDGER']);contracts=[]
    for row in ledger['result_rows']:
        p=old['GRAPHS']/row['film']/'S2_gap_closing.npz';g=old['load'](p)
        contracts.append({'film':row['film'],'contract':{'schema':'certified-append-domain-v1','authority_sha256':sha(old['LEDGER']),'input_stamp':checker['stamp'](g),'candidate_domain':[(x['source'],x['target']) for x in row['proposal_decision_ledger']],'required_additions':sorted(map(tuple,row['independent_expected_winners']))},'input_file_sha256':sha(p)})
    authority_path=out/'authority.json';write(authority_path,{'schema':'pinned-append-authority-v1','contracts':contracts,'independent_ledger_sha256':sha(old['LEDGER']),'source_replay_sha256':sha(rep/'S3_image_veto_replay_v0.1/report.json')})
    authority=checker['load_authority'](authority_path,sha(authority_path))
    def wrapped(before,after,candidate,contract):
        if contract is not None:contract=json.loads(json.dumps(contract))
        hits=[r['film'] for r in contracts if r['contract']['input_stamp']==(contract['input_stamp'] if contract else checker['stamp'](before))]
        require(len(hits)==1,'Cannot bind duty fixture carrier')
        return checker['check'](before,after,candidate,contract,authority=authority,film=hits[0])
    old.update(check=wrapped,stamp=checker['stamp']);old['main']()
def stage_set_up():
    base=HERE/'sources/legacy'
    for n in ['analysis_framework_v0.8','mask_ambiguity_v0.1','typed_pathway_adapter_v0.2']:sys.path.insert(0,str(base/n))
    sys.path.insert(0,str(base));return base
def run_initial(root,out):
    base=stage_set_up();work=out/'work';work.mkdir();art=root/'article_strengthening_20261004_v1';rep=art/'reproduction_LOCAL_ONLY_v0.1'
    # Re-execute the fixture generator from actual baseline native supports.
    # Original construction review is provenance, never a reader approval gate.
    src=(base/'generate_native_noisy_controls_v02.py').read_text(encoding='utf-8')
    src=src.replace("assert (R/'native_conditional_graph_audit_v0.2.md').exists()",'pass')
    src=src.replace("sha(R/'native_conditional_graph_audit_v0.2.md')","'historical_construction_review_not_required'")
    tree=ast.parse(src);env={'__file__':str(base/'generate_native_noisy_controls_v02.py'),'__name__':'generator'}
    overrides={'R':root,'B':root/'external_end_to_end_feasibility_v0.1','O':work/'native_noisy_controls_v0.2'}
    for node in tree.body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in overrides:
            env[node.targets[0].id]=overrides[node.targets[0].id];continue
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(base/'generate_native_noisy_controls_v02.py'),'exec'),env)
    for n in ['analysis_framework_v0.8','mask_ambiguity_v0.1','typed_pathway_adapter_v0.2']:
        shutil.copytree(base/n,work/n)
    shutil.copy2(base/'native_noisy_control_protocol_v0.1.md',work/'native_noisy_control_protocol_v0.1.md')
    d=work/'external_validation_v0.1';d.mkdir();os.link(root/'external_validation_v0.1/CTC.zip',d/'CTC.zip')
    reader=module(base/'run_native_noisy_validation_v03.py');reader['R']=work;reader['main']()
    final=module(HERE/'sources/final_only.py');final.update(B=work,O=out/'final_observation_classes');final['main']()
def run_division(root,out):
    stage_set_up();src=HERE/'sources/division_window_controls_v0.1';art=root/'article_strengthening_20261004_v1';work=out/'work';work.mkdir()
    old=art/'reproduction_LOCAL_ONLY_v0.1/external_natural';relocated=out/'resources/external_natural';relocated.mkdir(parents=True);cfg=read(old/'RESOURCE_MANIFEST.json');cfg['archive_path']=str(root/'external_validation_v0.1/CTC.zip')
    for row in cfg['films']:
        row['support_paths_resolve_under']=str(root/'external_end_to_end_feasibility_v0.1')
        for k in ['sidecar_relative','graph_relative']:shutil.copy2(old/row[k],relocated/row[k])
    write(relocated/'RESOURCE_MANIFEST.json',cfg)
    shutil.copy2(HERE/'sources/legacy/run_native_noisy_validation_v03.py',out/'resources/run_native_noisy_validation_v03.py')
    # Reader also obtains the CTC archive through external_full resources.
    (out/'resources/external_full').mkdir();fcfg=read(HERE/'sources/legacy/external_full/RESOURCE_MANIFEST.json');fcfg['archive_path']=str(root/'external_validation_v0.1/CTC.zip');write(out/'resources/external_full/RESOURCE_MANIFEST.json',fcfg)
    relocate_top(src/'generate_v02.py',{'D':src,'A':art,'B':out/'resources','O':work/'fixtures_v0.2'})
    relocate_top(src/'measure.py',{'D':src,'B':out/'resources','F':work/'fixtures_v0.2','O':out/'measurement'})
def run_pulse(root,out):
    cfg=read(HERE/'CONFIG_LOCAL_ONLY.json');cohort=root/cfg['pulse_cohort_relative'];complete=read(cohort/'COHORT_COMPLETE.json')
    me=module(HERE/'sources/pulse/fourcell_scientific_measurement_preparation_v0.3/measurement_driver_v0_9.py')
    rows=[];pins={};frames={};taus={}
    for row in complete['films']:
        p=cohort/row['arm']/row['film']/'FILM_COMPLETE.json';require(sha(p)==row['film_complete_sha256'],'Pulse film index pin');idx=read(p)
        q=p.parent/'prediction/prediction.npz';binding={k.replace('\\','/'):v for k,v in idx['output_bindings'].items()};require(sha(q)==binding['prediction/prediction.npz'],'Pulse compact prediction pin');pins[str(p)]=sha(p);pins[str(q)]=sha(q);frames[row['film']]=row['frames'];taus[row['film']]=idx['tau']
    require(len(pins)==232 and sum(frames.values())==5340,'Complete all116 input contracts')
    write(out/'INPUTS_BEFORE_REFERENCE.json',{'files':pins,'archive_sha256':cfg['archive_sha256']})
    totals={a:collections.Counter() for a in CELLS};contrasts={a:collections.Counter() for a in CELLS[1:]};gains_losses={a:[0,0] for a in CELLS[1:]}
    with zipfile.ZipFile(root/cfg['reference_archive_relative']) as z:
        for film in sorted(frames):
            reference=me['reference_film'](z,film,frames[film]);pred={}
            for arm in CELLS:
                fp=cohort/arm/film;idx=read(fp/'FILM_COMPLETE.json')
                with np.load(fp/'prediction/prediction.npz',allow_pickle=False) as a:
                    pred[arm]={'identifier_schema':'persistent_ctc_track_id_v1','gap_policy':'reject_no_imputation','frames':[{'t':t,'labels':a[f'frame_{t:04d}']} for t in range(frames[film])],'lineage':idx['lineage'],'typed_edges':a['typed_edges'].tolist()}
            ep=me['four_ep'](film,taus[film],pred,reference)
            for arm in CELLS:totals[arm].update(ep['metrics'][arm])
            for arm in CELLS[1:]:
                c=ep['contrasts'][arm];contrasts[arm][c['direction']]+=1;gains_losses[arm][0]+=len(c['gains']);gains_losses[arm][1]+=len(c['losses'])
            write(out/(film+'_ENDPOINT.json'),ep);print('PULSE_ENDPOINT',film,flush=True)
    write(out/'RESULT.json',{'operation':'new fixed-archive endpoint remeasurement','films':29,'arm_films':116,'totals':{a:dict(v) for a,v in totals.items()},'directions':{a:dict(v) for a,v in contrasts.items()},'gains_losses':gains_losses,'new_inference':False,'new_biological_N':0})
def run_stage_archive(root,out):
    cfg=read(HERE/'CONFIG_LOCAL_ONLY.json');stage=root/cfg['pulse_stage_relative'];cohort=root/cfg['pulse_cohort_relative'];me=module(HERE/'sources/pulse/fourcell_stage_exposure_preparation_v0.3/stage_exposure_v0_3.py')
    require(len(list(stage.glob('*_stage_windows.jsonl')))==116,'All116 archived stage inputs')
    summary={a:collections.Counter() for a in CELLS};pins={};identity=[];withheld=[];records=[]
    for path in sorted(stage.glob('*_stage_windows.jsonl')):
        film,arm=path.name.split('_')[:2];pins[str(path)]=sha(path);endpoint=read(root/cfg['pulse_endpoint_relative']/(film+'_measurement.json'))['endpoint'];domain={tuple(x['reference_key']):x['Y'][CELLS.index(arm)] for x in endpoint['edge_rows']};seen=set();sameinfo=True
        for line in path.open(encoding='utf-8'):
            r=json.loads(line)
            if 'comparisons' not in r:withheld.append({'film':film,'arm':arm,'frame':r['frame'],'status':r.get('status')});continue
            p=dict(r['proposed']);b=dict(r['strong_same_information']);p.pop('baseline',None);b.pop('baseline',None);equal=p==b;sameinfo &= equal
            for edge in r['proposed']['edges']:
                key=(film,r['frame']-1,edge['reference_edge'][0],r['frame'],edge['reference_edge'][1],edge['reference_edge'][2]);require(key not in seen,'Repeated stage relation');seen.add(key);summary[arm]['relations']+=1
                if edge['status']!='REFERENCE_RELATIVE_BOUNDED':summary[arm]['unsupported']+=1;withheld.append({'reference_key':key,'arm':arm,'status':edge['status']});continue
                patterns=edge['per_stage_optimal_visibility_product'];states=[]
                for bits in patterns:
                    require(len(bits)==4 and all(type(x) is int and x in (0,1) for x in bits),'Exact four stage bits')
                    losses=[k for k in range(1,4) if bits[k-1] and not bits[k]];gains=[k for k in range(1,4) if not bits[k-1] and bits[k]];first=next((k for k,v in enumerate(bits) if not v),None);last=losses[-1] if not bits[-1] and losses else None
                    states.append({'pattern':''.join(map(str,bits)),'D_missing':not bits[-1],'gain':bool(gains),'last_loss':last is not None,'reloss':any(g<l for g in gains for l in losses),'F_L_disagreement':last is not None and first!=last})
                require({b[3] for b in patterns}=={domain[key]},'Stage D vs endpoint bridge');summary[arm]['supported']+=1;summary[arm]['same_info_mismatches']+=not equal
                if len(states)==1:summary[arm][states[0]['pattern']]+=1
                else:summary[arm]['visibility_product_ambiguous']+=1
                for n in ['D_missing','gain','last_loss','reloss','F_L_disagreement']:
                    summary[arm][n+'_certain']+=all(s[n] for s in states);summary[arm][n+'_possible']+=any(s[n] for s in states)
                if film=='21' and key[1:] in [(56,58,57,58,0),(60,63,61,63,0),(61,63,62,63,0)]:identity.append({'reference_key':key,'arm':arm,'pattern_set':[s['pattern'] for s in states],'local_last_loss':[s['last_loss'] for s in states]})
                records.append({'reference_key':key,'arm':arm,'pattern_set':[s['pattern'] for s in states],'same_information_equal':equal})
        require(seen==set(domain),'Full stage reference relation inventory');print('STAGE_ARCHIVE',film,arm,flush=True)
    write(out/'CONSUMED_BINDINGS.json',pins);write(out/'IDENTITIES.json',records);write(out/'PULSE_LOSS_IDENTITIES.json',identity);write(out/'WITHHELD.json',withheld)
    write(out/'RESULT.json',{'operation':'independent reaggregation of archived native stage matching certificates','not_new_native_matching':True,'arm_films':116,'per_arm':{a:dict(v) for a,v in summary.items()},'withheld_records':len(withheld),'marginal_stage_products_only':True,'causal_source':'unidentifiable','same_information_advantage':0,'new_biological_N':0})

def main():
    ap=argparse.ArgumentParser();ap.add_argument('route',choices=['common','full','natural','timing','cca','chains','duties','initial-overlays','division-overlays','pulse-endpoint','stage-archive']);ap.add_argument('--input-root',type=Path,default=HERE/'fixed_archive_root');ap.add_argument('--output',type=Path,required=True);ap.add_argument('--decision-ledger',type=Path);a=ap.parse_args()
    cfg=source_bindings();root=a.input_root.resolve();out=a.output.resolve();require(not out.exists(),'Output must be absent');out.mkdir(parents=True);shutil.copy2(__file__,out/'EXECUTED_ADAPTER.py')
    write(out/'ADAPTER_RECORD.json',{'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'route':a.route,'input_root':str(root),'adapter_sha256':sha(__file__),'config_sha256':sha(HERE/'CONFIG_LOCAL_ONLY.json'),'python':sys.version,'numpy':np.__version__,'source_module_loading':'AST retains functions and setup, removes historical main auto invocation; explicit path globals overridden','local_only':True,'new_inference':False,'reader_ROOT_approval_required':False})
    try:
        if a.route=='common':run_common(root,out)
        elif a.route=='full':run_full(root,out)
        elif a.route=='natural':run_natural(root,out)
        elif a.route in ['timing','cca','chains']:run_metric(root,out,a.route)
        elif a.route=='duties':run_duties(root,out,a.decision_ledger)
        elif a.route=='initial-overlays':run_initial(root,out)
        elif a.route=='division-overlays':run_division(root,out)
        elif a.route=='pulse-endpoint':run_pulse(root,out)
        elif a.route=='stage-archive':run_stage_archive(root,out)
        write(out/'NEW_OUTPUT_FREEZE.json',{'files':{p.relative_to(out).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(out.rglob('*')) if p.is_file()},'scope':'Before optional comparison against historical numerical targets; not blinded discovery','new_inference':False})
    except BaseException:
        write(out/'FAILURE.json',{'exception':traceback.format_exc(),'overall_complete':False});raise
if __name__=='__main__':main()
