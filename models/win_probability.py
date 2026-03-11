"""
Win rate model — simple additive.

Standard pricing produces the baseline win rate (59%).
Each pricing lever adds or subtracts linearly based on how far
it deviates from standard, capped per lever, then clamped to
[WIN_RATE_FLOOR, WIN_RATE_CEILING].
"""
from __future__ import annotations
import copy

from scipy.optimize import brentq, minimize_scalar

import config as cfg
from models.revenue_model import PricingScenario


def _blended_cc(base_rate: float, amex_rate: float) -> float:
    return (
        cfg.CC_FIXED_COMPONENT
        + base_rate * cfg.CC_BASE_VOLUME_SHARE
        + amex_rate * cfg.CC_AMEX_VOLUME_SHARE
    )


_STD = cfg.STANDARD_PRICING
_STD_CC_BLENDED = _blended_cc(_STD["cc_base_rate"], _STD["cc_amex_rate"])
_BEST_CC_BLENDED = _blended_cc(
    cfg.LEVER_BOUNDS["cc_base_rate"]["min"],
    cfg.LEVER_BOUNDS["cc_amex_rate"]["min"],
)
_WORST_CC_BLENDED = _blended_cc(
    cfg.LEVER_BOUNDS["cc_base_rate"]["max"],
    cfg.LEVER_BOUNDS["cc_amex_rate"]["max"],
)

_IMPACTS = cfg.LEVER_MAX_IMPACT


def _linear_impact(
    value: float,
    standard: float,
    best: float,
    worst: float,
    max_impact: float,
    lower_is_better: bool = True,
) -> float:
    """Compute a linear impact in [-max_impact, +max_impact].

    At ``standard`` → 0.  At ``best`` → +max_impact.  At ``worst`` → -max_impact.
    """
    if lower_is_better:
        if value <= standard:
            denom = standard - best
            if denom == 0:
                return 0.0
            return max_impact * min(1.0, (standard - value) / denom)
        else:
            denom = worst - standard
            if denom == 0:
                return 0.0
            return -max_impact * min(1.0, (value - standard) / denom)
    else:
        if value >= standard:
            denom = best - standard
            if denom == 0:
                return 0.0
            return max_impact * min(1.0, (value - standard) / denom)
        else:
            denom = standard - worst
            if denom == 0:
                return 0.0
            return -max_impact * min(1.0, (standard - value) / denom)


def win_rate(pricing: PricingScenario) -> float:
    """Compute win rate using the simple additive model.

    Returns a value clamped to [WIN_RATE_FLOOR, WIN_RATE_CEILING].
    """
    lb = cfg.LEVER_BOUNDS

    saas_impact = _linear_impact(
        pricing.saas_arr_discount_pct,
        _STD["saas_arr_discount_pct"],
        lb["saas_arr_discount_pct"]["max"],   # 70% = most competitive
        lb["saas_arr_discount_pct"]["min"],    # 0% = least competitive
        _IMPACTS["saas_discount"],
        lower_is_better=False,
    )

    cc_blended = _blended_cc(pricing.cc_base_rate, pricing.cc_amex_rate)
    cc_impact = _linear_impact(
        cc_blended,
        _STD_CC_BLENDED,
        _BEST_CC_BLENDED,
        _WORST_CC_BLENDED,
        _IMPACTS["cc_rate"],
        lower_is_better=True,
    )

    ach_eff = _effective_ach(pricing)
    ach_impact = _linear_impact(
        ach_eff,
        _STD["ach_pct_rate"],
        lb["ach_pct_rate"]["min"],    # lowest rate = most competitive
        lb["ach_pct_rate"]["max"],    # highest rate = least competitive
        _IMPACTS["ach_rate"],
        lower_is_better=True,
    )

    avg_hold = (
        pricing.hold_days_cc * 0.30
        + pricing.hold_days_ach * 0.50
        + pricing.hold_days_bank * 0.20
    )
    std_avg_hold = (
        _STD["hold_days_cc"] * 0.30
        + _STD["hold_days_ach"] * 0.50
        + _STD["hold_days_bank"] * 0.20
    )
    best_hold = (
        lb["hold_days_cc"]["max"] * 0.30
        + lb["hold_days_ach"]["max"] * 0.50
        + lb["hold_days_bank"]["max"] * 0.20
    )
    worst_hold = (
        lb["hold_days_cc"]["min"] * 0.30
        + lb["hold_days_ach"]["min"] * 0.50
        + lb["hold_days_bank"]["min"] * 0.20
    )
    hold_impact = _linear_impact(
        avg_hold, std_avg_hold, best_hold, worst_hold,
        _IMPACTS["hold_time"],
        lower_is_better=False,  # longer hold = more competitive (float trade)
    )

    impl_impact = _linear_impact(
        pricing.impl_fee_discount_pct,
        _STD["impl_fee_discount_pct"],
        lb["impl_fee_discount_pct"]["max"],
        lb["impl_fee_discount_pct"]["min"],
        _IMPACTS["impl_discount"],
        lower_is_better=False,
    )

    total = cfg.WIN_RATE_BASELINE + saas_impact + cc_impact + ach_impact + hold_impact + impl_impact
    return max(cfg.WIN_RATE_FLOOR, min(cfg.WIN_RATE_CEILING, total))


