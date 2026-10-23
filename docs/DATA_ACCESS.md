# Data sources and input use

The study uses three datasets. Obtain original images and annotations from their
upstream records; they are not mirrored in this source repository.

| Dataset | Official source | Use in this study |
|---|---|---|
| Biohub cell tracking during development | [Kaggle competition](https://www.kaggle.com/competitions/biohub-cell-tracking-during-development) | Three-dimensional coordinate graphs and saved processing outputs |
| Bacterial cell tracking | [Cell Tracking Dataset](https://doi.org/10.5281/zenodo.11237127) | Mask-based relations, continuation/division types and processing histories |
| Epithelial imaging | [EpiCure](https://doi.org/10.5281/zenodo.20607705) | Image-to-graph processing stages and relation/path changes |

The [Cell-TRACTR checkpoint](https://doi.org/10.5281/zenodo.14509424) is a model
resource for the bacterial work, not a fourth dataset. Follow the terms supplied
with each dataset and checkpoint.

## Using downloaded data

Keep the three datasets separate and preserve their movie, frame and object
identities. They provide different experiments; the shared audit interface joins
predicted and reference relations within each experiment, rather than combining
the three image collections into one training set.

1. **Biohub:** obtain the relevant image sequences and reference graphs, together
   with the tracking outputs to be examined. The coordinate comparison entry
   accepts three NPZ files: reference, before and after. Each contains integer
   `ids[N]`, finite `coords[N,4]` ordered as `(frame,z,y,x)`, integer node-ID pairs
   `edges[E,2]`, and a Unicode scalar `unit='um'`. Acquisition indices remain
   integers. Convert spatial coordinates once using the image metadata. The
   retained Biohub conversion uses `(z,y,x)=(1.625,0.40625,0.40625)` micrometres per
   pixel. Preserve the original directed relations and object identities.
2. **Bacterial:** use matching raw frames, reference masks and lineage annotations,
   plus the saved predicted masks, graph pairs and continuation/division types for
   the states being compared. The mask analyses use the declared strict
   `IoU > 1/2` matching convention. Supply these files to the relevant retained
   study route or to a `pulse`/`native` case configuration.
3. **Epithelial:** use raw TIFF sequences and their curated reference labels with
   the predicted masks and graphs at the processing stages. Preserve TIFF axis
   metadata and frame indexing. Supply an `epithelial` case configuration or the
   inputs expected by the retained epithelial route.

The [case guide](FIGURE_CASES.md) lists the exact JSON fields, supported image
layouts and extraction command for the image-based interfaces. Upstream tracker
inference supplies predictions; the comparison and case entry points analyze
those predictions. Historical producer snapshots under
`paper/expanded/historical_producers/` record the original execution and may use
the original workspace layout; use the explicit-input entry points below for a
new local run.

From the repository root, after installation:

```bash
python paper/expanded/compare.py --reference inputs/reference.npz --before inputs/before.npz --after inputs/after.npz --contract identical-input --output outputs/comparison
python paper/expanded/verify_endpoints.py --task outputs/comparison --reference inputs/reference.npz --before inputs/before.npz --after inputs/after.npz
python paper/figures/export_case.py --config path/to/case.json --output outputs/case
```

Use `identical-input` only for outputs with the declared common object-ID
namespace and identical complete frame inputs where linkage applies. Otherwise
select `--contract independent`. Use a fresh output location for each command.
The first two commands operate on coordinate graphs; the third uses one of the
mask or coordinate case configurations in the case guide.

## Inputs for the exact reported study

The central [study input guide](../data/study_inputs/README.md) contains the archive
identity, release location, extraction instructions, six-directory layout and
dataset/checkpoint attribution. [SOURCES.csv](../data/study_inputs/SOURCES.csv)
distinguishes original dataset subsets, saved predictions/captures, upstream and
study-fitted checkpoints, computed audit evidence and historical records.

The retained study uses exact saved outputs. Downloading the original images and
running a tracker again produces new inputs; the archive provides the historical
predictions and intermediates used in the reported calculations. After extraction,
use [REPRODUCING.md](REPRODUCING.md) for the worked example, full suite, expanded
comparisons, module/head producers and exact figures.
