"""Explicit output/data bindings for the manuscript's original historical cohorts.

Scientific bodies and scenario definitions are reused without alteration. These
are known-result reproductions; a new execution freeze is not preregistration.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys


def read(p):
    return json.loads(Path(p).read_text(encoding="utf-8-sig"))


def write(p, x):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("x", encoding="utf-8") as f:
        json.dump(x, f, ensure_ascii=False, indent=2)


def sha(p):
    with Path(p).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def geometry(cfg, out):
    runtime = Path(cfg["runtime_root"])
    original = runtime / "historical_sources/geometry_sensitivity_v0.1/source"
    shutil.copytree(original, out / "source")
    sys.path.insert(0, str(out / "source"))
    s = module(out / "source/sensitivity.py", "sensitivity")
    s.ROOT = out; s.INPUT = Path(cfg["natural_input_root"])
    s.FAMILY = out / "primary"
    baseline = Path(cfg["natural_measurement_root"]) / "family/gate_07"
    # Preserve the old relative layout while using this execution's baseline.
    target = s.FAMILY / "actual_run_v0.1/gate_07"
    target.mkdir(parents=True)
    contracts = ["finite/unconstrained", "finite/geometry_constrained", "numerical/unconstrained"]
    comparisons = []
    for contract in contracts:
        p = baseline / contract / "ALL5751_HISTORY_SETS.json"
        q = target / contract / p.name
        q.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(p, q)
        comparisons.append({"contract": contract, "path": str(q), "sha256": sha(q)})
    scenarios = read(Path(__file__).parents[1] / "protocols/geometry_scenarios.json")
    assert len(scenarios) == 30
    write(out / "SCENARIOS.json", scenarios)
    inputs = []
    films = sorted(p.name for p in s.INPUT.iterdir() if p.is_dir())
    for film in films:
        for p in sorted((s.INPUT / film).glob("*.npz")):
            inputs.append({"film": film, "relative_path": p.relative_to(s.INPUT).as_posix(),
                           "absolute_path": str(p), "sha256": sha(p), "bytes": p.stat().st_size})
    assert len(films) == 8 and len(inputs) == 64
    sources = [{"path": str(p), "sha256": sha(p), "bytes": p.stat().st_size}
               for p in sorted((out / "source").rglob("*.py"))]
    write(out / "INPUT_CONSUMPTION_MANIFEST.json", {"films": films, "scientific_inputs": inputs,
          "comparison_bindings": comparisons, "source_bindings": sources})
    write(out / "PROTOCOL_FREEZE.json", {"reproduction_of_known_results": True,
          "preregistered": False, "sha256": {p.relative_to(out).as_posix(): sha(p)
          for p in [out / "SCENARIOS.json", out / "INPUT_CONSUMPTION_MANIFEST.json",
                    *sorted((out / "source").rglob("*.py"))]}})
    s.run()
    v = module(out / "source/verify.py", "geometry_verify")
    v.main()
    report = module(out / "source/make_report.py", "geometry_report")
    report.main()


def stress(cfg, out):
    original = Path(cfg["runtime_root"]) / "historical_sources/family_operating_domain_stress_v0.1"
    shutil.copy2(original / "run_stress.py", out / "run_stress.py")
    packet = out / "source_packet"
    destinations = {
        "sources/reconstruct.py": "scientific_routes/family/reconstruct.py",
        "sources/stage_accounting.py": "scientific_routes/family/sources/executed/stage_accounting.py",
        "sources/joint_history.py": "analysis_code/portable_analysis_candidate_v0.5/src/portable_analysis_candidate/joint_history.py",
    }
    for source, destination in destinations.items():
        q = packet / destination; q.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original / source, q)
    m = module(out / "run_stress.py", "original_stress")
    m.ROOT = out; m.SOURCE_ROOT = packet
    m.prepare(); m.run()
    complete = read(out / "RUN_COMPLETE.json")
    assert complete["attempted_cases"] == 36


def policy_generation(cfg, out):
    runtime = Path(cfg["runtime_root"])
    subprocess.run([sys.executable, "-B", "-X", "utf8",
        str(runtime / "inputs_LOCAL_ONLY/bacterial/generate_common.py"),
        "--input-root", cfg["common_generation_root"], "--iws-root", cfg["iws_root"],
        "--output", str(out / "generated_run")], check=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("route", choices=["geometry", "stress", "policy-generation"])
    p.add_argument("--config", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args(); cfg = read(a.config)
    a.output.mkdir(parents=True, exist_ok=False)
    {"geometry": geometry, "stress": stress, "policy-generation": policy_generation}[a.route](cfg, a.output)
    write(a.output / "ADAPTER_COMPLETE.json", {"route": a.route,
          "scientific_bodies_unchanged": True, "known_result_reproduction": True,
          "source_adapter_sha256": sha(__file__)})


if __name__ == "__main__":
    main()
