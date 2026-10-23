"""Pure numpy/scipy port of the official tracking_cellmot scorer.

Replicates ``tracking_cellmot.metrics`` + ``tracking_cellmot.division_metrics``
(patched commit 075fc5f) WITHOUT tracksdata / polars / zarr, so it can run
inside the Kaggle notebook where those packages are unavailable.

Inputs are plain structures:
    nodes: dict[int, tuple[t, z, y, x]]
    edges: list[(src, tgt)]      # edge id == list index
    n_est: float                 # estimated_number_of_nodes (nan if absent)

Validated against score_official.py (tracksdata-based) on v5.3's 4-movie
submission: edge/division counts and adjusted Jaccard must match exactly.
"""
from __future__ import annotations

import math
from collections import defaultdict

import numpy as np
from scipy.optimize import linear_sum_assignment

ADJUSTMENT_ALPHA: float = 0.1
SCORE_DIVISION_WEIGHT: float = 0.1
DEFAULT_SCALE = (1.625, 0.40625, 0.40625)
DEFAULT_MAX_DISTANCE = 7.0


# ---------------------------------------------------------------------------
# Node matching (tracksdata DistanceMatching semantics, per time point)
# ---------------------------------------------------------------------------
def match_nodes(
    pred_nodes: dict[int, tuple],
    gt_nodes: dict[int, tuple],
    scale=DEFAULT_SCALE,
    max_distance: float = DEFAULT_MAX_DISTANCE,
) -> dict[int, int]:
    """Per-time-point min-distance bipartite matching capped at max_distance."""
    scale = np.asarray(scale, float)
    pred_by_t = defaultdict(list)
    for nid, row in pred_nodes.items():
        pred_by_t[int(row[0])].append((nid, row[1], row[2], row[3]))
    gt_by_t = defaultdict(list)
    for gid, row in gt_nodes.items():
        gt_by_t[int(row[0])].append((gid, row[1], row[2], row[3]))

    mapping: dict[int, int] = {}
    for t, plist in pred_by_t.items():
        glist = gt_by_t.get(t, [])
        if not glist:
            continue
        P = np.asarray([p[1:] for p in plist], float) * scale
        G = np.asarray([g[1:] for g in glist], float) * scale
        cost = np.linalg.norm(P[:, None] - G[None, :], axis=2)
        cost[cost > max_distance] = 1e6
        rows, cols = linear_sum_assignment(cost)
        for ri, ci in zip(rows, cols):
            if cost[ri, ci] <= max_distance:
                mapping[plist[ri][0]] = glist[ci][0]
    return mapping


def node_recall(pred2gt: dict[int, int], gt_nodes: dict[int, tuple]) -> float:
    """Fraction of GT nodes matched by a predicted node."""
    if not gt_nodes:
        return 0.0
    matched_gt = len(set(pred2gt.values()))
    return matched_gt / len(gt_nodes)


# ---------------------------------------------------------------------------
# Edge TP/FP/FN (official metrics._evaluate_matched_graph + evaluate)
# ---------------------------------------------------------------------------
def _edge_counts(pred_edges, pred2gt, gt_edges, pred_times):
    """Return (edge_tp, edge_fp, edge_fn) following the official order of ops."""
    gt_edge_set = set(gt_edges)
    gt_out = defaultdict(int)
    gt_in = defaultdict(int)
    for s, t in gt_edges:
        gt_out[s] += 1
        gt_in[t] += 1

    matched = []
    for s, t in pred_edges:
        gs = pred2gt.get(s)
        gt = pred2gt.get(t)
        matched.append(gs is not None and gt is not None and (gs, gt) in gt_edge_set)

    # 1) dedup (source, target), keep the matched copy if any else first.
    best_by_key: dict[tuple, int] = {}
    for i, (s, t) in enumerate(pred_edges):
        key = (s, t)
        if key not in best_by_key:
            best_by_key[key] = i
        elif matched[i] and not matched[best_by_key[key]]:
            best_by_key[key] = i
    kept = sorted(best_by_key.values())

    # 2) keep only consecutive-frame edges (t_target - t_source == 1).
    kept = [i for i in kept if pred_times[pred_edges[i][1]] - pred_times[pred_edges[i][0]] == 1]

    # 3) collapse merges: multiple pred edges mapping onto the same matched
    #    GT node pair -> keep the lowest pred edge id, drop the rest.
    pair_ids: dict[tuple, list[int]] = defaultdict(list)
    for i in kept:
        s, t = pred_edges[i]
        gs = pred2gt.get(s)
        gt = pred2gt.get(t)
        if gs is not None and gt is not None:
            pair_ids[(gs, gt)].append(i)
    merge_drop = {
        i for ids in pair_ids.values() if len(ids) > 1 for i in ids[1:]
    }
    kept = [i for i in kept if i not in merge_drop]

    # 4) cap out-degree at 2 per source, keep the two lowest edge ids.
    out_count: dict[int, int] = defaultdict(int)
    out_keep = set()
    for i in kept:
        src = pred_edges[i][0]
        if out_count[src] < 2:
            out_keep.add(i)
            out_count[src] += 1
    kept = [i for i in kept if i in out_keep]

    # 5) pred_valid: matched source has GT out-degree>0 or matched target has
    #    GT in-degree>0.
    pred_valid = 0
    tp = 0
    for i in kept:
        s, t = pred_edges[i]
        gs = pred2gt.get(s)
        gt = pred2gt.get(t)
        valid = False
        if gs is not None and gt_out.get(gs, 0) > 0:
            valid = True
        if gt is not None and gt_in.get(gt, 0) > 0:
            valid = True
        if valid:
            pred_valid += 1
            if matched[i]:
                tp += 1

    fp = pred_valid - tp
    fn = len(gt_edges) - tp
    return tp, fp, fn


