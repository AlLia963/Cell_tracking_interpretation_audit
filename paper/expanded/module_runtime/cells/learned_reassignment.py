# Cell 15b - v7.2 evidence-aware reassignment (identical to the
# locally calibrated v72_reassign.v72_learned_reassign; default ON).
from collections import defaultdict
def v72_learned_reassign(
    nodes_by_id,
    edges,
    raw_edges,
    stats=None,
    threshold=0.85,
    margin=0.10,
    do_add_unassigned=True,
    max_add_per_source=1,
    source_continuity_min=0.70,
    max_edge_um=12.0,
):
    """Swap/add edges by learned edge probability, per target single in-edge.

    Rules (derived from the 80-movie coupling analysis):
      S1 swap: target already has one in-edge `cur`. If a learned candidate
              edge (s_alt -> t) exists with prob >= threshold and
              prob - prob(cur) >= margin, and s_alt != cur_source, replace
              cur with the best such candidate.
      S2 add:  target has no in-edge. If a learned candidate (s -> t) exists
              with prob >= threshold and source out-degree < 2 (and adding
              would not exceed max_add_per_source), add the best candidate.
      S3 reconnect: source that lost its only out-edge in S1 and now has 0
              out-edges gets its best learned candidate edge (prob >=
              threshold) into a target that currently has 0 in-edges.
              [REMOVED in v7.2 final: zero measured effect, adds risk.]
    Deterministic ordering: targets sorted by node id; candidates sorted by
    (-prob, source_id).
    """
    stats = stats if stats is not None else {}
    n0 = len(edges)

    learned_probs = {}
    for edge in raw_edges:
        p = edge.get("edge_prob")
        if p is None:
            continue
        try:
            p = float(p)
        except (TypeError, ValueError):
            continue
        if np.isfinite(p):
            key = (int(edge["source_id"]), int(edge["target_id"]))
            learned_probs[key] = max(learned_probs.get(key, float("-inf")), p)

    def prob_of(edge):
        return float(learned_probs.get((int(edge["source_id"]), int(edge["target_id"])), 0.0))

    succ = defaultdict(list)
    for e in edges:
        succ[int(e["source_id"])].append(int(e["target_id"]))
    in_edges = {}
    for e in edges:
        in_edges[int(e["target_id"])] = e

    cand_in = defaultdict(list)
    for (s, t), p in learned_probs.items():
        s, t = int(s), int(t)
        if p >= threshold and s in nodes_by_id and t in nodes_by_id:
            if max_edge_um > 0:
                d = float(np.linalg.norm(
                    np.asarray([float(nodes_by_id[s]["z"]), float(nodes_by_id[s]["y"]),
                                float(nodes_by_id[s]["x"])], float)
                    - np.asarray([float(nodes_by_id[t]["z"]), float(nodes_by_id[t]["y"]),
                                  float(nodes_by_id[t]["x"])], float)
                ))
                if d > max_edge_um:
                    continue
            cand_in[t].append((float(p), s, t))
    for t in cand_in:
        cand_in[t].sort(reverse=True)  # (-prob desc by p then source asc via tuple)

    def out_degree(s):
        return len(succ.get(int(s), []))

    # Continuity prior for candidate sources: a source with no strong learned
    # IN-edge (a real cell has a parent edge of its own) is likely a
    # ghost/duplicate detection, not a reliable parent. Key by TARGET id.
    best_in_prob = {}
    for (_s, t), p in learned_probs.items():
        t = int(t)
        if p > best_in_prob.get(t, 0.0):
            best_in_prob[t] = float(p)

    n_swap = 0
    n_add = 0
    touched_targets = set()

    # ---- S1 swaps ----
    for t in sorted(in_edges):
        cur = in_edges[t]
        cur_s = int(cur["source_id"])
        cur_p = prob_of(cur)
        if cur_p >= threshold:
            continue  # high-confidence current edge: leave alone
        best = None
        for p, s, _tt in cand_in.get(t, []):
            if s == cur_s:
                continue
            if p - cur_p < margin:
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
        new_edge = {
            "source_id": s,
            "target_id": t,
            "edge_prob": p,
            "distance_um": float(np.linalg.norm(
                np.asarray([float(nodes_by_id[s]["z"]), float(nodes_by_id[s]["y"]),
                            float(nodes_by_id[s]["x"])], float)
                - np.asarray([float(nodes_by_id[t]["z"]), float(nodes_by_id[t]["y"]),
                              float(nodes_by_id[t]["x"])], float)
            )),
            "v72_reassign": 1,
        }
        # replace cur in the edge list
        for i, e in enumerate(edges):
            if e is cur:
                edges[i] = new_edge
                break
        succ[cur_s].remove(t)
        succ[s].append(t)
        in_edges[t] = new_edge
        touched_targets.add(t)
        n_swap += 1
        stats.setdefault("v72_swaps", []).append((cur_s, t, s, round(cur_p, 4), round(p, 4)))

    # ---- S2 adds (targets without any in-edge) ----
    if do_add_unassigned:
        add_count_by_source = defaultdict(int)
        for t in sorted(cand_in):
            if t in in_edges:
                continue
            added = False
            for p, s, _tt in cand_in[t]:
                if out_degree(s) >= 2:
                    continue
                if add_count_by_source[s] >= max_add_per_source:
                    continue
                if best_in_prob.get(s, 0.0) < source_continuity_min:
                    continue
                edges.append({
                    "source_id": s,
                    "target_id": t,
                    "edge_prob": p,
                    "distance_um": float(np.linalg.norm(
                        np.asarray([float(nodes_by_id[s]["z"]), float(nodes_by_id[s]["y"]),
                                    float(nodes_by_id[s]["x"])], float)
                        - np.asarray([float(nodes_by_id[t]["z"]), float(nodes_by_id[t]["y"]),
                                      float(nodes_by_id[t]["x"])], float)
                    )),
                    "v72_add": 1,
                })
                succ[s].append(t)
                in_edges[t] = edges[-1]
                add_count_by_source[s] += 1
                n_add += 1
                stats.setdefault("v72_adds", []).append((s, t, round(p, 4)))
                added = True
                break

    # ---- final enforcement (belt & suspenders): single in-edge per target,
    # out-degree <= 2 per source, keep highest learned prob ----
    by_target = defaultdict(list)
    by_source = defaultdict(list)
    for e in edges:
        by_target[int(e["target_id"])].append(e)
        by_source[int(e["source_id"])].append(e)
    drop = set()
    for t, es in by_target.items():
        if len(es) > 1:
            es.sort(key=lambda e: (prob_of(e), -float(e.get("distance_um", 0.0))), reverse=True)
            for e in es[1:]:
                drop.add(id(e))
    for s, es in by_source.items():
        if len(es) > 2:
            es.sort(key=lambda e: (prob_of(e), -float(e.get("distance_um", 0.0))), reverse=True)
            for e in es[2:]:
                drop.add(id(e))
    if drop:
        edges = [e for e in edges if id(e) not in drop]
        stats["v72_enforcement_dropped"] = len(drop)
    else:
        stats["v72_enforcement_dropped"] = 0

    stats["v72_edges_before"] = n0
    stats["v72_edges_after"] = len(edges)
    stats["v72_swaps_n"] = n_swap
    stats["v72_adds_n"] = n_add
    return edges, stats
