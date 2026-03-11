"""
Cohort-level calculation engine.

Takes per-deal financials from the revenue model, scales them by deal
count, and produces side-by-side Standard vs LTV comparison data.

The LTV scenario is built by taking standard pricing and using the
multi-lever solver to find pricing adjustments that achieve the
target win rate increase.
"""
from __future__ import annotations
from dataclasses import dataclass, field

from models.revenue_model import (
    PricingScenario,
    YearlyRevenue,
    compute_three_year_financials,
)
from models.volume_forecast import VolumeForecastYear, forecast_volume_y1_y3
from models.win_probability import (
    win_probability,
    win_probability_uncapped,
    solve_multi_lever_for_target_win_rate,
    optimize_topline_pricing,
)
import config as cfg


@dataclass
class CohortYearMetrics:
    year: int
    deals: int
    saas_revenue: float
    impl_fee_revenue: float
    cc_revenue: float
    ach_revenue: float
    bank_revenue: float
    float_income: float
    teampay_saas_revenue: float
    teampay_processing_revenue: float
    teampay_cost: float
    total_revenue: float
    total_cost: float
    margin: float
    margin_pct: float
    take_rate: float


@dataclass
class CohortScenario:
    name: str
    deals_won: int
    win_rate: float
    per_deal_pricing: PricingScenario
    per_deal_yearly: dict[int, YearlyRevenue]
    per_deal_volumes: dict[int, VolumeForecastYear]
    cohort_yearly: dict[int, CohortYearMetrics]
    three_year_revenue: float
    three_year_margin: float
    three_year_margin_pct: float
    three_year_take_rate: float
    lever_changes: dict | None = None


def _retention_factor(year: int, quarterly_churn: float = 0.02) -> float:
    """Average active deal fraction for a given year.

    Models the average retention across the 4 quarters of each year.
    Quarter retention = (1 - quarterly_churn)^q where q counts from deal close.
    """
    r = 1 - quarterly_churn
    quarters_start = (year - 1) * 4
    quarters_end = year * 4
    avg = sum(r ** q for q in range(quarters_start, quarters_end)) / 4
    return avg


def _compute_teampay_year(
    deals_won: int,
    year: int,
    retention: float,
    tp_optin: float,
    tp_usage: float,
) -> tuple[float, float, float]:
    """Compute Teampay SaaS revenue, processing revenue, and cost for a year.

    All Teampay customers retain (no Teampay-specific drop-off),
    only regular cohort churn applies via retention.
    Year 1: free SaaS, 50% processing ramp. Years 2+: $7.5k SaaS, full volume.

    Returns (tp_saas_rev, tp_proc_rev, tp_cost).
    """
    active_tp = deals_won * tp_optin * tp_usage * retention

    annual_proc_vol = cfg.TEAMPAY_MONTHLY_VOLUME * 12
    vol_factor = 0.50 if year == 1 else 1.0
    growth = (1 + cfg.TEAMPAY_PROCESSING_GROWTH) ** (year - 1)
    tp_proc_rev = active_tp * annual_proc_vol * cfg.TEAMPAY_PROCESSING_RATE * vol_factor * growth
    tp_proc_cost = tp_proc_rev * (1 - cfg.TEAMPAY_PROCESSING_MARGIN)

    if year == 1:
        tp_saas_rev = 0.0
        tp_saas_cost = 0.0
    else:
        tp_saas_rev = active_tp * cfg.TEAMPAY_SAAS_ANNUAL
        tp_saas_cost = tp_saas_rev * (1 - cfg.TEAMPAY_SAAS_MARGIN)

    return tp_saas_rev, tp_proc_rev, tp_proc_cost + tp_saas_cost


def _scale_yearly(
    yearly: dict[int, YearlyRevenue], deals: int,
    quarterly_churn: float = 0.02,
    tp_optin: float = 0.0,
    tp_usage: float = 0.0,
) -> dict[int, CohortYearMetrics]:
    """Multiply per-deal yearly financials by number of deals, adjusted for churn."""
    result = {}
    for y, yr in yearly.items():
        retention = _retention_factor(y, quarterly_churn)
        active = deals * retention
        base_rev = yr.total_revenue * active
        base_cost = yr.total_cost * active

        tp_saas, tp_proc, tp_cost = _compute_teampay_year(
            deals, y, retention, tp_optin, tp_usage,
        )
        tp_rev = tp_saas + tp_proc

        rev = base_rev + tp_rev
        cost = base_cost + tp_cost
        margin = rev - cost
        mpct = margin / rev if rev > 0 else 0
        vol = (yr.total_revenue / yr.take_rate * active) if yr.take_rate > 0 else 0
        tr = rev / vol if vol > 0 else 0
        result[y] = CohortYearMetrics(
            year=y,
            deals=int(round(active)),
            saas_revenue=yr.saas_revenue * active,
            impl_fee_revenue=yr.impl_fee_revenue * active,
            cc_revenue=yr.cc_revenue * active,
            ach_revenue=yr.ach_revenue * active,
            bank_revenue=yr.bank_network_revenue * active,
            float_income=yr.float_income * active,
            teampay_saas_revenue=tp_saas,
            teampay_processing_revenue=tp_proc,
            teampay_cost=tp_cost,
            total_revenue=rev,
            total_cost=cost,
            margin=margin,
            margin_pct=mpct,
            take_rate=tr,
        )
    return result


