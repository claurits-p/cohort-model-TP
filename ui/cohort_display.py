"""
Display components for cohort comparison: summary metrics, year-by-year
side-by-side table, delta row, and pricing details.
"""
from __future__ import annotations
import pandas as pd
import streamlit as st

from ui.cohort_engine import CohortScenario

_STD_CLR = "#1B6AC9"
_LTV_CLR = "#2ECC71"
_TOP_CLR = "#E67E22"


def _scenario_label(scenario: CohortScenario) -> str:
    clr = {
        "Standard Pricing": _STD_CLR,
        "LTV Optimized": _LTV_CLR,
        "Top Line Optimized": _TOP_CLR,
    }.get(scenario.name, "#333")
    return (
        f'<span style="color:{clr};font-weight:600;font-size:1.05rem;">'
        f'{scenario.name}</span> ({scenario.deals_won} deals)'
    )


def render_volume_forecast(
    std: CohortScenario, ltv: CohortScenario, top: CohortScenario,
) -> None:
    """Volume forecast tables showing 3-year volumes by payment type for all scenarios."""
    st.subheader("Volume Forecast")

    def _vol_df(scenario: CohortScenario) -> pd.DataFrame:
        vols = scenario.per_deal_volumes
        deals = scenario.deals_won
        rows = []
        for y in (1, 2, 3):
            v = vols[y]
            rows.append({
                "Year": f"Year {y}",
                "Total Volume": f"${v.total * deals:,.0f}",
                "Card Volume": f"${v.cc * deals:,.0f}",
                "ACH Volume": f"${v.ach * deals:,.0f}",
                "Bank Volume": f"${v.bank_network * deals:,.0f}",
                "Card %": f"{v.cc / v.total:.1%}" if v.total > 0 else "0%",
            })
        t = sum(vols[y].total for y in (1, 2, 3)) * deals
        cc = sum(vols[y].cc for y in (1, 2, 3)) * deals
        ach = sum(vols[y].ach for y in (1, 2, 3)) * deals
        bank = sum(vols[y].bank_network for y in (1, 2, 3)) * deals
        rows.append({
            "Year": "3-Year Total",
            "Total Volume": f"${t:,.0f}",
            "Card Volume": f"${cc:,.0f}",
            "ACH Volume": f"${ach:,.0f}",
            "Bank Volume": f"${bank:,.0f}",
            "Card %": f"{cc / t:.1%}" if t > 0 else "0%",
        })
        return pd.DataFrame(rows)

    col1, col2, col3 = st.columns(3)
    for col, scenario in [(col1, std), (col2, ltv), (col3, top)]:
        with col:
            st.markdown(_scenario_label(scenario), unsafe_allow_html=True)
            st.dataframe(_vol_df(scenario), use_container_width=True, hide_index=True)


