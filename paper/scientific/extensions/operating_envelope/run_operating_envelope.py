import argparse, copy, hashlib, itertools, json, math, sys, time
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
LOCAL=HERE.parent/'natural/sources/local'
sys.path.insert(0,str(LOCAL))
import workflow as old
from stage_accounting import Graph
from factor_frames import factor_frame_blocks, extend_history_witness

def emit(p,x):
    with Path(p).open('x',encoding='utf-8') as h: json.dump(x,h,ensure_ascii=False,indent=2);h.write('\n')
def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def generate(n,k,v):
    rid=[t*n+j+1 for t in range(3) for j in range(n)]
    rc=[[t,0,0,30*j] for t in range(3) for j in range(n)]
    re=[(rid[t*n+j],rid[(t+1)*n+j]) for t in (0,1) for j in range(n)]
    ref=Graph(np.array(rid,dtype=np.int64),np.array(rc,dtype=float),np.array(re,dtype=np.int64),'pixel')
    pi,pc=[],[]; lookup={}
    for t in range(3):
        for j in range(n):
            values=[]
            for offset in ([-1,1] if t==1 and j<k else [0]):
                q=10000+len(pi);pi.append(q);pc.append([t,0,offset,30*j]);values.append(q)
            lookup[t,j]=values
    pe=[(lookup[t,j][0],lookup[t+1,j][0]) for t in (0,1) for j in range(n)]
    state=Graph(np.array(pi,dtype=np.int64),np.array(pc,dtype=float),np.array(pe,dtype=np.int64),'pixel')
    return ref,[copy.deepcopy(state) for _ in range(v)]
def independent_history(nodes,stages,maps,adj):
    a,b,c=nodes;r=[];ex=[]
    for s in stages:
        pa,pb,pc=[maps[s].get(x) for x in (a,b,c)]
        out,inc=adj[s]
        rr=pa is not None and pb is not None and pc is not None and pb in out.get(pa,set()) and pc in out.get(pb,set())
        cc=rr and out.get(pa,set())=={pb} and out.get(pb,set())=={pc} and inc.get(pb,set())=={pa} and inc.get(pc,set())=={pb}
        r.append(str(int(rr)));ex.append(str(int(cc)))
    return ''.join(r),''.join(ex)