def _build_cohort_scenario(
    name: str,
    deals_won: int,
    win_rate: float,
    pricing: PricingScenario,
    per_deal_yearly: dict[int, YearlyRevenue],
    per_deal_volumes: dict[int, VolumeForecastYear],
    lever_changes: dict | None = None,
    quarterly_churn: float = 0.02,
    tp_optin: float = 0.0,
    tp_usage: float = 0.0,
) -> CohortScenario:
    cohort_yearly = _scale_yearly(
        per_deal_yearly, deals_won, quarterly_churn,
        tp_optin=tp_optin, tp_usage=tp_usage,
    )
    total_rev = sum(cy.total_revenue for cy in cohort_yearly.values())
    total_margin = sum(cy.margin for cy in cohort_yearly.values())
    total_vol = sum(
        cy.total_revenue / cy.take_rate
        for cy in cohort_yearly.values() if cy.take_rate > 0
    )
    return CohortScenario(
        name=name,
        deals_won=deals_won,
        win_rate=win_rate,
        per_deal_pricing=pricing,
        per_deal_yearly=per_deal_yearly,
        per_deal_volumes=per_deal_volumes,
        cohort_yearly=cohort_yearly,
        three_year_revenue=total_rev,
        three_year_margin=total_margin,
        three_year_margin_pct=total_margin / total_rev if total_rev > 0 else 0,
        three_year_take_rate=total_rev / total_vol if total_vol > 0 else 0,
        lever_changes=lever_changes,
    )


