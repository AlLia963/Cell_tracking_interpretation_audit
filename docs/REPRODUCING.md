# Reproducing the paper: complete walkthrough and result index

This is the single execution guide for **Auditing interpretations of fixed cell
tracking outputs across processing changes**. Start at the repository README,
then follow Steps 1–9 here. The paper result index below identifies each main
result, all 13 figures, the 17 supplementary tables and all 59 Source Data tables.
It gives the command group and the newly written output to inspect.

## Start here

| Order | Task | Inputs | New outputs | Next |
|---|---|---|---|---|
| 1 | Install and set locations | Source checkout, Python, downloaded ZIP | Environment and empty run root | Step 2 |
| 2 | Reconstruct and check the real shared-path task | Two saved NPZs | Worked report, primitive verification, witness, actual refusal | Step 3 |
| 3 | Execute the retained study | Full-study companion | All 30 route outputs, with dependencies supplied automatically | Step 4 |
| 4 | Reconstruct expanded graphs/pairs and focused comparisons | Expanded corpus | Fresh families, pair records, 208+8 comparisons and 2,160 witness checks | Step 5 |
| 5 | Module/head experiments and cached-estimator replay | Three GEFF pairs; four-fold captures; 16 estimator inputs | 72-condition CSV, head scores/weights and estimator checks | Step 6 |
| 6 | Rebuild the exact figures | Retained numeric/pixel packets | Seven main and six supplementary figures | Step 7 |
| 7 | Re-extract original/alternative image cases | 16 relative case configurations | Per-case measurements, pixel arrays and previews | Step 8 |
| 8 | Interface tests, identity accounting and resource measurements | Worked NPZs; fresh study outputs | API probes, 123/64/30 checks, new timing records | Step 9 |
| 9 | Check completion and compare results | New outputs above | Reader's checked result set | Paper result index |

The paper starts its principal audit from retained tracking outputs. Original
data and checkpoint attribution are in [SOURCES.csv](../data/study_inputs/SOURCES.csv).
The archive supplies the saved predictions and intermediates for these tasks.
Three historical score rows remain unreproduced and explicitly identified in
Source Data Table 58. Full-cohort native certificate readouts and four-window
native reconstruction are distinct rows below. These records are preserved.

## Installation and locations

**Step 1.** The recorded environment is Windows with Python 3.13.12. The commands
below use PowerShell and the pinned requirements. Select the appropriate installed
Python before creating the environments. Git is needed to clone the source.
Keep this PowerShell session open so the location variables remain available.

Clone once, or open the root of an existing checkout:

```powershell
git clone https://github.com/AlLia963/Cell_tracking_interpretation_audit.git
if ($LASTEXITCODE -ne 0) { throw 'Clone failed; do not continue in an unrelated directory.' }
Set-Location -LiteralPath './Cell_tracking_interpretation_audit'
```

From the cloned repository root:

```powershell
$repoRoot = (Get-Location).Path
$studyInputs = 'D:/inputs'
$runRoot = 'D:/audit_outputs'
if (Test-Path -LiteralPath $runRoot) { throw 'Choose a new run directory.' }
New-Item -ItemType Directory -Path $runRoot -ErrorAction Stop | Out-Null
python -m venv .venv
$py = Join-Path $repoRoot '.venv/Scripts/python.exe'
& $py -m pip install -r requirements-verified.txt -r paper/requirements-paper.txt -r paper/figures/requirements.txt .
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $py -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
& $py paper/expanded/review_example.py --output "$runRoot/example"
if ($LASTEXITCODE -ne 0) { throw 'Constructed example failed.' }
```

