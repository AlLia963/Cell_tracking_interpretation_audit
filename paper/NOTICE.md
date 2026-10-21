# Manuscript source attribution and rights

`scientific/` contains pinned scientific sources, author-side application code,
and historical source snapshots needed to reconstruct the manuscript analyses.
`SOURCE_INDEX.json` records their bytes; explicit path/CLI adaptations have original
and effective hashes. The original generic library/examples remain MIT-licensed.
The root MIT license does not assert exclusive authorship or relicense every
historical/third-party snapshot in this extension.

Upstream material includes:

- **Cell-TRACTR**, Dunlop laboratory: Apache License 2.0, original upstream source
  [repository](https://gitlab.com/dunloplab/Cell-TRACTR). See
  `licenses/Cell-TRACTR-APACHE-2.0.txt`.
- **TrackFormer**: Apache License 2.0, original upstream
  [repository](https://github.com/timmeinhardt/trackformer). See
  `licenses/TrackFormer-APACHE-2.0.txt`. Original source headers are retained.
- **py-ctcmetrics**, pinned revision
  `59481c48a62d4376fe34bed3e3606b4ec4d60972`: selected event/CCA routines retain
  their implementation/attribution; BSD 2-Clause license, copyright Timo Kaiser.
  See `licenses/py-ctcmetrics-LICENSE.txt` and `licenses/SOURCES.json`.
- Historical community competition-producer snapshots are attributed as source
  dependencies, not as new upstream algorithms or exclusively authored source.
  They do not acquire a blanket MIT grant through inclusion in this repository.

The source-duty producer is the author-instrumented derivative of Igor Zharov's
**Biohub Harmonic Fusion**, released under Apache License 2.0. Its executed bytes
are included in `scientific/inputs_LOCAL_ONLY/bacterial/sources/source_duty/`;
see `licenses/Harmonic-Fusion-NOTICE.md` for ancestry and instrumentation details.

No competition images, coordinates, model weights, private reviewer reports or
raw competition inputs are versioned. The development catalog and focused numerical
records are included under `data/catalog/`. The authorized LOCAL ONLY input
companion and machine-path configurations remain outside Git. Hash-only original
source provenance in that companion is not imported as executable dependency code.

Scientific reconstruction does not reproduce all upstream model training/inference
or certify original-author performance. Publication status and manuscript readiness
are not inferred from software comparisons.
