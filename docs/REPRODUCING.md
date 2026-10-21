# Reproducing the analyses

Start with the unrestricted example in the main README. Use new output paths.
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

The historical 175,488-frame complete-family census and 124,237 same-movie pair
records remain in the controlled expanded evidence. Current endpoint checks reuse
them; they are not a new whole-corpus inference or completeness run.

## Retained full study routes

```bash
python -m pip install -r paper/requirements-paper.txt
python -B -X utf8 paper/configure_bundle.py --bundle path/to/full_study_inputs_LOCAL_ONLY --runtime paper/_local/review_runtime --config paper/local_config.json --runs outputs/full_study
python -B -X utf8 paper/prepare_local.py --config paper/local_config.json
python -B -X utf8 paper/run.py list
python -B -X utf8 paper/run_suite.py --config paper/local_config.json --output outputs/full_study
```

All 340 indexed scientific sources are supplied in the repository. On
2026-10-14, the 30-route suite completed in one run from a separate local input
copy and Python environment. Individual commands describe their actual operation;
`native-all` remains an optional full-cohort native rematching route requiring
additional captures. The default archived-certificate route uses retained captures.

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

`paper/figures/export_case.py` handles alternative actual cases; see
[case instructions](FIGURE_CASES.md). Source tables and pixel packets belong to
the input companions and retain their source terms.