# ---------------------------------------------------------------------------
# Division metrics (official division_metrics port)
# ---------------------------------------------------------------------------
def build_adjacency(edges):
    """Return (successors, predecessors) dicts for a directed edge list."""
    succ = defaultdict(list)
    pred = defaultdict(list)
    for s, t in edges:
        succ[s].append(t)
        pred[t].append(s)
    return succ, pred


def extract_divisions(gt_succ, gt_pred):
    """{divider: (parents, children, grandchildren_by_child)} for GT dividing nodes."""
    divisions = {}
    for div in list(gt_succ):
        children = list(gt_succ[div])
        if len(children) < 2:
            continue
        parents = list(gt_pred.get(div, ()))
        grandchildren = {child: list(gt_succ.get(child, ())) for child in children}
        divisions[div] = (parents, children, grandchildren)
    return divisions


def _matched_division_nodes(pred2gt, gt_div, divider_id):
    """Group matched pred ids by GT roles in a division window."""
    parents, children, grandchildren = gt_div
    gt_parent_ids = {divider_id, *parents}
    parent_ids = {pid for pid, gid in pred2gt.items() if gid in gt_parent_ids}
    daughter_ids = [
        {pid for pid, gid in pred2gt.items()
         if gid in {child, *grandchildren.get(child, [])}}
        for child in children
    ]
    if not parent_ids or sum(bool(ids) for ids in daughter_ids) < 2:
        return None
    return parent_ids, daughter_ids


def _is_strongly_connected_division(pred_succ, pred_pred, pred_div, parent_ids, daughter_ids):
    pred_parent_ids = {pred_div, *pred_pred.get(pred_div, ())}
    if pred_parent_ids.isdisjoint(parent_ids):
        return False
    pred_children = list(pred_succ.get(pred_div, ()))
    pred_lineages = [
        {child, *pred_succ.get(child, ())} for child in pred_children
    ]
    lineage_edges = {}
    for gt_lineage, matched_ids in enumerate(daughter_ids):
        lineage_edges[gt_lineage] = {
            pl for pl, pred_ids in enumerate(pred_lineages)
            if not matched_ids.isdisjoint(pred_ids)
        }
    return len(_bipartite_max_matching(list(lineage_edges), lineage_edges)) >= 2


def _bipartite_max_matching(left, edges):
    """Maximum-cardinality bipartite matching (left -> right dict)."""
    match_r = {}
    match_l = {}

    def augment(u, seen):
        for v in edges.get(u, ()):
            if v in seen:
                continue
            seen.add(v)
            if v not in match_r or augment(match_r[v], seen):
                match_l[u] = v
                match_r[v] = u
                return True
        return False

    for u in left:
        augment(u, set())
    return match_l


def _gt_weak_component_ids(gt_edges, gt_nodes):
    succ, pred = build_adjacency(gt_edges)
    component_ids = {}
    adj = defaultdict(list)
    for s, t in gt_edges:
        adj[s].append(t)
        adj[t].append(s)
    for seed in gt_nodes:
        if seed in component_ids:
            continue
        component_ids[seed] = seed
        stack = [seed]
        while stack:
            cur = stack.pop()
            for nb in adj.get(cur, ()):
                if nb not in component_ids:
                    component_ids[nb] = seed
                    stack.append(nb)
    return component_ids


