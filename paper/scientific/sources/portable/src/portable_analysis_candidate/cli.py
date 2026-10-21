"""Explicit-path local CLI. No dataset discovery, uploads, or implicit outputs."""
import argparse
import hashlib
from pathlib import Path
import sys

from . import (__version__, account_from_mapping_families, account_typed_from_matches,
               coupled_aggregate_bounds, history_features,
               match_coordinates, match_masks_iou, disjoint_mask_options)
from .io import (load_families_json, load_graph_json,
                 load_mask_json, load_typed_inputs, write_new_json)


def _inputs(args):
    paths = [args.reference]
    if getattr(args, "stage", None):
        paths.extend(args.stage)
        if args.command == "typed-history":
            paths.extend([args.matches, args.types])
        else:
            paths.append(args.families)
    else:
        paths.append(args.pred)
    return [{"argument_path": str(path),
             "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}
            for path in paths]


def build_parser():
    parser = argparse.ArgumentParser(
        description="Reference-relative coordinate histories/bounds and separate mask-instance matching")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("family-history", "coupled-bounds"):
        command = commands.add_parser(name)
        command.add_argument("--reference", required=True, type=Path)
        command.add_argument("--stage", required=True, action="append", type=Path,
                             help="Repeat in pipeline order; at least two stages")
        command.add_argument("--families", required=True, type=Path)
        command.add_argument("--output", required=True, type=Path,
                             help="New output file; existing files are refused")
        if name == "family-history":
            command.add_argument("--history-cap", type=int, default=4096)
        else:
            command.add_argument("--assignment-cap", type=int, default=65536)
    typed = commands.add_parser("typed-history")
    typed.add_argument("--reference", required=True, type=Path)
    typed.add_argument("--stage", required=True, action="append", type=Path)
    typed.add_argument("--matches", required=True, type=Path)
    typed.add_argument("--types", required=True, type=Path)
    typed.add_argument("--relation", required=True, choices=("continuation", "division"))
    typed.add_argument("--ambiguity", required=True,
                       choices=("not_assessed", "ambiguous", "unique_under_declared_rule"))
    typed.add_argument("--output", required=True, type=Path)
    for name, option in (("coordinate-match", "radius"), ("mask-match", "gate"), ("mask-envelope", None)):
        command = commands.add_parser(name)
        command.add_argument("--reference", required=True, type=Path)
        command.add_argument("--pred", required=True, type=Path)
        if option is not None:
            command.add_argument(f"--{option}", required=True, type=float)
        command.add_argument("--output", required=True, type=Path)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        receipts = _inputs(args)
        declaration = None
        if args.command in ("family-history", "coupled-bounds"):
            reference = load_graph_json(args.reference)
            stages = [load_graph_json(path) for path in args.stage]
            families, declaration = load_families_json(args.families)
            if args.command == "family-history":
                result = account_from_mapping_families(
                    stages, reference, families,
                    cross_stage_constraints=declaration["cross_stage_constraints"],
                    max_histories_per_edge=args.history_cap)
            else:
                result = coupled_aggregate_bounds(
                    stages, reference, families, history_features,
                    cross_stage_constraints=declaration["cross_stage_constraints"],
                    max_assignments_per_component=args.assignment_cap)
        elif args.command == "typed-history":
            matches, types = load_typed_inputs(args.matches, args.types)
            result = {"records": account_typed_from_matches(
                [load_graph_json(path) for path in args.stage], load_graph_json(args.reference), matches,
                stage_division_edges=types["stage_division_edges"],
                reference_division_edges=types["reference_division_edges"],
                relation_type=args.relation, ambiguity_status=args.ambiguity),
                "typed_history_alternatives_enumerated": False,
                "type_inference_performed": False,
                "biological_event_validity_certified": False}
        elif args.command == "coordinate-match":
            result = {"mapping_pairs": sorted(match_coordinates(
                load_graph_json(args.pred), load_graph_json(args.reference), args.radius).items()),
                "all_optimal_alternatives_enumerated": False,
                "semantic_types_supported": False}
        else:
            pred = load_mask_json(args.pred)
            reference = load_mask_json(args.reference)
            if pred.support_definition != reference.support_definition:
                raise ValueError("CLI requires equal support-definition declarations; this does not certify support comparability")
            if args.command == "mask-envelope":
                result = {"optimal_reference_id_options": [
                    [rid, list(options)] for rid, options in sorted(disjoint_mask_options(pred, reference).items())],
                    "gate": "strict_IoU_greater_than_one_half",
                    "reference_support_contract": "disjoint",
                    "support_comparability_certified_by_module": False,
                    "coordinate_matching_envelope": False,
                    "semantic_types_inferred": False}
            else:
                result = {"mapping_pairs": sorted(match_masks_iou(pred, reference, gate=args.gate).items()),
                          "support_comparability_certified_by_module": False,
                          "all_optimal_alternatives_enumerated": False,
                          "semantic_types_supported": False}
        envelope = {"package": "portable-analysis-candidate", "version": __version__,
                    "command": args.command, "input_receipts": receipts,
                    "family_declaration": declaration, "result": result}
        write_new_json(args.output, envelope)
    except (ValueError, TypeError, KeyError, OverflowError, OSError) as error:
        print(f"ERROR: {type(error).__name__}: {error}", file=sys.stderr)
        return 2
    print(str(args.output))
    return 0
