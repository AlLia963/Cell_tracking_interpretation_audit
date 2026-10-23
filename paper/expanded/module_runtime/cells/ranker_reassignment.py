# Cell 15c - v7.4 ranker-evidence pass (identical to the locally
# calibrated v74_pass.v74_ranker_reassign; default ON).
import numpy as np
from collections import defaultdict
_SCALE = (1.625, 0.40625, 0.40625)
def v74_ranker_reassign(
    nodes_by_id,
    edges,
    raw_edges,
    stats=None,
    r_thr=0.80,
    r_margin=0.10,
    do_add=True,
    source_continuity_min=0.70,
):
    """Per-target arbitration by local-ranker evidence (post v7.3)."""
    stats = stats if stats is not None else {}
    if LOCAL_ASSOCIATION_RANKER is None:
        stats["v74_skipped"] = 1
        return edges, stats

    scale = np.asarray(_SCALE, float)
    learned = {}
    for edge in raw_edges:
        p = edge.get("edge_prob")
        if p is None:
            continue
        try:
            p = float(p)
        except (TypeError, ValueError):
            continue
        if np.isfinite(p):
            learned[(int(edge["source_id"]), int(edge["target_id"]))] = p

    succ = defaultdict(list)
    pred = defaultdict(list)
    for e in edges:
        succ[int(e["source_id"])].append(int(e["target_id"]))
        pred[int(e["target_id"])].append(int(e["source_id"]))
    position = {
        n: np.asarray([float(v["z"]), float(v["y"]), float(v["x"])], float)
        for n, v in nodes_by_id.items()
    }
    t_of = {n: int(v["t"]) for n, v in nodes_by_id.items()}
    ids_by_t = defaultdict(list)
    for n in nodes_by_id:
        ids_by_t[t_of[n]].append(n)
    for ids in ids_by_t.values():
        ids.sort()

    ctx = _ranker_context(nodes_by_id, edges)
    globals()["nodes_by_id_global_for_ranker"] = nodes_by_id
    relaxed = MOTION_RELINK_RELAXED_UM
    vel_w = MOTION_RELINK_VELOCITY_WEIGHT

    records = []
    loc = []
    for t, srcs in sorted(ids_by_t.items()):
        tgts = ids_by_t.get(t + 1, [])
        if not srcs or not tgts:
            continue
        for s in srcs:
            s_pos = position[s]
            parents = pred.get(s)
            prev_pos = position[parents[0]] if parents else None
            predicted = s_pos if prev_pos is None else s_pos + vel_w * (s_pos - prev_pos)
            valid = []
            for tg in tgts:
                raw = float(np.linalg.norm((position[tg] - s_pos) * scale))
                if raw > relaxed:
                    continue
                valid.append((raw, tg))
            if not valid:
                continue
            valid.sort(key=lambda x: (x[0], x[1]))
            rank_by = {tg: i + 1 for i, (_r, tg) in enumerate(valid)}
            for raw, tg in valid:
                motion = float(np.linalg.norm((position[tg] - predicted) * scale))
                records.append({
                    "source_id": s,
                    "target_id": tg,
                    "raw_distance_um": raw,
                    "motion_distance_um": motion,
                    "primary_prob": float(learned.get((s, tg), 0.0)),
                    "has_learned_edge": bool((s, tg) in learned),
                    "candidate_rank_dist": int(rank_by[tg]),
                    "candidate_count": int(len(valid)),
                    "predicted_position_um": predicted,
                    "context": ctx,
                })
                loc.append((s, tg))
    if not records:
        stats["v74_scored"] = 0
        return edges, stats
    try:
        matrix = _ranker_matrix(records)
        probs = LOCAL_ASSOCIATION_RANKER.predict_proba(matrix)
    except Exception as exc:  # never let the arbitration kill a submission run
        stats["v74_error"] = f"{type(exc).__name__}: {exc}"
        stats["v74_scored"] = 0
        return edges, stats
    prob_map = {k: float(p) for k, p in zip(loc, probs)}
    stats["v74_scored"] = len(prob_map)

    best_in_prob = {}
    for (_s, t), p in learned.items():
        t = int(t)
        if p > best_in_prob.get(t, 0.0):
            best_in_prob[t] = float(p)

    in_edges = {}
    for e in edges:
        in_edges[int(e["target_id"])] = e

    def out_degree(s):
        return len(succ.get(int(s), []))

    cand_in = defaultdict(list)
    for (s, t), p in prob_map.items():
        cand_in[int(t)].append((float(p), int(s), int(t)))
    for t in cand_in:
        cand_in[t].sort(reverse=True)

    n_swap = n_add = 0
    stats["v74_swaps"] = []
    stats["v74_adds"] = []
    for t in sorted(in_edges):
        cur = in_edges[t]
        cur_s = int(cur["source_id"])
        cur_p = prob_map.get((cur_s, t), 0.0)
        best = None
        for p, s, _tt in cand_in.get(t, []):
            if s == cur_s:
                continue
            if p < r_thr or (p - cur_p) < r_margin:
                continue
            if out_degree(s) >= 2:
                continue
            if best_in_prob.get(s, 0.0) < source_continuity_min:
                continue
            best = (p, s)
            break
        if best is None:
            continue
        p, s = best
        new_edge = {"source_id": s, "target_id": t, "edge_prob": p, "v74_reassign": 1}
        for i, e in enumerate(edges):
            if e is cur:
                edges[i] = new_edge
                break
        succ[cur_s].remove(t)
        succ[s].append(t)
        in_edges[t] = new_edge
        stats["v74_swaps"].append((cur_s, t, s, round(cur_p, 4), round(p, 4)))
        n_swap += 1

    if do_add:
        add_count = defaultdict(int)
        for t in sorted(cand_in):
            if t in in_edges:
                continue
            for p, s, _tt in cand_in[t]:
                if p < r_thr:
                    continue
                if out_degree(s) >= 2 or add_count[s] >= 1:
                    continue
                if best_in_prob.get(s, 0.0) < source_continuity_min:
                    continue
                edges.append({"source_id": s, "target_id": t, "edge_prob": p, "v74_add": 1})
                succ[s].append(t)
                in_edges[t] = edges[-1]
                add_count[s] += 1
                stats["v74_adds"].append((s, t, round(p, 4)))
                n_add += 1
                break

    by_target = defaultdict(list)
    by_source = defaultdict(list)
    for e in edges:
        by_target[int(e["target_id"])].append(e)
        by_source[int(e["source_id"])].append(e)
    drop = set()
    for es in by_target.values():
        if len(es) > 1:
            es.sort(
                key=lambda e: prob_map.get((int(e["source_id"]), int(e["target_id"])), 0.0),
                reverse=True,
            )
            for e in es[1:]:
                drop.add(id(e))
    for es in by_source.values():
        if len(es) > 2:
            es.sort(
                key=lambda e: prob_map.get((int(e["source_id"]), int(e["target_id"])), 0.0),
                reverse=True,
            )
            for e in es[2:]:
                drop.add(id(e))
    if drop:
        edges = [e for e in edges if id(e) not in drop]
    stats["v74_swaps_n"] = n_swap
    stats["v74_adds_n"] = n_add
    stats["v74_dropped"] = len(drop)
    return edges, stats
