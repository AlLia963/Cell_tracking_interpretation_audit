"""Module-level ablation of the v7.3 pipeline on the 4 verifiable movies.

Backward ablation (full minus each module) + forward ablation (raw ILP graph
plus modules cumulatively). Every variant is scored with the full official
metric (adj_edge_jaccard + 0.1 * division_jaccard).

Runtime control: motion_relink_edges is deterministic given the raw input and
its constants (not toggled here), so it is computed once per movie and cached.
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

sys.setrecursionlimit(30000)

import numpy as np
import polars as pl
import tracksdata as td

ROOT = Path(r"C:\Users\24408\Desktop\cell")
sys.path.insert(0, str(ROOT))

from v75_sim import build_sim_env  # noqa: E402
from coupling_analysis import load_gt  # noqa: E402
from cv_scorer import evaluate_sample  # noqa: E402

REF = Path(os.environ.get(
    "V75_REF",
    ROOT / "output" / "biohub-gap2-joint-node-budget" / "tracking_repo" / "predictions" / "unknown" / "unet_transformer" / "split_0",
))
GT = ROOT / "gt_data" / "full" / "train"
OUT = Path(os.environ.get(
    "V75_OUT",
    ROOT / "output" / "v7.1" / "coupling_analysis",
))
SCALE = (1.625, 0.40625, 0.40625)
DEFAULT_DATASETS = ["44b6_0113de3b", "44b6_0b24845f", "6bba_05b6850b", "6bba_05db0fb1"]


def load_movie(ds):
    g = td.graph.IndexedRXGraph.from_geff(str(REF / f"{ds}.geff"))
    g = g[0] if isinstance(g, tuple) else g
    nodes = {}
    for r in g.node_attrs().iter_rows(named=True):
        nid = int(r["node_id"])
        nodes[nid] = {"node_id": nid, "t": float(r["t"]), "z": float(r["z"]),
                      "y": float(r["y"]), "x": float(r["x"])}
    raw_edges = []
    for r in g.edge_attrs().iter_rows(named=True):
        p = r.get("edge_prob")
        raw_edges.append({
            "source_id": int(r["source_id"]),
            "target_id": int(r["target_id"]),
            "edge_prob": None if p is None else float(p),
        })
    gt_nodes, gt_edges, n_est = load_gt(GT / f"{ds}.geff")
    return nodes, raw_edges, gt_nodes, gt_edges, n_est


def score_variant(nodes, edges, gt_nodes, gt_edges, n_est):
    pn = {n: (v["t"], v["z"], v["y"], v["x"]) for n, v in nodes.items()}
    pe = [(int(e["source_id"]), int(e["target_id"])) for e in edges]
    return evaluate_sample(pn, pe, gt_nodes, gt_edges, n_est, scale=SCALE)


TOGGLES = {
    "motion_relink": "OUTPUT_MOTION_RELINK",
    "single_parent": "OUTPUT_SINGLE_PARENT_REPAIR",
    "gap": "OUTPUT_GAP_CLOSE",
    "gap2": "OUTPUT_GAP2_RECOVERY",
    "safe_div": "OUTPUT_SAFE_DIVISIONS",
    "div_filter": "OUTPUT_DIVISION_GEOMETRY_FILTER",
    "prune": "OUTPUT_PRUNE_ISOLATED",
    "short_track": "OUTPUT_FILTER_SHORT_TRACKS",
    "linefit": "OUTPUT_LINEFIT_SMOOTH",
    "v72": "V72_REASSIGN",
    "v74": "V74_REASSIGN",
}


def main():
    ns = build_sim_env()
    _orig_mr = ns["motion_relink_edges"]  # capture ONCE, before any wrapping
    args = sys.argv[1:]
    if "--ref" in args:
        i = args.index("--ref")
        global REF
        REF = Path(args[i + 1])
        args = args[:i] + args[i + 2:]
    if "--out" in args:
        i = args.index("--out")
        global OUT
        OUT = Path(args[i + 1])
        args = args[:i] + args[i + 2:]
    if "--all" in args:
        args.remove("--all")
        datasets = sorted(p.stem for p in REF.glob("*.geff"))
    elif args:
        datasets = list(dict.fromkeys(args))
    else:
        datasets = DEFAULT_DATASETS
    datasets = [d for d in datasets if (REF / f"{d}.geff").exists()]
    if not datasets:
        raise SystemExit(f"No matching geffs under {REF}")
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for ds in datasets:
        nodes, raw_edges, gt_nodes, gt_edges, n_est = load_movie(ds)
        # cache motion relink per movie (deterministic given raw input + constants)
        _mr_cache = {}

        def cached_mr(nodes_by_id, stats, learned_edge_probs=None, raw_edges_for_context=None):
            key = id(nodes_by_id)
            if key not in _mr_cache:
                _mr_cache[key] = _orig_mr(nodes_by_id, stats, learned_edge_probs, raw_edges_for_context)
            return [dict(e) for e in _mr_cache[key]]

        ns["motion_relink_edges"] = cached_mr

        def run(toggles_off):
            for name, gname in TOGGLES.items():
                ns[gname] = name not in toggles_off
            t0 = time.time()
            nodes2, edges2, stats = ns["filter_output_graph"](
                {k: dict(v) for k, v in nodes.items()}, [dict(e) for e in raw_edges],
                dataset=None, deepcenter_bundle=None,
            )
            dt = time.time() - t0
            return nodes2, edges2, stats, dt

        # --- backward ablation ---
        variants = [("full", set())]
        for name in TOGGLES:
            variants.append((f"no_{name}", {name}))
        # --- forward ablation (cumulative) ---
        fwd_order = ["motion_relink", "single_parent", "gap", "gap2", "safe_div",
                     "div_filter", "prune", "short_track", "linefit", "v72", "v74"]
        for i in range(1, len(fwd_order) + 1):
            off = set(TOGGLES) - set(fwd_order[:i])
            variants.append(("fwd_" + "+".join(fwd_order[:i]), off))

        # raw baseline (no pipeline)
        r = score_variant(nodes, raw_edges, gt_nodes, gt_edges, n_est)
        rows.append({
            "dataset": ds, "variant": "raw", "mode": "forward",
            "n_nodes": len(nodes), "n_edges": len(raw_edges), "seconds": 0.0,
            "n_est": n_est,
            **{k: r[k] for k in ("edge_tp", "edge_fp", "edge_fn", "division_tp",
                                 "division_fp", "division_fn", "num_pred_nodes")},
        })

        for vname, off in variants:
            try:
                n2, e2, stats, dt = run(off)
                r = score_variant(n2, e2, gt_nodes, gt_edges, n_est)
                rows.append({
                    "dataset": ds, "variant": vname,
                    "mode": "backward" if vname.startswith("no_") or vname == "full" else "forward",
                    "n_nodes": len(n2), "n_edges": len(e2), "seconds": round(dt, 1),
                    "n_est": n_est,
                    **{k: r[k] for k in ("edge_tp", "edge_fp", "edge_fn", "division_tp",
                                         "division_fp", "division_fn", "num_pred_nodes")},
                })
                print(f"{ds} {vname}: tp/fp/fn={r['edge_tp']}/{r['edge_fp']}/{r['edge_fn']} ({dt:.0f}s)", flush=True)
            except Exception as exc:
                print(f"{ds} {vname}: ERROR {type(exc).__name__}: {exc}", flush=True)
                traceback.print_exc(limit=10)
                rows.append({"dataset": ds, "variant": vname, "mode": "error", "error": str(exc)})
        pl.DataFrame(rows).write_csv(OUT / "v75_ablation.csv")
        print(f"{ds} done; {len(rows)} rows so far", flush=True)

    # summary
    import pandas as pd

    df = pd.DataFrame([r for r in rows if "edge_tp" in r])
    out = []
    for variant, g in df.groupby("variant"):
        tp = int(g.edge_tp.sum()); fp = int(g.edge_fp.sum()); fn = int(g.edge_fn.sum())
        dtp = int(g.division_tp.sum()); dfp = int(g.division_fp.sum()); dfn = int(g.division_fn.sum())
        n_pred = int(g.num_pred_nodes.sum()); n_est = float(g.n_est.sum())
        ej = tp / (tp + fp + fn) if tp + fp + fn else 0
        dj = dtp / (dtp + dfp + dfn) if dtp + dfp + dfn else 0
        ratio = (n_pred - n_est) / n_est if n_est > 0 else 0
        adj = ej * max(0, 1 - 0.1 * ratio)
        score = adj + 0.1 * dj
        out.append({
            "variant": variant, "mode": g["mode"].iloc[0],
            "score": round(score, 6), "adj": round(adj, 6), "edge_j": round(ej, 6),
            "div_j": round(dj, 5), "edge_tp": tp, "edge_fp": fp, "edge_fn": fn,
            "div_tp": dtp, "div_fp": dfp, "div_fn": dfn,
            "n_edges": int(g.n_edges.sum()), "n_nodes": int(g.n_nodes.sum()),
        })
    agg = pd.DataFrame(out).sort_values("score", ascending=False)
    print()
    print(agg.to_string())
    agg.to_csv(OUT / "v75_ablation_summary.csv", index=False)


if __name__ == "__main__":
    main()
