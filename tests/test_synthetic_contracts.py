"""Meaningful constructed-contract checks; no production expected outputs."""
import itertools
from pathlib import Path
import unittest

from portable_analysis_candidate import (
    Graph, MaskFrame, account_from_mapping_families, account_typed_from_matches,
    coupled_aggregate_bounds, disjoint_mask_options, history_features,
    mask_edge_visibility_envelope, match_coordinates, match_masks_iou)
from portable_analysis_candidate.io import (
    load_families_json, load_graph_json, load_mask_json, load_typed_inputs)


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


class ConstructedContracts(unittest.TestCase):
    def coordinate_inputs(self):
        stages = [load_graph_json(EXAMPLES / f"coordinate_stage_{k}.json") for k in (0, 1)]
        reference = load_graph_json(EXAMPLES / "coordinate_reference.json")
        families, declaration = load_families_json(EXAMPLES / "coordinate_families.json")
        return stages, reference, families, declaration["cross_stage_constraints"]

    def test_shared_endpoint_coupling_matches_independent_brute_force(self):
        stages, reference, families, constraint = self.coordinate_inputs()
        actual = coupled_aggregate_bounds(stages, reference, families, history_features,
                                          cross_stage_constraints=constraint)
        # Direct whole-map enumeration is independent of component factorization.
        totals = []
        for whole_maps in itertools.product(*families):
            missing = 0
            for a, b in reference.edges:
                mapping = whole_maps[-1]
                missing += (mapping.get(int(a)), mapping.get(int(b))) not in set(map(tuple, stages[-1].edges.tolist()))
            totals.append(missing)
        bounds = actual["scalar_bounds"]["final_missing"]
        self.assertEqual((bounds["minimum"], bounds["maximum"]), (min(totals), max(totals)))
        self.assertEqual(set(totals), {1})
        histories = account_from_mapping_families(stages, reference, families,
                                                  cross_stage_constraints=constraint)
        self.assertTrue(all(record["admissible_visibility_strings"] == ["10", "11"]
                            for record in histories["records"]))
        self.assertFalse(actual["family_completeness_certified_by_module"])

    def test_caps_withhold_and_joint_stage_constraints_refused(self):
        stages, reference, families, constraint = self.coordinate_inputs()
        bounded = coupled_aggregate_bounds(stages, reference, families, history_features,
                                           cross_stage_constraints=constraint,
                                           max_assignments_per_component=1)
        self.assertEqual(bounded["status"], "WITHHELD_COMPONENT_ENUMERATION_CAP")
        self.assertIsNone(bounded["scalar_bounds"])
        history = account_from_mapping_families(stages, reference, families,
                                                cross_stage_constraints=constraint,
                                                max_histories_per_edge=1)
        self.assertTrue(all(r["status"] == "WITHHELD_HISTORY_CAP" for r in history["records"]))
        with self.assertRaises(ValueError):
            account_from_mapping_families(stages, reference, families,
                                          cross_stage_constraints="shared_trajectory_constraint")

    def test_coordinate_match_and_units(self):
        stages, reference, _, _ = self.coordinate_inputs()
        self.assertEqual(match_coordinates(stages[0], reference, 0.01), {101: 201, 102: 202, 103: 203})
        changed = Graph(stages[0].ids, stages[0].coords, stages[0].edges, "um")
        with self.assertRaises(ValueError):
            match_coordinates(changed, reference, 1)

    def test_mask_ties_strict_gate_and_disjoint_reference_contract(self):
        pred = load_mask_json(EXAMPLES / "mask_prediction.json")
        reference = load_mask_json(EXAMPLES / "mask_reference.json")
        self.assertEqual(disjoint_mask_options(pred, reference), {401: (501,), 402: (502, 503)})
        self.assertEqual(match_masks_iou(pred, reference, gate=0.75), {401: 501})
        self.assertEqual(mask_edge_visibility_envelope((501,), (502, 503), {(501, 502)},
                                                      relation_scope="division"), (False, True))
        invalid = MaskFrame(reference.ids, reference.masks[[0, 0]], reference.frame,
                            reference.support_definition)
        with self.assertRaises(ValueError):
            disjoint_mask_options(pred, invalid)

    def test_typed_relabel_with_raw_edge_preserved_and_unknown_ambiguity_withheld(self):
        reference = load_graph_json(EXAMPLES / "typed_reference.json")
        stage = load_graph_json(EXAMPLES / "typed_raw_stage.json")
        matches, types = load_typed_inputs(EXAMPLES / "typed_matches.json", EXAMPLES / "typed_views.json")
        kwargs = {"stage_division_edges": types["stage_division_edges"],
                  "reference_division_edges": types["reference_division_edges"],
                  "relation_type": "continuation"}
        records = account_typed_from_matches([stage, stage], reference, matches,
                                             ambiguity_status="unique_under_declared_rule", **kwargs)
        self.assertEqual(records[0]["visibility"], [1, 0])
        event = records[0]["loss_pathways"][0]
        self.assertEqual(event["pathway"], "matched-pair-relation-relabeled")
        self.assertFalse(event["raw_pair_deleted"])
        records = account_typed_from_matches([stage, stage], reference, matches,
                                             ambiguity_status="not_assessed", **kwargs)
        self.assertEqual(records[0]["loss_pathways"][0]["pathway"], "withheld-correspondence-ambiguity")
        self.assertIsNone(records[0]["loss_pathways"][0]["raw_pair_deleted"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
