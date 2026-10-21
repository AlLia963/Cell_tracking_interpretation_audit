"""Readout of caller-declared complete joint visibility component families.

Feasibility, correspondence optimality/completeness and product factorization
are adapter responsibilities. This module accepts correlated histories rather
than silently replacing them with independent per-edge marginal sets.
"""
from numbers import Integral


def joint_stage_features(history):
    """Additive descriptive features; a transition is not an identity change."""
    if len(history) < 2 or any(isinstance(v, bool) or not isinstance(v, Integral) or v not in (0, 1) for v in history):
        raise ValueError("At least two integral binary visibility values required")
    losses = [k for k in range(1, len(history)) if history[k-1] == 1 and history[k] == 0]
    gains = [k for k in range(1, len(history)) if history[k-1] == 0 and history[k] == 1]
    missing = history[-1] == 0
    values = {
        "final_missing": int(missing),
        "persistent_absence": int(not any(history)),
        "final_missing_with_loss": int(missing and bool(losses)),
        "visibility_transition_edges": int(bool(losses or gains)),
        "first_last_loss_disagreements_final_missing": int(missing and bool(losses) and losses[0] != losses[-1]),
        "final_last_loss_persistent": int(missing and not losses),
    }
    values.update({f"stage_visible_{k}": int(v) for k, v in enumerate(history)})
    for k in range(1, len(history)):
        values[f"gain_{k}"] = int(k in gains)
        values[f"loss_{k}"] = int(k in losses)
        values[f"final_last_loss_{k}"] = int(missing and bool(losses) and losses[-1] == k)
    return values


def _key(value):
    if not isinstance(value, list) or not value:
        raise ValueError("A reference identity is a nonempty list of strings/integers")
    if any(isinstance(v, bool) or not isinstance(v, (str, int)) or isinstance(v, str) and not v for v in value):
        raise ValueError("Identity fields require nonempty strings or integer IDs; floats/bools rejected")
    return tuple(value)


def _history(value, stage_count):
    if not isinstance(value, str) or len(value) != stage_count or set(value) - {"0", "1"}:
        raise ValueError("Each visibility history requires exactly stage_count binary characters")
    return tuple(int(v) for v in value)