def _effective_ach(pricing: PricingScenario) -> float:
    avg = cfg.ACH_AVG_TXN_SIZE
    if pricing.ach_mode == "percentage":
        return pricing.ach_pct_rate
    elif pricing.ach_mode == "capped":
        uncapped = avg * pricing.ach_pct_rate
        capped = min(uncapped, pricing.ach_cap)
        return capped / avg if avg > 0 else pricing.ach_pct_rate
    elif pricing.ach_mode == "fixed_fee":
        return pricing.ach_fixed_fee / avg if avg > 0 else 0.0
    return pricing.ach_pct_rate


# ── Backwards-compatible aliases used by cohort_engine ────────
def win_probability(pricing: PricingScenario, **kwargs) -> float:
    return win_rate(pricing)


def win_probability_uncapped(pricing: PricingScenario, **kwargs) -> float:
    return win_rate(pricing)


# ── LTV Solver: SaaS first, then CC, then ACH ────────────────

def solve_multi_lever_for_target_win_rate(
    pricing: PricingScenario,
    target_wp: float,
    wp_params: dict,
) -> dict | None:
    """Find lever adjustments to hit target_wp.

    Priority: SaaS discount → CC rates → ACH rate.
    Returns dict with adjusted pricing and changes, or None.
    """
    adjusted = copy.copy(pricing)
    changes = {}
    lb = cfg.LEVER_BOUNDS

    current = win_rate(adjusted)
    if current >= target_wp:
        return {"pricing": adjusted, "changes": changes}

    # 1) SaaS discount
    saas_lo = adjusted.saas_arr_discount_pct
    saas_hi = lb["saas_arr_discount_pct"]["max"]
    if saas_hi > saas_lo:
        def _wr_saas(d):
            p = copy.copy(adjusted)
            p.saas_arr_discount_pct = d
            return win_rate(p) - target_wp

        if _wr_saas(saas_hi) >= 0:
            try:
                result = brentq(_wr_saas, saas_lo, saas_hi, xtol=1e-4)
                changes["saas_arr_discount_pct"] = (pricing.saas_arr_discount_pct, result)
                adjusted.saas_arr_discount_pct = result
                return {"pricing": adjusted, "changes": changes}
            except ValueError:
                pass

        adjusted.saas_arr_discount_pct = saas_hi
        if saas_hi > pricing.saas_arr_discount_pct:
            changes["saas_arr_discount_pct"] = (pricing.saas_arr_discount_pct, saas_hi)

    # 2) CC base + AMEX together
    cc_hi = adjusted.cc_base_rate
    cc_lo = lb["cc_base_rate"]["min"]
    amex_hi = adjusted.cc_amex_rate
    amex_lo = lb["cc_amex_rate"]["min"]

    if cc_hi > cc_lo or amex_hi > amex_lo:
        def _wr_cc(t):
            p = copy.copy(adjusted)
            frac = max(0.0, min(1.0, t))
            if cc_hi > cc_lo:
                p.cc_base_rate = cc_hi - frac * (cc_hi - cc_lo)
            if amex_hi > amex_lo:
                p.cc_amex_rate = amex_hi - frac * (amex_hi - amex_lo)
            return win_rate(p) - target_wp

        if _wr_cc(1.0) >= 0:
            try:
                result = brentq(_wr_cc, 0.0, 1.0, xtol=1e-5)
                new_base = cc_hi - result * (cc_hi - cc_lo) if cc_hi > cc_lo else cc_hi
                new_amex = amex_hi - result * (amex_hi - amex_lo) if amex_hi > amex_lo else amex_hi
                if abs(new_base - pricing.cc_base_rate) > 1e-5:
                    changes["cc_base_rate"] = (pricing.cc_base_rate, new_base)
                if abs(new_amex - pricing.cc_amex_rate) > 1e-5:
                    changes["cc_amex_rate"] = (pricing.cc_amex_rate, new_amex)
                adjusted.cc_base_rate = new_base
                adjusted.cc_amex_rate = new_amex
                return {"pricing": adjusted, "changes": changes}
            except ValueError:
                pass

        adjusted.cc_base_rate = cc_lo if cc_hi > cc_lo else cc_hi
        adjusted.cc_amex_rate = amex_lo if amex_hi > amex_lo else amex_hi
        if cc_lo < pricing.cc_base_rate:
            changes["cc_base_rate"] = (pricing.cc_base_rate, cc_lo)
        if amex_lo < pricing.cc_amex_rate:
            changes["cc_amex_rate"] = (pricing.cc_amex_rate, amex_lo)

    # 3) ACH rate
    if adjusted.ach_mode == "percentage":
        ach_hi = adjusted.ach_pct_rate
        ach_lo = lb["ach_pct_rate"]["min"]

        if ach_hi > ach_lo:
            def _wr_ach(r):
                p = copy.copy(adjusted)
                p.ach_pct_rate = r
                return win_rate(p) - target_wp

            if _wr_ach(ach_lo) >= 0:
                try:
                    result = brentq(_wr_ach, ach_lo, ach_hi, xtol=1e-5)
                    changes["ach_pct_rate"] = (pricing.ach_pct_rate, result)
                    adjusted.ach_pct_rate = result
                    return {"pricing": adjusted, "changes": changes}
                except ValueError:
                    pass

            adjusted.ach_pct_rate = ach_lo
            if ach_lo < pricing.ach_pct_rate:
                changes["ach_pct_rate"] = (pricing.ach_pct_rate, ach_lo)

    final = win_rate(adjusted)
    if final >= target_wp - 0.005:
        return {"pricing": adjusted, "changes": changes}

    return None


