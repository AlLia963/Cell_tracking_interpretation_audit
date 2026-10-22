"""Paper experiment entry point. Local data stay outside the Git source tree.

This command reconstructs measurements; it never uploads, trains, or silently
starts historical GPU inference. Run `list` for the exact route scopes.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def command(argv, cwd, log):
    started = time.perf_counter()
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    with log.with_suffix(".stdout.txt").open("x", encoding="utf-8") as stdout, log.with_suffix(".stderr.txt").open("x", encoding="utf-8") as stderr:
        result = subprocess.run(argv, cwd=cwd, env=env, stdout=stdout, stderr=stderr)
    record = {"argv": list(map(str, argv)), "cwd": str(cwd), "returncode": result.returncode,
              "elapsed_seconds": time.perf_counter() - started}
    write(log.with_suffix(".json"), record)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}); retained logs: {log}")
    return record


def main():
    routes = read(HERE / "routes.json")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("route", choices=["list", *routes])
    parser.add_argument("--config", type=Path, default=HERE / "local_config.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.route == "list":
        for name, route in routes.items():
            print(f"{name:25} {route['kind']}: {route['scope']}")
        return
    if args.output is None:
        parser.error("--output must name a new, absent directory")
    cfg = read(args.config)
    runtime = Path(cfg["runtime_root"])
    out = args.output.resolve()
    # Refuse all outputs within immutable source/data companions, including links.
    for key in ["companion_root", "runtime_root", "natural_input_root", "bacterial_input_root"]:
        protected = Path(cfg[key]).resolve()
        if out == protected or protected in out.parents:
            raise ValueError(f"Output is inside protected input/runtime: {key}")
    out.mkdir(parents=True, exist_ok=False)
    route = routes[args.route]
    started = time.perf_counter()
    calls = []
    # The assembler records every code copy and external directory link. This
    # verifies code once, without repeatedly hashing every microscopy array.
    source_index = read(HERE / "SOURCE_INDEX.json")
    for row in source_index["files"]:
        source_root = Path(cfg.get("controlled_source_root", cfg["companion_root"])) if row.get("distribution") == "controlled_source" else HERE / "scientific"
        source = source_root / row["relative_path"]
        effective = runtime / row["relative_path"]
        if sha(source) != row["sha256"] or sha(effective) != row["sha256"]:
            raise ValueError("Source snapshot changed; rebuild and record its provenance: " + row["relative_path"])
    write(out / "START.json", {"utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "route": args.route, "route_contract": route, "source_index_sha256": sha(HERE / "SOURCE_INDEX.json"),
          "configuration": cfg, "prior_results_known": True, "new_model_inference": False,
          "new_biological_samples": 0, "python": sys.version})
    py = [sys.executable, "-B", "-X", "utf8"]

    def run(script, arguments, label="calculation"):
        calls.append(command([*py, str(runtime / script), *map(str, arguments)], runtime, out / label))

    try:
        name = args.route
        if name in ("historical-geometry", "historical-stress", "common-generate"):
            mode = {"historical-geometry": "geometry", "historical-stress": "stress", "common-generate": "policy-generation"}[name]
            calls.append(command([*py, str(HERE / "adapters/historical.py"), mode, "--config", str(args.config.resolve()), "--output", str(out / "measurement")], HERE.parent, out / "calculation"))
        elif name in ("projection", "historical-negative"):
            calls.append(command([*py, str(HERE / "adapters/extras.py"), name, "--config", str(args.config.resolve()), "--output", str(out / "measurement")], HERE.parent, out / "calculation"))
        elif name in ("allocation-replay", "common-score-generated"):
            adapter = "allocation.py" if name == "allocation-replay" else "common_score.py"
            calls.append(command([*py, str(HERE / "adapters" / adapter), "--config", str(args.config.resolve()), "--output", str(out / "measurement")], HERE.parent, out / "calculation"))
        elif name == "duty-boundary":
            run("inputs_LOCAL_ONLY/bacterial/validate_duty_boundary.py", ["--input-root", cfg["bacterial_input_root"], "--authority", cfg["duty_authority"], "--output", out / "measurement"])
        elif name.startswith("bacterial-"):
            arguments = [route["backend_route"], "--input-root", cfg["bacterial_input_root"], "--output", out / "measurement"]
            if name == "bacterial-duties" and cfg.get("decision_ledger"):
                arguments.extend(["--decision-ledger", cfg["decision_ledger"]])
            run("inputs_LOCAL_ONLY/bacterial/run_archive.py", arguments)
        elif name == "natural3d":
            run("extensions/natural/reproduce_natural.py", ["--input-root", cfg["natural_input_root"], "--output", out / "measurement"])
        elif name == "natural-gates":
            run("extensions/natural/sources/family/reconstruct.py", ["--input-root", cfg["natural_input_root"],
                "--gates", "6", "7", "8", "--output", out / "measurement"])
        elif name == "literal-baseline":
            if "natural_measurement_root" not in cfg:
                raise ValueError("Set natural_measurement_root to a completed natural3d measurement folder")
            run("extensions/natural/literal_constrained_baseline_v03.py", ["--input-root", cfg["natural_input_root"],
                "--compare-family", Path(cfg["natural_measurement_root"]) / "family/gate_07", "--output", out / "measurement"])
        elif name == "epithelial":
            run("sources/public/replay.py", ["--archive", cfg["epithelial_archive"], "--output", out / "measurement"])
        elif name == "operating-envelope":
            run("extensions/operating_envelope/run_operating_envelope.py", ["--output", out / "measurement"])
        elif name == "analyst-path":
            carrier = Path(cfg["common_carrier_root"])
            run("extras/analyst/audit_path_statement.py", ["--reference", carrier / "44b6_12dfb391_reference_pixel.npz",
                "--prediction", carrier / "44b6_12dfb391_unchanged.npz", "--unit", "pixel", "--gate-um", "7",
                "--path", "156000000073", "157000000073", "158000000073", "--proposed-value", "1", "--output", out / "measurement"])
        elif name == "common-family-census":
            # Only top-level path/output bindings differ from the original script.
            # Its objective, cohorts, matching and query bodies are unchanged.
            script = runtime / "extras/run_common_carrier_family_census_r2.py"
            import ast
            tree = ast.parse(script.read_text(encoding="utf-8-sig"))
            namespace = {"__file__": str(script), "__name__": "__paper_census__"}
            overrides = {"V": runtime, "O": out / "measurement", "INPUT": Path(cfg["common_carrier_root"]),
                         "SRC": runtime / "extensions/natural/sources/family"}
            overrides["O"].mkdir()
            for node in tree.body:
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id in overrides:
                    namespace[node.targets[0].id] = overrides[node.targets[0].id]
                elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == "O.mkdir":
                    continue
                else:
                    exec(compile(ast.Module(body=[node], type_ignores=[]), str(script), "exec"), namespace)
            calls.append({"script": str(script), "path_globals_overridden": list(overrides), "execution": "in_process_original_scientific_bodies"})
        elif name == "native16":
            run("inputs_LOCAL_ONLY/bacterial/rematch_stage.py", ["--input-root", cfg["bacterial_input_root"],
                "--native-root-map", runtime / "inputs_LOCAL_ONLY/bacterial/SELECTED_NATIVE_ROOT_MAP.json",
                "--windows", "21:57,21:61,21:62,29:41", "--output", out / "measurement"])
        elif name == "constructed":
            run("prepare_constructed.py", ["--output", out / "inputs"], "generate")
            run("sources/primitive/workflow.py", ["--manifest", out / "inputs/CONSTRUCTED_VARIABLE_VIEWS.json",
                "--input-root", out / "inputs/constructed_inputs", "--output", out / "measurement"], "coordinate")
        elif name == "identity-crosswalk":
            run("inputs_LOCAL_ONLY/bacterial/identity_crosswalk.py", ["--input-root", cfg["bacterial_input_root"],
                "--timing-root", cfg["timing_measurement_root"], "--chains-root", cfg["chains_measurement_root"],
                "--native-window-root", cfg["native_window_root"], "--output", out / "measurement"])
        elif name == "typed-constructed":
            for path in sorted((runtime / "inputs/typed").glob("*.json")):
                for convention in ["per_view_product", "same_map_identical_snapshots"]:
                    label = path.stem + "_" + convention
                    run("sources/typed/evaluate_typed_binary.py", ["--input", path, "--convention", convention,
                        "--output", out / label], label)
            if len(calls) != 8:
                raise RuntimeError("Expected four typed inputs under two conventions")
        else:
            raise NotImplementedError(name)
        write(out / "COMPLETE.json", {"route": name, "processes_completed": calls, "elapsed_seconds": time.perf_counter() - started,
              "completion_meaning": "Declared calculation finished; numerical agreement must be checked against the stated evidence separately",
              "new_inference": False, "new_biological_samples": 0})
    except BaseException:
        write(out / "FAILED.json", {"route": args.route, "traceback": traceback.format_exc(), "partial_outputs_retained": True})
        raise


if __name__ == "__main__":
    main()
