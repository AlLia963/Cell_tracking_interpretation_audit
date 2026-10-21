"""Explicit-path local CLI. No dataset discovery, uploads, or implicit outputs."""
import argparse
import hashlib
from pathlib import Path
import sys

from . import (__version__, account_from_mapping_families, account_typed_from_matches,
               coupled_aggregate_bounds, history_features,
               match_coordinates, match_masks_iou, disjoint_mask_options)
from .joint_history import account_joint_history_components
from .io import (load_families_json, load_graph_json,
                 load_mask_json, load_typed_inputs, read_json, write_new_json)


def _inputs(args):
    if args.command == "joint-history":
        paths = [args.joint_family]
    else:
        paths = [args.reference]
        if getattr(args, "stage", None):
            paths.extend(args.stage)
            if args.command == "typed-history":
                paths.extend([args.matches, args.types])
            else:
                paths.append(args.families)
        else:
            paths.append(args.pred)
    captured = {}
    receipts = []
    for path in paths:
        key = str(path)
        if key not in captured:
            captured[key] = Path(path).read_bytes()
        receipts.append({"argument_path": key,
                         "sha256": hashlib.sha256(captured[key]).hexdigest()})
    return receipts, captured


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
    joint = commands.add_parser("joint-history", help="Read caller-declared complete joint visibility components; no mapping inference")
    joint.add_argument("--joint-family", required=True, type=Path)
    joint.add_argument("--configuration-cap", type=int, default=65536)
    joint.add_argument("--output", required=True, type=Path)
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
        if args.command == "natural-ctc":
            from .ctc_natural import run_natural
            return run_natural(args.manifest, args.archive, args.support_root, args.output)
        receipts, source_bytes = _inputs(args)
        declaration = None
        if args.command == "joint-history":
            joint = read_json(args.joint_family, source_bytes=source_bytes)
            result = account_joint_history_components(joint, max_configurations_per_component=args.configuration_cap)
            declaration = {key: joint[key] for key in ("completeness_asserted_by_caller", "product_factorization_asserted_by_caller", "joint_family_rule")}
        elif args.command in ("family-history", "coupled-bounds"):
            reference = load_graph_json(args.reference, source_bytes=source_bytes)
            stages = [load_graph_json(path, source_bytes=source_bytes) for path in args.stage]
            families, declaration = load_families_json(args.families, source_bytes=source_bytes)
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
            matches, types = load_typed_inputs(args.matches, args.types, source_bytes=source_bytes)
            result = {"records": account_typed_from_matches(
                [load_graph_json(path, source_bytes=source_bytes) for path in args.stage], load_graph_json(args.reference, source_bytes=source_bytes), matches,
                stage_division_edges=types["stage_division_edges"],
                reference_division_edges=types["reference_division_edges"],
                relation_type=args.relation, ambiguity_status=args.ambiguity),
                "typed_history_alternatives_enumerated": False,
                "type_inference_performed": False,
                "biological_event_validity_certified": False}
        elif args.command == "coordinate-match":
            result = {"mapping_pairs": sorted(match_coordinates(
                load_graph_json(args.pred, source_bytes=source_bytes), load_graph_json(args.reference, source_bytes=source_bytes), args.radius).items()),
                "all_optimal_alternatives_enumerated": False,
                "semantic_types_supported": False}
        else:
            pred = load_mask_json(args.pred, source_bytes=source_bytes)
            reference = load_mask_json(args.reference, source_bytes=source_bytes)
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
        envelope = {"package": "stage-resolved-tracking-audit", "version": __version__,
                    "command": args.command, "input_receipts": receipts,
                    "family_declaration": declaration, "result": result}
        write_new_json(args.output, envelope)
    except (ValueError, TypeError, KeyError, OverflowError, OSError) as error:
        print(f"ERROR: {type(error).__name__}: {error}", file=sys.stderr)
        return 2
    print(str(args.output))
    return 0
