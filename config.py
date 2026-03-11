"""
Default assumptions, pricing lever bounds, and win-rate model config.
All values are configurable via the Streamlit UI.
"""

# ── SaaS Defaults ──────────────────────────────────────────────
SAAS_ARR_DEFAULT = 25_000          # $/year (standard list price)
SAAS_IMPL_FEE_DEFAULT = 3_000      # $ one-time implementation fee
SAAS_ARR_MARGIN = 0.85             # 85% margin on ARR

# ── CC Defaults ────────────────────────────────────────────────
CC_STANDARD_BASE_RATE = 0.022      # 2.20% standard base CC rate
CC_STANDARD_AMEX_RATE = 0.035      # 3.50% AMEX standard
CC_FIXED_COMPONENT = 0.0053        # 0.53% fixed component (mid-tier cards, assessments, etc.)
CC_BASE_VOLUME_SHARE = 0.75        # 75% of CC volume at base rate
CC_AMEX_VOLUME_SHARE = 0.25        # 25% of CC volume at AMEX rate
CC_COST_RATE = 0.024               # 2.40% blended cost (interchange + assessments + markup)

# ── ACH / Bank Network Defaults ───────────────────────────────
ACH_STANDARD_RATE = 0.0008         # 0.08% standard revenue rate
ACH_COST_PER_TXN = 0.13           # $0.13 per transaction cost
ACH_AVG_TXN_SIZE = 1_700          # $1,700 average transaction size

# ── Hold Time (per payment type) ──────────────────────────────
HOLD_DAYS_CC_DEFAULT = 2
HOLD_DAYS_ACH_DEFAULT = 6
HOLD_DAYS_BANK_DEFAULT = 4
FLOAT_ANNUAL_RATE = 0.065          # 6.5% return on float balances
FLOAT_CALENDAR_FACTOR = 7 / 5     # convert business hold days to calendar days
SAAS_ANNUAL_ESCALATOR = 0.07       # 7% annual increase on standard ARR

# ── Pricing Lever Bounds ──────────────────────────────────────
LEVER_BOUNDS = {
    "saas_arr_discount_pct": {"min": 0.0, "max": 0.70, "default": 0.30, "step": 0.05},
    "impl_fee_discount_pct":  {"min": 0.0, "max": 1.0,  "default": 0.0, "step": 0.10},
    "cc_base_rate":           {"min": 0.0199, "max": 0.0239, "default": 0.022, "step": 0.001},
    "cc_amex_rate":           {"min": 0.0315, "max": 0.035, "default": 0.035, "step": 0.005},
    "ach_pct_rate":           {"min": 0.0008, "max": 0.0049, "default": 0.0008, "step": 0.0005},
    "ach_cap":                {"min": 2.50, "max": 10.0, "default": 5.0, "step": 0.50},
    "ach_fixed_fee":          {"min": 1.00, "max": 5.00, "default": 2.50, "step": 0.25},
    "hold_days_cc":           {"min": 1, "max": 2, "default": 2, "step": 1},
    "hold_days_ach":          {"min": 1, "max": 7, "default": 6, "step": 1},
    "hold_days_bank":         {"min": 1, "max": 5, "default": 4, "step": 1},
}

# ── ACH Pricing Modes ─────────────────────────────────────────
ACH_MODES = ["percentage", "capped", "fixed_fee"]

# ── Win Rate Model (simple additive) ─────────────────────────
# Standard pricing = baseline win rate. Each lever adds/subtracts
# linearly based on deviation from standard. Clamped to [floor, ceiling].
WIN_RATE_BASELINE = 0.59           # 59% at standard pricing
WIN_RATE_FLOOR = 0.45              # absolute minimum
WIN_RATE_CEILING = 0.78            # absolute maximum

STANDARD_PRICING = {
    "saas_arr_discount_pct": 0.30,
    "cc_base_rate": 0.022,
    "cc_amex_rate": 0.035,
    "ach_pct_rate": 0.0008,
    "hold_days_cc": 2,
    "hold_days_ach": 3,
    "hold_days_bank": 2,
    "impl_fee_discount_pct": 0.0,
}

# Max win-rate impact per lever (in percentage points).
# Positive = full move toward most competitive end.
# Negative = full move toward least competitive end.
LEVER_MAX_IMPACT = {
    "saas_discount":  0.12,   # ±12pp — dominant lever
    "cc_rate":        0.02,   # ±2pp — small impact
    "ach_rate":       0.05,   # ±5pp — capped
    "hold_time":      0.01,   # ±1pp — minor
    "impl_discount":  0.01,   # ±1pp — minor
}

# ── Teampay Defaults ─────────────────────────────────────────
TEAMPAY_SAAS_ANNUAL = 7_500        # $7,500/year SaaS (free Year 1)
TEAMPAY_SAAS_MARGIN = 0.80         # 80% margin on Teampay SaaS
TEAMPAY_PROCESSING_RATE = 0.023    # 2.3% per transaction
TEAMPAY_PROCESSING_MARGIN = 0.27   # 27% margin on processing
TEAMPAY_MONTHLY_VOLUME = 50_000    # $50k/month per Teampay deal (Y1 at 50% ramp)
