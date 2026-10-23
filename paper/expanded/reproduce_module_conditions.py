"""Reproduce the 24 graph-processing conditions on the three reported movies.

Backward ablation (full minus each module) + forward ablation (raw ILP graph
plus modules cumulatively). Every variant is scored with the full official
metric (adj_edge_jaccard + 0.1 * division_jaccard).

Runtime control: motion_relink_edges is deterministic given the raw input and
its constants (not toggled here), so it is computed once per movie and cached.
"""

from __future__ import annotations

import json
import os
import argparse
import platform
import sys
import time
import traceback
from pathlib import Path

sys.setrecursionlimit(30000)

import numpy as np
import polars as pl
import tracksdata as td

from module_runtime import build_sim_env, load_gt
from module_runtime.cv_scorer import evaluate_sample
REF = GT = OUT = None
SCALE = (1.625, 0.40625, 0.40625)
DEFAULT_DATASETS = ['44b6_0113de3b','44b6_0b24845f','6bba_05b6850b']


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
    global REF,GT,OUT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-root',type=Path,required=True,help='Folder containing predictions/, reference_train/ and ranker/')
    parser.add_argument('--output',type=Path,required=True,help='New absent output directory outside inputs')
    parser.add_argument('--films',nargs='+',choices=DEFAULT_DATASETS,help='Optional subset of the declared three movies')
    parser.add_argument('--conditions',nargs='+',help='Optional named condition subset; omit for all 24')
    parser.add_argument('--threads',type=int,default=1)
    args=parser.parse_args();root=args.input_root.resolve();OUT=args.output.resolve()
    if OUT.exists() or OUT==root or root in OUT.parents:raise ValueError('Use a new output directory outside inputs')
    if args.threads<1:raise ValueError('threads must be positive')
    import torch
    torch.set_num_threads(args.threads)
    REF=root/'predictions';GT=root/'reference_train';datasets=args.films or DEFAULT_DATASETS
    if len(set(datasets))!=len(datasets):raise ValueError('Duplicate movie')
    for film in datasets:
        if not (REF/(film+'.geff')).is_dir() or not (GT/(film+'.geff')).is_dir():raise FileNotFoundError('Declared movie input missing: '+film)
    OUT.mkdir(parents=True,exist_ok=False)
    ns=build_sim_env(root/'ranker')
    _orig_mr=ns['motion_relink_edges']
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

        allowed={'raw'}|{v[0] for v in variants}
        if args.conditions:
            if not set(args.conditions).issubset(allowed):raise ValueError('Unknown condition')
            variants=[v for v in variants if v[0] in args.conditions]
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
    import csv
    expected_path=root/'expected/72_module_conditions.csv'
    differences=[]
    if expected_path.is_file():
        expected={(r['dataset'],r['variant']):r for r in csv.DictReader(expected_path.open(encoding='utf-8-sig'))}
        numeric=['n_nodes','n_edges','edge_tp','edge_fp','edge_fn','division_tp','division_fp','division_fn','num_pred_nodes']
        for row in rows:
            key=(row['dataset'],row['variant']);prev=expected[key]
            for field in numeric:
                if field not in row or int(row[field])!=int(prev[field]):differences.append({'movie':key[0],'condition':key[1],'field':field,'actual':row.get(field),'expected':prev[field]})
    complete=(datasets==DEFAULT_DATASETS and not args.conditions)
    if complete and len(rows)!=72:differences.append({'field':'row_count','actual':len(rows),'expected':72})
    report={'status':'MODULE_REPRODUCTION_PASS' if not differences else 'MODULE_REPRODUCTION_DIFFERENCES',
            'complete_72_conditions':complete,'rows':len(rows),'movies':datasets,'mismatches':differences,
            'historical_timings_replaced':False,'runtime':{'python':platform.python_version(),'numpy':np.__version__,'torch':torch.__version__,'threads':args.threads},
            'scope':'Original graph-only postprocessing and original scorer; no new detector inference or image refinement.'}
    (OUT/'REPRODUCTION_CHECK.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(report['status'],flush=True)
    if differences:raise SystemExit(2)


if __name__ == "__main__":
    main()