def account_joint_history_components(data, *, max_configurations_per_component=65536):
    """Exact separate scalar bounds conditional on declared product components.

    Input validation consumes the full supplied family, including when its cap
    withholds a result. The cap does not truncate alternatives or bound input
    validation cost. Duplicate configurations are allowed as repeated supplied
    correspondence witnesses; they never add statistical replication.
    """
    required = {"reference_edge_ids", "stage_count", "fixed_histories", "components",
                "completeness_asserted_by_caller", "product_factorization_asserted_by_caller",
                "joint_family_rule"}
    if not isinstance(data, dict) or set(data) != required:
        raise ValueError("Joint-history document requires exactly its declared schema keys")
    if data["completeness_asserted_by_caller"] is not True or data["product_factorization_asserted_by_caller"] is not True:
        raise ValueError("Explicit caller completeness and Cartesian-factorization declarations required")
    if not isinstance(data["joint_family_rule"], str) or not data["joint_family_rule"].strip():
        raise ValueError("Nonempty joint-family rule required")
    count = data["stage_count"]
    if isinstance(count, bool) or not isinstance(count, int) or count < 2:
        raise ValueError("At least two ordered stages required")
    if isinstance(max_configurations_per_component, bool) or not isinstance(max_configurations_per_component, int) or max_configurations_per_component < 1:
        raise ValueError("Positive integral component configuration cap required")
    if not isinstance(data["reference_edge_ids"], list) or not data["reference_edge_ids"]:
        raise ValueError("Nonempty explicit reference identity domain required")
    keys = [_key(q) for q in data["reference_edge_ids"]]
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate reference identity")
    domain = set(keys)
    if not isinstance(data["fixed_histories"], list) or not isinstance(data["components"], list):
        raise ValueError("Fixed histories and components require explicit lists")
    used = set()
    fixed = []
    for row in data["fixed_histories"]:
        if not isinstance(row, dict) or set(row) != {"reference_edge_id", "history"}:
            raise ValueError("Fixed history row has invalid keys")
        key = _key(row["reference_edge_id"])
        if key not in domain or key in used:
            raise ValueError("Unknown/duplicate/overlapping fixed reference identity")
        used.add(key)
        fixed.append((key, _history(row["history"], count)))
    components = []
    for component in data["components"]:
        if not isinstance(component, dict) or set(component) != {"reference_edge_ids", "configurations"}:
            raise ValueError("Component requires exactly reference_edge_ids and configurations")
        if not isinstance(component["reference_edge_ids"], list) or not component["reference_edge_ids"]:
            raise ValueError("Every component requires a nonempty identity list")
        local = [_key(q) for q in component["reference_edge_ids"]]
        if len(set(local)) != len(local) or not set(local) <= domain or set(local) & used:
            raise ValueError("Unknown/duplicate/overlapping component reference identities")
        used.update(local)
        raw_configs = component["configurations"]
        if not isinstance(raw_configs, list) or not raw_configs:
            raise ValueError("Every component requires a nonempty full configuration family")
        configs = []
        for row in raw_configs:
            if not isinstance(row, list) or len(row) != len(local):
                raise ValueError("Configuration history width must match its component identity list")
            configs.append(tuple(_history(h, count) for h in row))
        components.append((local, configs))
    if used != domain:
        raise ValueError("Fixed and component identities must cover the entire declared reference domain exactly")
    if any(len(configs) > max_configurations_per_component for _, configs in components):
        return {
            "status": "WITHHELD_COMPONENT_CONFIGURATION_CAP", "records": None, "scalar_bounds": None,
            "declared_component_sizes": [len(c) for _, c in components], "cap": max_configurations_per_component,
            "no_truncated_results_reported": True, "input_validation_complete": True,
            "family_completeness_or_factorization_certified_by_module": False,
        }
    names = tuple(joint_stage_features((0,) * count))
    lower = {name: 0 for name in names}
    upper = dict(lower)
    histories = {key: {h} for key, h in fixed}
    for _, h in fixed:
        for name, value in joint_stage_features(h).items():
            lower[name] += value
            upper[name] += value
    component_summary = []
    for local, configs in components:
        totals = []
        for config in configs:
            total = {name: 0 for name in names}
            for key, h in zip(local, config):
                histories.setdefault(key, set()).add(h)
                for name, value in joint_stage_features(h).items():
                    total[name] += value
            totals.append(total)
        for name in names:
            lower[name] += min(t[name] for t in totals)
            upper[name] += max(t[name] for t in totals)
        component_summary.append({"supplied_configurations": len(configs),
                                  "distinct_joint_visibility_configurations": len(set(configs)),
                                  "reference_edge_count": len(local)})
    records = []
    for key in keys:
        alternatives = sorted("".join(map(str, h)) for h in histories[key])
        categories = set()
        for h in histories[key]:
            loss = [k for k in range(1, count) if h[k-1] == 1 and h[k] == 0]
            categories.add("final_present" if h[-1] else f"loss_stage_{loss[-1]}" if loss else "persistent_absence")
        records.append({"reference_edge_id": list(key), "admissible_visibility_strings": alternatives,
                        "final_history_categories": sorted(categories), "history_determinate": len(alternatives) == 1})
    return {
        "status": "EXACT_READOUT_CONDITIONAL_ON_SUPPLIED_JOINT_COMPONENT_FAMILY",
        "reference_edge_count": len(keys), "stage_count": count, "records": records,
        "scalar_bounds": {name: {"minimum": lower[name], "maximum": upper[name]} for name in names},
        "components": component_summary, "fixed_edge_count": len(fixed),
        "joint_family_rule": data["joint_family_rule"],
        "separate_scalar_extrema_conditional_on_caller_product_family": True,
        "arbitrary_extrema_vector_certified": False,
        "family_completeness_or_factorization_certified_by_module": False,
        "mapping_eligibility_or_equality_links_inferred": False,
        "typed_semantics_inferred": False, "biological_truth_certified": False,
        "pipeline_causal_independence_certified": False, "new_statistical_replication": False,
    }
