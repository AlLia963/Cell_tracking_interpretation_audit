# Reconstructing real-image cases

`paper/figures/export_case.py` extracts and measures an explicitly selected case.
Input locations are declared in a JSON file and resolved relative to that file.
There are no author-machine default paths in this entry point.

```bash
python -m pip install -r paper/figures/requirements.txt
python paper/figures/export_case.py --config path/to/case.json --output outputs/case
```

The output is `RESULT.json`, extracted image/mask arrays in `PIXELS.npz`, and
separate single-frame PNG previews. These arrays include declared crops and
z projections or normalized channel-mean displays; they are not all untouched
raw frames. Measurements use the source coordinates, masks and graph records,
never the PNG.

Obtain the figure and alternative-case inputs using the
[study input guide](../data/study_inputs/README.md). Their original dataset
sources and transformations are indexed in [SOURCES.csv](../data/study_inputs/SOURCES.csv).

For the **exact manuscript figures**, use the two figure-builder commands in [REPRODUCING.md](REPRODUCING.md#figures) with `figure_inputs_LOCAL_ONLY`. Those builders consume the retained `SOURCE.json`, named pixel arrays and numeric tables.

For a **different selected case**, this exporter supplies freshly checked `RESULT.json`, `PIXELS.npz` and single-frame previews. These are not drop-in inputs to `build_integrated.py`: metadata, array names and case-specific layouts differ. For example, coordinate export uses `raw_<frame>` arrays, whereas the fixed Figure 4 packet uses `frame_<frame>` in `DISPLAY_PIXELS.npz`. A new presentation must use the new result and its actual arrays; the existing figure builders retain the declared manuscript cases. The exporter therefore reproduces the measurement/extraction procedure for other cases, rather than automatically drawing an alternative final manuscript figure.

The controlled `case_reuse_LOCAL_ONLY` companion includes relative configurations under `configs/` and their necessary files under `inputs/`. From the repository root, run the exporter with the absolute path to a chosen JSON in `configs/` and a new output directory; no files are written into the companion. The expected original and alternative readouts are retained with that companion and in Source Data Table 59.

| `kind` | Required input fields in addition to `case_id` | Recomputed evidence |
|---|---|---|
| `coordinates` | `reference`, `reference_ids`, `raw`, `scale_um_zyx`, `before` and `after` objects with `graph`/`report` | Selected reference path, fresh frame families and independent family equality, canonical map equality, saved directed pairs, real z-slab projection |
| `pulse` | `movie`, `frames`, `reference_labels`, `reference_type`, `archive`, `predictions` mapping arm names to NPZs | Strict IoU mask matches, literal raw pairs and saved continuation/division types |
| `native` | `movie`, `frames`, `reference_labels`, `reference_type`, `archive`, two `states` files, `graph` | Shared previous-return anchor, all four current mask states, pairs/types and history |
| `epithelial` | `frames`, `reference_label`, `raw`, `reference`, `stages` mapping each stage to `masks`/`graph` | Strict IoU matches and actual saved graph pairs at all stages |

Optional `expected_typed_history` (native) or `expected_history` (epithelial) checks
the fresh result against a retained identity record. Ambiguous mask matches cause
explicit refusal by this singleton-case renderer; it does not choose a convenient
mask. Coordinate checks certify the selected frames, not the entire comparison.

Coordinates use normalized micrometres and the caller-declared image scale.
Raw coordinate images can be the original Zarr or an NPZ containing losslessly
copied complete ZYX arrays named `frame_<acquisition-index>`. An absent requested
frame is refused; no image padding or invented intensities replace it. The controlled
case companion records original array identities for this storage conversion.
Epithelial raw TIFF axes are read from series metadata: `TYX` is one channel per
frame; `TCYX` uses its actual channel count. The retained series have one, two and
three channels respectively. A static `CYX` image or an out-of-range acquisition
index is rejected by this temporal-case entry. Bacterial TIFF RGB channels
must be exact repeats of the same grayscale channel. Native states retain original
row identities; pulse predictions use their saved label IDs. The JSON schemas are
specific to these input formats, not a universal adapter for arbitrary trackers.

The manuscript examples were selected after complete cohort analysis: an adjacent
gain/loss, an affected pulse window, the one natural typed relabel, and one member
of an exhaustive eight-identity exchange set. They illustrate mechanisms rather
than estimate frequencies. A separately frozen seed selected 12 other cases,
including null cases; see the paper's Source Data Table 59 for selection and all
readouts. All 12 alternatives and the four original examples also reproduced
their readouts and decoded arrays from copied necessary inputs with relative
configurations on the same host. The exporter rebuilds correspondence evidence and measures saved
predictions; it does not run the upstream tracker or create microscopy images.
