# Harmonic Fusion source attribution

The archived `inputs_LOCAL_ONLY/bacterial/sources/source_duty/executed_producer.py`
is the author-instrumented stage-export derivative of **Biohub Harmonic Fusion**
by Igor Zharov (flexonafft), published under Apache License 2.0:
https://www.kaggle.com/code/flexonafft/biohub-harmonic-fusion

The notebook builds on the Biohub tracking support and DeepCenter/TemporalUNet
components supplied by pilkwang. Their model/data resources retain their own terms.
The stage-export instrumentation was added for this study. The historical source
bytes are preserved to reproduce allocation decisions from recorded image scores.

Provenance checked 2026-10-14: the retained pre-instrumentation source has 73
top-level function/class definitions. Against the public notebook retrieved from
Kaggle (notebook ID 131620291), 72 definitions are AST-identical; the remaining
definition is `deepcenter_heatmap_for_frame`. This is an ancestry comparison,
not a claim that the current public notebook is the executed historical version.
The executed snapshot is identified by SHA-256 in `SOURCE_INDEX.json`.