def _branch_component_evidence(pred_succ, pred_pred, pred_div, child, pred_to_gt, gt_component):
    """Return (gt_component_or_None, malformed_flag) for a predicted child branch."""
    if set(pred_pred.get(child, ())) != {pred_div}:
        return None, True
    if child in pred_to_gt:
        return gt_component.get(pred_to_gt[child]), False
    grandchildren = pred_succ.get(child, ())
    if any(set(pred_pred.get(node, ())) != {child} for node in grandchildren):
        return None, True
    components = {
        gt_component.get(pred_to_gt[node])
        for node in grandchildren
        if node in pred_to_gt
    }
    if len(components) == 1:
        return next(iter(components)), False
    return None, False


def _pred_division_fork_sets(pred_succ, pred_pred, pred_nodes, gt_nodes, gt_edges, pred2gt):
    """Return (evaluable_forks, cross_component_forks, malformed_forks)."""
    pred_forks = {
        node for node in pred_nodes if len(pred_succ.get(node, ())) >= 2
    }
    gt_succ, _ = build_adjacency(gt_edges)
    evaluable_forks = {
        pid for pid in pred_forks
        if pid in pred2gt and len(gt_succ.get(pred2gt[pid], ())) >= 1
    }
    gt_component = _gt_weak_component_ids(gt_edges, gt_nodes)
    cross_component_forks = set()
    malformed_forks = set()
    for pred_id in pred_forks:
        branch_evidence = []
        malformed = False
        for child in pred_succ.get(pred_id, ()):
            component, bad = _branch_component_evidence(
                pred_succ, pred_pred, pred_id, child, pred2gt, gt_component
            )
            if bad:
                malformed_forks.add(pred_id)
                malformed = True
                break
            if component is not None:
                branch_evidence.append(component)
        if not malformed and len(set(branch_evidence)) >= 2:
            cross_component_forks.add(pred_id)
    return evaluable_forks, cross_component_forks, malformed_forks


def score_divisions(pred_nodes, pred_edges, pred_succ, pred_pred,
                    gt_nodes, gt_edges, pred2gt_full,
                    scale=DEFAULT_SCALE, max_distance=DEFAULT_MAX_DISTANCE):
    """Per-GT-division recovery + FP forks, mirroring official score_divisions."""
    gt_succ, gt_pred = build_adjacency(gt_edges)
    gt_divisions = extract_divisions(gt_succ, gt_pred)
    pred_div_nodes = {
        node for node in pred_nodes if len(pred_succ.get(node, ())) >= 2
    }
    evaluable_forks, cross_component_forks, malformed_forks = _pred_division_fork_sets(
        pred_succ, pred_pred, pred_nodes, gt_nodes, gt_edges, pred2gt_full
    )
    invalid_forks = cross_component_forks | malformed_forks

    candidates = {}
    considered = set()
    for div_node, gt_div in gt_divisions.items():
        # Window nodes: parents + divider + children + grandchildren (per child).
        parents, children, grandchildren = gt_div
        window = set(parents) | {div_node} | set(children) | {
            gc for gcs in grandchildren.values() for gc in gcs
        }
        window_gt = {gid: gt_nodes[gid] for gid in window if gid in gt_nodes}
        matched_pred = match_nodes(pred_nodes, window_gt, scale, max_distance)
        roles = _matched_division_nodes(matched_pred, gt_div, div_node)
        if roles is None:
            candidates[div_node] = set()
            continue
        parent_ids, daughter_ids = roles
        local_nodes = parent_ids | {
            succ for pid in parent_ids for succ in pred_succ.get(pid, ())
        }
        local_forks = local_nodes & pred_div_nodes
        considered |= local_forks
        candidates[div_node] = {
            pd for pd in local_forks - invalid_forks
            if _is_strongly_connected_division(
                pred_succ, pred_pred, pd, parent_ids, daughter_ids)
        }

    pairing = _bipartite_max_matching(list(candidates), candidates)
    scores = {div: int(div in pairing) for div in candidates}
    tp_forks = set(pairing.values())
    fp_forks = (considered | evaluable_forks | invalid_forks) - tp_forks
    return scores, tp_forks, fp_forks


def evaluate_divisions(pred_nodes, pred_edges, gt_nodes, gt_edges, pred2gt_full,
                       scale=DEFAULT_SCALE, max_distance=DEFAULT_MAX_DISTANCE):
    pred_succ, pred_pred = build_adjacency(pred_edges)
    scores, tp_forks, fp_forks = score_divisions(
        pred_nodes, pred_edges, pred_succ, pred_pred,
        gt_nodes, gt_edges, pred2gt_full, scale, max_distance
    )
    tp = sum(scores.values())
    fn = len(scores) - tp
    return tp, fn, len(fp_forks)