# ── Top Line Optimizer: min CC/ACH, optimize SaaS for revenue ─

def optimize_topline_pricing(
    pricing: PricingScenario,
    deals_to_pricing: int,
    volumes: dict,
    quarterly_churn: float = 0.02,
) -> tuple[PricingScenario, dict, float]:
    """Maximize total 3-year cohort revenue with CC/ACH at floor rates.

    Sets CC/ACH to minimum, then finds the SaaS discount that maximizes
    total cohort revenue (win_rate * deals * per_deal_revenue).

    Returns (optimized_pricing, lever_changes, achieved_win_rate).
    """
    from models.revenue_model import compute_three_year_financials

    lb = cfg.LEVER_BOUNDS

    def _retention_factor(year):
        r = 1 - quarterly_churn
        qs = (year - 1) * 4
        qe = year * 4
        return sum(r ** q for q in range(qs, qe)) / 4

    base = copy.copy(pricing)
    base.cc_base_rate = lb["cc_base_rate"]["min"]
    base.cc_amex_rate = lb["cc_amex_rate"]["min"]
    base.hold_days_cc = cfg.HOLD_DAYS_CC_DEFAULT
    base.hold_days_ach = cfg.HOLD_DAYS_ACH_DEFAULT
    base.hold_days_bank = cfg.HOLD_DAYS_BANK_DEFAULT

    if base.ach_mode == "percentage":
        base.ach_pct_rate = lb["ach_pct_rate"]["min"]
    elif base.ach_mode == "capped":
        base.ach_pct_rate = lb["ach_pct_rate"]["min"]
        base.ach_cap = lb["ach_cap"]["min"]
    elif base.ach_mode == "fixed_fee":
        base.ach_fixed_fee = lb["ach_fixed_fee"]["min"]

    def _neg_revenue(saas_d):
        base.saas_arr_discount_pct = saas_d
        wp = win_rate(base)
        deals = deals_to_pricing * wp
        yearly = compute_three_year_financials(volumes, base, include_float=True)
        return -sum(
            yearly[y].total_revenue * deals * _retention_factor(y)
            for y in [1, 2, 3]
        )

    result = minimize_scalar(
        _neg_revenue,
        bounds=(lb["saas_arr_discount_pct"]["min"], lb["saas_arr_discount_pct"]["max"]),
        method="bounded",
    )
    best_saas = result.x

    adjusted = copy.copy(base)
    adjusted.saas_arr_discount_pct = best_saas
    changes = {}

    if abs(best_saas - pricing.saas_arr_discount_pct) > 1e-4:
        changes["saas_arr_discount_pct"] = (pricing.saas_arr_discount_pct, best_saas)
    if abs(adjusted.cc_base_rate - pricing.cc_base_rate) > 1e-5:
        changes["cc_base_rate"] = (pricing.cc_base_rate, adjusted.cc_base_rate)
    if abs(adjusted.cc_amex_rate - pricing.cc_amex_rate) > 1e-5:
        changes["cc_amex_rate"] = (pricing.cc_amex_rate, adjusted.cc_amex_rate)
    if base.ach_mode == "percentage" and abs(adjusted.ach_pct_rate - pricing.ach_pct_rate) > 1e-5:
        changes["ach_pct_rate"] = (pricing.ach_pct_rate, adjusted.ach_pct_rate)

    achieved = win_rate(adjusted)
    return adjusted, changes, achieved