def render_summary_metrics(
    std: CohortScenario, ltv: CohortScenario, top: CohortScenario,
) -> None:
    """Top-level summary cards comparing all three scenarios."""

    st.subheader("Cohort Impact Summary")

    st.markdown(
        f'<div style="margin-bottom:8px;font-size:0.85rem;">'
        f'<span style="display:inline-block;width:12px;height:12px;'
        f'background:{_LTV_CLR};border-radius:2px;margin-right:4px;vertical-align:middle;"></span>'
        f'<span style="color:{_LTV_CLR};font-weight:600;vertical-align:middle;">LTV Optimized</span>'
        f'<span style="margin:0 12px;color:#aaa;vertical-align:middle;">|</span>'
        f'<span style="display:inline-block;width:12px;height:12px;'
        f'background:{_TOP_CLR};border-radius:2px;margin-right:4px;vertical-align:middle;"></span>'
        f'<span style="color:{_TOP_CLR};font-weight:600;vertical-align:middle;">Top Line Optimized</span>'
        f'<span style="margin:0 12px;color:#aaa;vertical-align:middle;">|</span>'
        f'<span style="display:inline-block;width:12px;height:12px;'
        f'background:{_STD_CLR};border-radius:2px;margin-right:4px;vertical-align:middle;"></span>'
        f'<span style="color:{_STD_CLR};font-weight:600;vertical-align:middle;">Standard</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    def _delta_html(value: float, label: str, is_pos: bool) -> str:
        bg = "rgba(9,171,59,0.15)" if is_pos else "rgba(255,43,43,0.15)"
        clr = "#09ab3b" if is_pos else "#ff2b2b"
        arrow = "▲" if is_pos else "▼"
        return (
            f'<div style="display:inline-block;font-size:0.75rem;color:{clr};'
            f'background:{bg};padding:2px 6px;border-radius:4px;margin-right:4px;">'
            f'{arrow} {label}</div>'
        )

    metrics = [
        ("Win Rate",
         f"{ltv.win_rate:.0%}", f"{top.win_rate:.0%}", f"{std.win_rate:.0%}",
         f"{(ltv.win_rate - std.win_rate)*100:+.0f}pp", (ltv.win_rate - std.win_rate) >= 0,
         f"{(top.win_rate - std.win_rate)*100:+.0f}pp", (top.win_rate - std.win_rate) >= 0),
        ("Deals Won",
         str(ltv.deals_won), str(top.deals_won), str(std.deals_won),
         f"{ltv.deals_won - std.deals_won:+d}", (ltv.deals_won - std.deals_won) >= 0,
         f"{top.deals_won - std.deals_won:+d}", (top.deals_won - std.deals_won) >= 0),
        ("3-Year Revenue",
         f"${ltv.three_year_revenue:,.0f}", f"${top.three_year_revenue:,.0f}", f"${std.three_year_revenue:,.0f}",
         f"${ltv.three_year_revenue - std.three_year_revenue:+,.0f}", (ltv.three_year_revenue - std.three_year_revenue) >= 0,
         f"${top.three_year_revenue - std.three_year_revenue:+,.0f}", (top.three_year_revenue - std.three_year_revenue) >= 0),
        ("3-Year Margin",
         f"${ltv.three_year_margin:,.0f}", f"${top.three_year_margin:,.0f}", f"${std.three_year_margin:,.0f}",
         f"${ltv.three_year_margin - std.three_year_margin:+,.0f}", (ltv.three_year_margin - std.three_year_margin) >= 0,
         f"${top.three_year_margin - std.three_year_margin:+,.0f}", (top.three_year_margin - std.three_year_margin) >= 0),
        ("Margin %",
         f"{ltv.three_year_margin_pct:.1%}", f"{top.three_year_margin_pct:.1%}", f"{std.three_year_margin_pct:.1%}",
         f"{(ltv.three_year_margin_pct - std.three_year_margin_pct)*100:+.1f}pp", (ltv.three_year_margin_pct - std.three_year_margin_pct) >= 0,
         f"{(top.three_year_margin_pct - std.three_year_margin_pct)*100:+.1f}pp", (top.three_year_margin_pct - std.three_year_margin_pct) >= 0),
        ("Take Rate",
         f"{ltv.three_year_take_rate:.2%}", f"{top.three_year_take_rate:.2%}", f"{std.three_year_take_rate:.2%}",
         f"{(ltv.three_year_take_rate - std.three_year_take_rate)*100:+.2f}pp", (ltv.three_year_take_rate - std.three_year_take_rate) >= 0,
         f"{(top.three_year_take_rate - std.three_year_take_rate)*100:+.2f}pp", (top.three_year_take_rate - std.three_year_take_rate) >= 0),
    ]

    cols = st.columns(6)
    for i, (label, ltv_val, top_val, std_val, ltv_delta, ltv_pos, top_delta, top_pos) in enumerate(metrics):
        cols[i].markdown(
            f'<div>'
            f'<div style="font-size:0.875rem;font-weight:400;color:#808495;'
            f'padding:0 0 0.3rem 0;">{label}</div>'
            f'<div style="font-size:1.6rem;font-weight:400;line-height:1.2;'
            f'padding:0 0 0.4rem 0;">'
            f'<span style="color:{_LTV_CLR};">{ltv_val}</span>'
            f' <span style="color:#808495;font-size:0.9rem;">|</span> '
            f'<span style="color:{_TOP_CLR};">{top_val}</span>'
            f' <span style="color:#808495;font-size:0.9rem;">|</span> '
            f'<span style="color:{_STD_CLR};">{std_val}</span>'
            f'</div>'
            f'<div>'
            f'{_delta_html(0, f"LTV {ltv_delta}", ltv_pos)}'
            f'{_delta_html(0, f"Top {top_delta}", top_pos)}'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def render_scenario_header(scenario: CohortScenario) -> None:
    """Render a scenario header with key stats."""
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Deals Won", scenario.deals_won)
    c2.metric("Win Rate", f"{scenario.win_rate:.0%}")
    c3.metric("3-Year Revenue", f"${scenario.three_year_revenue:,.0f}")
    c4.metric("3-Year Margin", f"${scenario.three_year_margin:,.0f}")


def _yearly_df(scenario: CohortScenario) -> pd.DataFrame:
    """Build a year-by-year DataFrame for a cohort scenario."""
    rows = []
    for y in [1, 2, 3]:
        cy = scenario.cohort_yearly[y]
        rows.append({
            "Year": str(y),
            "SaaS Rev": f"${cy.saas_revenue:,.0f}",
            "Impl Fee": f"${cy.impl_fee_revenue:,.0f}",
            "CC Rev": f"${cy.cc_revenue:,.0f}",
            "ACH Rev": f"${cy.ach_revenue:,.0f}",
            "Float": f"${cy.float_income:,.0f}",
            "TP SaaS": f"${cy.teampay_saas_revenue:,.0f}",
            "TP Proc": f"${cy.teampay_processing_revenue:,.0f}",
            "Total Rev": f"${cy.total_revenue:,.0f}",
            "Total Cost": f"${cy.total_cost:,.0f}",
            "Margin": f"${cy.margin:,.0f}",
            "Margin %": f"{cy.margin_pct:.1%}",
        })

    total_rev = sum(scenario.cohort_yearly[y].total_revenue for y in [1, 2, 3])
    total_cost = sum(scenario.cohort_yearly[y].total_cost for y in [1, 2, 3])
    total_margin = total_rev - total_cost
    rows.append({
        "Year": "Total",
        "SaaS Rev": f"${sum(scenario.cohort_yearly[y].saas_revenue for y in [1,2,3]):,.0f}",
        "Impl Fee": f"${sum(scenario.cohort_yearly[y].impl_fee_revenue for y in [1,2,3]):,.0f}",
        "CC Rev": f"${sum(scenario.cohort_yearly[y].cc_revenue for y in [1,2,3]):,.0f}",
        "ACH Rev": f"${sum(scenario.cohort_yearly[y].ach_revenue for y in [1,2,3]):,.0f}",
        "Float": f"${sum(scenario.cohort_yearly[y].float_income for y in [1,2,3]):,.0f}",
        "TP SaaS": f"${sum(scenario.cohort_yearly[y].teampay_saas_revenue for y in [1,2,3]):,.0f}",
        "TP Proc": f"${sum(scenario.cohort_yearly[y].teampay_processing_revenue for y in [1,2,3]):,.0f}",
        "Total Rev": f"${total_rev:,.0f}",
        "Total Cost": f"${total_cost:,.0f}",
        "Margin": f"${total_margin:,.0f}",
        "Margin %": f"{total_margin / total_rev:.1%}" if total_rev > 0 else "0.0%",
    })
    return pd.DataFrame(rows)


def render_side_by_side_tables(
    std: CohortScenario, ltv: CohortScenario, top: CohortScenario,
) -> None:
    """Year-by-year tables for each scenario, side by side."""

    col1, col2, col3 = st.columns(3)
    for col, scenario in [(col1, std), (col2, ltv), (col3, top)]:
        with col:
            st.markdown(_scenario_label(scenario), unsafe_allow_html=True)
            st.dataframe(_yearly_df(scenario), use_container_width=True, hide_index=True)


def render_delta_table(
    std: CohortScenario, ltv: CohortScenario, top: CohortScenario,
) -> None:
    """Delta tables showing differences vs Standard for both optimized scenarios."""

    def _build_delta_rows(base: CohortScenario, comp: CohortScenario) -> list[dict]:
        rows = []
        for y in [1, 2, 3]:
            s = base.cohort_yearly[y]
            c = comp.cohort_yearly[y]
            tp_s = s.teampay_saas_revenue + s.teampay_processing_revenue
            tp_c = c.teampay_saas_revenue + c.teampay_processing_revenue
            rows.append({
                "Year": str(y),
                "Δ SaaS": f"${c.saas_revenue - s.saas_revenue:+,.0f}",
                "Δ CC": f"${c.cc_revenue - s.cc_revenue:+,.0f}",
                "Δ ACH": f"${c.ach_revenue - s.ach_revenue:+,.0f}",
                "Δ Float": f"${c.float_income - s.float_income:+,.0f}",
                "Δ Teampay": f"${tp_c - tp_s:+,.0f}",
                "Δ Revenue": f"${c.total_revenue - s.total_revenue:+,.0f}",
                "Δ Cost": f"${c.total_cost - s.total_cost:+,.0f}",
                "Δ Margin": f"${c.margin - s.margin:+,.0f}",
                "Δ Margin %": f"{(c.margin_pct - s.margin_pct) * 100:+.1f}pp",
            })

        t_s_rev = sum(base.cohort_yearly[y].total_revenue for y in [1, 2, 3])
        t_c_rev = sum(comp.cohort_yearly[y].total_revenue for y in [1, 2, 3])
        t_s_cost = sum(base.cohort_yearly[y].total_cost for y in [1, 2, 3])
        t_c_cost = sum(comp.cohort_yearly[y].total_cost for y in [1, 2, 3])
        t_s_m = t_s_rev - t_s_cost
        t_c_m = t_c_rev - t_c_cost
        tp_delta = sum(
            (comp.cohort_yearly[y].teampay_saas_revenue + comp.cohort_yearly[y].teampay_processing_revenue)
            - (base.cohort_yearly[y].teampay_saas_revenue + base.cohort_yearly[y].teampay_processing_revenue)
            for y in [1, 2, 3]
        )

        rows.append({
            "Year": "Total",
            "Δ SaaS": f"${sum(comp.cohort_yearly[y].saas_revenue - base.cohort_yearly[y].saas_revenue for y in [1,2,3]):+,.0f}",
            "Δ CC": f"${sum(comp.cohort_yearly[y].cc_revenue - base.cohort_yearly[y].cc_revenue for y in [1,2,3]):+,.0f}",
            "Δ ACH": f"${sum(comp.cohort_yearly[y].ach_revenue - base.cohort_yearly[y].ach_revenue for y in [1,2,3]):+,.0f}",
            "Δ Float": f"${sum(comp.cohort_yearly[y].float_income - base.cohort_yearly[y].float_income for y in [1,2,3]):+,.0f}",
            "Δ Teampay": f"${tp_delta:+,.0f}",
            "Δ Revenue": f"${t_c_rev - t_s_rev:+,.0f}",
            "Δ Cost": f"${t_c_cost - t_s_cost:+,.0f}",
            "Δ Margin": f"${t_c_m - t_s_m:+,.0f}",
            "Δ Margin %": f"{((t_c_m / t_c_rev if t_c_rev else 0) - (t_s_m / t_s_rev if t_s_rev else 0)) * 100:+.1f}pp",
        })
        return rows

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f'<span style="color:{_LTV_CLR};font-weight:600;font-size:1.05rem;">'
            f'LTV Optimized</span> − Standard Delta',
            unsafe_allow_html=True,
        )
        st.dataframe(pd.DataFrame(_build_delta_rows(std, ltv)), use_container_width=True, hide_index=True)
    with col2:
        st.markdown(
            f'<span style="color:{_TOP_CLR};font-weight:600;font-size:1.05rem;">'
            f'Top Line Optimized</span> − Standard Delta',
            unsafe_allow_html=True,
        )
        st.dataframe(pd.DataFrame(_build_delta_rows(std, top)), use_container_width=True, hide_index=True)


def render_pricing_comparison(
    std: CohortScenario, ltv: CohortScenario, top: CohortScenario,
) -> None:
    """Side-by-side pricing lever comparison."""
    st.markdown("**Pricing Decisions Comparison (Per Deal)**")

    s = std.per_deal_pricing
    l = ltv.per_deal_pricing
    t = top.per_deal_pricing

    def _ach_desc(p):
        if p.ach_mode == "fixed_fee":
            return f"${p.ach_fixed_fee:.2f} fixed"
        elif p.ach_mode == "capped":
            return f"{p.ach_pct_rate:.2%} capped at ${p.ach_cap:.2f}"
        return f"{p.ach_pct_rate:.2%}"

    rows = [
        {"Lever": "SaaS Discount", "Standard": f"{s.saas_arr_discount_pct:.0%}", "LTV Optimized": f"{l.saas_arr_discount_pct:.0%}", "Top Line Optimized": f"{t.saas_arr_discount_pct:.0%}"},
        {"Lever": "Impl Fee Discount", "Standard": f"{s.impl_fee_discount_pct:.0%}", "LTV Optimized": f"{l.impl_fee_discount_pct:.0%}", "Top Line Optimized": f"{t.impl_fee_discount_pct:.0%}"},
        {"Lever": "CC Base Rate", "Standard": f"{s.cc_base_rate:.2%}", "LTV Optimized": f"{l.cc_base_rate:.2%}", "Top Line Optimized": f"{t.cc_base_rate:.2%}"},
        {"Lever": "AMEX Rate", "Standard": f"{s.cc_amex_rate:.2%}", "LTV Optimized": f"{l.cc_amex_rate:.2%}", "Top Line Optimized": f"{t.cc_amex_rate:.2%}"},
        {"Lever": "ACH Pricing", "Standard": _ach_desc(s), "LTV Optimized": _ach_desc(l), "Top Line Optimized": _ach_desc(t)},
        {"Lever": "Hold Days (CC/Bank/ACH)", "Standard": f"{s.hold_days_cc}/{s.hold_days_bank}/{s.hold_days_ach}", "LTV Optimized": f"{l.hold_days_cc}/{l.hold_days_bank}/{l.hold_days_ach}", "Top Line Optimized": f"{t.hold_days_cc}/{t.hold_days_bank}/{t.hold_days_ach}"},
        {"Lever": "SaaS ARR (Y1)", "Standard": f"${s.effective_saas_arr:,.0f}", "LTV Optimized": f"${l.effective_saas_arr:,.0f}", "Top Line Optimized": f"${t.effective_saas_arr:,.0f}"},
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_per_deal_comparison(
    std: CohortScenario, ltv: CohortScenario, top: CohortScenario,
) -> None:
    """Per-deal economics comparison so the SaaS trade-off is visible."""
    st.markdown("**Per-Deal Economics (Single Average Deal)**")

    rows = []
    for y in [1, 2, 3]:
        sy = std.per_deal_yearly[y]
        ly = ltv.per_deal_yearly[y]
        ty = top.per_deal_yearly[y]
        rows.append({
            "Year": str(y),
            "Std SaaS": f"${sy.saas_revenue:,.0f}",
            "LTV SaaS": f"${ly.saas_revenue:,.0f}",
            "Top SaaS": f"${ty.saas_revenue:,.0f}",
            "Std Revenue": f"${sy.total_revenue:,.0f}",
            "LTV Revenue": f"${ly.total_revenue:,.0f}",
            "Top Revenue": f"${ty.total_revenue:,.0f}",
            "Std Margin": f"${sy.margin:,.0f}",
            "LTV Margin": f"${ly.margin:,.0f}",
            "Top Margin": f"${ty.margin:,.0f}",
        })

    std_3yr = sum(std.per_deal_yearly[y].total_revenue for y in [1, 2, 3])
    ltv_3yr = sum(ltv.per_deal_yearly[y].total_revenue for y in [1, 2, 3])
    top_3yr = sum(top.per_deal_yearly[y].total_revenue for y in [1, 2, 3])
    std_3yr_m = sum(std.per_deal_yearly[y].margin for y in [1, 2, 3])
    ltv_3yr_m = sum(ltv.per_deal_yearly[y].margin for y in [1, 2, 3])
    top_3yr_m = sum(top.per_deal_yearly[y].margin for y in [1, 2, 3])
    std_3yr_s = sum(std.per_deal_yearly[y].saas_revenue for y in [1, 2, 3])
    ltv_3yr_s = sum(ltv.per_deal_yearly[y].saas_revenue for y in [1, 2, 3])
    top_3yr_s = sum(top.per_deal_yearly[y].saas_revenue for y in [1, 2, 3])
    rows.append({
        "Year": "Total",
        "Std SaaS": f"${std_3yr_s:,.0f}",
        "LTV SaaS": f"${ltv_3yr_s:,.0f}",
        "Top SaaS": f"${top_3yr_s:,.0f}",
        "Std Revenue": f"${std_3yr:,.0f}",
        "LTV Revenue": f"${ltv_3yr:,.0f}",
        "Top Revenue": f"${top_3yr:,.0f}",
        "Std Margin": f"${std_3yr_m:,.0f}",
        "LTV Margin": f"${ltv_3yr_m:,.0f}",
        "Top Margin": f"${top_3yr_m:,.0f}",
    })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
