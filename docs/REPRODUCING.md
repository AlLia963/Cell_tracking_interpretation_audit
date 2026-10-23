# Reproducing the analyses

Start with the unrestricted example in the main README. Use new output paths.
For original datasets, see [data sources and input use](DATA_ACCESS.md): it
identifies the three upstream sources, the input formats and the next executable
commands. The routes below use the named saved study inputs. Tracker inference
and analysis of fixed predictions are separate steps.
`COMPLETE` means the requested implementation scope completed; `WITHHELD_*`
records a reason and contains no truncated bounds.

## Core comparison

`compare.py` writes `COMPARISON_CONTRACT.json`, input bindings, two graph reports,
frame families and `REPORT.json`. Complete reports contain minimum and maximum
before-TP, after-TP, gains, losses and net. Each endpoint has its own whole-map
witness. Different metric endpoints need not coexist in one map, and intermediate
integers are not automatically attainable.

`verify_endpoints.py` requires exactly those ten names and integer-valued bounds,
then checks primitive endpoints, frames, injection, gate, actual identical-input
eligibility, family membership and literal readouts. It checks all reference
frames because the report promises full-map witnesses. It does not establish
extremality by replay alone.

## Actual worked path

After obtaining the [controlled input companion](DATA_ACCESS.md):

```bash
python paper/review_d47.py --input-root "../controlled_companion_LOCAL_ONLY/03_最小D47/LOCAL_ONLY_INPUTS" --expected-report "../controlled_companion_LOCAL_ONLY/04_既有补充证据_v1.2/packaged_cli_execution/EXPLICIT_PROBE/NEW_ROOT_TASK/REPORT.json" --output outputs/worked_path
```

Expected: `WORKED_AUDIT_REVIEW_PASS`; families 1/2/1; joint recovery `{0}`;
marginal relaxation `{0,1}`; proposal 1 rejected; proposal 0 witnessed; primitive
optimality and family checks complete; query cap one withheld. This replays saved
graphs without new inference or historical timing reruns.

## Expanded archive and focused comparisons

`corpus` must contain `graphs`, `references`, `graph_reports` and `frame_cache`;
`records` must contain `linked_records` and `motion_linked`.

```bash
python paper/expanded/review_linked_records.py --corpus path/to/corpus --records path/to/comparison_records --output outputs/endpoint_checks.json
python paper/expanded/summarize_focused_inputs.py --comparisons path/to/55_all_208_movie_comparisons.csv --corpus path/to/corpus --output outputs/focused_inputs.json
python paper/summarize_module_context.py --input path/to/57_all_72_module_conditions.csv --output outputs/module_context.json
```

Expected: 216 comparisons and 2,160 endpoint witnesses; reference denominators
28,063 for each 40-movie threshold contrast, 2,127 for each four-movie comparison,
and 43,394 for the 80-movie line-fitting contrast. The module table has 72 rows;
19 of 66 nonbaseline rows retain full-setting TP/FP while changing node or edge
counts. This reaggregation does not execute the old module producer.

The retained expanded companion contains `04_统一重分析/GRAPH_INDEX.jsonl`, `graphs/`, `references/`, `frame_cache/`, `graph_reports/`, `visibility/` and the complete pair records. A fresh complete-family/graph census and subsequent within-movie pair calculation use explicit locations:

```bash
python paper/expanded/historical_producers/13_run_complete_graph_audit.py --corpus path/to/expanded_evidence/04_统一重分析 --output outputs/expanded_graphs
python paper/expanded/historical_producers/15_all_within_movie_contrasts.py --corpus path/to/expanded_evidence/04_统一重分析 --audit-root outputs/expanded_graphs --output outputs/expanded_pairs
```

To recalculate pairs from the retained completed graph census, set `--audit-root` to that same `04_统一重分析` directory. Use new output directories outside the input corpus. `--limit` supports a bounded execution check and leaves a partial census; omit it for all graphs or pairs. The 175,488 distinct frame geometries and 124,237 pairs are expected outcomes for the exact retained corpus and declared caps. These commands reconstruct matching/query evidence from saved graphs; they do not run detector inference. The 216 endpoint checks above replay retained focused comparisons rather than reconstructing the whole corpus.

To recalculate all 208 focused linked comparisons and the eight saved motion-intervention comparisons, use the graph-pair definitions from Source Data Tables 55–56:

```bash
python paper/expanded/historical_producers/run_linked_focused.py --corpus path/to/expanded_evidence/04_统一重分析 --audit-root outputs/expanded_graphs --contrasts path/to/55_LINKED_FOCUSED_CONTRASTS.json --motion path/to/56_motion_source_and_result_join.json --output outputs/focused_recalculated
python paper/expanded/review_linked_records.py --corpus path/to/expanded_evidence/04_统一重分析 --audit-root outputs/expanded_graphs --records outputs/focused_recalculated --output outputs/focused_witness_checks.json
```

The first command recalculates the linked bounds from graphs and supplied complete-frame families; prior linked result fields in the cohort JSON do not enter the calculation. Set `--audit-root` to the retained corpus to reuse its families, or to a fresh `13_run_complete_graph_audit.py` output for new primitive construction. The second command uses primitive graphs at `--corpus` and the corresponding graph reports/frame families at `--audit-root`, so a fresh audit can be checked without copying inputs or mixing report sets. The eight-movie command remeasures the saved intervention outputs; it does not regenerate their upstream processing.

