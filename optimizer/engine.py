"""
Optimization engine.

Three objective-driven scenarios:
  1. Margin % Optimized:   maximize pure margin % (no P(win))
  2. Take Rate Optimized:  maximize pure take rate (no P(win))
  3. LTV Optimized:        maximize P(win) * sum(margin * retention)
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable

import numpy as np
from scipy.optimize import differential_evolution

import config as cfg
from models.volume_forecast import VolumeForecastYear
from models.revenue_model import (
    PricingScenario,
    YearlyRevenue,
    compute_three_year_financials,
    _saas_arr_for_year,
)
from models.win_probability import win_probability


@dataclass
class OptimizationResult:
    name: str
    pricing: PricingScenario
    win_prob: float
    yearly: dict[int, YearlyRevenue]
    objective_value: float
    explanation: str = ""


RETENTION_CURVE = {1: 1.0, 2: 0.90, 3: 0.82}
WIN_PROB_FLOOR = 0.35  # minimum viable win probability for constrained objectives


def _build_pricing_from_vector(
    x: np.ndarray,
    ach_mode: str,
    saas_arr_list: float,
    impl_fee_list: float,
) -> PricingScenario:
    hold_cc = int(round(x[7]))
    hold_ach = int(round(x[8]))
    hold_bank = int(round(x[9]))

    if ach_mode == "percentage":
        hold_cc = 2
        hold_ach = 2
        hold_bank = 1

    return PricingScenario(
        saas_arr_discount_pct=float(x[0]),
        impl_fee_discount_pct=float(x[1]),
        cc_base_rate=float(x[2]),
        cc_amex_rate=float(x[3]),
        ach_mode=ach_mode,
        ach_pct_rate=float(x[4]),
        ach_cap=float(x[5]),
        ach_fixed_fee=float(x[6]),
        hold_days_cc=hold_cc,
        hold_days_ach=hold_ach,
        hold_days_bank=hold_bank,
        saas_arr_list=saas_arr_list,
        impl_fee_list=impl_fee_list,
    )


def _get_bounds(strategy: str = "default") -> list[tuple[float, float]]:
    """Lever bounds, optionally constrained by strategy."""
    lb = cfg.LEVER_BOUNDS

    if strategy == "saas_passive":
        return [
            (0.50, 0.70),                                          # SaaS discount: 50-70%
            (lb["impl_fee_discount_pct"]["min"], lb["impl_fee_discount_pct"]["max"]),
            (lb["cc_base_rate"]["min"], lb["cc_base_rate"]["max"]),
            (lb["cc_amex_rate"]["min"], lb["cc_amex_rate"]["max"]),
            (lb["ach_pct_rate"]["min"], lb["ach_pct_rate"]["max"]),
            (lb["ach_cap"]["min"], lb["ach_cap"]["max"]),
            (lb["ach_fixed_fee"]["min"], lb["ach_fixed_fee"]["max"]),
            (1, 2),                                                 # CC hold: up to 2
            (1, 10),                                                # ACH hold: up to 10
            (1, 10),                                                # Bank hold: up to 10
        ]

    return [
        (lb["saas_arr_discount_pct"]["min"], lb["saas_arr_discount_pct"]["max"]),
        (lb["impl_fee_discount_pct"]["min"], lb["impl_fee_discount_pct"]["max"]),
        (lb["cc_base_rate"]["min"], lb["cc_base_rate"]["max"]),
        (lb["cc_amex_rate"]["min"], lb["cc_amex_rate"]["max"]),
        (lb["ach_pct_rate"]["min"], lb["ach_pct_rate"]["max"]),
        (lb["ach_cap"]["min"], lb["ach_cap"]["max"]),
        (lb["ach_fixed_fee"]["min"], lb["ach_fixed_fee"]["max"]),
        (lb["hold_days_cc"]["min"], lb["hold_days_cc"]["max"]),
        (lb["hold_days_ach"]["min"], lb["hold_days_ach"]["max"]),
        (lb["hold_days_bank"]["min"], lb["hold_days_bank"]["max"]),
    ]


# ── Objective Functions ───────────────────────────────────────────────

def _objective_margin_pct(
    x, ach_mode, volumes, saas_arr_list, impl_fee_list, wp_params,
) -> float:
    """Maximize pure 3-year margin % — no win probability factor."""
    pricing = _build_pricing_from_vector(x, ach_mode, saas_arr_list, impl_fee_list)
    yearly = compute_three_year_financials(volumes, pricing)
    total_rev = sum(yr.total_revenue for yr in yearly.values())
    total_margin = sum(yr.margin for yr in yearly.values())
    margin_pct = total_margin / total_rev if total_rev > 0 else 0
    return -margin_pct


def _objective_take_rate(
    x, ach_mode, volumes, saas_arr_list, impl_fee_list, wp_params,
) -> float:
    """Maximize pure 3-year average take rate — no win probability factor."""
    pricing = _build_pricing_from_vector(x, ach_mode, saas_arr_list, impl_fee_list)
    yearly = compute_three_year_financials(volumes, pricing)
    total_rev = sum(yr.total_revenue for yr in yearly.values())
    total_vol = sum(yr.total_revenue / yr.take_rate for yr in yearly.values() if yr.take_rate > 0)
    avg_take_rate = total_rev / total_vol if total_vol > 0 else 0
    return -avg_take_rate


def _objective_ltv(
    x, ach_mode, volumes, saas_arr_list, impl_fee_list, wp_params,
) -> float:
    """Maximize expected lifetime value: P(win) * sum(margin * retention)."""
    pricing = _build_pricing_from_vector(x, ach_mode, saas_arr_list, impl_fee_list)
    yearly = compute_three_year_financials(volumes, pricing)
    wp = win_probability(pricing, **wp_params)
    elv = sum(
        yr.margin * RETENTION_CURVE.get(yr.year, 0.80)
        for yr in yearly.values()
    )
    return -(elv * wp)


# ── Optimization Machinery ────────────────────────────────────────────

def _run_single_optimization(
    objective_fn: Callable,
    ach_mode: str,
    volumes: dict[int, VolumeForecastYear],
    saas_arr_list: float,
    impl_fee_list: float,
    wp_params: dict,
    strategy: str = "default",
) -> tuple[float, np.ndarray]:
    bounds = _get_bounds(strategy)
    result = differential_evolution(
        objective_fn,
        bounds=bounds,
        args=(ach_mode, volumes, saas_arr_list, impl_fee_list, wp_params),
        seed=42,
        maxiter=400,
        tol=1e-8,
        popsize=20,
        mutation=(0.5, 1.5),
        recombination=0.8,
    )
    return result.fun, result.x


def optimize_scenario(
    name: str,
    objective_fn: Callable,
    volumes: dict[int, VolumeForecastYear],
    saas_arr_list: float,
    impl_fee_list: float,
    wp_params: dict,
    explanation_fn: Callable | None = None,
    strategy: str = "default",
    ach_modes: list[str] | None = None,
    saas_discount_persists: bool = False,
) -> OptimizationResult:
    best_obj = float("inf")
    best_x = None
    best_mode = "percentage"

    for mode in (ach_modes or cfg.ACH_MODES):
        obj, x = _run_single_optimization(
            objective_fn, mode, volumes,
            saas_arr_list, impl_fee_list, wp_params,
            strategy=strategy,
        )
        if obj < best_obj:
            best_obj = obj
            best_x = x
            best_mode = mode

    pricing = _build_pricing_from_vector(
        best_x, best_mode, saas_arr_list, impl_fee_list
    )
    if saas_discount_persists:
        pricing.saas_discount_persists = True
    yearly = compute_three_year_financials(volumes, pricing)
    wp = win_probability(pricing, **wp_params)

    explanation = ""
    if explanation_fn:
        explanation = explanation_fn(pricing, yearly, wp)

    return OptimizationResult(
        name=name,
        pricing=pricing,
        win_prob=wp,
        yearly=yearly,
        objective_value=-best_obj,
        explanation=explanation,
    )


# ── Pre-built Scenarios ──────────────────────────────────────────────

def build_msrp_scenario(
    volumes: dict[int, VolumeForecastYear],
    saas_arr_list: float = cfg.SAAS_ARR_DEFAULT,
    impl_fee_list: float = cfg.SAAS_IMPL_FEE_DEFAULT,
    wp_params: dict | None = None,
) -> OptimizationResult:
    """Sticker price scenario — no discounts, standard everything."""
    pricing = PricingScenario(
        saas_arr_discount_pct=0.0,
        impl_fee_discount_pct=0.0,
        cc_base_rate=cfg.CC_STANDARD_BASE_RATE,
        cc_amex_rate=cfg.CC_STANDARD_AMEX_RATE,
        ach_mode="percentage",
        ach_pct_rate=cfg.ACH_STANDARD_RATE,
        ach_cap=10.0,
        ach_fixed_fee=2.50,
        hold_days_cc=2,
        hold_days_ach=2,
        hold_days_bank=1,
        saas_arr_list=saas_arr_list,
        impl_fee_list=impl_fee_list,
    )
    yearly = compute_three_year_financials(volumes, pricing)
    wp = win_probability(pricing, **(wp_params or {}))

    return OptimizationResult(
        name="Pre Discount Pricing Today",
        pricing=pricing,
        win_prob=wp,
        yearly=yearly,
        objective_value=0.0,
        explanation="Standard pricing with no discounts or concessions.",
    )


def _scenario_explanation(
    pricing: PricingScenario,
    yearly: dict[int, YearlyRevenue],
    wp: float,
) -> str:
    total_margin = sum(yr.margin for yr in yearly.values())
    total_rev = sum(yr.total_revenue for yr in yearly.values())
    margin_pct = total_margin / total_rev * 100 if total_rev > 0 else 0
    renewal = _saas_arr_for_year(pricing, 2)

    total_vol = sum(
        yr.total_revenue / yr.take_rate
        for yr in yearly.values() if yr.take_rate > 0
    )
    avg_take_rate = total_rev / total_vol * 100 if total_vol > 0 else 0

    parts = []
    if pricing.saas_arr_discount_pct > 0.25:
        parts.append(
            f"Y1 SaaS discount of {pricing.saas_arr_discount_pct:.0%} drives win rate, "
            f"then renews at ${renewal:,.0f}/yr"
        )
    if pricing.cc_base_rate < cfg.CC_STANDARD_BASE_RATE:
        parts.append(f"CC promo at {pricing.cc_base_rate:.2%} reverts to {cfg.CC_STANDARD_BASE_RATE:.2%} in Y2")

    parts.append(f"{margin_pct:.0f}% blended margin, {avg_take_rate:.1f}% avg take rate")

    processing_rev = sum(
        yr.cc_revenue + yr.ach_revenue + yr.bank_network_revenue
        for yr in yearly.values()
    )
    processing_pct = processing_rev / total_rev * 100 if total_rev > 0 else 0
    parts.append(f"{processing_pct:.0f}% of revenue from processing")

    return " | ".join(parts)


def run_all_optimizations(
    volumes: dict[int, VolumeForecastYear],
    saas_arr_list: float = cfg.SAAS_ARR_DEFAULT,
    impl_fee_list: float = cfg.SAAS_IMPL_FEE_DEFAULT,
    wp_params: dict | None = None,
) -> dict[str, OptimizationResult]:
    """
    Run all optimization scenarios.
    Returns {"msrp": ..., "margin_pct": ..., "take_rate": ..., "ltv": ...}.
    """
    wp = wp_params or {}

    msrp = build_msrp_scenario(volumes, saas_arr_list, impl_fee_list, wp)

    margin_pct = optimize_scenario(
        name="Margin % Optimized",
        objective_fn=_objective_margin_pct,
        volumes=volumes,
        saas_arr_list=saas_arr_list,
        impl_fee_list=impl_fee_list,
        wp_params=wp,
        explanation_fn=_scenario_explanation,
    )

    take_rate = optimize_scenario(
        name="Take Rate Optimized",
        objective_fn=_objective_take_rate,
        volumes=volumes,
        saas_arr_list=saas_arr_list,
        impl_fee_list=impl_fee_list,
        wp_params=wp,
        explanation_fn=_scenario_explanation,
    )

    ltv = optimize_scenario(
        name="LTV Optimized",
        objective_fn=_objective_ltv,
        volumes=volumes,
        saas_arr_list=saas_arr_list,
        impl_fee_list=impl_fee_list,
        wp_params=wp,
        explanation_fn=_scenario_explanation,
    )

    saas_passive = optimize_scenario(
        name="SaaS Passive",
        objective_fn=_objective_ltv,
        volumes=volumes,
        saas_arr_list=saas_arr_list,
        impl_fee_list=impl_fee_list,
        wp_params=wp,
        explanation_fn=_scenario_explanation,
        strategy="saas_passive",
        ach_modes=["fixed_fee"],
        saas_discount_persists=True,
    )

    return {
        "msrp": msrp,
        "margin_pct": margin_pct,
        "take_rate": take_rate,
        "ltv": ltv,
        "saas_passive": saas_passive,
    }
