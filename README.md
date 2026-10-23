# Cell tracking interpretation audit

This repository provides the analysis code, reproduction workflows and figure-generation scripts supporting the paper **Auditing interpretations of fixed cell tracking outputs across processing changes**.

**Reproduce the paper:** follow [one complete walkthrough](docs/REPRODUCING.md#start-here), Steps 1–9. It lists every paper result and the output to inspect. The [repository map](#repository-map) below explains the folders.

Given saved tracking graphs, reference objects and a declared matching convention,
this software evaluates proposed statements about recovered relations, processing
changes and local histories. It constructs complete correspondence families,
preserves shared endpoints and declared cross-output links, and returns attainable
readouts with whole-map witnesses or an explicit construction/query refusal.

## Install

Tested on Windows with Python 3.13.12, NumPy 2.4.6 and SciPy 1.18.0.

```bash
git clone https://github.com/AlLia963/Cell_tracking_interpretation_audit.git
cd Cell_tracking_interpretation_audit
python -m venv .venv
# PowerShell: .venv\Scripts\Activate.ps1
# POSIX: source .venv/bin/activate
python -m pip install -r requirements-verified.txt .
```

## Try the method

```bash
python paper/expanded/review_example.py --output outputs/example
python paper/review_smoke.py --output outputs/path_controls
python -m unittest discover -s tests -v
```

Expected messages are `EXPANDED_EXAMPLE_PASS` and `REVIEW_SMOKE_PASS`.
The examples construct their own inputs and exercise complete families, shared
correspondence constraints, witness checks and actual cap refusals. All 24 tests
run when the figure dependencies are installed; otherwise four image-IO tests skip.
Use a new output directory for each run.

## Analyze saved graphs

```bash
python paper/expanded/compare.py --reference inputs/reference.npz --before inputs/before.npz --after inputs/after.npz --contract identical-input --output outputs/comparison
python paper/expanded/verify_endpoints.py --task outputs/comparison --reference inputs/reference.npz --before inputs/before.npz --after inputs/after.npz
```

Each NPZ contains unique integer `ids[N]`, finite `coords[N,4]` in `(frame,z,y,x)`
order, integer node-ID pairs `edges[E,2]`, and Unicode scalar `unit='um'`. Edges
advance acquisition time. The matching objective maximizes cardinality within an
inclusive 7 µm gate, then minimizes the exact sum of calculated float64 distances.

`independent` reevaluates the two outputs independently. `identical-input` shares
matching variables for equal complete frame IDs and coordinates within a declared
common object-ID namespace. Each reported metric endpoint has its own witness.
The endpoint checker verifies its existence and constraints; complete construction
and query calculation establish the domain and extrema.

## Reader guide

**To reproduce the paper, follow [the complete walkthrough](docs/REPRODUCING.md)
from Step 1 to Step 9.** It contains the execution order, required inputs,
dependencies, expected outputs and a result index for every main result, all
figures, supplementary tables and Source Data entries. Stay in that document
through the run; supporting pages are linked where needed.

| Reader goal | Read next |
|---|---|
| Reproduce the complete supplied paper workflow | [Steps 1–9](docs/REPRODUCING.md#start-here) |
| Locate one paper result | [Paper result index](docs/REPRODUCING.md#paper-result-index), then its listed step |
| Locate a particular figure | [Figure index](docs/REPRODUCING.md#figure-index) |
| Locate a Source Data entry | [All 59 entries](docs/REPRODUCING.md#source-data-index) |
| Obtain the archive and source attribution | [Study inputs](data/study_inputs/README.md), then return to the walkthrough |
| Analyze a new coordinate comparison or another real-image case | [Reuse interfaces](docs/REPRODUCING.md#supporting-files-and-reuse) |

## Repository map

The folders below have distinct implementation roles. The walkthrough selects
the commands in the required order; readers do not need to choose scripts from
these directories by trial and error.

| Folder | Purpose | Reader action |
|---|---|---|
| `.github/workflows/` | Automated source/test checks on GitHub. | No manual action for the reproduction walkthrough. |
| `data/catalog/` | Notebook/run/output identities and the retained focused/module CSV tables. | Read for development coverage; used by Steps 4–5. |
| `data/study_inputs/` | Archive identity, source attribution, checksum and extraction layout. | Obtain the release input archive; then follow the single walkthrough. |
| `docs/` | Reader instructions, input schemas, case formats and route inventory. | REPRODUCING.md is the complete paper walkthrough. |
| `examples/` | Small library examples and constructed JSON/coordinate fixtures. | Optional examples after the first run. |
| `src/portable_analysis_candidate/` | Reusable graph, family, window and typed-relation audit API. | Read when integrating the method with another analysis. |
| `src/portable_analysis_candidate/_upstream/` | Pinned implementation dependencies of that library. | Implementation reference; invoked by the public API. |
| `workflows/coordinate/` | Coordinate-input workflow and its scientific_backend/ adapter. | Optional lower-level coordinate integration. |
| `tests/` | Executable tests of library contracts and image input handling. | Run in Step 1. |
| `paper/` | Current commands for study execution, explicit-input audit and checks. | The walkthrough invokes the required entry points. |
| `paper/adapters/` | Explicit-root adapters connecting the 30-route runner to retained scientific implementations. | Called by run_suite.py; no manual path editing. |
| `paper/expanded/` | Expanded graph audits, focused comparisons and portable module/head producers. | Steps 4–5. |
| `paper/expanded/reference_backend/` | Pinned primitive matching/family backend used by the expanded audit. | Called by the expanded commands. |
| `paper/expanded/module_runtime/` | Original selected notebook cells, their hashes and the original module scorer. | Loaded by reproduce_module_conditions.py in Step 5. |
| `paper/expanded/historical_producers/` | Historical producer snapshots plus explicitly adapted graph/pair/focused/estimator entry points. | Run only the explicitly named current commands in Steps 4–5. |
| `paper/figures/` | Exact manuscript figure builders and configurable real-image case exporter. | Steps 6–7. |
| `paper/scientific/` | 336 indexed study dependencies. Subfolders extensions/, extras/, historical_sources/, inputs_LOCAL_ONLY/ and sources/ retain the original calculation packages. | prepare_local.py assembles these dependencies; do not reconstruct their old directory layout by hand. |
| `paper/historical_validation_scripts/` | Retained validation snapshots supporting earlier executions. | Provenance/reference; the walkthrough names current checks explicitly. |
| `paper/resources_v1_1/` | Original worked-task resource measurement implementations. | Invoked through the explicit-root timing wrapper in Step 8. |
| `paper/protocols/` | Fixed definitions of the original geometry scenarios. | Consumed by the sensitivity route. |
| `paper/licenses/` | Upstream licenses and source attribution. | Read for reuse of third-party source. |
| `paper/_local/ [created locally]` | Prepared runtime and local input bindings; ignored by Git. | Created in Step 3. |
| `data/study_inputs/downloads/ [local only]` | Optional local copy of the release ZIP; ignored by Git. | Storage only; extracted INPUTS may be elsewhere. |

Root files: `pyproject.toml` and the requirements files define installation;
`LICENSE` and `NOTICE.md` identify source terms; `SOFTWARE_MANIFEST.json` and
`SOURCE_PROVENANCE.json` identify delivered source/provenance. The script
`paper/run_suite.py` runs the original 30 routes. Expanded graph/pair, module,
head, figure, case and resource steps are additional commands explicitly included
in the complete walkthrough.

## Development archive

The retained work comprises **419 notebook files**, representing 351 distinct
contents, plus two archive-only contents (353 total). Of these, 134 contents have
recorded output associations. The [catalog](data/catalog/summary.json) connects
source identities, saved outputs and execution records without duplicating the
original notebooks in Git.

The [125 run records](data/catalog/score_records.csv) include **114 scored
successes and 11 failures**: three scoring errors, two exceptions, five timeouts
and one out-of-memory run. [Source/output associations](data/catalog/source_output_links.csv)
retain their evidence basis. These development records support a deduplicated
analysis corpus of 2,738 saved graphs over 199 movies; the focused analyses retain
208 output comparisons, eight component-intervention comparisons and 72 module
conditions. Repeated runs and overlapping outputs retain their movie identities.

## Contents and license

`src/` provides the audit library; `workflows/` the coordinate adapter;
`paper/expanded/` saved-output comparison tools; `paper/figures/` figure and case
programs; `paper/scientific/` the pinned dependencies of the full study routes;
and `tests/` executable checks.

Project code uses [MIT](LICENSE). Upstream components retain their licenses and
attribution in [NOTICE](NOTICE.md) and `paper/licenses/`. Dataset and checkpoint
sources are listed in [data/study_inputs/SOURCES.csv](data/study_inputs/SOURCES.csv).
For the research method, cite the manuscript title above; publication metadata
will be added when assigned. A software revision identifies the code used for a run.
For reproducibility questions or bug reports, open a repository issue and include
the command, environment, input archive identity and relevant error log.