def run_cohort_comparison(
    deals_to_pricing: int,
    current_win_rate: float,
    avg_saas_arr: float,
    avg_impl_fee: float,
    total_arr_won: float,
    standard_pricing_inputs: dict,
    win_rate_increase: float,
    quarterly_churn: float = 0.02,
    tp_contract_optin: float = 0.50,
    tp_actual_usage: float = 0.20,
) -> tuple[CohortScenario, CohortScenario, CohortScenario, str]:
    """
    Run Standard, LTV-Optimized, and Top-Line-Optimized scenarios.

    Returns (standard, ltv, topline, solver_message).
    """
    std_deals = int(round(deals_to_pricing * current_win_rate))
    per_deal_arr = total_arr_won / std_deals if std_deals > 0 else 0.0

    volumes = forecast_volume_y1_y3(per_deal_arr)

    # --- Standard scenario ---
    std_pricing = PricingScenario(
        saas_arr_discount_pct=standard_pricing_inputs["saas_arr_discount_pct"],
        impl_fee_discount_pct=standard_pricing_inputs["impl_fee_discount_pct"],
        cc_base_rate=standard_pricing_inputs["cc_base_rate"],
        cc_amex_rate=standard_pricing_inputs["cc_amex_rate"],
        ach_mode=standard_pricing_inputs["ach_mode"],
        ach_pct_rate=standard_pricing_inputs["ach_pct_rate"],
        ach_cap=standard_pricing_inputs["ach_cap"],
        ach_fixed_fee=standard_pricing_inputs["ach_fixed_fee"],
        hold_days_cc=standard_pricing_inputs["hold_days_cc"],
        hold_days_ach=standard_pricing_inputs["hold_days_ach"],
        hold_days_bank=standard_pricing_inputs["hold_days_bank"],
        saas_arr_list=avg_saas_arr,
        impl_fee_list=avg_impl_fee,
    )
    std_wp = win_probability(std_pricing)
    std_yearly = compute_three_year_financials(volumes, std_pricing, include_float=True)

    standard = _build_cohort_scenario(
        "Standard Pricing", std_deals, current_win_rate,
        std_pricing, std_yearly, volumes, quarterly_churn=quarterly_churn,
        tp_optin=tp_contract_optin, tp_usage=tp_actual_usage,
    )

    # --- Boosted scenario via solver ---
    target_wp = min(current_win_rate + win_rate_increase, 0.80)
    solver_msg = ""

    if win_rate_increase <= 0:
        return standard, standard, standard, "No win rate increase selected."

    result = solve_multi_lever_for_target_win_rate(
        std_pricing, target_wp, {},
    )

    if result is not None:
        boosted_pricing = result["pricing"]
        lever_changes = result["changes"]
        boosted_wp = target_wp
    else:
        import copy
        maxed = copy.copy(std_pricing)
        lb = cfg.LEVER_BOUNDS
        lever_changes = {}

        if maxed.saas_arr_discount_pct < lb["saas_arr_discount_pct"]["max"]:
            lever_changes["saas_arr_discount_pct"] = (std_pricing.saas_arr_discount_pct, lb["saas_arr_discount_pct"]["max"])
            maxed.saas_arr_discount_pct = lb["saas_arr_discount_pct"]["max"]
        if maxed.cc_base_rate > lb["cc_base_rate"]["min"]:
            lever_changes["cc_base_rate"] = (std_pricing.cc_base_rate, lb["cc_base_rate"]["min"])
            maxed.cc_base_rate = lb["cc_base_rate"]["min"]
        if maxed.cc_amex_rate > lb["cc_amex_rate"]["min"]:
            lever_changes["cc_amex_rate"] = (std_pricing.cc_amex_rate, lb["cc_amex_rate"]["min"])
            maxed.cc_amex_rate = lb["cc_amex_rate"]["min"]
        if maxed.ach_mode == "fixed_fee" and maxed.ach_fixed_fee > lb["ach_fixed_fee"]["min"]:
            lever_changes["ach_fixed_fee"] = (std_pricing.ach_fixed_fee, lb["ach_fixed_fee"]["min"])
            maxed.ach_fixed_fee = lb["ach_fixed_fee"]["min"]
        elif maxed.ach_mode == "percentage" and maxed.ach_pct_rate > lb["ach_pct_rate"]["min"]:
            lever_changes["ach_pct_rate"] = (std_pricing.ach_pct_rate, lb["ach_pct_rate"]["min"])
            maxed.ach_pct_rate = lb["ach_pct_rate"]["min"]
        elif maxed.ach_mode == "capped":
            if maxed.ach_pct_rate > lb["ach_pct_rate"]["min"]:
                lever_changes["ach_pct_rate"] = (std_pricing.ach_pct_rate, lb["ach_pct_rate"]["min"])
                maxed.ach_pct_rate = lb["ach_pct_rate"]["min"]
            if maxed.ach_cap > lb["ach_cap"]["min"]:
                lever_changes["ach_cap"] = (std_pricing.ach_cap, lb["ach_cap"]["min"])
                maxed.ach_cap = lb["ach_cap"]["min"]

        max_wp = win_probability_uncapped(maxed)
        max_boost = max_wp - current_win_rate
        boosted_pricing = maxed
        boosted_wp = current_win_rate + max(max_boost, 0)
        solver_msg = (
            f"Target +{win_rate_increase:.0%} not fully reachable. "
            f"Showing max achievable: +{max_boost:.1%}"
        )

    # Set LTV hold times to config defaults (higher than standard) to earn float
    ltv_holds = {
        "hold_days_cc": cfg.HOLD_DAYS_CC_DEFAULT,
        "hold_days_ach": cfg.HOLD_DAYS_ACH_DEFAULT,
        "hold_days_bank": cfg.HOLD_DAYS_BANK_DEFAULT,
    }
    for k, new_val in ltv_holds.items():
        old_val = getattr(std_pricing, k)
        if new_val != old_val:
            lever_changes[k] = (old_val, new_val)
            setattr(boosted_pricing, k, new_val)

    boosted_yearly = compute_three_year_financials(volumes, boosted_pricing, include_float=True)
    boosted_deals = int(round(deals_to_pricing * boosted_wp))

    boosted = _build_cohort_scenario(
        "LTV Optimized", boosted_deals, boosted_wp,
        boosted_pricing, boosted_yearly, volumes, lever_changes,
        quarterly_churn=quarterly_churn,
        tp_optin=tp_contract_optin, tp_usage=tp_actual_usage,
    )

    # --- Top Line Optimized: maximize 3-year cohort revenue ---
    top_pricing, top_changes, top_wp = optimize_topline_pricing(
        std_pricing, deals_to_pricing, volumes, quarterly_churn,
    )

    for k in ("hold_days_cc", "hold_days_ach", "hold_days_bank"):
        new_val = getattr(top_pricing, k)
        old_val = getattr(std_pricing, k)
        if new_val != old_val:
            top_changes[k] = (old_val, new_val)

    top_yearly = compute_three_year_financials(volumes, top_pricing, include_float=True)
    top_deals = int(round(deals_to_pricing * top_wp))

    topline = _build_cohort_scenario(
        "Top Line Optimized", top_deals, top_wp,
        top_pricing, top_yearly, volumes, top_changes,
        quarterly_churn=quarterly_churn,
        tp_optin=tp_contract_optin, tp_usage=tp_actual_usage,
    )

    return standard, boosted, topline, solver_msg
