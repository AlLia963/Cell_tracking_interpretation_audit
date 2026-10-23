# Cell 1 — Config & preset (verbatim from base cell 4)
# v7.0 keeps the exact base preset values. BIOHUB_V7_PRISTINE=1 is an
# explicit no-op escape hatch documenting that this IS the base behavior.
import os
BIOHUB_PRESET = 'gap2_joint_node_budget'
BIOHUB_SCORE_AXIS = 'enable the previously-disabled two-frame (recover_strict_gap2) gap recovery, but replace its independent synthetic-node cap and close_single_frame_gaps\' independent cap with one shared, monotonically-decreasing node-insertion budget threaded through both stages; forward acceleration lookahead, ranker evidence, and every other stage remain fixed'

# Parameters for constrained lineage reconstruction.
os.environ["BIOHUB_OUTPUT_FILTER_SHORT_TRACKS"] = "1"
os.environ["BIOHUB_DET_THRESHOLD"] = "0.96875"
os.environ["BIOHUB_MOTION_RELINK_LEARNED_BONUS"] = '1.0'
os.environ["BIOHUB_ILP_APPEARANCE_WEIGHT"] = "0.0"
os.environ["BIOHUB_ILP_DISAPPEARANCE_WEIGHT"] = "1.5"
os.environ["BIOHUB_GAP_CLOSE_MAX_GAP"] = "2"
os.environ["BIOHUB_GAP_CLOSE_UM"] = "5.8"
os.environ["BIOHUB_GAP_DENSITY_ADAPTIVE"] = "1"
os.environ["BIOHUB_GAP_DENSITY_REFERENCE_UM"] = "6.5"
os.environ["BIOHUB_GAP_DENSITY_GAIN"] = "0.040"
os.environ["BIOHUB_GAP_DENSITY_MAX_STEP_DELTA_UM"] = "0.125"
os.environ["BIOHUB_GAP_DENSITY_NEIGHBORS"] = "3"
os.environ["BIOHUB_OUTPUT_MIN_TRACK_LEN"] = "6"
os.environ["BIOHUB_OUTPUT_KEEP_DIVISION_COMPONENTS"] = "1"
os.environ["BIOHUB_OUTPUT_GAP2_RECOVERY"] = "1"
os.environ["BIOHUB_SHARED_SYNTHETIC_NODE_BUDGET_FRAC"] = "0.05"
os.environ["BIOHUB_SHARED_SYNTHETIC_NODE_BUDGET_ABS"] = "2000"
os.environ["BIOHUB_SAFE_DIV_MAX_UM"] = "4.66"
os.environ["BIOHUB_SAFE_DIV_SISTER_MAX_UM"] = '8.5'
os.environ["BIOHUB_SAFE_DIV_EXISTING_CHILD_MAX_UM"] = "7.65"
os.environ["BIOHUB_SAFE_DIV_FRAME_FRAC_CAP"] = "0.0076"
os.environ["BIOHUB_SAFE_DIV_GLOBAL_FRAC_CAP"] = "0.00375"
os.environ["BIOHUB_ADAPTIVE_SHORT_TRACK_RESCUE"] = "0"
os.environ["BIOHUB_USE_DEEPCENTER_VETO"] = '0'
os.environ["BIOHUB_REQUIRE_DEEPCENTER_VETO"] = '0'
os.environ["BIOHUB_DEEPCENTER_EXPECTED_EPOCH"] = '0'
os.environ["BIOHUB_DEEPCENTER_GAP_CONFIRM_MIN_SPAN_UM"] = "8.0"
os.environ["BIOHUB_DEEPCENTER_CHECKPOINT"] = ''
os.environ["BIOHUB_DEEPCENTER_GAP_VETO"] = '0'
os.environ["BIOHUB_DEEPCENTER_GAP_THRESHOLD"] = "0.20"
os.environ["BIOHUB_DEEPCENTER_SAFE_DIV_VETO"] = '0'
os.environ["BIOHUB_RUN_OUTPUT_DIAGNOSTICS"] = "0"
os.environ["BIOHUB_BIDIRECTIONAL_EDGE_WEIGHT"] = "0.20"
os.environ["BIOHUB_BIDIRECTIONAL_FUSION_MODE"] = "harmonic_probability"
os.environ["BIOHUB_EDGE_TTA_MODE"] = "js_reliability_log_pool"
os.environ["BIOHUB_EDGE_TTA_VIEWS"] = "4"
os.environ["BIOHUB_USE_LOCAL_ASSOCIATION_RANKER"] = "1"
os.environ["BIOHUB_LOCAL_RANKER_MODE"] = "full_motion_assignment"
os.environ["BIOHUB_LOCAL_RANKER_FULL_WEIGHT"] = "0.85"
os.environ["BIOHUB_LOCAL_RANKER_PRIMARY_RETAIN_WEIGHT"] = "0.15"
os.environ["BIOHUB_LOCAL_RANKER_MARGIN_UM"] = "0.35"
os.environ["BIOHUB_LOCAL_RANKER_MIN_ADVANTAGE"] = "0.15"
os.environ["BIOHUB_LOCAL_RANKER_MAX_BONUS"] = "0.20"
os.environ["BIOHUB_USE_FORWARD_ACCELERATION_LOOKAHEAD"] = "1"
os.environ["BIOHUB_FORWARD_LOOKAHEAD_MAX_ACCEL_UM"] = "4.0"
os.environ["BIOHUB_FORWARD_LOOKAHEAD_MAX_BONUS"] = "0.20"

