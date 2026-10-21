"""Inspect NPZ schema and source bindings, test exact solver, freeze protocol.
No perturbed scientific outcome is calculated here.
"""
import itertools, json, sys
from pathlib import Path
import numpy as np
import sensitivity as S

def controls():
    rng=np.random.Generator(np.random.PCG64(997041));checks=[]
    for i in range(100):
        nr=1+i%4;npred=1+(i//4)%4;allowed=rng.random((nr,npred))>.3
        costs=rng.integers(0,10,(nr,npred));ci={(int(r),int(c)):int(costs[r,c]) for r,c in zip(*np.nonzero(allowed))}
        m,steps=S.exact_solve(nr,npred,allowed,ci)
        candidates=[]
        for choice in itertools.product(*([None]+list(map(int,np.flatnonzero(allowed[r]))) for r in range(nr))):
            vals=[x for x in choice if x is not None]
            if len(vals)!=len(set(vals)):continue
            candidates.append((len(vals),sum(ci[r,c] for r,c in enumerate(choice) if c is not None)))
        k=max(x[0] for x in candidates);cost=min(x[1] for x in candidates if x[0]==k)
        assert (len(m),sum(ci[r,c] for r,c in m.items()))==(k,cost)
        a,b,arcs=S.R.residual(nr,npred,allowed,ci,m)
        assert b not in S.R.reachable(b+1,arcs,a)
        potentials,rounds=S.R.potential(b+1,arcs)
        assert all(c+potentials[u]-potentials[v]>=0 for u,v,c in arcs)
        checks.append({'case':i,'nr':nr,'npred':npred,'allowed':allowed.tolist(),'integer_costs':costs.tolist(),
          'exact_pairs':sorted([list(x) for x in m.items()]),'maximum_cardinality':k,'minimum_exact_integer_cost':cost,
          'exhaustive_partial_injective_maps':len(candidates),'dual_rounds':rounds})
    allowed=np.ones((2,2),dtype=bool);ci={(0,0):0,(0,1):1,(1,0):1,(1,1):0};wrong={0:1,1:0}
    a,b,arcs=S.R.residual(2,2,allowed,ci,wrong);cycle=S.negative_cycle(b+1,arcs);assert cycle is not None
    fixed,steps=S.exact_solve(2,2,allowed,ci);assert sum(ci[x] for x in fixed.items())==0
    return {'status':'PASS','synthetic_bruteforce_cases':100,'scientific_perturbed_outcomes_computed':0,
      'objective':'maximum eligible cardinality, then exact integer costs','cases':checks,
      'deliberately_wrong_cost_optimum_negative_cycle_control':{'wrong_pairs':[[0,1],[1,0]],'cycle':cycle,'repair_pairs':sorted([list(x) for x in fixed.items()]),'augmentations':steps}}

def main():
    root=S.ROOT
    S.write(root/'execution'/'PREOUTCOME_SOLVER_CONTROLS.json',controls())
    films=sorted(p.name for p in S.INPUT.iterdir() if p.is_dir() and (p/'reference.npz').exists());assert len(films)==8
    declared=S.read(S.FAMILY/'SCIENTIFIC_INPUT_AND_SOURCE_MANIFEST.json')
    oldhash={x['archive_relative_path']:x['sha256'] for x in declared['files'] if x.get('role')=='scientific_input_local_only'}
    inputs=[];total=0
    for film in films:
        for name in ['reference.npz']+[f'stage_{k}.npz' for k in range(7)]:
            p=S.INPUT/film/name;h=S.sha(p);rel=f'inputs_LOCAL_ONLY/coordinate_all8/{film}/{name}';assert h==oldhash[rel]
            with np.load(p,allow_pickle=False) as data:
                assert set(data.files)=={'ids','coords','edges','unit'}
                schema={k:{'dtype':str(data[k].dtype),'shape':list(data[k].shape)} for k in data.files}
                assert str(data['unit'].item())=='um'
            graph=S.load_npz(p)
            if name=='reference.npz':total+=len(graph.edges)
            inputs.append({'film':film,'relative_path':rel,'absolute_path':str(p),'sha256':h,'bytes':p.stat().st_size,
              'schema':schema,'nodes':len(graph.ids),'relations':len(graph.edges),'frame_count':len(np.unique(graph.coords[:,0])),'unit':'um'})
    assert len(inputs)==64 and total==5751
    sourcepaths=[S.FAMILY/'reconstruct.py',S.FAMILY/'sources'/'executed'/'stage_accounting.py',
      S.PACKET/'documentation'/'FAMILY_SCIENTIFIC_ROUTE_AND_CONTRACTS.md',
      S.PACKET/'analysis_code'/'six_chain_source_extracts'/'coordinate_all8'/'analyze_one.py',
      S.PACKET/'analysis_code'/'six_chain_source_extracts'/'coordinate_all8'/'reproduce_all.py',
      S.PACKET/'analysis_code'/'six_chain_source_extracts'/'common_carrier96'/'source_relative_score.py']
    sourcebindings=[{'path':str(p),'sha256':S.sha(p),'bytes':p.stat().st_size,'role':'source_or_contract_read_not_additional_scientific_data'} for p in sourcepaths]
    baselines=[]
    for contract in ['finite/unconstrained','finite/geometry_constrained','numerical/unconstrained']:
        p=S.FAMILY/'actual_run_v0.1'/'gate_07'/contract/'ALL5751_HISTORY_SETS.json'
        assert len(S.read(p))==5751
        baselines.append({'path':str(p),'sha256':S.sha(p),'contract':contract,'role':'existing_primary_comparison_only; no zero perturbation recomputation'})
    S.write(root/'INPUT_CONSUMPTION_MANIFEST.json',{'UTC':S.now(),'films':films,'scientific_inputs':inputs,'source_bindings':sourcebindings,
      'comparison_bindings':baselines,'total_reference_relations':total,'npz_count':64,'scientific_raw_hash_passes':1,
      'coordinate_order_verified_from_source':'frame,z,y,x','archive_unit':'um','second_scale_conversion_applied':False,
      'conversion_source_provenance':'Full family contract explicitly reports one existing conversion with z/y/x factors 1.625/.40625/.40625; supplied coordinate route analysis scripts load already-converted NPZ. common_carrier96 score has same factors, but does not prove original NPZ voxel calibration. Original raw conversion producer not present in the consumed family route.',
      'scale_interpretation':'source-coordinate grid-relative sensitivity only; no independently verified physical voxel calibration, localization uncertainty or measured registration-error distribution'})
    scenarios=[]
    for a in [.01,.1,.5]:
        label=str(a).replace('.','p')
        for axis,j in zip('zyx',range(3)):
            for sign,word in [(1,'plus'),(-1,'minus')]:
                scenarios.append({'scenario_id':f'a{label}_rigid_{word}_{axis}','kind':'rigid_reference_translation','amplitude':a,'axis':axis,'axis_index':j,'sign':sign,'seed':None,'maximum_axis_offset_um':a*S.SCALE[j]})
        for seed in [1701,1702,1703,1704]:
            scenarios.append({'scenario_id':f'a{label}_jitter_seed{seed}','kind':'reference_node_jitter','amplitude':a,'axis':None,'axis_index':None,'sign':None,'seed':seed,'axis_offset_bounds_um':(a*S.SCALE).tolist()})
    assert len(scenarios)==30
    S.write(root/'SCENARIOS.json',scenarios)
    S.csvwrite(root/'SCENARIOS.csv',[{'scenario_id':x['scenario_id'],'kind':x['kind'],'amplitude':x['amplitude'],'axis':x['axis'],'sign':x['sign'],'seed':x['seed']} for x in scenarios],['scenario_id','kind','amplitude','axis','sign','seed'])
    protocol={'version':'geometry_sensitivity_v0.1','created_UTC':S.now(),'scope':'LOCAL ONLY; fixed stored data correspondence geometry sensitivity',
      'designed_after_review':True,'preregistered':False,'blinded':False,'measured_noise':False,'films':films,'reference_relations':5751,'stage_count':7,
      'gate_um':7.,'eligibility':'inclusive np.hypot.reduce calculated float64 spatial distance <= 7',
      'coordinate_order':['frame','z','y','x'],'NPZ_spatial_unit':'um','source_scale_zyx_um':[1.625,.40625,.40625],
      'scale_basis':'contract-declared once-conversion factors, source-coordinate grid sensitivity only; no independently verified physical voxel calibration',
      'fixed_inputs':['all prediction coordinates','all IDs','all directed edges','frame indices','all processing stages','reference relation identities'],
      'reference_offsets_shared_across_stages':True,'offset_realization':'float64 addition to already converted NPZ; no second conversion',
      'scenario_count':30,'scenario_table':'SCENARIOS.json','jitter_rng':'NumPy Generator(PCG64(seed)); restart each scenario; sequential films lexicographic, node IDs numeric; rng.uniform(-a,a, size=(node_count,3))*source_scale_zyx',
      'finite_primary':'maximum eligible cardinality, minimum exact sum of already calculated float64 distances using as_integer_ratio; whole partial one-to-one maps, including achievable nulls',
      'numerical_secondary':'distinct math.fsum distance gap <=64eps*max(1,abs(sum),abs(base)); screen=66eps*max(1,K*7)',
      'frame_cap':S.CAP,'component_cap':S.CAP,'cap_action':'withhold global branch, retain incomplete evidence, never truncate alternatives',
      'canonical_check_and_repair':'retain original map and negative exact residual cycle or augmenting path failure; exact integer shortest augmenting paths repair; independently dual/cover certify repaired frame; objective unchanged',
      'repair_solver_preoutcome_validation':'100 exhaustive small partial-injective-map controls plus deliberately adverse exact negative-cycle control; no scientific perturbed outcomes',
      'components':'whole-frame correlated map blocks; union shared variable reference IDs directly and reference relation incidence; equality links; exact full configuration products',
      'source_adaptation':'source/reconstruct.py copies packet source except touching=nodes | incidence-neighbours, ensuring shared variable objects also union if isolated from reference edges; packet unchanged',
      'geometry_equality_secondary':'same reference coordinates across stages by design; only complete candidate identity domain and full candidate frame,z,y,x tuples equal accept adjacent link; report actual accepted/rejected boundaries',
      'comparison':'read existing gate7 finite unconstrained and geometry constrained, numerical unconstrained full history outputs only; no baseline/gate6/gate8 rerun',
      'planned_outputs':['all30 and all8 per scenario partitions','complete 5751 identity history/category comparisons for each branch','31 joint attainable scalar bounds global and by film','exact residual and maximality certificates','whole-frame enumerations','complete component configurations and scalar witness indices','candidate sizes and gate margins','actual elapsed time and process memory samples','all failure/adverse/null cases retained'],
      'limits':['bounded sampled scenarios, no continuous-domain worst-case guarantee','no probability-calibrated noise or confidence intervals','no correspondence biological-truth claim','no accuracy/utility advantage claim','no prediction-only perturbation','no joint-registration perturbation','no new biological N','same host fixed stored cohort','no upload or model inference','no article edits']}
    S.write(root/'PROTOCOL.json',protocol)
    protocolmd='''# 固定数据 correspondence geometry sensitivity 协议\n\n本设计在审稿后制定，冻结先于任何扰动后的科学结果计算。它不是预注册、blind、实测噪声或定位误差分布。全 30 个预定场景均保留，包括 null/adverse。\n\n唯一科学数据为 packet/scientific_routes/family 中 64 个 NPZ：8 个 reference 和 56 个 processing-stage snapshot，共 5,751 个固定 reference relations。全部 prediction coordinates、IDs、edges、frame indices 保持固定。reference 每个 node 一次一致偏移，并跨七个 stages 共用同一个 reference。坐标顺序由 stage_accounting.py 明确为 frame,z,y,x，NPZ unit=um；不再次缩放既有坐标。\n\n完整科学契约记载原转换因子 z/y/x=(1.625,0.40625,0.40625)。已消费的转换相关源码只加载既有 NPZ，common-carrier score 使用同因子，但它不证成原始 NPZ voxel 标定。因此 amplitude 的 voxel-step 字样仅指这组 source-coordinate grid-relative scales；没有独立物理标定、localization-error 或 registration-error 分布依据。仍执行本地 sensitivity，不虚构物理误差。\n\n每个 a={0.01,0.1,0.5}，reference rigid translation 为 ±z/±y/±x 共六个；另有四个 reference jitter seeds={1701,1702,1703,1704}。PCG64 每个场景重启，film lexicographic、node numeric ID 次序；独立每 axis uniform[-a,a] 乘对应 source scale。精确场景表为 SCENARIOS.json/CSV。\n\n唯一 gate 为 inclusive 7 um。primary finite objective 先最大化 frame eligible one-to-one cardinality，再最小化已经由 np.hypot.reduce 计算的 float64 距离的精确二进制有理数总和；它不是 exact real Euclidean objective。所有 pair/null 同 cardinality forced gaps 用 exact residual costs 筛选，完整 whole-map 组合经过 injectivity/cardinality/objective admission。numerical 64-eps fsum 容差是单独 secondary family。\n\n原 canonical matcher 每 frame 必须经过最大基数 cover 和 exact residual dual 检查。实际失败保留原 map、traceback、负 cycle/augmenting-path evidence；预先核验的 exact integer successive shortest augmenting path solver 在新输出修复，然后重新证书核验。同一个 objective 不静默改变。\n\n所有 whole-frame blocks 经 shared variable reference objects、reference-edge incidence、accepted geometry links 连接成 components；完整枚举 component map configurations 后算 joint visibility，fixed complement 加上 components 构成精确 product。31 项 scalar extrema 各有可组合配置 witness，不能当作同时可实现的向量，也不能用 per-edge extrema 代替 joint attainable bounds。源码仅将 component neighbour set 加入 nodes 本身，保证没有 incident edge 的 shared objects 也连接；原 packet 不变。\n\nframe/component cap 均为 1,048,576；超限 withhold，不截断。finite unconstrained 是 primary；finite geometry equality 是 secondary constraint sensitivity，仅 complete candidate domain 和所有 candidate full coordinate tuples 都相同时接收相邻 link，实际接受与拒绝必须报告。numerical unconstrained 独立报告。\n\n对照读取原 gate7 三个 branch 的完整 primary histories，不重新跑 zero-perturbation、6/8 gate。输出全30场景、全8片 partition（present/observed loss/persistent/ambiguous）、missing 的 certain/possible counts、全部身份历史与类别变化、全31 scalar bounds、完整证书/可实现 configurations、候选数量/geometry margins、实际耗时和进程内存。报告 prediction-only 与 joint-registration 未测；不声称 biological correspondence 正确、新 N、accuracy/utility advantage、概率校准 noise/CI 或连续扰动域最坏界。禁止读取 reviewer、作者旧审稿、AE；不上传、不模型推理、不修改文章或自称 Major 已关闭。\n'''
    with (root/'PROTOCOL.md').open('x',encoding='utf-8',newline='\n') as f:f.write(protocolmd)
    frozenfiles=[p for p in sorted(root.rglob('*')) if p.is_file()]
    S.write(root/'PROTOCOL_FREEZE.json',{'UTC':S.now(),'status':'FROZEN_BEFORE_ANY_PERTURBED_SCIENTIFIC_OUTCOME',
      'scientific_perturbed_outcome_count':0,'sha256':{p.relative_to(root).as_posix():S.sha(p) for p in frozenfiles},
      'scientific_raw_hash_passes':1,'scenario_count':30,'source_and_protocol_frozen':True})
    print(json.dumps({'status':'PROTOCOL_FROZEN','scenario_count':30,'npz_count':64,'relations':5751,'freeze_sha256':S.sha(root/'PROTOCOL_FREEZE.json')}))

if __name__=='__main__':main()
