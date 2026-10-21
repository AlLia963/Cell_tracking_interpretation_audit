"""Post-execution reporting only; no scenario, objective or solver edits.
Reads complete outcomes and supplied primary histories, then freezes artifacts.
"""
import collections, csv, gzip, json, math
import sensitivity as S

def main():
    root=S.ROOT;result=S.read(root/'RESULT.json');verification=S.read(root/'execution'/'VERIFICATION.json');resource=S.read(root/'execution'/'RESOURCE_MEASUREMENT.json')
    assert result['scenario_count']==30 and verification['status']=='PASS_COMPLETE_EXECUTED_EVIDENCE'
    manifest=S.read(root/'INPUT_CONSUMPTION_MANIFEST.json');primary={}
    for b in manifest['comparison_bindings']:
        rows=S.read(b['path']);primary[b['contract']]={'partition':S.partition(rows),'canonical_features':S.R.total_features(x['canonical_history'] for x in rows)}
    summaryrows=[];summary=[]
    for ss in result['scenarios']:
        scenario=ss['scenario'];sid=scenario['scenario_id'];branches=ss['branches']
        for branch,b in branches.items():
            if 'all31_scalar_bounds' not in b or b['all31_scalar_bounds'] is None:
                summaryrows.append({'scenario_id':sid,'branch':branch,'status':b['status']});continue
            summaryrows.append({'scenario_id':sid,'branch':branch,'status':b['status'],'amplitude':scenario['amplitude'],'kind':scenario['kind'],
              **{k:b[k] for k in ['reference_relations','partition_final_present','partition_persistent_absence','partition_observed_loss','partition_ambiguous','ambiguous_history','ambiguous_category','certain_final_missing','possible_final_missing','canonical_history_changed_from_primary','canonical_category_changed_from_primary','category_set_changed_from_primary','admissible_history_set_changed_from_primary','component_count','whole_graph_joint_assignments_represented','whole_frame_blocks','whole_frame_assignments','geometry_links_accepted','geometry_boundaries_rejected']},
              'canonical_final_missing':b['canonical_feature_totals']['final_missing'],'minimum_final_missing':b['all31_scalar_bounds']['final_missing']['minimum'],
              'maximum_final_missing':b['all31_scalar_bounds']['final_missing']['maximum'],'canonical_observed_loss':b['canonical_feature_totals']['final_missing_with_loss'],
              'minimum_observed_loss':b['all31_scalar_bounds']['final_missing_with_loss']['minimum'],'maximum_observed_loss':b['all31_scalar_bounds']['final_missing_with_loss']['maximum'],
              'canonical_persistent_absence':b['canonical_feature_totals']['persistent_absence'],'minimum_persistent_absence':b['all31_scalar_bounds']['persistent_absence']['minimum'],
              'maximum_persistent_absence':b['all31_scalar_bounds']['persistent_absence']['maximum'],'frame_cap':S.CAP,'component_cap':S.CAP,
              'component_raw_product_counts':json.dumps(b['component_raw_product_counts']),'component_feasible_counts':json.dumps(b['component_configurations']),
              'scenario_elapsed_seconds':ss['elapsed_seconds'],'original_matcher_repaired_frames':ss['original_matcher_repaired_frames']})
        p=branches['finite/unconstrained'];g=branches['finite/geometry_constrained'];n=branches['numerical/unconstrained']
        summary.append({'scenario_id':sid,'finite_primary':p,'finite_geometry_secondary':g,'numerical_secondary':n})
    fields=[]
    for r in summaryrows:
        for k in r:
            if k not in fields:fields.append(k)
    S.csvwrite(root/'ALL_SCENARIO_BRANCH_SUMMARY.csv',summaryrows,fields)
    S.csvwrite(root/'INPUT_SOURCE_HASH_TABLE.csv',[{'kind':'scientific_npz','path':x['absolute_path'],'sha256':x['sha256'],'bytes':x['bytes']} for x in manifest['scientific_inputs']]+
      [{'kind':'source_or_contract','path':x['path'],'sha256':x['sha256'],'bytes':x['bytes']} for x in manifest['source_bindings']]+
      [{'kind':'existing_primary_comparison','path':x['path'],'sha256':x['sha256'],'bytes':None} for x in manifest['comparison_bindings']],['kind','path','sha256','bytes'])
    with gzip.open(root/'FRAME_CANDIDATE_MARGIN_AND_FAMILY_PROFILE.csv.gz','rt',encoding='utf-8',newline='') as f:fr=list(csv.DictReader(f))
    byscenario={};profiles=[]
    for sid in [x['scenario_id'] for x in S.read(root/'SCENARIOS.json')]:
        rows=[x for x in fr if x['scenario_id']==sid]
        margins=[float(x['minimum_abs_gate_margin_um']) for x in rows if x['minimum_abs_gate_margin_um']]
        row={'scenario_id':sid,'frame_count':len(rows),'eligible_pairs':sum(int(x['eligible_pairs']) for x in rows),
          'max_eligible_candidates_per_reference':max(int(x['max_candidate_count']) for x in rows),
          'minimum_absolute_gate_boundary_margin_um':min(margins) if margins else None,
          'maximum_screened_whole_frame_combinations':max(int(x['screened_combinations']) for x in rows),
          'maximum_finite_whole_frame_maps':max(int(x['finite_whole_maps']) for x in rows),
          'maximum_numerical_whole_frame_maps':max(int(x['numerical_whole_maps']) for x in rows),
          'frame_cap':S.CAP};profiles.append(row);byscenario[sid]=row
    S.csvwrite(root/'SCENARIO_GEOMETRY_PROFILE.csv',profiles,list(profiles[0]))
    del fr
    primaryrows=[r for r in summaryrows if r['branch']=='finite/unconstrained']
    repairs=sum(ss['original_matcher_repaired_frames'] for ss in result['scenarios'])
    measured={'elapsed_seconds':resource['elapsed_seconds'],'sampled_peak_process_RSS_bytes':resource['sampled_peak_process_RSS_bytes'],
      'Windows_peak_working_set_bytes':resource['Windows_process_peak_working_set_bytes'],'verification_elapsed_seconds':verification['elapsed_seconds']}
    audit={'UTC':S.now(),'status':'COMPLETE_LOCAL_BOUNDED_SENSITIVITY_VERIFIED','completed_scenarios':30,'completed_film_scenario_pairs':240,
      'completed_branch_scenario_pairs':len(summaryrows),'frame_certificates':verification['frame_certificates_checked'],
      'primary_comparison':primary,'original_matcher_exact_failures_and_repairs':repairs,
      'withheld_branches':sum(r['status'].startswith('WITHHELD') for r in summaryrows),'actual_branch_failures':result['failures'],
      'geometry_profiles':profiles,'measured_resources':measured,'all_scenarios':summary,
      'interpretation':'Post-review source-coordinate-grid-relative bounded reference sensitivity. Supplied finite primary retained. No calibration/error distribution, biological truth, accuracy advantage, CI, new N or continuous-domain worst-case guarantee; prediction-only and joint-registration perturbations not tested.',
      'reporting_source_preoutcome_frozen':False,'reporting_source_role':'Post-execution formatting and table summaries only. All outcome-computing sources and scenario definitions were frozen before outcomes.'}
    S.write(root/'REPORT.json',audit)
    lines=['# 固定数据 correspondence geometry sensitivity 实际报告','',
      f'30/30 个预定场景全部执行，240/240 个 film-scenario pair，{len(summaryrows)}/90 个 branch-scenario pair。7 个 stages，固定 7 um inclusive gate，每场景 5,751 个原 reference relations；共核验 {verification["frame_certificates_checked"]:,} 个 exact residual/max-cardinality frame certificates。原 gate7 primary 结果保留，不重新计算 zero perturbation 或 6/8 gate。','',
      f'协议冻结 SHA256：{S.sha(root/"PROTOCOL_FREEZE.json")}。冻结时扰动后科学结果数为 0；100 个 synthetic 穷举 controls 与故意负循环 control 先于冻结完成。新运算的原 canonical matcher exact objective 失败并修复次数：{repairs}；withheld branch={audit["withheld_branches"]}；实际 branch failure={len(result["failures"])}。若为 0，只是这些具体场景没有触发，不能推广为普遍保证。','',
      'NPZ 明确是 frame,z,y,x，空间单位 um。完整科学契约记载曾用 (1.625,0.40625,0.40625) 进行一次 conversion；消费的原 coordinate 入口只加载已经转换的 NPZ，没有原始 NPZ 生产转换脚本。这里 amplitude 的 voxel-step 字样仅表示这些 source-coordinate grid-relative scales，没有独立物理 voxel 标定、localization error 或 registration-error 分布依据。坐标不做第二次转换。','',
      'finite unconstrained 是 primary；有限 family 目标为最大 eligible cardinality 与最小“已计算 float64 距离的精确有理总和”，不是 exact real Euclidean objective。numerical fsum/64-epsilon admission 独立报告。geometry equality 是 secondary declared constraint sensitivity：complete identity domain 和全部 candidate full coordinate tuples 相同才接受 link。全体共享 reference endpoint、whole-frame map correlation 和 reference relation incidence 都纳入 joint components。完整 product enumeration、31 scalar 单独 witness 与 fixed complement 存在各 branch 输出，不能将单条 edge extrema 当成 joint bounds，独立极值向量也不保证同时达到。','',
      '这是审稿后设计的 bounded sensitivity scenarios，不是 preregistered、blind 或实测噪声。所有预测坐标、ID 和 edge 保持固定，仅 reference node 偏移并跨七个 stages 共用。所有 null/adverse case 保留；这些 sampled scenarios 不建立连续扰动域最坏界、probability calibration、CI、biology truth、accuracy/utility 优势或新 N。prediction-only 与 joint-registration 均未测。','',
      f'原 finite/unconstrained canonical missing/observed-loss/persistent={primary["finite/unconstrained"]["canonical_features"]["final_missing"]}/{primary["finite/unconstrained"]["canonical_features"]["final_missing_with_loss"]}/{primary["finite/unconstrained"]["canonical_features"]["persistent_absence"]}；对应某个 admissible canonical representative，不是原始 biological correspondence 验证。','',
      '以下为全部 30 个 primary finite unconstrained 场景，missing / observed-loss / persistent 以 canonical 值与完整 joint family scalar bounds 并列；ΔH/ΔC 是与原同 branch primary 的 canonical history/category 身份变化数。ambiguity 是 attribution category partition 的 ambiguous 数，history ambiguity 另见完整表。','',
      '| 场景 | missing canonical [joint min,max] | observed loss canonical [min,max] | persistent canonical [min,max] | ambiguous category | ΔH / ΔC | joint maps | geometry links accept/reject |',
      '|---|---:|---:|---:|---:|---:|---:|---:|']
    for row in primaryrows:
        p=row
        lines.append(f'| {p["scenario_id"]} | {p["canonical_final_missing"]} [{p["minimum_final_missing"]},{p["maximum_final_missing"]}] | {p["canonical_observed_loss"]} [{p["minimum_observed_loss"]},{p["maximum_observed_loss"]}] | {p["canonical_persistent_absence"]} [{p["minimum_persistent_absence"]},{p["maximum_persistent_absence"]}] | {p["ambiguous_category"]} | {p["canonical_history_changed_from_primary"]} / {p["canonical_category_changed_from_primary"]} | {p["whole_graph_joint_assignments_represented"]} | {p["geometry_links_accepted"]}/{p["geometry_boundaries_rejected"]} |')
    lo=min(r['canonical_final_missing'] for r in primaryrows);hi=max(r['canonical_final_missing'] for r in primaryrows)
    dlo=min(r['canonical_history_changed_from_primary'] for r in primaryrows);dhi=max(r['canonical_history_changed_from_primary'] for r in primaryrows)
    lines.extend(['',f'仅在这 30 个 sampled scenarios 内，primary canonical final_missing 范围为 {lo}–{hi}，canonical history 身份变化数为 {dlo}–{dhi}。这些是场景间描述性汇总；不能称为连续误差域最坏界。','',
      f'实际新计算耗时 {resource["elapsed_seconds"]:.3f} 秒；该 Python 进程每 0.02 秒 RSS 采样峰值 {resource["sampled_peak_process_RSS_bytes"]:,} bytes，Windows peak working set={resource["Windows_process_peak_working_set_bytes"]:,} bytes。独立完整证据核验另耗时 {verification["elapsed_seconds"]:.3f} 秒。时长包括本次输入加载、计算、gzip serialization 与表格写出；不包含 shell、协议准备或此前 route。精确内存采样见 execution/MEMORY_SAMPLES.csv.gz，不能当成全机器峰值。','',
      '全8片和三 branch 的完整 partition（present/observed loss/persistent/ambiguous）、missing certain/possible、全部 component counts/caps 见 SCENARIO_FILM_PARTITIONS.csv 与 ALL_SCENARIO_BRANCH_SUMMARY.csv。ALL31_SCALAR_BOUNDS_BY_SCENARIO_FILM.csv 包含全部 30×3×9×31 个独立 scalar bounds（9=8片+全cohort）。','',
      'ALL_IDENTITY_CHANGES_VS_PRIMARY.csv.gz 保存每个 scenario、branch、film、reference_a/reference_b 的完整 5,751 身份：原/新 canonical histories、admissible history sets、category sets 及变化 flags，包含所有未变化 identities。FRAME_CANDIDATE_MARGIN_AND_FAMILY_PROFILE.csv.gz 保留所有 frames 的候选数量、gate margins、whole-frame screened/finite/numerical map counts；每-film 完整证书还保留每 reference candidate counts、nearest distances/slack 以及全部 forced pair/null exact gaps。SCENARIO_GEOMETRY_PROFILE.csv 汇总 candidate-size 与最小 gate-boundary margin，均是 geometry diagnostics，不是定位误差估计。','',
      'outcomes/<scenario>/<film>.json.gz 包含固定输入 hash reference、实际 offsets、reference coordinate identity hash、原/证实 canonical maps、失败原始输出与完整 frame certificate。各 branch 的 WHOLE_FRAME_FAMILIES、JOINT_INPUT、COMPLETE_MAPPING_CONFIGURATION_WITNESSES 和 ALL5751_HISTORY_SETS 为完整 gzip 证据；geometry acceptance/rejection 包含完整两侧 domain/coordinate 与实际理由。frame/component cap 都为 1,048,576，超限只 withhold。','',
      'INPUT_CONSUMPTION_MANIFEST.json 与 INPUT_SOURCE_HASH_TABLE.csv 记录唯一 64 NPZ 一次消费 hash、源码/契约和既有 primary 对照文件 hash；执行/验证没有循环 rehash 未变原 NPZ。原 packet、旧版本、桌面与只读材料不修改；不读取 reviewer、作者旧审稿或 AE，不上传或模型推理。不改文章，不自行宣称 Major 已关闭。','',
      '下一步可将本报告作为独立 sensitivity evidence 交由作者评估 claim 边界；若要研究 prediction-only、joint-registration 或概率校准误差，必须另定协议与实测依据，不能从本结果外推。',''])
    with (root/'REPORT.md').open('x',encoding='utf-8',newline='\n') as f:f.write('\n'.join(lines))
    files=[p for p in sorted(root.rglob('*')) if p.is_file() and p.name!='OUTPUT_FREEZE.json']
    S.write(root/'OUTPUT_FREEZE.json',{'UTC':S.now(),'status':'COMPLETE_RESULTS_REPORT_TABLES_SOURCES_EXECUTION_FROZEN',
      'files':{p.relative_to(root).as_posix():{'sha256':S.sha(p),'bytes':p.stat().st_size} for p in files},
      'total_new_artifact_bytes':sum(p.stat().st_size for p in files),'scientific_raw_rehashed':False,
      'original_packet_modified':False,'original_scientific_outcome_sources_postfreeze_modified':False,
      'protocol_freeze_sha256':S.sha(root/'PROTOCOL_FREEZE.json'),'verification_status':verification['status']})
    print(json.dumps({'status':audit['status'],'output_freeze_sha256':S.sha(root/'OUTPUT_FREEZE.json'),
      'primary_canonical_missing_range':[lo,hi],'primary_canonical_history_changes_range':[dlo,dhi],
      'original_exact_failures_repaired':repairs,'bytes':sum(p.stat().st_size for p in files),**measured}))

if __name__=='__main__':main()