print("BIOHUB_PRESET:", BIOHUB_PRESET)
print("BIOHUB_SCORE_AXIS:", BIOHUB_SCORE_AXIS)


# ---- v7.2 evidence-aware reassignment (default ON) ----
# S1/S2 restore learned-candidate edges that repair stages replaced/missed.
# BIOHUB_V72_REASSIGN=0 restores exact v7.0 behavior.
os.environ["BIOHUB_V72_REASSIGN"] = "1"
os.environ["BIOHUB_V72_THRESHOLD"] = "0.80"
os.environ["BIOHUB_V72_MARGIN"] = "0.10"
os.environ["BIOHUB_V72_ADD_UNASSIGNED"] = "1"
os.environ["BIOHUB_V72_SOURCE_CONTINUITY_MIN"] = "0.70"
os.environ["BIOHUB_V72_MAX_EDGE_UM"] = "0.0"
V72_REASSIGN = os.environ.get("BIOHUB_V72_REASSIGN", "1") == "1"
V72_THRESHOLD = float(os.environ.get("BIOHUB_V72_THRESHOLD", "0.85"))
V72_MARGIN = float(os.environ.get("BIOHUB_V72_MARGIN", "0.10"))
V72_ADD_UNASSIGNED = os.environ.get("BIOHUB_V72_ADD_UNASSIGNED", "1") == "1"
V72_SOURCE_CONTINUITY_MIN = float(os.environ.get("BIOHUB_V72_SOURCE_CONTINUITY_MIN", "0.70"))
V72_MAX_EDGE_UM = float(os.environ.get("BIOHUB_V72_MAX_EDGE_UM", "0.0"))
print("V72_REASSIGN:", V72_REASSIGN)

# ---- v7.4 ranker-evidence pass (default ON; 0 restores exact v7.3) ----
os.environ["BIOHUB_V74_REASSIGN"] = "1"
os.environ["BIOHUB_V74_R_THR"] = "0.80"
os.environ["BIOHUB_V74_R_MARGIN"] = "0.10"
os.environ["BIOHUB_V74_ADD"] = "1"
os.environ["BIOHUB_V74_SOURCE_CONTINUITY_MIN"] = "0.70"
V74_REASSIGN = os.environ.get("BIOHUB_V74_REASSIGN", "1") == "1"
V74_R_THR = float(os.environ.get("BIOHUB_V74_R_THR", "0.80"))
V74_R_MARGIN = float(os.environ.get("BIOHUB_V74_R_MARGIN", "0.10"))
V74_ADD = os.environ.get("BIOHUB_V74_ADD", "1") == "1"
V74_SOURCE_CONTINUITY_MIN = float(os.environ.get("BIOHUB_V74_SOURCE_CONTINUITY_MIN", "0.70"))
print("V74_REASSIGN:", V74_REASSIGN)
