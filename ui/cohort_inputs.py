"""
Cohort-level input form for the pricing impact model.
"""
from __future__ import annotations
import streamlit as st
import config as cfg


def render_cohort_inputs() -> dict:
    """Render cohort inputs and return collected values."""

    st.header("Cohort Data")

    c1, c2, c3 = st.columns(3)
    with c1:
        cohort_name = st.text_input("Cohort Name", value="Q4 2025")
        deals_to_pricing = st.number_input(
            "Deals to Pricing", min_value=1, value=126, step=1,
        )
        current_win_rate = st.number_input(
            "Current Win Rate (%)", min_value=0.0, max_value=100.0,
            value=59.0, step=1.0, format="%.1f",
        ) / 100

    with c2:
        avg_saas_arr = st.number_input(
            "Avg ARR / Deal (Pre-Discount)", min_value=0.0,
            value=30_476.0, step=1000.0, format="%.0f",
        )
        avg_impl_fee = st.number_input(
            "Avg Implementation Fee ($/deal)", min_value=0.0,
            value=5_599.0, step=500.0, format="%.0f",
        )

    with c3:
        total_arr_won = st.number_input(
            "Total ARR Won ($)", min_value=0.0,
            value=1_654_046.0, step=10_000.0, format="%.0f",
            help="Recurring ARR only (excludes implementation fees). "
                 "Used for volume forecast via historical Vol/MRR ratios.",
        )

    st.subheader("Win Rate & Churn")
    w1, w2 = st.columns(2)
    with w1:
        win_rate_increase = st.slider(
            "Target Win Rate Increase",
            min_value=0, max_value=15, value=10, step=1,
            format="%d%%",
            help="The model will adjust SaaS discount (and other levers if needed) "
                 "to achieve this win rate increase over standard pricing.",
        ) / 100
    with w2:
        quarterly_churn = st.number_input(
            "Quarterly Churn Rate (%)",
            min_value=0.0, max_value=20.0, value=2.0, step=0.5,
            format="%.1f",
            help="Percentage of deals that churn each quarter. "
                 "Applied to all revenue (SaaS, processing, float).",
        ) / 100

    st.subheader("Teampay Assumptions")
    tp1, tp2 = st.columns(2)
    with tp1:
        tp_contract_optin = st.slider(
            "Teampay Contract Opt-in %",
            min_value=0, max_value=100, value=80, step=5,
            format="%d%%",
            help="Percentage of deals that allow Teampay in their contract.",
        ) / 100
    with tp2:
        tp_actual_usage = st.slider(
            "Teampay Actual Usage %",
            min_value=0, max_value=100, value=45, step=5,
            format="%d%%",
            help="Of those who opt in, the percentage that actually use Teampay.",
        ) / 100

    return {
        "cohort_name": cohort_name,
        "deals_to_pricing": deals_to_pricing,
        "current_win_rate": current_win_rate,
        "avg_saas_arr": avg_saas_arr,
        "avg_impl_fee": avg_impl_fee,
        "total_arr_won": total_arr_won,
        "win_rate_increase": win_rate_increase,
        "quarterly_churn": quarterly_churn,
        "tp_contract_optin": tp_contract_optin,
        "tp_actual_usage": tp_actual_usage,
    }


def render_standard_pricing() -> dict:
    """Render inputs for standard (current) pricing baseline."""

    with st.expander("Standard Pricing (Current Baseline)", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            saas_disc = st.slider(
                "SaaS ARR Discount %", 0, 70, 30, key="std_saas_disc",
            ) / 100
            impl_disc = st.slider(
                "Impl Fee Discount %", 0, 100, 0, key="std_impl_disc",
            ) / 100
        with c2:
            cc_rate = st.number_input(
                "CC Base Rate %", min_value=1.50, max_value=3.50,
                value=2.20, step=0.05, key="std_cc",
                help="Q4 avg non-AMEX base rate. Model adds 0.53% fixed component.",
            ) / 100
            amex_rate = st.number_input(
                "AMEX Rate %", min_value=2.50, max_value=4.0,
                value=3.21, step=0.05, key="std_amex",
                help="Q4 avg AMEX fee: 3.21%",
            ) / 100
        with c3:
            ach_mode = st.selectbox(
                "ACH Mode", cfg.ACH_MODES,
                format_func=lambda m: {
                    "percentage": "Percentage",
                    "capped": "Capped",
                    "fixed_fee": "Fixed Fee",
                }.get(m, m),
                index=0, key="std_ach_mode",
            )
            ach_pct = 0.08
            ach_cap = 10.0
            ach_fixed = 2.00
            if ach_mode in ("percentage", "capped"):
                ach_pct = st.number_input(
                    "ACH % Rate", min_value=0.01, max_value=1.0,
                    value=0.08, step=0.01, key="std_ach_pct",
                    help="Q4 avg ACH fee: 0.08%",
                )
            if ach_mode == "capped":
                ach_cap = st.number_input(
                    "ACH Cap ($)", min_value=1.0, max_value=25.0,
                    value=10.0, step=0.50, key="std_ach_cap",
                )
            if ach_mode == "fixed_fee":
                ach_fixed = st.number_input(
                    "ACH Fixed Fee ($)", min_value=0.50, max_value=10.0,
                    value=2.00, step=0.25, key="std_ach_fixed",
                )

        h1, h2, h3 = st.columns(3)
        with h1:
            hold_cc = st.slider("CC Hold Days", 1, 2, 2, key="std_hold_cc")
        with h2:
            hold_bank = st.slider("Bank Hold Days", 1, 5, 2, key="std_hold_bank")
        with h3:
            hold_ach = st.slider("ACH Hold Days", 1, 7, 3, key="std_hold_ach")

    return {
        "saas_arr_discount_pct": saas_disc,
        "impl_fee_discount_pct": impl_disc,
        "cc_base_rate": cc_rate,
        "cc_amex_rate": amex_rate,
        "ach_mode": ach_mode,
        "ach_pct_rate": ach_pct / 100,
        "ach_cap": ach_cap,
        "ach_fixed_fee": ach_fixed,
        "hold_days_cc": hold_cc,
        "hold_days_ach": hold_ach,
        "hold_days_bank": hold_bank,
    }
