# Manuscript analysis workflows / 论文实验运行指南

Code accompanying **Auditing interpretations of fixed cell tracking outputs across processing changes**. Start with the repository README and `docs/REPRODUCING.md` for the current explicit-input interface. This page documents the retained full-study analysis routes and their historical execution scope. Figure programs are in `paper/figures/`.

## Install

The integration was executed on Windows with Python 3.13.12. From the repository root in an activated environment:

```bash
python -m pip install .
python -m pip install -r paper/requirements-paper.txt
python -m unittest discover -s tests -v
```

Paper analyses use CPU. Upstream model training/inference has a separate environment and is not started by the suite.

## Study inputs

The full-study suite uses `full_study_inputs_LOCAL_ONLY`, containing fixed
stage/reference graphs, saved predictions, captures and historical comparison
inputs. See [data sources and input use](../docs/DATA_ACCESS.md) for the three
original datasets and the formats used by the explicit-input interfaces.

The repository supplies the analysis code and development catalog. Dataset
images are obtained upstream; the named companions retain the exact saved
predictions and intermediates for the paper. Each companion has a per-file
SHA256 manifest. `scientific/inputs_LOCAL_ONLY/` is a historical source-code path.
Author-side `export_inputs.py` and `build_extra_inputs.py` assemble existing
study inputs; they are not raw-dataset download or tracker-inference commands.

Configure the supplied companion and prepare a fresh runtime:

```bash
python -B -X utf8 paper/configure_bundle.py --bundle "<absolute-input-bundle>" --runtime "<absolute-repo>/paper/_local/study_runtime" --config paper/local_config.json --runs outputs/study
python -B -X utf8 paper/prepare_local.py --config paper/local_config.json
python -B -X utf8 paper/run.py list
```

`configure_bundle.py` verifies every declared file and writes location-specific configuration. `prepare_local.py` installs indexed repository code into the runtime and binds external inputs. Existing runtimes/config files are refused. Runtime directory links remain inputs: do not recursively delete through them. All outputs must be outside the input/runtime directories and use absent paths.

## Run the analyses

```bash
python -B -X utf8 paper/run_suite.py --config paper/local_config.json --output outputs/study
```

The default suite contains **30 routes**. It calculates new outputs before optional known-result comparison. It connects a newly calculated allocation ledger to duty controls, freshly generated common-carrier policies to scoring/census/path queries, and timing/chains/native windows to the identity crosswalk. `run_suite.py` records progress and stops on failure; partial evidence is retained. The full default suite completed in one uninterrupted run on 2026-10-14 using a separate local input copy and Python environment.

| Analysis | Routes | Scientific output |
|---|---|---|
| Original 3D stage histories | `natural3d`, `natural-gates`, `literal-baseline` | All 5751 relation histories, complete correspondence families, 31 scalar bounds, witnesses and 6/7/8 µm gate calculations |
| Original sensitivity and scale | `historical-geometry`, `historical-stress` | All original 30 perturbation scenarios × three contracts; all 36 scale/cap cases; fresh resource measurements |
| Constructed method cases | `constructed`, `typed-constructed`, `operating-envelope` | Variable-view coordinate/typed cases; 27 moderate cases and 54 comparisons; withholding and witness reports |
| Known-origin support changes | `bacterial-initial-overlays`, `bacterial-division-overlays` | 290 and 1144 actual-support overlays, eligibility/history sets and final-observation collision classes |
| Source duties | `allocation-replay`, `bacterial-duties`, `duty-boundary` | 274 proposals, 115 winners, 159 exclusions; all 734 controls and 13 authority-boundary cases |
| Common-carrier policies | `common-generate`, `common-score-generated`, `bacterial-common`, `common-family-census`, `analyst-path` | Regenerate all 96 policy graphs, score them, enumerate full frame/path families and test the specified proposed path statement |
| Historical negative results | `historical-negative` | All 48 SVM saved-output pairs/6 groups, 20 SDY scores and 16 paired contrasts |
| Bacterial processing and pulses | `bacterial-natural`, `bacterial-full`, `bacterial-pulse-endpoint`, `projection` | Raw/typed relation histories, three full policies, 116 fixed four-arm endpoints and all 14 captured geometry-feedback pulses |
| Native histories | `bacterial-stage-archive`, `native16` | Reaggregate all 116 certificates/124372 relation-arm identities; freshly project/rematch four selected windows × four arms |
| Event/lineage consequences | `bacterial-timing`, `bacterial-chains`, `bacterial-cca`, `identity-crosswalk` | Timing tolerances, complete focal chains, 87 CCA values, exact relation/event/chain crosswalks and Figure 4 pixels |
| Epithelial domain | `epithelial` | Execute E0–E3 from specified images, then calculate reference-relative relation/path results |

Individual routes use the same interface:

```bash
python -B -X utf8 paper/run.py projection --config paper/local_config.json --output outputs/projection_run
```

Dependencies are supplied automatically by the suite. For manual runs, configure the completed `natural_measurement_root`, `timing_measurement_root`, `chains_measurement_root`, `native_window_root`, `generated_common_root`, `decision_ledger` and `duty_authority` where needed. Some bacterial outputs reside under `measurement/measurement/`; use the actual containing directory.

Native-stage reconstruction uses the retained full-cohort records in `bacterial-stage-archive`. The `native16` route separately reprojects and rematches four selected windows in all four arms.

## Checking a run

Each route writes its calculation logs, measurements and completion record.
The expected outcomes and separate witness/primitive checks are described in
[REPRODUCING.md](../docs/REPRODUCING.md). Source dependencies and their attribution
are recorded in [NOTICE.md](NOTICE.md) and `SOURCE_INDEX.json`.
