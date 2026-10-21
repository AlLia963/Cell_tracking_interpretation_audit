"""Compose an offline runtime from repository code and existing companion data.

No data are copied into versioned files. Directory links are read-only by
convention; experiment commands require separate absent output directories.
The manifest records links explicitly. Never recursively delete this runtime.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess

HERE = Path(__file__).resolve().parent


def junction(source, target):
    if os.name == "nt":
        # Native literal paths: no command string interpolation or cmd.exe.
        script = "param([string]$src,[string]$dst) New-Item -ItemType Junction -Path $dst -Target $src | Out-Null"
        helper = HERE / "_local" / "new-junction.ps1"
        if not helper.exists():
            helper.write_text(script, encoding="utf-8-sig")
        subprocess.run(["powershell", "-NoProfile", "-File", str(helper), str(source), str(target)], check=True, capture_output=True)
    else:
        target.symlink_to(source, target_is_directory=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, default=HERE / "local_config.json")
    a = p.parse_args()
    cfg = json.loads(a.config.read_text(encoding="utf-8-sig"))
    source = Path(cfg["companion_root"]).resolve()
    target = Path(cfg["runtime_root"]).absolute()
    local = (HERE / "_local").absolute()
    if local not in target.parents or target.exists():
        raise ValueError("Runtime must be a new directory inside paper/_local")
    index = json.loads((HERE / "SOURCE_INDEX.json").read_text(encoding="utf-8"))
    controlled = Path(cfg.get("controlled_source_root", source)).resolve()
    replacements = {r["relative_path"]: (controlled if r.get("distribution") == "controlled_source" else HERE / "scientific") / r["relative_path"] for r in index["files"]}
    for rel, path in replacements.items():
        if not path.is_file():
            raise FileNotFoundError('Required indexed source is absent: '+str(path)+'. For controlled sources, set controlled_source_root in the local configuration to the authorized source companion; see docs/DATA_ACCESS.md.')
        if hashlib.sha256(path.read_bytes()).hexdigest() != next(r["sha256"] for r in index["files"] if r["relative_path"] == rel):
            raise ValueError("Source index mismatch: " + rel)
    ancestors = set()
    for rel in replacements:
        ancestors.update(p.as_posix() for p in Path(rel).parents)
    records = []
    excluded = {"records", "__pycache__", ".git", "recipes_prepared_unexecuted"}
    local.mkdir(exist_ok=True)

    def overlay(src, dst, rel=Path()):
        dst.mkdir(exist_ok=False)
        for child in sorted(src.iterdir()):
            if child.name in excluded or child.suffix == ".pyc":
                continue
            if child.name == "results" and rel.as_posix() == "inputs_LOCAL_ONLY/bacterial":
                continue  # historical measurement outputs, not source contracts
            key = (rel / child.name).as_posix()
            dest = dst / child.name
            if child.is_dir():
                if key in ancestors:
                    overlay(child, dest, rel / child.name)
                else:
                    junction(child, dest)
                    records.append({"kind": "external_directory_link", "runtime": key, "target": str(child)})
            else:
                if key in replacements:
                    shutil.copy2(replacements[key], dest)
                    records.append({"kind": "repository_source_copy", "runtime": key})
                elif child.suffix == ".py":
                    # Native registration hashes original source bytes as inert
                    # provenance. They are not imported or executed by readers.
                    if key.startswith("inputs_LOCAL_ONLY/bacterial/fixed_archive_root/"):
                        shutil.copy2(child, dest)
                        records.append({"kind": "hash_only_source_provenance", "runtime": key})
                    continue
                else:
                    try:
                        os.link(child, dest)
                        kind = "external_file_hardlink"
                    except OSError:
                        shutil.copy2(child, dest)
                        kind = "external_metadata_copy"
                    records.append({"kind": kind, "runtime": key, "target": str(child)})
    overlay(source, target)
    # Extra paper producers were not inside the old supplement.
    for rel, path in replacements.items():
        dest = target / rel
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            records.append({"kind": "repository_extra_source_copy", "runtime": rel})
    # r2 replaces the erroneous historical absolute native roots with relative
    # mappings. This metadata patch is local and does not touch the companion.
    patch = Path(cfg["native_map_patch"])
    map_dest = target / "inputs_LOCAL_ONLY/bacterial/SELECTED_NATIVE_ROOT_MAP.json"
    if map_dest.exists():
        map_dest.unlink()  # unlink our hardlink only; never write through it
    shutil.copy2(patch, map_dest)
    # Record explicit, indexed source adaptations without writing through old
    # metadata hardlinks or pretending adapted bytes are historical originals.
    config_path = target / "inputs_LOCAL_ONLY/bacterial/CONFIG_LOCAL_ONLY.json"
    if config_path.exists():
        metadata = json.loads(config_path.read_text(encoding="utf-8-sig"))
        changes = []
        for row in metadata["source_files"]:
            effective = config_path.parent / row["package"]
            if effective.is_file() and row["package"].endswith(".py"):
                actual = hashlib.sha256(effective.read_bytes()).hexdigest()
                if actual != row["sha256"]:
                    key = "inputs_LOCAL_ONLY/bacterial/" + row["package"]
                    indexed = next((r for r in index["files"] if r["relative_path"] == key), None)
                    if not indexed or indexed["sha256"] != actual or indexed.get("original_sha256") != row["sha256"]:
                        raise ValueError("Unexplained source adaptation: " + key)
                    changes.append({"package": row["package"], "historical_sha256": row["sha256"], "effective_sha256": actual})
                    row["historical_sha256"] = row["sha256"]
                    row["sha256"] = actual
                    row["bytes"] = effective.stat().st_size
        if changes:
            config_path.unlink()
            config_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            (target / "SOURCE_ADAPTATION_BINDINGS.json").write_text(json.dumps(changes, indent=2), encoding="utf-8")
    with (target / "LOCAL_COMPOSITION.json").open("x", encoding="utf-8") as f:
        json.dump({"companion": str(source), "runtime": str(target), "records": records,
                   "raw_data_copied_into_git": False, "links_are_inputs_do_not_delete_recursively": True}, f, ensure_ascii=False, indent=2)
    print(json.dumps({"runtime": str(target), "bindings": len(records), "source_files": len(replacements)}))


if __name__ == "__main__":
    main()
