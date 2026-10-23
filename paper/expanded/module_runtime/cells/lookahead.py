# Cell 6 — Forward-acceleration lookahead (verbatim from base cell 11)
# Exact preflight for the forward acceleration lookahead used later in motion assignment.
import numpy as np


def forward_acceleration_lookahead(
    source_id: int,
    target_id: int,
    node_time: dict[int, int],
    ids_by_t: dict[int, list[int]],
    position_um: dict[int, np.ndarray],
    next_step_gate_um: float,
) -> tuple[float | None, int]:
    source_pos = np.asarray(position_um[source_id], dtype=np.float64)
    target_pos = np.asarray(position_um[target_id], dtype=np.float64)
    target_t = int(node_time[target_id])
    future_ids = ids_by_t.get(target_t + 1, [])
    current_velocity = target_pos - source_pos
    residuals: list[float] = []
    for next_id in future_ids:
        next_pos = np.asarray(position_um[next_id], dtype=np.float64)
        next_velocity = next_pos - target_pos
        if float(np.linalg.norm(next_velocity)) > float(next_step_gate_um):
            continue
        residual = float(np.linalg.norm(next_velocity - current_velocity))
        if np.isfinite(residual):
            residuals.append(residual)
    if not residuals:
        return None, 0
    return min(residuals), len(residuals)


def forward_acceleration_bonus(residual_um: float | None, max_accel_um: float, max_bonus: float) -> float:
    if residual_um is None or not np.isfinite(residual_um) or max_accel_um <= 0 or max_bonus <= 0:
        return 0.0
    support = max(0.0, 1.0 - float(residual_um) / float(max_accel_um))
    return float(max_bonus) * support


# Semantic unit test: straight continuation receives full support; a sharp turn receives less.
_test_time = {1: 0, 2: 1, 3: 2, 4: 2}
_test_ids = {0: [1], 1: [2], 2: [3, 4]}
_test_pos = {
    1: np.array([0.0, 0.0, 0.0]),
    2: np.array([0.0, 1.0, 0.0]),
    3: np.array([0.0, 2.0, 0.0]),
    4: np.array([0.0, 1.0, 3.0]),
}
_test_residual, _test_count = forward_acceleration_lookahead(1, 2, _test_time, _test_ids, _test_pos, 10.0)
_test_bonus = forward_acceleration_bonus(_test_residual, 4.0, 0.20)
assert _test_count == 2
assert abs(float(_test_residual)) < 1e-12
assert abs(_test_bonus - 0.20) < 1e-12
print('Forward-acceleration semantic preflight: PASS | residual=', _test_residual, '| bonus=', _test_bonus)
