"""Rebuild the source-duty proposal allocation from fixed graphs and image scores.

Image scores are explicit frozen inputs. No image-model inference is claimed.
Proposal production, veto application and cap/ownership allocation are executed.
"""
from pathlib import Path
import argparse
import ast
from collections import defaultdict
import importlib.util
import json
import sys

from historical import read, write, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args(); c = read(a.config); a.output.mkdir(parents=True, exist_ok=False)
    root = Path(c["runtime_root"]) / "inputs_LOCAL_ONLY/bacterial"
    source = root / "sources/source_duty/executed_producer.py"
    spec = importlib.util.spec_from_file_location("proposal_source", root / "sources/source_duty/real_S3_policy_sensitivity_v0.1/run_sensitivity.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    m.SOURCE = source
    graphs = Path(c["bacterial_input_root"]) / "article_strengthening_20261004_v1/reproduction_LOCAL_ONLY_v0.1/3d_original_pixel_stage_exports"
    score_path = Path(c["allocation_scores"])
    score = read(score_path)
    assert score["source_sha256"] == sha(source)
    lookup = {}
    for row in score["rows"]:
        for q in row["scores"]:
            key = (row["film"], row["frame"], *q["point"])
            if key in lookup:
                assert lookup[key] == q["score"]
            lookup[key] = q["score"]
    ns, env = m.producer_namespace()
    function = next(n for n in ast.parse(source.read_text(encoding="utf-8-sig")).body
                    if isinstance(n, ast.FunctionDef) and n.name == "add_safe_divisions_postlink")

    class Observe(ast.NodeTransformer):
        hits = 0

        def visit_Expr(self, node):
            if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) and ast.unparse(node.value.func) == "proposals.append":
                self.hits += 1
                extra = ast.parse("_TRACE.append(dict(frame=int(t), score=float(score), source=int(source_id), target=int(candidate_id), parent_distance=float(parent_dist), sister_distance=float(sister_dist), frame_cap=int(frame_cap), global_cap=int(global_cap)))").body[0]
                return [node, extra]
            return self.generic_visit(node)

    observer = Observe(); function = observer.visit(function); ast.fix_missing_locations(function)
    assert observer.hits == 1
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), ns)
    rows = []; queries = []; bindings = {"scores": sha(score_path), "producer": sha(source)}
    for film in sorted(p for p in graphs.iterdir() if p.is_dir()):
        before = film / "S2_gap_closing.npz"; after = film / "S3_safe_divisions.npz"
        nodes, edges = m.load_graph(before); n3, e3 = m.load_graph(after); assert nodes == n3
        bindings[film.name + "/S2"] = sha(before); bindings[film.name + "/S3"] = sha(after)
        ns["_TRACE"] = []; ns["deepcenter_accept_repair_point"] = lambda *args: True
        ns["add_safe_divisions_postlink"](nodes, edges, defaultdict(int), dataset=film.name)
        proposals = list(ns["_TRACE"])

        def veto(dataset, frame, point, bundle, frames, heatmaps, stats, prefix, threshold):
            key = (dataset, int(frame), *map(float, point)); value = lookup[key]
            accepted = value >= threshold
            stats["deepcenter_" + prefix + "_checked"] += 1
            stats["deepcenter_" + prefix + ("_accepted" if accepted else "_rejected")] += 1
            queries.append({"film": dataset, "frame": int(frame), "point": list(point), "score": value, "accepted": accepted})
            return accepted

        ns["_TRACE"] = []; ns["deepcenter_accept_repair_point"] = veto
        result = ns["add_safe_divisions_postlink"](nodes, edges, defaultdict(int), dataset=film.name)
        origin = {(x["source_id"], x["target_id"]) for x in edges}
        replay = {(x["source_id"], x["target_id"]) for x in result} - origin
        historical = {(x["source_id"], x["target_id"]) for x in e3} - origin
        accept_all_groups = defaultdict(list)
        for q in proposals:
            accept_all_groups[q["frame"]].append(q)
        ordered = []; all_selected = set(); all_sources = set(); all_targets = set()
        for frame in sorted(accept_all_groups):
            count = 0
            for q in sorted(accept_all_groups[frame], key=lambda x: x["score"]):
                pair = (q["source"], q["target"])
                if len(all_selected) >= q["global_cap"]: reason = "global_cap"
                elif count >= q["frame_cap"]: reason = "frame_cap"
                elif q["target"] in all_targets: reason = "target_used"
                elif q["source"] in all_sources: reason = "source_used"
                else:
                    reason = "accepted"; all_selected.add(pair)
                    all_sources.add(q["source"]); all_targets.add(q["target"]); count += 1
                ordered.append({**q, "allocation": reason, "historical_addition": pair in historical})
        groups = defaultdict(list)
        for order, proposal in enumerate(ordered):
            point = list(map(float, [nodes[proposal["target"]][k] for k in ["z", "y", "x"]]))
            value = lookup[(film.name, int(nodes[proposal["target"]]["t"]), *point)]
            groups[proposal["frame"]].append({**proposal, "point": point, "image_score": value,
                                             "image_accepted": value >= .25, "trace_order": order})
        selected = []; used_source = set(); used_target = set(); ledger = []
        for frame in sorted(groups):
            count = 0
            for q in sorted(groups[frame], key=lambda x: (x["score"], x["trace_order"])):
                q["global_selected_before"] = len(selected); q["frame_selected_before"] = count
                if not q["image_accepted"]: reason = "image_veto"
                elif len(selected) >= q["global_cap"]: reason = "global_cap"
                elif count >= q["frame_cap"]: reason = "frame_cap"
                elif q["target"] in used_target: reason = "target_used"
                elif q["source"] in used_source: reason = "source_used"
                else:
                    reason = "accepted"; selected.append((q["source"], q["target"]))
                    used_source.add(q["source"]); used_target.add(q["target"]); count += 1
                ledger.append({**q, "independent_decision": reason})
        assert set(selected) == replay == historical
        rows.append({"film": film.name, "independent_expected_winners": sorted(selected),
                     "proposal_decision_ledger": ledger, "exact_archived_parity": True})
    write(a.output / "decision_ledger.json", {"result_rows": rows, "input_bindings": bindings,
          "proposals": sum(len(x["proposal_decision_ledger"]) for x in rows),
          "expected_winners": sum(len(x["independent_expected_winners"]) for x in rows),
          "image_score_invocations": len(queries), "unique_image_scores": len(lookup),
          "image_scores_are_frozen_inputs": True, "new_image_model_inference": False})
    # Freeze the complete computed ledger before opening historical answers.
    expected = read(root / "inputs_LOCAL_ONLY/decision_ledger.json")
    assert read(a.output / "decision_ledger.json")["result_rows"] == expected["result_rows"]
    write(a.output / "COMPARISON.json", {"all8_complete_ledgers_equal": True,
          "computed_ledger_sha256": sha(a.output / "decision_ledger.json")})
    print(json.dumps({"films": len(rows), "proposals": sum(len(x["proposal_decision_ledger"]) for x in rows),
          "winners": sum(len(x["independent_expected_winners"]) for x in rows), "complete_ledger_equal": True}))


if __name__ == "__main__":
    main()
