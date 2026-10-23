# Cell 10 — Motion relink (association core, 1:1 Hungarian with ranker-fused
# cost + forward lookahead bonus). Verbatim from base cell 15.
def motion_relink_edges(
    nodes_by_id: dict[int, dict[str, object]],
    stats: dict[str, int],
    learned_edge_probs: dict[tuple[int, int], float] | None = None,
    raw_edges_for_context: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    if not OUTPUT_MOTION_RELINK or not nodes_by_id:
        return []
    if LOCAL_ASSOCIATION_RANKER is None:
        raise RuntimeError('Local association ranker was not loaded during preflight.')

    learned_edge_probs = learned_edge_probs or {}
    raw_edges_for_context = raw_edges_for_context or []
    global nodes_by_id_global_for_ranker
    nodes_by_id_global_for_ranker = nodes_by_id
    ranker_context = _ranker_context(nodes_by_id, raw_edges_for_context)

    def learned_prob(source_id: int, target_id: int) -> float:
        value = learned_edge_probs.get((source_id, target_id), 0.0)
        try:
            value = float(value)
        except (TypeError, ValueError):
            return 0.0
        if not np.isfinite(value):
            return 0.0
        if value < 0.0 or value > 1.0:
            value = 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, value))))
        return float(np.clip(value, 0.0, 1.0))

    ids_by_t: dict[int, list[int]] = {}
    for node_id, node in nodes_by_id.items():
        ids_by_t.setdefault(int(node['t']), []).append(node_id)
    for ids in ids_by_t.values():
        ids.sort()

    frame_sizes = [len(ids) for ids in ids_by_t.values()]
    if frame_sizes and max(frame_sizes) > MOTION_RELINK_MAX_FRAME_NODES:
        stats['motion_relink_skipped_large_frame'] = 1
        return []

    position_um = {node_id: _position_um(node) for node_id, node in nodes_by_id.items()}
    node_time = {node_id: int(node['t']) for node_id, node in nodes_by_id.items()}
    predecessor_position_um: dict[int, np.ndarray] = {}
    selected_edges: list[dict[str, object]] = []

    def assign_pass(
        source_ids: list[int],
        target_ids: list[int],
        gate_um: float,
    ) -> list[tuple[int, int, float, float, float]]:
        if not source_ids or not target_ids:
            return []
        big = gate_um * 1000.0 + 1.0
        cost = np.full((len(source_ids), len(target_ids)), big, dtype=np.float64)
        baseline_cost = np.full_like(cost, big)
        raw_dist = np.full_like(cost, np.inf)
        motion_dist = np.full_like(cost, np.inf)
        primary_matrix = np.zeros_like(cost)
        ranker_matrix = np.zeros_like(cost)
        predicted_by_source: dict[int, np.ndarray] = {}
        valid_by_row: dict[int, list[int]] = {}

        for i, source_id in enumerate(source_ids):
            source_pos = position_um[source_id]
            prev_pos = predecessor_position_um.get(source_id)
            predicted = source_pos if prev_pos is None else source_pos + MOTION_RELINK_VELOCITY_WEIGHT * (source_pos - prev_pos)
            predicted_by_source[source_id] = predicted
            valid_cols = []
            for j, target_id in enumerate(target_ids):
                target_pos = position_um[target_id]
                raw = float(np.linalg.norm(target_pos - source_pos))
                if raw > gate_um:
                    continue
                motion = float(np.linalg.norm(target_pos - predicted))
                prob = learned_prob(source_id, target_id)
                raw_dist[i, j] = raw
                motion_dist[i, j] = motion
                primary_matrix[i, j] = prob
                baseline_cost[i, j] = motion + 0.05 * raw - MOTION_RELINK_LEARNED_BONUS * prob
                valid_cols.append(j)
            valid_by_row[i] = valid_cols

        records = []
        record_locations = []
        for i, source_id in enumerate(source_ids):
            valid_cols = valid_by_row.get(i, [])
            if not valid_cols:
                continue
            # Public feature candidate_rank_dist is the 1-based rank by raw physical distance.
            ranked_cols_dist = sorted(valid_cols, key=lambda col: (raw_dist[i, col], target_ids[col]))
            rank_by_col_dist = {col: rank + 1 for rank, col in enumerate(ranked_cols_dist)}
            for col in valid_cols:
                target_id = target_ids[col]
                records.append({
                    'source_id': source_id,
                    'target_id': target_id,
                    'raw_distance_um': float(raw_dist[i, col]),
                    'motion_distance_um': float(motion_dist[i, col]),
                    'primary_prob': float(primary_matrix[i, col]),
                    'has_learned_edge': bool((source_id, target_id) in learned_edge_probs),
                    'candidate_rank_dist': int(rank_by_col_dist[col]),
                    'candidate_count': int(len(valid_cols)),
                    'predicted_position_um': predicted_by_source[source_id],
                    'context': ranker_context,
                })
                record_locations.append((i, col))
        if records:
            feature_matrix = _ranker_matrix(records)
            ranker_probs = LOCAL_ASSOCIATION_RANKER.predict_proba(feature_matrix)
            for (i, col), prob in zip(record_locations, ranker_probs):
                ranker_matrix[i, col] = float(prob)
            stats['local_ranker_candidates'] += len(records)
            stats['local_ranker_scored'] += len(records)
            stats['local_ranker_probability_milli_sum'] += int(round(float(ranker_probs.sum()) * 1000.0))

        if LOCAL_ASSOCIATION_RANKER_MODE == 'full_motion_assignment':
            for i, valid_cols in valid_by_row.items():
                if not valid_cols:
                    continue
                stats['local_ranker_full_rows'] += 1
                for col in valid_cols:
                    evidence = (
                        LOCAL_ASSOCIATION_RANKER_FULL_WEIGHT * ranker_matrix[i, col]
                        + LOCAL_ASSOCIATION_PRIMARY_RETAIN_WEIGHT * primary_matrix[i, col]
                    )
                    cost[i, col] = motion_dist[i, col] + 0.05 * raw_dist[i, col] - MOTION_RELINK_LEARNED_BONUS * evidence
                    if USE_FORWARD_ACCELERATION_LOOKAHEAD:
                        target_id = target_ids[col]
                        residual_um, continuation_count = forward_acceleration_lookahead(
                            source_ids[i],
                            target_id,
                            node_time,
                            ids_by_t,
                            position_um,
                            next_step_gate_um=MOTION_RELINK_RELAXED_UM,
                        )
                        if continuation_count > 0:
                            stats['forward_lookahead_candidates'] += int(continuation_count)
                            stats['forward_lookahead_supported_edges'] += 1
                        bonus = forward_acceleration_bonus(
                            residual_um,
                            FORWARD_LOOKAHEAD_MAX_ACCEL_UM,
                            FORWARD_LOOKAHEAD_MAX_BONUS,
                        )
                        if bonus > 0.0:
                            cost[i, col] -= bonus
                            stats['forward_lookahead_bonus_edges'] += 1
                            stats['forward_lookahead_bonus_milli_sum'] += int(round(bonus * 1000.0))
        elif LOCAL_ASSOCIATION_RANKER_MODE == 'low_margin_top2_rescue':
            cost[:, :] = baseline_cost
            for i, valid_cols in valid_by_row.items():
                if len(valid_cols) < 2:
                    continue
                ordered = sorted(valid_cols, key=lambda col: (baseline_cost[i, col], target_ids[col]))
                best_col, second_col = ordered[0], ordered[1]
                margin = float(baseline_cost[i, second_col] - baseline_cost[i, best_col])
                if margin > LOCAL_ASSOCIATION_RANKER_MARGIN_UM:
                    continue
                stats['local_ranker_ambiguous_rows'] += 1
                ranker_best = ranker_matrix[i, best_col]
                ranker_second = ranker_matrix[i, second_col]
                advantage = float(ranker_second - ranker_best)
                if advantage < LOCAL_ASSOCIATION_RANKER_MIN_ADVANTAGE:
                    continue
                bonus = min(LOCAL_ASSOCIATION_RANKER_MAX_BONUS, advantage)
                cost[i, second_col] -= bonus
                stats['local_ranker_rescue_adjustments'] += 1
                stats['local_ranker_rescue_bonus_milli_sum'] += int(round(bonus * 1000.0))
        else:
            raise RuntimeError(f'Unknown BIOHUB_LOCAL_RANKER_MODE={LOCAL_ASSOCIATION_RANKER_MODE!r}')

        row_ind, col_ind = linear_sum_assignment(cost)
        matches: list[tuple[int, int, float, float, float]] = []
        for r, c in zip(row_ind, col_ind):
            if cost[r, c] >= big:
                continue
            matches.append((
                source_ids[int(r)],
                target_ids[int(c)],
                float(raw_dist[r, c]),
                float(motion_dist[r, c]),
                float(ranker_matrix[r, c]),
            ))
        return matches

    times = sorted(ids_by_t)
    for t in times:
        source_ids = ids_by_t.get(t, [])
        target_ids = ids_by_t.get(t + 1, [])
        if not source_ids or not target_ids:
            continue
        unmatched_sources = set(source_ids)
        unmatched_targets = set(target_ids)
        frame_matches: list[tuple[int, int, float, float, str, float]] = []
        for pass_name, gate_um in (('tight', MOTION_RELINK_TIGHT_UM), ('relaxed', MOTION_RELINK_RELAXED_UM)):
            pass_sources = [node_id for node_id in source_ids if node_id in unmatched_sources]
            pass_targets = [node_id for node_id in target_ids if node_id in unmatched_targets]
            matches = assign_pass(pass_sources, pass_targets, gate_um)
            for source_id, target_id, raw, motion, ranker_prob in matches:
                if source_id not in unmatched_sources or target_id not in unmatched_targets:
                    continue
                unmatched_sources.remove(source_id)
                unmatched_targets.remove(target_id)
                frame_matches.append((source_id, target_id, raw, motion, pass_name, ranker_prob))
                if pass_name == 'tight':
                    stats['motion_relink_tight_edges'] += 1
                else:
                    stats['motion_relink_relaxed_edges'] += 1
        for source_id, target_id, raw, motion, pass_name, ranker_prob in frame_matches:
            selected_edges.append({
                'source_id': source_id,
                'target_id': target_id,
                'edge_prob': ranker_prob,
                'distance_um': raw,
                'motion_distance_um': motion,
                'motion_relinked': 1,
                'motion_pass': pass_name,
                'local_ranker_prob': ranker_prob,
            })
            predecessor_position_um[target_id] = position_um[source_id]
        stats['motion_relink_frames'] += 1

    stats['motion_relink_edges'] = len(selected_edges)
    return selected_edges


