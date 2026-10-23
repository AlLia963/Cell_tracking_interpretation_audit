# Study reproduction inputs

Inputs for **Auditing interpretations of fixed cell tracking outputs across processing changes**.
Start with the repository [README](../../README.md). The complete command guide is
[docs/REPRODUCING.md](../../docs/REPRODUCING.md).

## Obtain and verify the archive

The archive is prepared for attachment to this repository's
[Releases](https://github.com/AlLia963/Cell_tracking_interpretation_audit/releases), under the tag `study-inputs-2026-10-23`.
**At preparation it has not yet been uploaded.** The download below becomes usable
when that release is published; GitHub's source-code ZIP does not contain the data.

- File: [`study_reproduction_inputs.zip`](https://github.com/AlLia963/Cell_tracking_interpretation_audit/releases/download/study-inputs-2026-10-23/study_reproduction_inputs.zip)
- Size: 1,864,437,422 bytes (about 1.86 GB compressed)
- SHA256: `6a8e0bf2abee7c0f9cfc7e61ea893dc0540e3288eb9ba0c9333eceaca59b8b2c`
- Identity and contents: [ARCHIVE.json](ARCHIVE.json)
- Dataset/checkpoint/derived-data attribution: [SOURCES.csv](SOURCES.csv)

In PowerShell, set the ZIP path to the file you downloaded:

```powershell
$studyZip = 'C:\Downloads\study_reproduction_inputs.zip'
$expectedHash = '6a8e0bf2abee7c0f9cfc7e61ea893dc0540e3288eb9ba0c9333eceaca59b8b2c'
if ((Get-FileHash -LiteralPath $studyZip -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedHash) {
    throw 'Input archive checksum mismatch.'
}
$studyInputs = 'D:\inputs'
if (Test-Path -LiteralPath $studyInputs) { throw 'Choose a new, absent extraction directory.' }
Expand-Archive -LiteralPath $studyZip -DestinationPath $studyInputs -ErrorAction Stop
```

Use a short extraction path, keep all six top-level names below, and write analysis
outputs to new paths outside the input directory. The archive contains
`REPRODUCTION_INPUT_MANIFEST.json` with per-file sizes and hashes, and preserves
the earlier companion manifests used by the study commands.

## Input layout and first commands

The following commands run from the source repository root. Replace `INPUTS`
with the extracted root, for example `D:/inputs`.

| Directory under INPUTS | Content and origin | Use |
|---|---|---|
| `full_study_inputs_LOCAL_ONLY` | Retained predictions/captures, references, frozen targets and provenance for the original study routes | Configure and run the 30-route suite |
| `controlled_companion_LOCAL_ONLY` | Saved actual shared-correspondence case and its analysis/interface records | Run the worked-audit path |
| `expanded_evidence` | Normalized saved graphs, references, complete families, comparisons, development identities and head-validation captures | Expanded graph/pair analysis and four-fold head validation |
| `figure_inputs_LOCAL_ONLY` | Selected original pixel/label subsets, measured relations and exact plot packets | Generate the manuscript figures |
| `case_reuse_LOCAL_ONLY` | Original and alternative case inputs, relative configurations and provenance | Extract and measure another real-image case |
| `historical_module_inputs` | Three saved prediction/reference GEFF pairs and the retained pilkwang ranker | Recalculate three movies × 24 module conditions |

For a first actual saved-input check:

```powershell
python paper/review_d47.py --input-root "INPUTS/controlled_companion_LOCAL_ONLY/03_最小D47/LOCAL_ONLY_INPUTS" --expected-report "INPUTS/controlled_companion_LOCAL_ONLY/04_既有补充证据_v1.2/packaged_cli_execution/EXPLICIT_PROBE/NEW_ROOT_TASK/REPORT.json" --output outputs/worked_path
```

Expected: `WORKED_AUDIT_REVIEW_PASS`, family sizes 1/2/1, attainable joint value
`{0}`, and a real query-cap refusal. The example that constructs its own inputs
is available without the archive: `python paper/expanded/review_example.py --output outputs/example`.

For the retained full-study suite, after installing its dependencies:

```powershell
python -m pip install -r paper/requirements-paper.txt
python -B -X utf8 paper/configure_bundle.py --bundle "INPUTS/full_study_inputs_LOCAL_ONLY" --runtime paper/_local/study_runtime --config paper/local_config.json --runs outputs/study
python -B -X utf8 paper/prepare_local.py --config paper/local_config.json
python -B -X utf8 paper/run_suite.py --config paper/local_config.json --output outputs/study
```

The runtime and configuration must also be new. For the expanded census, the 72
module conditions, four-fold head validation and exact figures, follow
[REPRODUCING.md](../../docs/REPRODUCING.md); each section identifies its environment,
explicit input root, command and expected output. Alternative image cases use
[FIGURE_CASES.md](../../docs/FIGURE_CASES.md).

## Sources and attribution

Original images and annotations come from:

1. [Biohub - Cell Tracking During Development](https://www.kaggle.com/competitions/biohub-cell-tracking-during-development).
2. [Dunlop lab Cell Tracking Dataset](https://doi.org/10.5281/zenodo.11237127).
3. [EpiCure epithelium movies and curated tracks](https://doi.org/10.5281/zenodo.20607705), specifically the selected `MovieEpitheliumFigure5.zip` material.

Selected original arrays/annotations and derived pixels remain identified by the
figure `SOURCE.json` and case `INPUT_PROVENANCE.json` records. The three datasets
support separate experiments; they are not merged into one training set.

The archive contains two retained upstream checkpoints:
[pilkwang's association ranker](https://www.kaggle.com/datasets/pilkwang/biohub-local-association-ranker-unet300-v1)
and [Anvith Pothula's shipped coordinate head](https://www.kaggle.com/datasets/anvithpothula/biohub-v1284-head-s075).
The revised `v1284_head_v2.pt` is the study's subsequent fitted head; its training
entry and negative held-out result are documented separately. Individual sizes
and hashes are in `ARCHIVE.json`.

[Cell-TRACTR model weights](https://doi.org/10.5281/zenodo.14509424) were an upstream
prediction resource and are not included in this archive. Saved-output audit
commands consume the retained outputs rather than requiring a new tracker run.

`SOURCES.csv` maps the relevant paths, source creators/URLs, use and provenance
records. Dataset subsets and upstream checkpoints retain their source terms;
the code repository's MIT license does not replace those terms.

## Historical records

The archive preserves complete existing companions and their manifests. It also
contains historical text/source snapshots used for provenance or compatibility,
including `full_study_inputs_LOCAL_ONLY/article/`. These are historical records:
use the current manuscript and current source-checkout commands. Frozen expected
reports are comparison targets read after calculation. The six directory names
are retained so the validated interfaces keep working.