The historical cached-coordinate estimator replay has an explicit input entry:

```bash
python paper/expanded/historical_producers/replay_local_smoother.py --input-root "path/to/expanded_evidence/05_补证与核验/16片局部重放_历史证据" --film 44b6_12dfb391 --output outputs/smoother_check.json
```

Use a film directory actually present under that input root. The command reads its pinned cached coordinates and repaired graph, executes the retained estimator and compares the three output arrays with its frozen target. It does not execute detector inference.

## Historical module and head experiments

These two producers reconstruct the reported experiments separately from the
30-route fixed-output suite. Use the original graph-processing conditions and
held-out movies. Install the recorded dependencies in a separate environment:

```bash
python -m pip install -r paper/requirements-historical.txt
```

The tested Windows CPU environment is recorded in
`paper/expanded/HISTORICAL_RUNTIME.json`. No GPU detector training or new image
inference is needed by these two producers.

```bash
python paper/expanded/reproduce_module_conditions.py --input-root INPUTS/historical_module_inputs --output outputs/module_conditions
python paper/summarize_module_context.py --input outputs/module_conditions/v75_ablation.csv --output outputs/module_context.json
python paper/expanded/reproduce_head_validation.py --input-root INPUTS/expanded_evidence/05_补证与核验/四折负结果_历史证据 --expected INPUTS/expanded_evidence/05_补证与核验/四折负结果_历史证据/head_v2_gate.json --threads 16 --output outputs/head_validation
```

Replace `INPUTS` with the root of the extracted study reproduction input archive.
The module producer executes the original notebook processing cells and scorer
from `paper/expanded/module_runtime/`, with saved GEFF prediction/reference
graphs and the retained association ranker. Its default cohort is exactly the
three reported movies, with 24 conditions each. `--films` and `--conditions`
support bounded checks; omit them for all 72 rows. The output CSV retains every
condition and fresh execution time. `REPRODUCTION_CHECK.json` compares calculated
counts with the frozen table; historical paper timings are not overwritten.

The head producer reconstructs training labels from the 400 retained captures and
four reference graphs, uses the original movie holdouts, model widths, seeds,
400-epoch fold fits and 600-epoch final fit, and writes predictions/errors and
weights to the new output directory. Use 16 CPU threads for the recorded
numerical replay. Changing thread count can alter float32 trained weights.
`REPRODUCTION_CHECK.json` records every comparison and exits nonzero on a frozen
score mismatch. Frozen expected scores enter only the post-computation check.
The reported head and ensemble each win in zero of the four held-out movies.

`paper/summarize_module_context.py` remains the quick saved-table reaggregation
entry; it does not train or regenerate conditions. The original archived producer
snapshots remain as provenance. The input archive readme gives the exact folder
layout for these commands.

## Retained full study routes

```bash
python -m pip install -r paper/requirements-paper.txt
python -B -X utf8 paper/configure_bundle.py --bundle path/to/full_study_inputs_LOCAL_ONLY --runtime paper/_local/review_runtime --config paper/local_config.json --runs outputs/full_study
python -B -X utf8 paper/prepare_local.py --config paper/local_config.json
python -B -X utf8 paper/run.py list
python -B -X utf8 paper/run_suite.py --config paper/local_config.json --output outputs/full_study
```

All 336 currently indexed scientific sources are supplied in the repository. On
2026-10-14, the 30-route suite completed in one run from a separate local input
copy and Python environment. Individual commands describe their actual operation.
The `bacterial-stage-archive` route reaggregates all 116 retained movie-arm certificate records. `native16` separately reprojects and rematches four selected windows in all four arms from native captures. The supplied selected-capture map covers that execution. The retained backend `rematch_stage.py --windows all` requests all 21,244 movie-arm windows and needs the corresponding full native capture set; the current selected-capture bundle does not supply it. This backend extension was not a completed full-cohort raw rematch in the reader validation.

The original absence classification remains 71/135/3, distinct from historical
canonical 72/137. D44 has 123 relation identities (102/13/8), 64 linked events
(51/13), and 30 chain discrepancies. D01–D52 name source-data entries, not 52
independent experiments. The commands above identify the corresponding calculations and expected results.

## Figures

Figure builders take explicit input roots and write separate PNG/PDF/SVG files.
First reconstruct the retained base figures from their numeric/pixel inputs,
then construct the manuscript set:

```bash
python -m pip install -r paper/figures/requirements.txt
python paper/figures/retained_build_figures.py --input-root path/to/figure_inputs_LOCAL_ONLY/retained_inputs --output outputs/base_figures
python paper/figures/build_integrated.py --input-root path/to/figure_inputs_LOCAL_ONLY --retained-figures outputs/base_figures --output outputs/paper_figures
```

`paper/figures/export_case.py` handles alternative actual cases; see [case instructions](FIGURE_CASES.md). It emits measured cases and previews, using a different schema from the fixed manuscript plot packets. The two commands above reproduce the manuscript figure set from its retained figure inputs. The base builder's historical `Figure4_actual_type_change` output is copied as the current `Figure6_support_and_relation_type`; it is unrelated to the current three-dimensional Figure 4. Source tables and pixel packets belong to the input companions and retain their source terms.
