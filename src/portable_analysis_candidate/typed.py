"""Explicit external type views; no unified coordinate/mask family estimator."""
import numpy as np

from ._upstream.stage_accounting import Graph, account_from_matches
from ._upstream.exact_disjoint_envelope import envelope, edge_envelope
from ._upstream.typed_pathways import annotate_typed_pathways


def disjoint_mask_options(pred, reference):
    """Optimal mask-ID domains for disjoint reference supports at strict IoU > 1/2.

    Prediction supports may overlap. Pixel registration and biological support
    meaning are caller duties. This is not a coordinate-matching envelope.
    """
    if pred.support_definition != reference.support_definition:
        raise ValueError("Equal support-definition declarations required; comparability is not certified")
    return envelope(pred, reference)


def mask_edge_visibility_envelope(source_options, target_options, edges, *, relation_scope):
    """Certain/possible visibility for explicitly selected edge relation.

    Options must be optimal mask-ID domains at adjacent frames under the
    disjoint-reference rule. No history or coupled aggregate is inferred here.
    """
    if relation_scope not in ("untyped", "continuation", "division"):
        raise ValueError("Explicit untyped/continuation/division relation scope required")
    return edge_envelope(source_options, target_options, set(map(tuple, edges)))


def _view(graph, division_edges):
    edges = set(map(tuple, graph.edges.tolist()))
    divisions = set()
    for pair in division_edges:
        if len(pair) != 2 or any(
            isinstance(v, (bool, np.bool_)) or not isinstance(v, (int, np.integer))
            for v in pair
        ):
            raise ValueError("Division labels require integer endpoint pairs")
        item = tuple(map(int, pair))
        if item in divisions:
            raise ValueError("Duplicate division relation label")
        divisions.add(item)
    if not divisions.issubset(edges):
        raise ValueError("Division labels must be a subset of raw directed edges")
    return {"edges": edges, "division": divisions}


def _subset(graph, view, relation_type):
    selected = view["division"] if relation_type == "division" else view["edges"] - view["division"]
    return Graph(graph.ids, graph.coords,
                 np.asarray(sorted(selected), dtype=np.int64).reshape(-1, 2), graph.unit)


def account_typed_from_matches(stages, reference, matches, *, stage_division_edges,
                               reference_division_edges, relation_type, ambiguity_status):
    """Typed subset history with raw-edge provenance under caller-supplied maps.

    All raw edges must be explicitly classifiable as division or continuation
    (the complement). Types are external edge views, not Graph or mask fields.
    `ambiguity_status` is a caller declaration. Unknown or ambiguous
    correspondence withholds pathway uniqueness; it does not enumerate typed
    history alternatives. Biological event validity is not certified.
    """
    if relation_type not in ("continuation", "division"):
        raise ValueError("Explicit continuation/division relation required")
    if ambiguity_status not in ("not_assessed", "ambiguous", "unique_under_declared_rule"):
        raise ValueError("Explicit correspondence ambiguity status required")
    if len(stages) != len(stage_division_edges):
        raise ValueError("One division-edge view per ordered stage required")
    views = [_view(graph, divisions) for graph, divisions in zip(stages, stage_division_edges)]
    reference_view = _view(reference, reference_division_edges)
    records = account_from_matches(
        [_subset(graph, view, relation_type) for graph, view in zip(stages, views)],
        _subset(reference, reference_view, relation_type), matches)
    for record in records:
        record["kind"] = relation_type
        record["ambiguous_correspondence"] = ambiguity_status != "unique_under_declared_rule"
        record["correspondence_ambiguity_status_declared_by_user"] = ambiguity_status
        record["correspondence_uniqueness_certified_by_module"] = False
    return annotate_typed_pathways(records, views)
