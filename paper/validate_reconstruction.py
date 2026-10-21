"""Compare freshly calculated scientific records with retained research outputs.

Targets are read only after calculation. Known-result reconstruction, not a
blind validation, training experiment or evaluation of publication readiness.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import sys
import numpy as np
import tifffile

HERE = Path(__file__).resolve().parent


def read(p):
    if p.suffix == ".jsonl":
        return [json.loads(line) for line in p.read_text(encoding="utf-8-sig").splitlines()]
    return json.loads(p.read_text(encoding="utf-8-sig"))


def sha(p):
    with p.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def differences(a, b, where="$"):
    if type(a) is not type(b):
        return [{"field": where, "reason": "type"}]
    if isinstance(a, dict):
        result = []
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                result.append({"field": where + "." + k, "reason": "missing_key"})
            else:
                result.extend(differences(a[k], b[k], where + "." + k))
        return result
    if isinstance(a, list):
        if len(a) != len(b):
            return [{"field": where, "reason": "length", "old": len(a), "new": len(b)}]
        return [r for i, (x, y) in enumerate(zip(a, b)) for r in differences(x, y, f"{where}[{i}]")]
    return [] if a == b else [{"field": where, "reason": "value", "old": a, "new": b}]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=HERE / "local_config.json")
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    a = parser.parse_args()
    cfg = read(a.config); companion = Path(cfg["companion_root"])
    cleanup = cfg.get("cleanup_records_root")
    duplicate_index = {}
    current = lambda p: Path(p)
    if cleanup:
        cleanup = Path(cleanup)
        sys.path.insert(0, str(cleanup / "深层目录整理"))
        from path_locations import current_path, all_moves
        current = current_path
        workspace = cleanup.parents[1]
        moves = all_moves()
        def original(p):
            p = Path(p)
            for m in sorted(moves, key=lambda m: -len(m["destination"])):
                q = Path(m["destination"])
                if p == q or q in p.parents:
                    return Path(m["source"]) / p.relative_to(q)
            return p
        for name in ["duplicate_payload_deletion_manifest.json", "organized_mirror_deletion_manifest_v2.json", "remaining_mirror_deletion_manifest.json"]:
            for row in read(cleanup / name)["deletions"]:
                duplicate_index[os.path.normcase(str(workspace / row["target"]))] = row
        def resolve(p, depth=0):
            p = current(p)
            if p.is_file():
                return p
            if depth > 10:
                raise FileNotFoundError(p)
            row = duplicate_index.get(os.path.normcase(str(original(p))))
            if not row:
                raise FileNotFoundError(p)
            retained = Path(row["retained"])
            return resolve(retained if retained.is_absolute() else workspace / retained, depth + 1)
    else:
        resolve = lambda p: Path(p)
    routes = {}; records = []

    def compare(route, target, actual, selector=None, allowed_location=False):
        target = resolve(target)
        x, y = read(target), read(actual)
        if selector:
            x, y = selector(x), selector(y)
        diff = differences(x, y)
        location = []
        if allowed_location:
            location = [d for d in diff if d["field"].endswith(".prediction_track_path")]
            diff = [d for d in diff if not d["field"].endswith(".prediction_track_path")]
            # Scientific rows still compare their exact input SHA256 and IDs.
            for d in location:
                if str(d["old"]).replace("\\", "/").split("/external_trajectory_intervention_v0.1/")[-1] != str(d["new"]).replace("\\", "/").split("/external_trajectory_intervention_v0.1/")[-1]:
                    diff.append(d)
        records.append({"route": route, "target": str(target), "actual": str(actual),
                        "target_sha256": sha(target), "actual_sha256": sha(actual),
                        "equal_scientific_records": not diff, "differences": diff,
                        "relocated_input_path_fields": location,
                        "identity_rows": len(x) if isinstance(x, list) else None})

    aliases = {"pulse": "bacterial-pulse-endpoint", "initial": "bacterial-initial-overlays"}
    for folder in sorted(a.runs.iterdir()):
        if folder.is_dir() and (folder / "COMPLETE.json").is_file():
            r = read(folder / "COMPLETE.json")
            routes[r["route"]] = {"status": "已实跑；科学记录比较另列", "output": str(folder), "elapsed_seconds": r["elapsed_seconds"]}
    target_root = companion / "inputs_LOCAL_ONLY/bacterial/results"
    for route, target_dir, actual_dir, pattern in [
        ("bacterial-full", "full_run01", "bacterial-full", "measurement/{film}_results.json"),
        ("bacterial-natural", "natural_run01", "bacterial-natural", "measurement/{film}_edge_records.jsonl"),
        ("bacterial-timing", "timing_run01", "bacterial-timing", "measurement/{film}_EVENTS.json"),
        ("bacterial-chains", "chains_run01", "bacterial-chains", "measurement/{film}_RECORDS.json"),
        ("bacterial-pulse-endpoint", "pulse-endpoint_run02", "pulse", "{film}_ENDPOINT.json"),
    ]:
        if route not in routes: continue
        for i in range(1, 30):
            rel = pattern.format(film=f"{i:02}")
            compare(route, target_root / target_dir / rel, a.runs / actual_dir / "measurement" / rel)
    if "bacterial-common" in routes:
        compare("bacterial-common", target_root / "common_run01/RESULT.json", a.runs / "bacterial-common/measurement/RESULT.json")
    if "bacterial-cca" in routes:
        compare("bacterial-cca", target_root / "cca_run01/measurement/IDENTITIES_AND_LENGTHS.json",
                a.runs / "bacterial-cca/measurement/measurement/IDENTITIES_AND_LENGTHS.json", allowed_location=True)
    if "bacterial-initial-overlays" in routes:
        rel = "work/native_noisy_validation_v0.3/case_records.json"
        compare("bacterial-initial-overlays", target_root / "initial-overlays_run01" / rel, a.runs / "initial/measurement" / rel)
        rel = "final_observation_classes/RESULT.json"
        compare("bacterial-initial-overlays", target_root / "initial-overlays_run01" / rel, a.runs / "initial/measurement" / rel,
                selector=lambda x: {k: v for k, v in x.items() if k != "UTC"})
    if "bacterial-division-overlays" in routes:
        for name in ["CASE_RECORDS.json", "TARGET_ELIGIBILITY.json"]:
            compare("bacterial-division-overlays", target_root / "division-overlays_run01/measurement" / name,
                    a.runs / "bacterial-division-overlays/measurement/measurement" / name)
    if "bacterial-stage-archive" in routes:
        for name in ["IDENTITIES.json", "PULSE_LOSS_IDENTITIES.json", "WITHHELD.json"]:
            compare("bacterial-stage-archive", target_root / "stage-archive_run01" / name, a.runs / "bacterial-stage-archive/measurement" / name)
    if "epithelial" in routes:
        for name in [f"movie{i}_complete_result.json" for i in range(1, 5)]:
            compare("epithelial", companion / "expected/public/reference_measurement" / name,
                    a.runs / "epithelial/measurement/reference_measurement" / name)
        for movie in range(1, 5):
            for stage in range(4):
                rel = f"raw_stages/movie{movie}/S{stage}"
                compare("epithelial", companion / "expected/public" / (rel + "_graph.json"),
                        a.runs / "epithelial/measurement" / (rel + "_graph.json"))
                old = resolve(companion / "expected/public" / (rel + "_labels.tif"))
                new = a.runs / "epithelial/measurement" / (rel + "_labels.tif")
                equal = np.array_equal(tifffile.imread(old), tifffile.imread(new))
                records.append({"route": "epithelial", "target": str(old), "actual": str(new), "equal_scientific_records": equal,
                                "differences": [] if equal else ["label arrays differ"]})
    if "typed-constructed" in routes:
        for path in sorted((a.runs / "typed-constructed").glob("*/RESULT.json")):
            for conv in ["per_view_product", "same_map_identical_snapshots"]:
                if path.parent.name.endswith("_" + conv):
                    name = path.parent.name.removesuffix("_" + conv) + "__" + conv
                    compare("typed-constructed", companion / "expected/typed" / name / "RESULT.json", path,
                            selector=lambda x: {k: v for k, v in x.items() if k not in ["time_seconds", "input_path"]})
    v = companion.parent
    if "common-family-census" in routes:
        for name in ["ALL96_FILM_ARM_CENSUS.json", "ALL_FRAME_CERTIFICATES.json", "ALL_PATH_REPORTS.json"]:
            compare("common-family-census", v / "02_实验复现与验证/common_carrier_family_census_r2" / name,
                    a.runs / "common-family-census/measurement" / name)
    if "analyst-path" in routes:
        compare("analyst-path", v / "02_实验复现与验证/analyst_usecase_r2/actual_natural_statement_01/REPORT.json",
                a.runs / "analyst-path/measurement/REPORT.json")
    if "identity-crosswalk" in routes:
        target = v / "02_实验复现与验证/full_relocated_integration_r2/actual_complete_run_03/bacterial/identity_crosswalk"
        for name in ["ALL123_WRONG_TYPE_RELATION_EVENT_CROSSWALK.json", "EVENT_UNITS.json", "ALL30_STRICT_CHAIN_INCOMING_EVENT_CROSSWALK.json", "FIGURE4_EXACT_SINGLE_RELATION_AND_COMPANION_TYPE_TABLE.json", "RESULT.json"]:
            compare("identity-crosswalk", target / name, a.runs / "identity-crosswalk/measurement" / name)
    if "natural3d" in routes:
        compare("natural3d", v / "02_实验复现与验证/full_relocated_integration_r2/actual_complete_run_03/natural/REPORT_DECISION_YIELD.json",
                a.runs / "natural3d/measurement/REPORT_DECISION_YIELD.json")
        routes["natural3d"]["embedded_full_comparison"] = read(a.runs / "natural3d/measurement/COMPLETE_SCIENTIFIC_COMPARISON.json")
    for name, row in routes.items():
        checks = [r for r in records if r["route"] == name]
        row["compared_record_units"] = len(checks)
        if checks:
            row["status"] = "已实跑且所列完整科学记录相等" if all(r["equal_scientific_records"] for r in checks) else "已实跑但比较有差异；见报告"
    result = {"scope": "Local known-result scientific reconstruction; exact fields/arrays except explicitly reported relocated paths and execution time",
              "remote_updated": False, "new_biological_N": 0, "new_model_inference": False,
              "routes": routes, "comparisons": records,
              "all_compared_records_equal": all(r["equal_scientific_records"] for r in records),
              "comparison_units": len(records), "not_full_lifecycle_or_clean_machine_validation": True}
    with a.report.open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps({"completed_routes": len(routes), "comparisons": len(records), "all_equal": result["all_compared_records_equal"]}))


if __name__ == "__main__":
    main()