def main(output):
    output.mkdir(parents=True,exist_ok=False);start=time.perf_counter()
    inputs=output/'constructed_inputs';inputs.mkdir();manifest=[]
    # Complete declared input cohort is written and hashed before any query.
    for n,k,v in itertools.product((32,64,128),(2,4,8),(2,3,5)):
        name=f'n{n}_k{k}_v{v}';ref,states=generate(n,k,v);d=inputs/name;d.mkdir()
        files=[]
        for label,g in [('reference',ref)]+[(f'V{i}',s) for i,s in enumerate(states)]:
            p=d/(label+'.npz');np.savez_compressed(p,ids=g.ids,coords=g.coords,edges=g.edges,unit=np.array(g.unit));files.append({'label':label,'path':str(p.relative_to(output)),'sha256':digest(p)})
        manifest.append({'name':name,'objects_per_frame':n,'ambiguous_middle_frame_objects':k,'ordered_views':v,'files':files})
    emit(output/'INPUT_COHORT_FROZEN_BEFORE_QUERY.json',{'cases':manifest,'protocol_sha256':digest(HERE/'PROTOCOL_BEFORE_EXECUTION.md'),'caps':{'frame':65536,'component':1024,'query':1024}})
    rows=[];witnesses=[];compared=0;replays=0;new_complete=0
    for case in manifest:
        ref=old.load_npz(output/case['files'][0]['path']);states=[old.load_npz(output/f['path']) for f in case['files'][1:]];stages=[f'V{i}' for i in range(len(states))]
        tt=time.perf_counter();bases={};blocks=[];certs=[];fail=[]
        for s,state in zip(stages,states):
            base=old.match(state,ref,2);bases[s]=base
            for frame in (0,1,2):
                cert,b,_,failure=old.frame_family(ref,state,base,2,frame,65536);certs.append(dict(cert,stage=s))
                if failure: fail.append(failure)
                if b is not None: blocks.append(dict(b,stage=s,id=len(blocks)))
        construction=time.perf_counter()-tt
        if fail: raise AssertionError('Declared under-cap frame construction failed')
        tt=time.perf_counter();split,proofs=factor_frame_blocks(blocks);factor_seconds=time.perf_counter()-tt
        adj={s:old.adjacency(g) for s,g in zip(stages,states)};queries,_=old.census(case['name'],ref)
        links,rejected=old.derive_links(blocks,bases,states,stages)
        if len(queries)!=case['objects_per_frame']: raise AssertionError('Unexpected census')
        for convention in ('per_view_product','unchanged_geometry_equality'):
            linkset=links if convention=='unchanged_geometry_equality' else []
            timings={};route={};assemblies={}
            for name,bs in [('whole_frame',blocks),('certified_projection',split)]:
                tt=time.perf_counter();cs,owner,cf=old.components(bs,linkset,bases,1024)
                results=[old.project_query(q,stages,bases,bs,cs,owner,adj,convention,1024,cf) for q in queries]
                timings[name]=time.perf_counter()-tt;route[name]=results;assemblies[name]=(cs,owner,cf)
            for previous,current in zip(route['whole_frame'],route['certified_projection']):
                if current['status']!='COMPLETE': raise AssertionError('Certified local route unexpectedly withheld')
                if previous['status']=='COMPLETE':
                    for key in ('pair_recovery','structural_consistency','joint_history_pairs'):
                        if key=='joint_history_pairs':equal=previous[key]==current[key]
                        else:equal=all(previous[key][k]==current[key][k] for k in ('histories','categories','per_view_possibilities'))
                        if not equal: raise AssertionError('Completed same-information reports disagree')
                    compared+=1
                else: new_complete+=1
                cs=assemblies['certified_projection'][0]
                for key,idx in [('pair_recovery',0),('structural_consistency',1)]:
                    for history,witness in current[key]['history_witnesses'].items():
                        maps,wi=extend_history_witness(witness,split,cs,blocks,stages,bases)
                        rr,ee=independent_history(current['nodes'],stages,maps,adj)
                        if (rr,ee)[idx]!=history:raise AssertionError('Independent witness readout differs')
                        witnesses.append({'case':case['name'],'convention':convention,'query_id':current['query_id'],'readout':key,'history':history,'whole_frame_family_indices':wi});replays+=1
            row={'case':case['name'],'objects_per_frame':case['objects_per_frame'],'ambiguity_groups':case['ambiguous_middle_frame_objects'],'views':len(states),'convention':convention,'raw_frame_family_sizes':[len(b['assignments']) for b in blocks],'factor_sizes':[len(b['assignments']) for b in split],'shared_frame_construction_seconds':construction,'additional_factor_certificate_seconds':factor_seconds,'query_assembly_seconds':timings,'old_complete':sum(x['status']=='COMPLETE' for x in route['whole_frame']),'old_withheld':sum(x['status']!='COMPLETE' for x in route['whole_frame']),'new_complete':len(queries),'new_ambiguous_histories':sum(len(x['pair_recovery']['histories'])>1 for x in route['certified_projection']),'max_new_relevant_combinations':max(x['relevant_combinations'] for x in route['certified_projection']),'old_component_failures':assemblies['whole_frame'][2]}
            rows.append(row)
            d=output/case['name'];d.mkdir(exist_ok=True);emit(d/(convention+'.json'),{'old':route['whole_frame'],'new':route['certified_projection'],'original_blocks':blocks,'split_blocks':split,'factor_proofs':proofs,'split_components':assemblies['certified_projection'][0]})
        emit(output/case['name']/'FRAME_CERTIFICATES.json',certs)
        print(json.dumps({'case':case['name'],'construction_seconds':round(construction,4),'completed':len(rows)}),flush=True)
    # Input-family constraints must never be silently discarded.
    negative=[]
    for name,refs,assignments in [('shared_candidates',[1,2],[{'1':11,'2':12},{'1':12,'2':11}]),('parity',[1,2,3],[dict(zip(('1','2','3'),[10+b[0],20+b[1],30+b[2]])) for b in itertools.product((0,1),repeat=3) if sum(b)%2==0])]:
        fs,proof=factor_frame_blocks([{'stage':'V0','frame':1,'references':refs,'assignments':assignments}])
        if len(fs)!=1 or len(fs[0]['assignments'])!=len(assignments):raise AssertionError('Nonfactorable family was falsely split')
        negative.append({'name':name,'proofs':proof,'merged_assignments':fs[0]['assignments']})
    # The last case has an actually ambiguous focal path under per-view product.
    cs,owner,cf=old.components(split,[],bases,1024)
    capped=old.project_query(queries[0],stages,bases,split,cs,owner,adj,'per_view_product',1,cf)
    if capped['status']!='WITHHELD_QUERY_CAP' or capped['pair_recovery'] is not None:raise AssertionError('Query cap returned truncated history')
    emit(output/'NEGATIVE_CONTROLS.json',{'nonfactorable':negative,'query_cap_1':capped})
    emit(output/'REPORT_TABLE.json',rows);emit(output/'HISTORY_WITNESS_MEMBERSHIP_AND_REPLAY.json',witnesses)
    emit(output/'RUN_COMPLETE.json',{'status':'ACTUAL_RAW_27_CASES_54_COMPARISONS_ALL_WITNESSES_REPLAYED','cases':27,'comparison_rows':len(rows),'old_complete_report_comparisons_equal':compared,'additional_completed_reports_under_fixed_caps':new_complete,'new_completed_reports':sum(r['new_complete'] for r in rows),'history_endpoint_witness_replays':replays,'old_complete_rows':sum(r['old_withheld']==0 for r in rows),'new_complete_rows':sum(r['new_complete']>0 for r in rows),'elapsed_wall_seconds':time.perf_counter()-start,'not_new_biological_N':True,'no_speed_advantage_claim':True,'shared_construction_not_credited_twice':True,'source_pins':[{'path':str(p),'sha256':digest(p)} for p in (Path(__file__),HERE/'factor_frames.py',LOCAL/'workflow.py',LOCAL/'scientific_backend/reconstruct.py',LOCAL/'local_graph_core.py',LOCAL/'scientific_backend/sources/executed/stage_accounting.py')]})
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    try:main(a.output)
    except Exception as e:
        if a.output.is_dir():emit(a.output/'FAILED.json',{'type':type(e).__name__,'error':str(e)})
        raise