# ---------------------------------------------------------------------------
# Per-sample metrics + run summary (official metrics.per_sample_metrics/summarise)
# ---------------------------------------------------------------------------
def per_sample_metrics(er, n_est, recall):
    """er: dict with edge_tp/fp/fn, division_tp/fp/fn, num_pred_nodes."""
    if n_est and n_est > 0:
        total_node_ratio = (er["num_pred_nodes"] - n_est) / n_est
    else:
        total_node_ratio = float("nan")
    edge_denom = er["edge_tp"] + er["edge_fp"] + er["edge_fn"]
    edge_jaccard = er["edge_tp"] / edge_denom if edge_denom > 0 else float("nan")
    if not math.isnan(edge_jaccard) and not math.isnan(total_node_ratio):
        adj_edge_jaccard = max(
            0.0, edge_jaccard * (1 - ADJUSTMENT_ALPHA * total_node_ratio)
        )
    else:
        adj_edge_jaccard = float("nan")
    return {
        "edge_tp": er["edge_tp"], "edge_fp": er["edge_fp"], "edge_fn": er["edge_fn"],
        "division_tp": er["division_tp"], "division_fp": er["division_fp"],
        "division_fn": er["division_fn"], "num_pred_nodes": er["num_pred_nodes"],
        "node_recall": recall, "total_node_ratio": total_node_ratio,
        "edge_jaccard": edge_jaccard, "adj_edge_jaccard": adj_edge_jaccard,
    }


def summarise(rows):
    """Official run-level summary (weighted adj Jaccard + 0.1*division Jaccard)."""
    valid = [r for r in rows if r["edge_tp"] == r["edge_tp"]]
    if not valid:
        return {
            "n": 0, "edge_jaccard": float("nan"), "division_jaccard": float("nan"),
            "division_tp": 0, "division_fp": 0, "division_fn": 0,
            "node_recall": float("nan"), "adj_edge_jaccard": float("nan"),
            "n_adj": 0, "score": float("nan"),
        }
    totals = {c: sum(r[c] for r in valid) for c in
              ("edge_tp", "edge_fp", "edge_fn", "division_tp", "division_fp", "division_fn")}
    adj_rows = [r for r in valid if r["adj_edge_jaccard"] == r["adj_edge_jaccard"]]
    weights = [r["edge_tp"] + r["edge_fp"] + r["edge_fn"] for r in adj_rows]
    total_w = sum(weights)
    if total_w > 0:
        adj_edge_jaccard = sum(
            w * r["adj_edge_jaccard"] for w, r in zip(weights, adj_rows)
        ) / total_w
    else:
        adj_edge_jaccard = float("nan")
    division_total = totals["division_tp"] + totals["division_fp"] + totals["division_fn"]
    if division_total == 0:
        division_jaccard = float("nan")
        score = adj_edge_jaccard
    else:
        division_jaccard = totals["division_tp"] / division_total
        score = adj_edge_jaccard + SCORE_DIVISION_WEIGHT * division_jaccard
    return {
        "n": len(valid),
        "edge_jaccard": totals["edge_tp"] / max(
            totals["edge_tp"] + totals["edge_fp"] + totals["edge_fn"], 1
        ),
        "division_jaccard": division_jaccard,
        "division_tp": totals["division_tp"],
        "division_fp": totals["division_fp"],
        "division_fn": totals["division_fn"],
        "node_recall": sum(r["node_recall"] for r in valid) / len(valid),
        "adj_edge_jaccard": adj_edge_jaccard,
        "n_adj": len(adj_rows),
        "score": score,
    }


def evaluate_sample(pred_nodes, pred_edges, gt_nodes, gt_edges, n_est,
                    scale=DEFAULT_SCALE, max_distance=DEFAULT_MAX_DISTANCE):
    """Full official per-sample metric for one movie."""
    pred2gt = match_nodes(pred_nodes, gt_nodes, scale, max_distance)
    if not pred_edges or not pred_nodes:
        edge_tp, edge_fp, edge_fn = 0, 0, len(gt_edges)
    else:
        pred_times = {nid: int(row[0]) for nid, row in pred_nodes.items()}
        edge_tp, edge_fp, edge_fn = _edge_counts(pred_edges, pred2gt, gt_edges, pred_times)
    div_tp, div_fn, div_fp = evaluate_divisions(
        pred_nodes, pred_edges, gt_nodes, gt_edges, pred2gt, scale, max_distance
    )
    recall = node_recall(pred2gt, gt_nodes)
    er = {
        "edge_tp": edge_tp, "edge_fp": edge_fp, "edge_fn": edge_fn,
        "division_tp": div_tp, "division_fp": div_fp, "division_fn": div_fn,
        "num_pred_nodes": len(pred_nodes),
    }
    return per_sample_metrics(er, n_est, recall)
