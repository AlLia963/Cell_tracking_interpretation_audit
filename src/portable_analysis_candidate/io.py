"""Strict JSON adapters. Every source and output path is caller supplied."""
import json
from pathlib import Path

import numpy as np

from . import Graph, MaskFrame


def read_json(path, *, source_bytes=None):
    def reject_constant(value):
        raise ValueError(f"Nonstandard JSON numeric constant: {value}")

    def unique_object(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    # If supplied by the CLI, parse precisely the bytes used for its receipt.
    # Standalone adapters also capture once; no second path read is performed.
    raw = Path(path).read_bytes() if source_bytes is None else source_bytes[str(path)]
    return json.loads(raw.decode("utf-8"), parse_constant=reject_constant,
                      object_pairs_hook=unique_object)


def require_keys(data, keys, context):
    if not isinstance(data, dict) or set(data) != set(keys):
        raise ValueError(f"{context} requires exactly these keys: {sorted(keys)}")


def integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def integer_ids(values, context):
    if not isinstance(values, list) or not all(integer(v) for v in values):
        raise ValueError(f"{context} requires integer JSON IDs; float/bool IDs rejected")
    # Let the upstream schema reject IDs outside signed int64 rather than
    # accepting a float conversion or silently wrapping them.
    array = np.asarray(values) if values else np.empty(0, dtype=np.int64)
    return array


def load_graph_json(path, *, source_bytes=None):
    data = read_json(path, source_bytes=source_bytes)
    require_keys(data, {"ids", "coords", "edges", "unit"}, "Coordinate graph")
    ids = integer_ids(data["ids"], "Coordinate graph")
    edges = data["edges"]
    if not isinstance(edges, list) or any(
        not isinstance(edge, list) or len(edge) != 2 or
        not all(integer(v) for v in edge) for edge in edges
    ):
        raise ValueError("Edges require pairs of integer JSON IDs")
    edge_array = np.asarray(edges) if edges else np.empty((0, 2), dtype=np.int64)
    coords = data["coords"]
    if not isinstance(coords, list) or any(
        not isinstance(row, list) or len(row) != 4 or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) for v in row
        ) for row in coords
    ):
        raise ValueError("coords require numeric [frame,z,y,x] rows; bool rejected")
    coord_array = np.asarray(coords) if coords else np.empty((0, 4), dtype=float)
    return Graph(ids, coord_array, edge_array, data["unit"])


def load_families_json(path, *, source_bytes=None):
    data = read_json(path, source_bytes=source_bytes)
    require_keys(data, {"completeness_asserted_by_user", "correspondence_rule",
                        "cross_stage_constraints", "mapping_families"},
                 "Mapping-family declaration")
    if data["completeness_asserted_by_user"] is not True:
        raise ValueError("Caller must explicitly assert family completeness for its declared rule")
    if not isinstance(data["correspondence_rule"], str) or not data["correspondence_rule"].strip():
        raise ValueError("A nonempty correspondence-rule declaration is required")
    raw_families = data["mapping_families"]
    if not isinstance(raw_families, list) or not raw_families:
        raise ValueError("A nonempty ordered list of mapping families is required")
    families = []
    for family in raw_families:
        if not isinstance(family, list) or not family:
            raise ValueError("Every stage needs a nonempty whole-map family")
        checked = []
        for pairs in family:
            if not isinstance(pairs, list) or any(
                not isinstance(pair, list) or len(pair) != 2 or
                not all(integer(v) for v in pair) for pair in pairs
            ):
                raise ValueError("Every whole map requires a list of integer [reference_id,stage_id] pairs")
            if len({pair[0] for pair in pairs}) != len(pairs):
                raise ValueError("Duplicate reference ID in one whole mapping")
            checked.append(dict(map(tuple, pairs)))
        families.append(checked)
    declaration = {key: data[key] for key in (
        "completeness_asserted_by_user", "correspondence_rule", "cross_stage_constraints")}
    return families, declaration


def load_mask_json(path, *, source_bytes=None):
    data = read_json(path, source_bytes=source_bytes)
    require_keys(data, {"ids", "masks", "frame", "support_definition"}, "Mask instances")
    ids = integer_ids(data["ids"], "Mask instances")
    masks = np.asarray(data["masks"])
    # JSON true/false values only: integer 0/1 supports are rejected.
    if masks.dtype.kind != "b":
        raise ValueError("Mask supports require JSON true/false arrays")
    return MaskFrame(ids, masks, data["frame"], data["support_definition"])


def write_new_json(path, data):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def _pair_list(values, context):
    if not isinstance(values, list) or any(
        not isinstance(pair, list) or len(pair) != 2 or
        not all(integer(v) for v in pair) for pair in values
    ):
        raise ValueError(f"{context} requires integer endpoint-pair lists")
    if len({tuple(pair) for pair in values}) != len(values):
        raise ValueError(f"{context} contains duplicate pairs")
    return values


def load_typed_inputs(matches_path, types_path, *, source_bytes=None):
    maps = read_json(matches_path, source_bytes=source_bytes)
    require_keys(maps, {"stage_matches"}, "Supplied matches")
    if not isinstance(maps["stage_matches"], list):
        raise ValueError("stage_matches requires an ordered list")
    matches = []
    for pairs in maps["stage_matches"]:
        pairs = _pair_list(pairs, "One stage correspondence")
        if len({pair[0] for pair in pairs}) != len(pairs):
            raise ValueError("Duplicate reference ID in supplied match")
        matches.append(dict(map(tuple, pairs)))
    types = read_json(types_path, source_bytes=source_bytes)
    require_keys(types, {"reference_division_edges", "stage_division_edges"}, "Explicit type views")
    _pair_list(types["reference_division_edges"], "Reference division view")
    if not isinstance(types["stage_division_edges"], list):
        raise ValueError("stage_division_edges requires an ordered list")
    for values in types["stage_division_edges"]:
        _pair_list(values, "Stage division view")
    return matches, types
