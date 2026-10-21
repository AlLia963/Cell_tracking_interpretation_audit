"""Local candidate API for supplied coordinate graphs and mask instances.

These are separate measurement interfaces. Mask instances have no semantic
type schema. Supplied mapping families are not inferred or certified complete.
"""

from ._upstream.stage_accounting import Graph, account_from_matches
from ._upstream.stage_accounting import match as match_coordinates
from ._upstream.mask_correspondence import MaskFrame
from ._upstream.mask_correspondence import match_iou as match_masks_iou
from ._upstream.family_accounting import account_from_mapping_families
from ._upstream.coupled_accounting import coupled_aggregate_bounds
from .typed import (account_typed_from_matches, disjoint_mask_options,
                    mask_edge_visibility_envelope)

__version__ = "0.1.0"
__all__ = [
    "Graph", "MaskFrame", "match_coordinates", "match_masks_iou",
    "account_from_matches", "account_from_mapping_families",
    "coupled_aggregate_bounds", "history_features",
    "account_typed_from_matches", "disjoint_mask_options",
    "mask_edge_visibility_envelope",
]


def history_features(history):
    """Integer additive features used by the CLI; stage indices are zero based.

    An observed loss is a 1-to-0 transition. A later gain can restore final
    visibility. These are reference-relative observations, not causal labels.
    """
    if len(history) < 2 or any(value not in (0, 1) for value in history):
        raise ValueError("At least two binary stage values are required")
    losses = sum(history[k - 1] == 1 and history[k] == 0
                 for k in range(1, len(history)))
    final_missing = int(history[-1] == 0)
    return {
        "final_missing": final_missing,
        "final_visible": int(history[-1] == 1),
        "persistent_absence": int(not any(history)),
        "observed_loss_transitions": losses,
        "final_missing_after_observed_loss": int(final_missing and losses > 0),
    }
