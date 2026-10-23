# Cell tracking interpretation audit

This repository provides the analysis code, reproduction workflows and figure-generation scripts supporting the paper **Auditing interpretations of fixed cell tracking outputs across processing changes**.

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

Use this README as the starting point. Choose a task below; each linked guide
gives the required inputs, commands and expected outputs.

| Task | Start here |
|---|---|
| Install and run a first example without external data | [Install](#install), then [Try the method](#try-the-method) |
| Obtain the paper's saved inputs and identify their sources | [Study input archive](data/study_inputs/README.md) |
| Reproduce the reported analyses | [Step-by-step reproduction commands](docs/REPRODUCING.md) |
| Generate the exact manuscript figures | [Figure commands](docs/REPRODUCING.md#figures) |
| Extract a different real-image case | [Case formats and commands](docs/FIGURE_CASES.md) |
| Analyze new saved coordinate graphs | [Analyze saved graphs](#analyze-saved-graphs) and [input formats](docs/DATA_ACCESS.md#using-downloaded-data) |

## Reproduce the study

- [Inputs and access](docs/DATA_ACCESS.md)
- [Commands and expected results](docs/REPRODUCING.md)
- [Real-image extraction and alternative cases](docs/FIGURE_CASES.md)
- [Full analysis routes](paper/README.md)

The [study input directory](data/study_inputs/README.md) identifies the archive,
checksum, six-folder layout, original data sources and checkpoint attribution.
Large input files are distributed as repository release assets; only their guide
and metadata are tracked under `data/study_inputs/`. The reproduction guide starts
with a small actual saved-input check, then covers the 30-route suite, expanded
comparisons, module/head experiments and figures. The constructed example above
can be run immediately after installation.

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