Expected: 24 tests pass and the example prints `EXPANDED_EXAMPLE_PASS`.
Download `study_reproduction_inputs.zip` from the
[study input release](https://github.com/AlLia963/Cell_tracking_interpretation_audit/releases/tag/study-inputs-2026-10-23).
Set the actual downloaded ZIP path below. Verify and extract it once to the new
short path assigned to `$studyInputs`, keeping all six top-level folders:

```powershell
$studyZip = Join-Path $env:USERPROFILE 'Downloads/study_reproduction_inputs.zip'
$archiveInfo = Get-Content -LiteralPath 'data/study_inputs/ARCHIVE.json' -Raw -Encoding UTF8 | ConvertFrom-Json
if ((Get-FileHash -LiteralPath $studyZip -Algorithm SHA256).Hash.ToLowerInvariant() -ne $archiveInfo.sha256) {
    throw 'Study ZIP checksum mismatch.'
}
if (Test-Path -LiteralPath $studyInputs) { throw 'Choose a new extraction directory.' }
Expand-Archive -LiteralPath $studyZip -DestinationPath $studyInputs -ErrorAction Stop
```

If the archive is already verified and extracted, skip this extraction block
and set `$studyInputs` to that existing root. The [input guide](../data/study_inputs/README.md)
explains its six directories and source attribution; the steps below identify
the exact subdirectory used by every command. Continue here to Step 2.

`INPUTS` and `RUNS` in the result tables mean `$studyInputs` and `$runRoot`.
Every command runs from `$repoRoot`. Each task writes to its own absent output
path. Input files remain in INPUTS. The historical-training environment in Step 5
is separate from `.venv`. The graph/pair runs in Step 4 are the full runs; `--limit`
would produce only a partial run and is omitted here.

## Actual worked path

**Step 2 — main Section 3.1 and Figure 1.** Read two saved coordinate graphs,
construct all three frame families, decide the proposed path recovery, independently
check primitive optimality/coverage, replay a witness, and exercise query-cap refusal.

```powershell
$workedInputs = "$studyInputs/controlled_companion_LOCAL_ONLY/03_最小D47/LOCAL_ONLY_INPUTS"
$workedExpected = "$studyInputs/controlled_companion_LOCAL_ONLY/04_既有补充证据_v1.2/packaged_cli_execution/EXPLICIT_PROBE/NEW_ROOT_TASK/REPORT.json"
& $py paper/review_d47.py --input-root $workedInputs --expected-report $workedExpected --output "$runRoot/worked_path"
if ($LASTEXITCODE -ne 0) { throw 'Worked audit failed; retain its logs.' }
```

Inspect `RUNS/worked_path/SUMMARY.json`: `WORKED_AUDIT_REVIEW_PASS`, family
sizes `[1,2,1]`, joint attainable values `[0]`, marginal relaxation `[0,1]`,
proposal 1 rejected and proposal 0 witnessed. The directory also contains the
actual `task/REPORT.json`, `PRIMITIVE_VERIFICATION.json`, `WITNESS_REPLAY.json`
and `query_cap_one/REPORT.json` with `WITHHELD_QUERY_CAP`. Continue to Step 3.

## Retained full study routes

**Step 3 — original 3D, controls, policies, bacterial relations/events/chains and epithelial analysis.**
Configuration verifies the full companion, then the runtime assembler copies the
indexed calculation code and binds the declared inputs. The suite supplies its
dependency outputs in order, including new allocation decisions and new policy
graphs. No manual movement of intermediate files is needed.

```powershell
$studyConfig = "$runRoot/study_config.json"
& $py -B -X utf8 paper/configure_bundle.py --bundle "$studyInputs/full_study_inputs_LOCAL_ONLY" --runtime "$repoRoot/paper/_local/review_runtime" --config $studyConfig --runs "$runRoot/full_study"
if ($LASTEXITCODE -ne 0) { throw 'Input configuration failed.' }
& $py -B -X utf8 paper/prepare_local.py --config $studyConfig
if ($LASTEXITCODE -ne 0) { throw 'Runtime preparation failed.' }
& $py -B -X utf8 paper/run_suite.py --config $studyConfig --output "$runRoot/full_study"
if ($LASTEXITCODE -ne 0) { throw 'A study route failed; inspect SUITE_PROGRESS.json and that route log.' }
```

The runtime path and config must be absent at first use. They are local bindings;
do not recursively delete through runtime directory links. To list the routes,
run `& $py paper/run.py list`. To execute an individual route, use
`paper/run.py ROUTE --config PREPARED_CONFIG --output NEW_PATH`; its upstream
dependencies must already exist. For the complete paper, use the suite above.

Inspect `RUNS/full_study/SUITE_COMPLETE.json` for 30 zero-return routes. Each route
has `COMPLETE.json`, calculation logs and its measurement files. Completion records
establish execution; compare the numerical fields against the expected readouts
and Source Data entries listed below. Some backend files are under
`measurement/measurement/`; the output tables below give their actual locations.

The natural family classification is 71/135/3; the historical canonical point
classification 72/137 remains separately recorded. Bacterial relation/event/chain
denominators are respectively 123/64/30. The native-stage archive aggregates all
116 retained certificates; `native16` reconstructs four selected windows in four
arms. The full native capture set needed by the unexecuted all-window extension
is not supplied. Continue to Step 4.

## Expanded archive and focused comparisons

**Step 4 — Section 3.2, Section 3.4, Table 3 and expanded cohort evidence.**
First reconstruct complete matching/frame evidence for all admitted saved graphs,
then calculate all within-movie pairs. The second command uses the first command's
new output. These are full computations over the retained saved graph corpus.

```powershell
$corpus = "$studyInputs/expanded_evidence/04_统一重分析"
& $py paper/expanded/historical_producers/13_run_complete_graph_audit.py --corpus $corpus --output "$runRoot/expanded_graphs"
if ($LASTEXITCODE -ne 0) { throw 'Expanded graph audit failed.' }
& $py paper/expanded/historical_producers/15_all_within_movie_contrasts.py --corpus $corpus --audit-root "$runRoot/expanded_graphs" --output "$runRoot/expanded_pairs"
if ($LASTEXITCODE -ne 0) { throw 'Expanded pair calculation failed.' }
& $py paper/expanded/historical_producers/run_linked_focused.py --corpus $corpus --audit-root "$runRoot/expanded_graphs" --contrasts "$studyInputs/expanded_evidence/integration/LINKED_FOCUSED_CONTRASTS.json" --motion "$studyInputs/expanded_evidence/integration/MOTION_INTERVENTION_RESULTS.json" --output "$runRoot/focused_recalculated"
if ($LASTEXITCODE -ne 0) { throw 'Focused comparison calculation failed.' }
& $py paper/expanded/review_linked_records.py --corpus $corpus --audit-root "$runRoot/expanded_graphs" --records "$runRoot/focused_recalculated" --output "$runRoot/focused_witness_checks.json"
if ($LASTEXITCODE -ne 0) { throw 'Focused witness check failed.' }
& $py paper/expanded/summarize_focused_inputs.py --comparisons data/catalog/focused_comparisons.csv --corpus $corpus --output "$runRoot/focused_input_summary.json"
if ($LASTEXITCODE -ne 0) { throw 'Focused input summary failed.' }
```

Inspect `expanded_graphs/GRAPH_AUDIT_PROGRESS.json` and
`GRAPH_AUDIT_SUMMARIES.jsonl`, `expanded_pairs/SUMMARY.json`,
`focused_recalculated/LINKED_FOCUSED_CONTRASTS.json` and
`focused_witness_checks.json` under RUNS. Expected coverage: 2,738 graphs over
199 movies, 175,488 distinct frame geometries, 124,237 within-movie pairs,
208 focused comparisons plus eight intervention comparisons, and 2,160 witnesses.
The focused input summary retains each design's distinct reference denominator.

Table 3 checks: threshold 0.60→0.78 canonical net −18, independent net
[−117,83], linked net [−83,49]; threshold 0.78→0.90 net −28 and linked
[−121,69]; threshold 0.60→0.90 net −46 and linked [−140,54]; two policies
disabled net +5; structural refactor net 0; line-fitting change net +22 and
linked [12,34]. The eight-movie intervention has 55 gains, 29 losses and linked
net [24,27]. Each interval is a separately attainable scalar range.

For a shorter check that reuses the retained full families, set `--audit-root`
to `$corpus` in the focused commands and use fresh output paths. This is an
explicit alternative to the full family reconstruction, not the full Step 4 run.
Continue to Step 5.

## Historical module and head experiments

**Step 5 — complete module conditions, negative head result and cached estimator.**
Use a separate environment for the recorded CPU training/GEFF dependencies.

```powershell
python -m venv .venv-historical
$histPy = Join-Path $repoRoot '.venv-historical/Scripts/python.exe'
& $histPy -m pip install -r paper/requirements-historical.txt
if ($LASTEXITCODE -ne 0) { throw 'Historical environment installation failed.' }
& $histPy paper/expanded/reproduce_module_conditions.py --input-root "$studyInputs/historical_module_inputs" --output "$runRoot/module_conditions"
if ($LASTEXITCODE -ne 0) { throw 'Module calculation differs or failed.' }
& $histPy paper/summarize_module_context.py --input "$runRoot/module_conditions/v75_ablation.csv" --output "$runRoot/module_context_recalculated.json"
if ($LASTEXITCODE -ne 0) { throw 'Module summary failed.' }
& $histPy paper/expanded/reproduce_head_validation.py --input-root "$studyInputs/expanded_evidence/05_补证与核验/四折负结果_历史证据" --expected "$studyInputs/expanded_evidence/05_补证与核验/四折负结果_历史证据/head_v2_gate.json" --threads 16 --output "$runRoot/head_validation"
if ($LASTEXITCODE -ne 0) { throw 'Head calculation differs or failed.' }
```

Module outputs: `module_conditions/v75_ablation.csv`,
`v75_ablation_summary.csv`, `REPRODUCTION_CHECK.json` and
`module_context_recalculated.json`. Expect 72 rows = three movies × 24 conditions,
19/66 nonbaseline rows with equal TP/FP but different node/edge counts; pooled
raw TP/FP/FN 930/15/14 and full 933/18/11. Original timings are retained separately.

Head outputs: `head_validation/head_v2_gate.json`, `folds/`,
`v1284_head_v2.pt` and `REPRODUCTION_CHECK.json`. Expect zero held-out wins for
both revised head and ensemble. The recorded numerical replay uses 16 CPU threads;
the environment and thread count are in `paper/expanded/HISTORICAL_RUNTIME.json`.

The cached-coordinate estimator has 16 actual saved movie inputs. Its portable
entry imports the retained estimator from that input folder's `sources/` directory.
Run all supplied movies as follows:

```powershell
$estimatorRoot = "$studyInputs/expanded_evidence/05_补证与核验/16片局部重放_历史证据"
$estimatorMovies = @(Get-ChildItem -LiteralPath "$estimatorRoot/inputs" -Directory)
if ($estimatorMovies.Count -ne 16) { throw 'Expected 16 retained estimator movies.' }
foreach ($movie in $estimatorMovies) {
    & $py paper/expanded/historical_producers/replay_local_smoother.py --input-root $estimatorRoot --film $movie.Name --output "$runRoot/estimator_checks/$($movie.Name).json"
    if ($LASTEXITCODE -ne 0) { throw "Estimator replay failed: $($movie.Name)" }
}
```

Each output checks IDs, coordinates and edges against its retained target.
Historical before/after relation counts are also part of Step 3's
`historical-negative` output and the Source Data Table 58 evidence. Continue to Step 6.

## Figures

**Step 6 — exact seven main and six supplementary figures.** The base builder
reconstructs retained designs from numeric/pixel inputs. The integrated builder
then produces the current manuscript set, preserving the selected real cases.

```powershell
& $py paper/figures/retained_build_figures.py --input-root "$studyInputs/figure_inputs_LOCAL_ONLY/retained_inputs" --output "$runRoot/base_figures"
if ($LASTEXITCODE -ne 0) { throw 'Base figure construction failed.' }
& $py paper/figures/build_integrated.py --input-root "$studyInputs/figure_inputs_LOCAL_ONLY" --retained-figures "$runRoot/base_figures" --output "$runRoot/paper_figures"
if ($LASTEXITCODE -ne 0) { throw 'Manuscript figure construction failed.' }
```

Inspect `RUNS/paper_figures/FIGURE_MANIFEST.json` and the 13 independent
PNG/PDF/SVG sets listed in the figure index below. These programs draw from
retained plot packets; Steps 2–5 and the result index identify the separate
calculations supporting their numbers. Each real-image case has source and
transformation records. Historical `Figure4_actual_type_change` is the base
builder's name for the current Figure 6, not the current 3D Figure 4.
Continue to Step 7.

## Alternative real-image cases

**Step 7 — Source Data Table 59.** Re-extract the four original and 12 alternative
cases using their supplied relative configurations. This produces new measurements,
pixel arrays and previews. The exact figure layout is provided by Step 6.

```powershell
$caseConfigs = @(Get-ChildItem -LiteralPath "$studyInputs/case_reuse_LOCAL_ONLY/configs" -Filter '*.json' -File)
if ($caseConfigs.Count -ne 16) { throw 'Expected four original and 12 alternative case configurations.' }
foreach ($caseConfig in $caseConfigs) {
    & $py paper/figures/export_case.py --config $caseConfig.FullName --output "$runRoot/cases/$($caseConfig.BaseName)"
    if ($LASTEXITCODE -ne 0) { throw "Case failed: $($caseConfig.Name)" }
}
```

Inspect each `RUNS/cases/CASE/RESULT.json`, `PIXELS.npz` and previews. Selection
is recorded in `INPUTS/case_reuse_LOCAL_ONLY/SELECTION_BEFORE_EXTRACTION.json`,
sources in `INPUT_PROVENANCE.json`, and retained case comparison in
`RELOCATION_CHECK.json`. Format details are optional reference in
[FIGURE_CASES.md](FIGURE_CASES.md). Return here and continue to Step 8.

## Cost and interface checks

**Step 8 — validation responsibility, separate identities and operating costs.**
First run the actual interface/omission probes on the same input as Step 2:

```powershell
& $py paper/probe_contracts.py --reference "$workedInputs/reference.npz" --prediction "$workedInputs/prediction.npz" --unit pixel --gate-um 7 --path 156000000073 157000000073 158000000073 --expected-report $workedExpected --output "$runRoot/interface_probes"
if ($LASTEXITCODE -ne 0) { throw 'Interface probe failed.' }
& $py paper/reaggregate_d44.py --relations "$runRoot/full_study/identity-crosswalk/measurement/ALL123_WRONG_TYPE_RELATION_EVENT_CROSSWALK.json" --events "$runRoot/full_study/identity-crosswalk/measurement/EVENT_UNITS.json" --chains "$runRoot/full_study/identity-crosswalk/measurement/ALL30_STRICT_CHAIN_INCOMING_EVENT_CROSSWALK.json" --output "$runRoot/relation_event_chain_check.json"
if ($LASTEXITCODE -ne 0) { throw 'Identity denominator check failed.' }
& $py paper/measure_d47_resources.py --task "$runRoot/worked_path/task" --output "$runRoot/worked_cost"
if ($LASTEXITCODE -ne 0) { throw 'Worked-task resource measurement failed.' }
& $py paper/measure_coupled_resources.py --inputs "$runRoot/full_study/operating-envelope/measurement" --output "$runRoot/coupled_cost"
if ($LASTEXITCODE -ne 0) { throw 'Coupled resource measurement failed.' }
```

Inspect `interface_probes/ACTUAL_INTERFACE_PROBES.json` and its actual query-cap
report, `relation_event_chain_check.json`, `worked_cost/SUMMARY.json` and
`coupled_cost/SUMMARY.json`. The resource commands use three fresh processes per
workload/route. The coupled measurement uses the fresh operating-envelope inputs
from Step 3 and checks scientific results before comparing to the frozen targets.
It measures all three workloads, both conventions and both routes. Memory
instrumentation in the coupled command is Windows-specific. Numerical/readout
checks are distinct from timings, which vary with the reader's machine.

## Completion checklist

**Step 9.** Check these before describing a complete run of the supplied workflow:

- Step 2 summary passes primitive construction/checking, witnessed zero and actual cap refusal.
- Step 3 has 30 zero-return routes, and their numerical/identity outputs match the result index below; retain each calculation log.
- Step 4 has the complete graph/pair counts and all 208+8 comparison identities; check each scalar against Table 3/Table 56 and all 2,160 endpoint witnesses.
- Step 5 retains all 72 conditions, 19/66 structural-count cases, every head fold and both zero-win outcomes; all 16 supplied estimator checks pass.
- Step 6 has seven main and six supplementary figure entries; inspect the images at reading size.
- Step 7 has 16 case result directories and their pixels/provenance.
- Step 8 completes actual API tests, keeps relation/event/chain denominators independent, and writes all workload records.

An old `validate_reconstruction.py`, `verify_completion.py` or export helper is
not the entry to this walkthrough: those helpers retain earlier author integration
layouts. The current steps name the explicit-root entry points and current outputs.

The complete default 30-route suite has an existing 14 October 2026 execution;
subsequent focused/module/head and portable-entry checks have their own execution
scope. The current full expanded producers were checked on real subsets after
path adaptation; this document does not present a new complete expanded run as
already executed. Source Data Table 58 retains the three unreproduced historical
score rows. Neither those historical rows nor a new full native rematch are
silently relabeled as freshly reproduced results.

To inspect one complete archived comparison entry, the input companion includes
a result-store reader. For example, restore the full original Table 44 records
outside the frozen input directory:

```powershell
& $py "$studyInputs/controlled_companion_LOCAL_ONLY/tools/result_store.py" extract --entry D44 --output "$runRoot/archived_table44"
if ($LASTEXITCODE -ne 0) { throw 'Archived result extraction failed.' }
```

`RUNS/archived_table44/D44/` then contains the original CSV/JSON identity lists.
Change D44 to another D01–D47 entry and use a new output directory as needed.
These are retained comparison records, separate from the fresh outputs above.

## Paper result index

The following lists connect the paper to the commands above. A paper table may
summarize multiple outputs; the complete identities remain in the named records.
Methods/definition/literature tables are documentary materials, not new experiments.

| Paper location | Work | Execute | Inspect under RUNS (unless stated otherwise) |
|---|---|---|---|
| Methods 2.1–2.2; Table 1 | Study materials, development units and experimental designs | data/catalog; Step 3; Steps 4–5 | `data/catalog/summary.json, notebooks.csv, score_records.csv, graphs.csv; full cohort records below` |
| Methods 2.3–2.5; Table 2; Results 3.1; Figure 1 | Shared-correspondence audit, exclusion, witness and same-information checks | Steps 2, 3 and 8 | `worked_path/task/REPORT.json; worked_path/PRIMITIVE_VERIFICATION.json; full_study/literal-baseline/measurement/COMPLETE_FAMILY_AND_SCIENTIFIC_COMPARISON.json; interface_probes/ACTUAL_INTERFACE_PROBES.json` |
| Results 3.2; Table 3; Figure 2; Figures S4–S5 | All focused saved-output contrasts and linked scalar ranges | Step 4 | `focused_recalculated/LINKED_FOCUSED_CONTRASTS.json; focused_witness_checks.json; focused_input_summary.json` |
| Results 3.3; Figure 3 | Eight-movie motion-component intervention readout | Step 4 | `motion_replacement_disabled comparison in focused_recalculated/LINKED_FOCUSED_CONTRASTS.json; each motion_linked/ witness record` |
| Results 3.3; Table 4 | All common-carrier and bacterial policy effects, including adverse/null cases | Step 3 | `full_study/common-score-generated/measurement/RESULT.json; full_study/bacterial-full/measurement/measurement/RESULT.json` |
| Results 3.3–3.4; Supplement S4/S10; Tables 57–58 | Module contexts, revised head/ensemble and historical negative results | Steps 3 and 5 | `module_conditions/v75_ablation.csv; module_context_recalculated.json; head_validation/head_v2_gate.json; full_study/historical-negative/measurement/RESULT.json` |
| Results 3.4; Figure 4; Tables 53–55 | Archive-wide correspondence sensitivity, strict paths, cancellation and selected 3D case | Steps 4, 6 and 7 | `expanded_graphs/GRAPH_AUDIT_SUMMARIES.jsonl; expanded_pairs/SUMMARY.json; cases/original_figure4/RESULT.json` |
| Results 3.5; Figure 5 | All-29 pulse outcomes versus selected local A–D evidence | Steps 3, 6 and 7 | `full_study/bacterial-pulse-endpoint/measurement/RESULT.json; full_study/bacterial-stage-archive/measurement/PULSE_LOSS_IDENTITIES.json; cases/original_figure5/RESULT.json` |
| Results 3.5; Figure 6; Supplement S5 | Raw/typed relations, event timing and chain consequences | Steps 3, 6–8 | `full_study/identity-crosswalk/measurement/ALL123_WRONG_TYPE_RELATION_EVENT_CROSSWALK.json; EVENT_UNITS.json; ALL30_STRICT_CHAIN_INCOMING_EVENT_CROSSWALK.json; relation_event_chain_check.json` |
| Results 3.6; Figure 7; Figures S1/S3/S6 | Epithelial stages, all eight exchanged identities and complete TP/FP series | Steps 3, 6 and 7 | `full_study/epithelial/measurement/reference_measurement/movie1_complete_result.json through movie4_complete_result.json; cases/original_figure7/RESULT.json` |
| Results 3.7; Table 5; Supplement S7 | Worked-task adoption and three coupled workloads | Step 8 | `worked_cost/SUMMARY.json; coupled_cost/SUMMARY.json; their process and phase records` |

## All 30 study routes and their outputs

All are run by Step 3, in the order below. Every output path here is relative to `RUNS/full_study/`. The listed files were matched against an existing complete 30-route execution; route dependencies come from the current runner.

| Order | Route | Work / readout | Key output | Source Data tables |
|---|---|---|---|---|
| 1 | `natural3d` | Eight films, all5751 relation histories, primary/linked31 scalar fields and5556 local queries | `natural3d/measurement/ALL31_FIELD_DEFINITIONS_BOUNDS.json`; `natural3d/measurement/ALL62_ENDPOINT_ADMISSIONS.json` | 3, 8, 40, 41, 42 |
| 2 | `natural-gates` | All eight films at gates6/7/8; calculated-distance families, distinct finite/numerical contracts | `natural-gates/measurement/gate_06/CANONICAL_HISTORIES.json`; `natural-gates/measurement/gate_07/CANONICAL_HISTORIES.json` | 4, 5, 6, 7 |
| 3 | `literal-baseline` | Exhaustive partial-injection baseline on5751 relations; requires natural_measurement_root | `literal-baseline/measurement/COMPLETE_FAMILY_AND_SCIENTIFIC_COMPARISON.json`; `literal-baseline/measurement/REFUSALS.json` | Supports the associated validation/cohort results |
| 4 | `historical-geometry` | All 30 fixed rigid/jitter scenarios, all eight films and three correspondence contracts; complete scientific reports. | `historical-geometry/measurement/ALL_SCENARIO_BRANCH_SUMMARY.csv`; `historical-geometry/measurement/ALL31_SCALAR_BOUNDS_BY_SCENARIO_FILM.csv` | 9 |
| 5 | `historical-stress` | Original 36 cases, exact-degenerate caps/refusals and fresh runtime/memory measurements. | `historical-stress/measurement/case_results.csv`; `historical-stress/measurement/all_frame_results.csv` | 10, 11 |
| 6 | `constructed` | Six 2/3/5-view coordinate inputs, complete families and local graph queries | `constructed/measurement/film_0000_census.json`; `constructed/measurement/film_0000_construction.json` | Supports the associated validation/cohort results |
| 7 | `typed-constructed` | Four typed binary cases under two conventions; full whole-map readout | `typed-constructed/complete_binary_ambiguous_per_view_product/RESULT.json`; `typed-constructed/complete_binary_ambiguous_same_map_identical_snapshots/RESULT.json` | 39 |
| 8 | `operating-envelope` | 27 moderate inputs,54 comparisons,4032 local reports and whole-map witnesses | `operating-envelope/measurement/REPORT_TABLE.json`; `operating-envelope/measurement/NEGATIVE_CONTROLS.json` | 43 |
| 9 | `allocation-replay` | Replay producer proposals, frozen image scores and exact allocation; independently rebuild all eight decision ledgers. | `allocation-replay/measurement/decision_ledger.json`; `allocation-replay/measurement/COMPARISON.json` | 18 |
| 10 | `bacterial-duties` | 734 source-duty controls; original allocation ledger supplied, image inference not repeated | `bacterial-duties/measurement/measurement/fixtures.json`; `bacterial-duties/measurement/measurement/report.json` | 16, 17 |
| 11 | `duty-boundary` | Execute all 13 intact/missing/stale/tampered authority boundary cases. | `duty-boundary/measurement/RESULT.json` | Supports the associated validation/cohort results |
| 12 | `bacterial-initial-overlays` | Generate and rematch290 actual-support overlays; final-observation collision classes | `bacterial-initial-overlays/measurement/work/native_noisy_validation_v0.3/case_records.json`; `bacterial-initial-overlays/measurement/final_observation_classes/RESULT.json` | 12, 13 |
| 13 | `bacterial-division-overlays` | Generate and rematch1144 overlays on104 retained predicted-division relations | `bacterial-division-overlays/measurement/measurement/CASE_RECORDS.json`; `bacterial-division-overlays/measurement/measurement/TARGET_ELIGIBILITY.json` | 14, 15 |
| 14 | `common-generate` | Re-execute all six policies on all 16 fixed B/E carriers before reading reference answers. | `common-generate/measurement/generated_run/PREDICTIONS_BEFORE_REFERENCE.json`; `common-generate/measurement/generated_run/RESULT.json` | 21 |
| 15 | `common-score-generated` | Score all 96 freshly generated outputs with the original sparse-reference FP definition. | `common-score-generated/measurement/RESULT.json` | 19, 20 |
| 16 | `bacterial-common` | 96 saved common-carrier graph measurements; does not regenerate B/E source policies | `bacterial-common/measurement/RESULT.json` | Supports the associated validation/cohort results |
| 17 | `common-family-census` | 96 common-carrier snapshots; complete frame families and63894 paths | `common-family-census/measurement/ALL96_FILM_ARM_CENSUS.json`; `common-family-census/measurement/ALL_FRAME_CERTIFICATES.json` | 45, 46 |
| 18 | `analyst-path` | Reconstruct three raw-coordinate frame families and decide an actual proposed path recovery | `analyst-path/measurement/REPORT.json`; `analyst-path/measurement/COMPLETE_FRAME_FAMILIES.json` | 47 |
| 19 | `bacterial-full` | Three full bacterial policies; rematch16020 saved label frames against reference | `bacterial-full/measurement/measurement/RESULT.json`; `bacterial-full/measurement/measurement/01_results.json` | 22 |
| 20 | `bacterial-natural` | All31093 baseline A-D raw and typed histories from actual supports | `bacterial-natural/measurement/measurement/RESULT.json`; `bacterial-natural/measurement/measurement/01_edge_records.jsonl` | 23, 24 |
| 21 | `bacterial-pulse-endpoint` | Remeasure116 fixed final predictions,29 four-arm contrasts including null/harmful | `bacterial-pulse-endpoint/measurement/RESULT.json`; `bacterial-pulse-endpoint/measurement/01_ENDPOINT.json` | 26 |
| 22 | `bacterial-stage-archive` | Reaggregate116 archived native stage certificates,124372 relation-arm identities; not fresh pixel rematching | `bacterial-stage-archive/measurement/RESULT.json`; `bacterial-stage-archive/measurement/IDENTITIES.json` | 27, 28 |
| 23 | `bacterial-chains` | 5167 track eligibility records and2391 complete birth-to-division chain queries | `bacterial-chains/measurement/measurement/RESULT.json`; `bacterial-chains/measurement/measurement/01_RECORDS.json` | 29, 30, 31 |
| 24 | `bacterial-timing` | 29movies x3policies x2timing tolerances; actual BC function and event identities | `bacterial-timing/measurement/measurement/RESULT.json`; `bacterial-timing/measurement/measurement/01_EVENTS.json` | 32, 34 |
| 25 | `bacterial-cca` | 87 CCA values from actual saved prediction/reference tracks | `bacterial-cca/measurement/measurement/RESULT.json`; `bacterial-cca/measurement/measurement/PER_MOVIE.csv` | 33 |
| 26 | `native16` | Four selected bacterial windows in all four arms; raw/typed support and D bridge, not full-cohort new rematching | `native16/measurement/RESULT.json` | Supports the associated validation/cohort results |
| 27 | `identity-crosswalk` | 123 wrong-type relations,64 linked events,30 chain incoming records and support pixels for current Figure 6 (historical FIGURE4 filenames); needs three completed measurement roots | `identity-crosswalk/measurement/ALL123_WRONG_TYPE_RELATION_EVENT_CROSSWALK.json`; `identity-crosswalk/measurement/EVENT_UNITS.json` | 44 |
| 28 | `epithelial` | Official pinned ZIP; reference-free E0-E3 image processing, then6427 relation/5963 path measurements | `epithelial/measurement/reference_measurement/movie1_complete_result.json`; `epithelial/measurement/reference_measurement/movie2_complete_result.json` | 35 |
| 29 | `projection` | 14 fixed G pulses, all140 actual arrays, next-call boxes and raw heads; no new model inference | `projection/measurement/RESULT.json`; `projection/measurement/COMPARISON.json` | 25 |
| 30 | `historical-negative` | 48 SVM control/intervention pairs and20 SDY arm-film recounts, negative/null results included; not retraining | `historical-negative/measurement/RESULT.json`; `historical-negative/measurement/COMPARISON.json` | Supports the associated validation/cohort results |

## Figure index

Step 6 generates every figure below in `RUNS/paper_figures/`, each as PNG, PDF and SVG. The last two columns identify the calculations and actual source evidence, separately from rendering.

| Figure | Filename stem | Calculation / evidence | Display content |
|---|---|---|---|
| Figure 1 | `Figure1_shared_correspondence` | Step 2; S7.8; Tables 47/50 | Complete reference/prediction/correspondence schematic from the actual worked task |
| Figure 2 | `Figure2_complete_40_movie_contrast` | Step 4; Table 55 | All 40 threshold 0.60→0.78 movie intervals |
| Figure 3 | `Figure3_component_intervention` | Step 4; Table 56 | All eight intervention gains/losses and linked endpoints |
| Figure 4 | `Figure4_actual_80_movie_exchange` | Steps 4/7; Tables 55/59 | Actual 3D pixels and before/after saved relations |
| Figure 5 | `Figure5_pulse_actual_support` | Steps 3/7; Tables 26–28/59 | Actual bacterial pulse masks and saved typed pairs |
| Figure 6 | `Figure6_support_and_relation_type` | Steps 3/7/8; Tables 44/59 | Previous-D anchor and current A–D support/type records |
| Figure 7 | `Figure7_epithelial_border_loss` | Steps 3/7; Tables 35/59 | Actual epithelial border case |
| Figure S1 | `FigureS1_all_eight_exchanged_identities` | Step 3; Table 35 | All eight exchanged epithelial identities |
| Figure S2 | `FigureS2_original_seven_stage_changes` | Step 3; Table 8 | All original seven-stage 3D changes |
| Figure S3 | `FigureS3_complete_epithelial_TP` | Step 3; Table 35 | All epithelial TP stage counts |
| Figure S4 | `FigureS4_threshold_078_090` | Step 4; Table 55 | All threshold 0.78→0.90 movie intervals |
| Figure S5 | `FigureS5_threshold_060_090` | Step 4; Table 55 | All threshold 0.60→0.90 movie intervals |
| Figure S6 | `FigureS6_complete_epithelial_FP` | Step 3; Table 35 | All epithelial FP stage counts |

## Supplementary table index

| Table | Content | Command or record |
|---|---|---|
| S1 | Domain notation | Definitions; Tables 1/38; Methods 2.1 and Supplement S1.1 |
| S2 | Capabilities and premises | Steps 2/8 plus the mathematical specification in Supplement S1.3–S1.5 |
| S3 | Failure and responsibility cases | Step 8 ACTUAL_INTERFACE_PROBES.json; Tables 49/52 |
| S4 | Seven-stage operation definitions | Documentary operation specification; Table 2; original processing sources |
| S5 | Alternative-gate families | Step 3 natural-gates; Table 6 |
| S6 | Controlled support/authority comparisons | Step 3 overlay, duty and boundary routes; Tables 12–17 |
| S7 | Common-carrier and policy outcomes | Step 3 common-score-generated, bacterial-full and historical-negative; Tables 19–28/58 |
| S8 | Division timing sensitivity | Step 3 bacterial-timing; Tables 32/34 |
| S9 | Full epithelial cohort | Step 3 epithelial; Table 35 |
| S10 | Inputs and reproduction routes | This walkthrough and data/study_inputs/SOURCES.csv; no separate experiment |
| S11 | Worked-task cost | Step 8 worked_cost/SUMMARY.json; Table 48 |
| S12 | Coupled workload measurements | Step 8 coupled_cost/SUMMARY.json; Table 51 |
| S13 | Actual returned report fields | Step 2 worked_path/task/REPORT.json; Tables 47/52 |
| S14 | Three pulse-loss prediction pairs | Step 3 bacterial-stage-archive and Step 7 original_figure5; Table 28 |
| S15 | Eight epithelial exchanged identities | Step 3 epithelial and Figure S1; Table 35 |
| S16 | Related-method functional positioning | Documentary literature comparison; Table 36; no performance experiment |
| S17 | Focused cohort denominators and counts | Step 4 focused_input_summary.json; Table 55 |

## Source Data index

These are the paper's 59 data entries, not 59 independent experiments. For Tables 1–47, the archived result catalog at `INPUTS/controlled_companion_LOCAL_ONLY/02_完整结果/RESULT_CATALOG.json` locates every complete original record. Its `direct_read_path` gives small readable records; `object_path` locates losslessly stored large records. The companion's `D_ENTRY_LOCATORS.json` additionally locates Tables 44 and 47–52. The list below gives the current calculation and newly written output, so readers do not have to infer it from the archived export filename.

| Table | Paper entry | Execute / type | Inspect |
|---|---|---|---|
| 1 | Notation and measurement axes | Definition record | `INPUTS/controlled_companion_LOCAL_ONLY/02_完整结果/直接阅读/D01/DOCUMENTARY.md` |
| 2 | Recorded seven-stage operations | Operation specification | `INPUTS/controlled_companion_LOCAL_ONLY/02_完整结果/直接阅读/D02/DOCUMENTARY.md` |
| 3 | Primary transition counts and separately attainable ranges | Step 3: natural3d | `RUNS/full_study/natural3d/measurement/ALL31_FIELD_DEFINITIONS_BOUNDS.json; RUNS/full_study/natural3d/measurement/ALL62_ENDPOINT_ADMISSIONS.json; complete per-movie/per-case records in the same route` |
| 4 | Canonical gate sensitivity | Step 3: natural-gates | `RUNS/full_study/natural-gates/measurement/gate_06/CANONICAL_HISTORIES.json; RUNS/full_study/natural-gates/measurement/gate_07/CANONICAL_HISTORIES.json; complete per-movie/per-case records in the same route` |
| 5 | Canonical reference-identity changes across gates | Step 3: natural-gates | `RUNS/full_study/natural-gates/measurement/gate_06/CANONICAL_HISTORIES.json; RUNS/full_study/natural-gates/measurement/gate_07/CANONICAL_HISTORIES.json; complete per-movie/per-case records in the same route` |
| 6 | Complete-family alternative-gate results | Step 3: natural-gates | `RUNS/full_study/natural-gates/measurement/gate_06/CANONICAL_HISTORIES.json; RUNS/full_study/natural-gates/measurement/gate_07/CANONICAL_HISTORIES.json; complete per-movie/per-case records in the same route` |
| 7 | All-film persistent-absence and observed-loss ranges | Step 3: natural-gates | `RUNS/full_study/natural-gates/measurement/gate_06/CANONICAL_HISTORIES.json; RUNS/full_study/natural-gates/measurement/gate_07/CANONICAL_HISTORIES.json; complete per-movie/per-case records in the same route` |
| 8 | All 31 primary scalar fields and unchanged-geometry comparison | Step 3: natural3d | `RUNS/full_study/natural3d/measurement/ALL31_FIELD_DEFINITIONS_BOUNDS.json; RUNS/full_study/natural3d/measurement/ALL62_ENDPOINT_ADMISSIONS.json; complete per-movie/per-case records in the same route` |
| 9 | All 30 primary sampled scenarios and secondary link acceptance | Step 3: historical-geometry | `RUNS/full_study/historical-geometry/measurement/ALL_SCENARIO_BRANCH_SUMMARY.csv; RUNS/full_study/historical-geometry/measurement/ALL31_SCALAR_BOUNDS_BY_SCENARIO_FILM.csv; complete per-movie/per-case records in the same route` |
| 10 | Constructed regimes and output coverage | Step 3: historical-stress | `RUNS/full_study/historical-stress/measurement/case_results.csv; RUNS/full_study/historical-stress/measurement/all_frame_results.csv; complete per-movie/per-case records in the same route` |
| 11 | Every degenerate size and separate enumeration limits | Step 3: historical-stress | `RUNS/full_study/historical-stress/measurement/case_results.csv; RUNS/full_study/historical-stress/measurement/all_frame_results.csv; complete per-movie/per-case records in the same route` |
| 12 | Initial-window support overlays | Step 3: bacterial-initial-overlays | `RUNS/full_study/bacterial-initial-overlays/measurement/work/native_noisy_validation_v0.3/case_records.json` |
| 13 | Final-observation collision classes | Step 3: bacterial-initial-overlays | `RUNS/full_study/bacterial-initial-overlays/measurement/final_observation_classes/RESULT.json; RUNS/full_study/bacterial-initial-overlays/measurement/final_observation_classes/known_last_loss_130.json; complete per-movie/per-case records in the same route` |
| 14 | Predicted-division-window control coverage | Step 3: bacterial-division-overlays | `RUNS/full_study/bacterial-division-overlays/measurement/measurement/CASE_RECORDS.json; RUNS/full_study/bacterial-division-overlays/measurement/measurement/TARGET_ELIGIBILITY.json` |
| 15 | All eleven division-window overlays | Step 3: bacterial-division-overlays | `RUNS/full_study/bacterial-division-overlays/measurement/measurement/CASE_RECORDS.json; RUNS/full_study/bacterial-division-overlays/measurement/measurement/TARGET_ELIGIBILITY.json` |
| 16 | Source-duty validation and withholding | Step 3: bacterial-duties | `RUNS/full_study/bacterial-duties/measurement/measurement/fixtures.json; RUNS/full_study/bacterial-duties/measurement/measurement/report.json; complete per-movie/per-case records in the same route` |
| 17 | Source-duty fixtures and missing evidence | Step 3: bacterial-duties | `RUNS/full_study/bacterial-duties/measurement/measurement/fixtures.json; RUNS/full_study/bacterial-duties/measurement/measurement/report.json; complete per-movie/per-case records in the same route` |
| 18 | Audited S3 allocation by film | Step 3: allocation-replay | `RUNS/full_study/allocation-replay/measurement/decision_ledger.json; RUNS/full_study/allocation-replay/measurement/COMPARISON.json` |
| 19 | All 96 common-carrier outputs | Step 3: common-score-generated | `RUNS/full_study/common-score-generated/measurement/RESULT.json` |
| 20 | Sparse scoring and ignored deletions by split/policy | Step 3: common-score-generated | `RUNS/full_study/common-score-generated/measurement/RESULT.json` |
| 21 | Executed carrier gates and actions | Step 3: common-generate | `RUNS/full_study/common-generate/measurement/generated_run/PREDICTIONS_BEFORE_REFERENCE.json; RUNS/full_study/common-generate/measurement/generated_run/RESULT.json; complete per-movie/per-case records in the same route` |
| 22 | Complete-policy trajectories and byte changes | Step 3: bacterial-full | `RUNS/full_study/bacterial-full/measurement/measurement/RESULT.json; RUNS/full_study/bacterial-full/measurement/measurement/01_results.json; complete per-movie/per-case records in the same route` |
| 23 | Natural coverage by relation type | Step 3: bacterial-natural | `RUNS/full_study/bacterial-natural/measurement/measurement/RESULT.json; RUNS/full_study/bacterial-natural/measurement/measurement/01_edge_records.jsonl; complete per-movie/per-case records in the same route` |
| 24 | Natural typed/raw processing-view visibility | Step 3: bacterial-natural | `RUNS/full_study/bacterial-natural/measurement/measurement/RESULT.json; RUNS/full_study/bacterial-natural/measurement/measurement/01_edge_records.jsonl; complete per-movie/per-case records in the same route` |
| 25 | Saved checkpoint, actual execution and equivalence boundaries | Step 3: projection | `RUNS/full_study/projection/measurement/RESULT.json; RUNS/full_study/projection/measurement/COMPARISON.json` |
| 26 | All-29 pulse schedule outcomes | Step 3: bacterial-pulse-endpoint | `RUNS/full_study/bacterial-pulse-endpoint/measurement/RESULT.json; RUNS/full_study/bacterial-pulse-endpoint/measurement/01_ENDPOINT.json; complete per-movie/per-case records in the same route` |
| 27 | All-arm local observations and bridge coverage | Step 3: bacterial-stage-archive | `RUNS/full_study/bacterial-stage-archive/measurement/RESULT.json; RUNS/full_study/bacterial-stage-archive/measurement/IDENTITIES.json; complete per-movie/per-case records in the same route` |
| 28 | Complete identities of all three pulse-induced final losses | Step 3: bacterial-stage-archive | `RUNS/full_study/bacterial-stage-archive/measurement/RESULT.json; RUNS/full_study/bacterial-stage-archive/measurement/IDENTITIES.json; complete per-movie/per-case records in the same route` |
| 29 | Focal-chain eligibility and overlapping exclusions | Step 3: bacterial-chains | `RUNS/full_study/bacterial-chains/measurement/measurement/RESULT.json; RUNS/full_study/bacterial-chains/measurement/measurement/01_RECORDS.json; complete per-movie/per-case records in the same route` |
| 30 | Focal-chain failures in every eligible track | Step 3: bacterial-chains | `RUNS/full_study/bacterial-chains/measurement/measurement/RESULT.json; RUNS/full_study/bacterial-chains/measurement/measurement/01_RECORDS.json; complete per-movie/per-case records in the same route` |
| 31 | Retrospective focal-chain span strata | Step 3: bacterial-chains | `RUNS/full_study/bacterial-chains/measurement/measurement/RESULT.json; RUNS/full_study/bacterial-chains/measurement/measurement/01_RECORDS.json; complete per-movie/per-case records in the same route` |
| 32 | Division timing sensitivity | Step 3: bacterial-timing | `RUNS/full_study/bacterial-timing/measurement/measurement/RESULT.json; RUNS/full_study/bacterial-timing/measurement/measurement/01_EVENTS.json; complete per-movie/per-case records in the same route` |
| 33 | Pinned biological-metric APIs | Step 3: bacterial-cca | `RUNS/full_study/bacterial-cca/measurement/measurement/RESULT.json; RUNS/full_study/bacterial-cca/measurement/measurement/PER_MOVIE.csv; complete per-movie/per-case records in the same route` |
| 34 | Exact/early/late acquisition indices | Step 3: bacterial-timing | `RUNS/full_study/bacterial-timing/measurement/measurement/RESULT.json; RUNS/full_study/bacterial-timing/measurement/measurement/01_EVENTS.json; complete per-movie/per-case records in the same route` |
| 35 | Complete epithelial cohort and saved-view counts | Step 3: epithelial | `RUNS/full_study/epithelial/measurement/reference_measurement/movie1_complete_result.json; RUNS/full_study/epithelial/measurement/reference_measurement/movie2_complete_result.json; complete per-movie/per-case records in the same route` |
| 36 | Functional relationship to supplied primary literature | Literature comparison | `INPUTS/controlled_companion_LOCAL_ONLY/02_完整结果/直接阅读/D36/DOCUMENTARY.md` |
| 37 | Earlier measurement reconstruction coverage | Historical coverage record | `INPUTS/controlled_companion_LOCAL_ONLY/02_完整结果/直接阅读/D37/DOCUMENTARY.md` |
| 38 | Domain-specific source labels and interpretation | Notation/source-label record | `INPUTS/controlled_companion_LOCAL_ONLY/02_完整结果/直接阅读/D38/DOCUMENTARY.md` |
| 39 | Complete shared-map typed-event reports for all four constructed cases under two conventions | Step 3: typed-constructed | `RUNS/full_study/typed-constructed/complete_binary_ambiguous_per_view_product/RESULT.json; RUNS/full_study/typed-constructed/complete_binary_ambiguous_same_map_identical_snapshots/RESULT.json; complete per-movie/per-case records in the same route` |
| 40 | Complete reference-context census before local-graph readout | Step 3: natural3d | `RUNS/full_study/natural3d/measurement/ALL31_FIELD_DEFINITIONS_BOUNDS.json; RUNS/full_study/natural3d/measurement/ALL62_ENDPOINT_ADMISSIONS.json; complete per-movie/per-case records in the same route` |
| 41 | Supported output specimen for the natural shared-middle path | Step 3: natural3d | `RUNS/full_study/natural3d/measurement/ALL31_FIELD_DEFINITIONS_BOUNDS.json; RUNS/full_study/natural3d/measurement/ALL62_ENDPOINT_ADMISSIONS.json; complete per-movie/per-case records in the same route` |
| 42 | Actual and constructed controls of selected-path scope | Step 3: natural3d | `RUNS/full_study/natural3d/measurement/ALL31_FIELD_DEFINITIONS_BOUNDS.json; RUNS/full_study/natural3d/measurement/ALL62_ENDPOINT_ADMISSIONS.json; complete per-movie/per-case records in the same route` |
| 43 | Complete local-query operating-envelope coverage | Step 3: operating-envelope | `RUNS/full_study/operating-envelope/measurement/REPORT_TABLE.json; RUNS/full_study/operating-envelope/measurement/NEGATIVE_CONTROLS.json; complete per-movie/per-case records in the same route` |
| 44 | Wrong-type relation/event crosswalk | Steps 3/8; complete identities and current separate denominators | `RUNS/full_study/identity-crosswalk/measurement/ALL123_WRONG_TYPE_RELATION_EVENT_CROSSWALK.json; EVENT_UNITS.json; ALL30_STRICT_CHAIN_INCOMING_EVENT_CROSSWALK.json; RUNS/relation_event_chain_check.json` |
| 45 | Complete common-carrier correspondence census | Step 3: common-family-census | `RUNS/full_study/common-family-census/measurement/ALL96_FILM_ARM_CENSUS.json; RUNS/full_study/common-family-census/measurement/ALL_FRAME_CERTIFICATES.json; complete per-movie/per-case records in the same route` |
| 46 | All ambiguous common-carrier path/arm identities | Step 3: common-family-census | `RUNS/full_study/common-family-census/measurement/ALL96_FILM_ARM_CENSUS.json; RUNS/full_study/common-family-census/measurement/ALL_FRAME_CERTIFICATES.json; complete per-movie/per-case records in the same route` |
| 47 | Actual executable analyst statement | Step 3: analyst-path | `RUNS/full_study/analyst-path/measurement/REPORT.json; RUNS/full_study/analyst-path/measurement/COMPLETE_FRAME_FAMILIES.json` |
| 48 | Instrumented actual-path construction and query costs | Step 8; new timing measurements | `RUNS/worked_cost/SUMMARY.json; recorded paper timing in INPUTS/controlled_companion_LOCAL_ONLY/05_既有采用成本_v1.1/COST_AND_ADOPTION_SUMMARY.json` |
| 49 | Completeness responsibility probes with corrected validation scope | Step 8; actual interface probes | `RUNS/interface_probes/ACTUAL_INTERFACE_PROBES.json; Step 2 primitive verification` |
| 50 | Same-task adoption decisions and retained comparison boundary | Synthesis of Steps 2/3/8; no extra experiment | `RUNS/worked_path/SUMMARY.json; natural3d, operating-envelope, literal-baseline and worked_cost results` |
| 51 | Coupled-task resource measurements | Step 8; new workload measurements | `RUNS/coupled_cost/SUMMARY.json and all process/phase records; historical records at INPUTS/controlled_companion_LOCAL_ONLY/04_既有补充证据_v1.2/coupled_cost/` |
| 52 | Actual delivery and interface probes | Steps 2/8; actual API and refusal checks | `RUNS/interface_probes/ACTUAL_INTERFACE_PROBES.json; RUNS/worked_path/PRIMITIVE_VERIFICATION.json and query_cap_one/REPORT.json` |
| 53 | Development archive and source associations | Retained development inventory | `data/catalog/summary.json; notebooks.csv; score_records.csv; source_output_links.csv; INPUTS/expanded_evidence/02_实验身份与谱系/` |
| 54 | Complete expanded corpus and natural identities | Step 4; full graph/pair census | `RUNS/expanded_graphs/GRAPH_AUDIT_PROGRESS.json; GRAPH_AUDIT_SUMMARIES.jsonl; RUNS/expanded_pairs/SUMMARY.json and complete records` |
| 55 | Every focused output comparison and declared linkage | Step 4; 208 focused comparisons | `RUNS/focused_recalculated/LINKED_FOCUSED_CONTRASTS.json; RUNS/focused_input_summary.json; data/catalog/focused_comparisons.csv` |
| 56 | Complete frozen raw input component intervention | Step 4; eight saved component-intervention comparisons | `RUNS/focused_recalculated/LINKED_FOCUSED_CONTRASTS.json (motion_replacement_disabled); motion_linked/; retained context INPUTS/expanded_evidence/integration/MOTION_INTERVENTION_RESULTS.json` |
| 57 | Complete retained module deletion and addition results | Step 5; 72 module conditions | `RUNS/module_conditions/v75_ablation.csv; REPRODUCTION_CHECK.json; RUNS/module_context_recalculated.json` |
| 58 | Negative training and unreproduced historical counts | Steps 3/5; head and historical negative evidence | `RUNS/head_validation/head_v2_gate.json; full_study/historical-negative/measurement/RESULT.json; INPUTS/expanded_evidence/05_补证与核验/历史计数对照/ALL_279_MOVIE_RECORDS.csv (three historical rows remain unreproduced)` |
| 59 | Actual image and relation provenance | Steps 6/7; exact figures and all case measurements | `RUNS/paper_figures/FIGURE_MANIFEST.json; RUNS/cases/*/RESULT.json; INPUTS/case_reuse_LOCAL_ONLY/INPUT_PROVENANCE.json and SELECTION_BEFORE_EXTRACTION.json` |

## Supporting files and reuse

The root [folder map](../README.md#repository-map) describes each functional
directory. The detailed [30-route reference](../paper/README.md) is optional
implementation reference after this walkthrough. [DATA_ACCESS.md](DATA_ACCESS.md)
describes original dataset formats, and [FIGURE_CASES.md](FIGURE_CASES.md) gives
the four case configuration schemas. Neither replaces the execution order above.

For a new coordinate comparison, prepare reference/before/after NPZs using the
schema in DATA_ACCESS.md, run `paper/expanded/compare.py`, then
`paper/expanded/verify_endpoints.py`. The former constructs/query-computes; the
latter checks endpoint witnesses against declared primitive inputs. Different
scalar endpoints can have different witnesses. Full family construction and
query optimization establish extrema; one witness establishes an attainable value.
