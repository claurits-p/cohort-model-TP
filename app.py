"""
Paystand Cohort Pricing Impact Model

Compares Standard pricing vs LTV-Optimized vs Top-Line-Optimized pricing
applied to a full deal cohort, showing 3-year financials, break-even,
and revenue impact.
"""
import streamlit as st

st.set_page_config(
    page_title="Paystand Cohort Impact Model",
    page_icon="paystand_logo.png",
    layout="wide",
)

st.markdown(
    """<style>
    /* Bigger text in all dataframe tables */
    .stDataFrame table,
    .stDataFrame th,
    .stDataFrame td,
    div[data-testid="stDataFrame"] table,
    div[data-testid="stDataFrame"] th,
    div[data-testid="stDataFrame"] td,
    .dvn-scroller table,
    .dvn-scroller th,
    .dvn-scroller td,
    [data-testid="glideDataEditor"] * {
        font-size: 1.15rem !important;
    }
    /* Paystand blue primary button */
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="baseButton-primary"] {
        background-color: #003B91 !important;
        border-color: #003B91 !important;
    }
    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="baseButton-primary"]:hover {
        background-color: #002D6F !important;
        border-color: #002D6F !important;
    }
    </style>""",
    unsafe_allow_html=True,
)

from ui.cohort_inputs import render_cohort_inputs, render_standard_pricing
from ui.cohort_engine import run_cohort_comparison
from ui.cohort_display import (
    render_volume_forecast,
    render_summary_metrics,
    render_scenario_header,
    render_side_by_side_tables,
    render_delta_table,
    render_pricing_comparison,
)
from ui.cohort_charts import (
    render_break_even_chart,
    render_revenue_composition,
    render_insight_callouts,
)


def main():
    logo_col, title_col = st.columns([0.06, 0.94], gap="small")
    with logo_col:
        st.image("paystand_logo.png", width=55)
    with title_col:
        st.markdown(
            '<h1 style="color: #003B91; margin-top: -5px;">'
            "Paystand Cohort Pricing Impact Model</h1>",
            unsafe_allow_html=True,
        )

    cohort = render_cohort_inputs()
    std_pricing = render_standard_pricing()

    if st.button("Run Cohort Analysis", type="primary", use_container_width=True):
        with st.spinner("Solving for target win rate and scaling to cohort..."):
            standard, ltv, topline, solver_msg = run_cohort_comparison(
                deals_to_pricing=cohort["deals_to_pricing"],
                current_win_rate=cohort["current_win_rate"],
                avg_saas_arr=cohort["avg_saas_arr"],
                avg_impl_fee=cohort["avg_impl_fee"],
                total_arr_won=cohort["total_arr_won"],
                standard_pricing_inputs=std_pricing,
                win_rate_increase=cohort["win_rate_increase"],
                quarterly_churn=cohort["quarterly_churn"],
                tp_contract_optin=cohort["tp_contract_optin"],
                tp_actual_usage=cohort["tp_actual_usage"],
            )

        _BOX_BLUE = (
            '<div style="padding:12px 16px;background:#e8f4fd;border-left:4px solid #1B6AC9;'
            'border-radius:4px;margin-bottom:8px;color:#1B6AC9;font-size:0.95rem;">'
        )
        _BOX_WARN = (
            '<div style="padding:12px 16px;background:#fff8e1;border-left:4px solid #f0a500;'
            'border-radius:4px;margin-bottom:8px;color:#7a5900;font-size:0.95rem;">'
        )

        if solver_msg:
            st.markdown(f'{_BOX_WARN}{solver_msg}</div>', unsafe_allow_html=True)

        def _format_changes(scenario):
            if not scenario.lever_changes:
                return None
            parts = []
            for k, (old, new) in scenario.lever_changes.items():
                label = k.replace("_", " ").title()
                if "rate" in k or "pct" in k:
                    parts.append(f"{label}: {old:.2%} → {new:.2%}")
                elif "fee" in k or "cap" in k:
                    parts.append(f"{label}: ${old:.2f} → ${new:.2f}")
                else:
                    parts.append(f"{label}: {old} → {new}")
            return " | ".join(parts)

        ltv_changes = _format_changes(ltv)
        top_changes = _format_changes(topline)

        if ltv_changes:
            st.markdown(
                f'{_BOX_BLUE}<b>LTV Optimized adjustments:</b> {ltv_changes}</div>',
                unsafe_allow_html=True,
            )
        if top_changes:
            _BOX_ORANGE = (
                '<div style="padding:12px 16px;background:#fef3e8;border-left:4px solid #E67E22;'
                'border-radius:4px;margin-bottom:8px;color:#a85d1a;font-size:0.95rem;">'
            )
            st.markdown(
                f'{_BOX_ORANGE}<b>Top Line Optimized adjustments:</b> {top_changes}</div>',
                unsafe_allow_html=True,
            )

        st.divider()
        render_volume_forecast(standard, ltv, topline)

        st.divider()
        render_pricing_comparison(standard, ltv, topline)

        st.divider()
        render_insight_callouts(standard, ltv, topline)

        st.divider()
        render_summary_metrics(standard, ltv, topline)

        st.divider()
        render_break_even_chart(standard, ltv, topline)

        st.divider()
        render_revenue_composition(standard, ltv, topline)

        st.divider()
        render_side_by_side_tables(standard, ltv, topline)

        st.divider()
        render_delta_table(standard, ltv, topline)


if __name__ == "__main__":
    main()
