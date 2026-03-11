"""
Visualizations for the cohort pricing impact model.
"""
from __future__ import annotations
import plotly.graph_objects as go
import streamlit as st

from ui.cohort_engine import CohortScenario

STD_COLOR = "#1B6AC9"
LTV_COLOR = "#2ECC71"
TOP_COLOR = "#E67E22"
DELTA_POS = "#27AE60"
DELTA_NEG = "#E74C3C"


def render_break_even_chart(
    std: CohortScenario, ltv: CohortScenario, top: CohortScenario,
) -> None:
    """Cumulative margin over time with crossover points."""
    st.markdown("**Cumulative Margin Timeline**")

    years = [1, 2, 3]

    def _cum_margins(scenario):
        cum = []
        running = 0.0
        for y in years:
            running += scenario.cohort_yearly[y].margin
            cum.append(running)
        return cum

    std_cum = _cum_margins(std)
    ltv_cum = _cum_margins(ltv)
    top_cum = _cum_margins(top)

    def _find_crossover(base, comp):
        for i in range(len(years)):
            diff = comp[i] - base[i]
            if diff >= 0:
                if i == 0:
                    return float(years[0])
                prev_diff = comp[i - 1] - base[i - 1]
                if prev_diff < 0:
                    frac = -prev_diff / (diff - prev_diff)
                    return years[i - 1] + frac
                return float(years[i])
        return None

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=years, y=std_cum, mode="lines+markers+text",
        name="Standard", line=dict(color=STD_COLOR, width=3),
        text=[f"${v:,.0f}" for v in std_cum],
        textposition="top left", textfont=dict(size=11),
    ))
    fig.add_trace(go.Scatter(
        x=years, y=ltv_cum, mode="lines+markers+text",
        name="LTV Optimized", line=dict(color=LTV_COLOR, width=3),
        text=[f"${v:,.0f}" for v in ltv_cum],
        textposition="top center", textfont=dict(size=11),
    ))
    fig.add_trace(go.Scatter(
        x=years, y=top_cum, mode="lines+markers+text",
        name="Top Line Optimized", line=dict(color=TOP_COLOR, width=3),
        text=[f"${v:,.0f}" for v in top_cum],
        textposition="bottom center", textfont=dict(size=11),
    ))

    ltv_cross = _find_crossover(std_cum, ltv_cum)
    if ltv_cross is not None:
        label = f"LTV break-even: Year {int(ltv_cross)}" if ltv_cross == int(ltv_cross) else f"LTV break-even: ~Year {ltv_cross:.1f}"
        fig.add_vline(x=ltv_cross, line_dash="dash", line_color=LTV_COLOR,
                      annotation_text=label, annotation_position="top right",
                      annotation_font_color=LTV_COLOR)

    top_cross = _find_crossover(std_cum, top_cum)
    if top_cross is not None and top_cross != ltv_cross:
        label = f"Top Line break-even: Year {int(top_cross)}" if top_cross == int(top_cross) else f"Top Line break-even: ~Year {top_cross:.1f}"
        fig.add_vline(x=top_cross, line_dash="dash", line_color=TOP_COLOR,
                      annotation_text=label, annotation_position="bottom right",
                      annotation_font_color=TOP_COLOR)

    fig.update_layout(
        xaxis_title="Year", yaxis_title="Cumulative Margin ($)",
        xaxis=dict(tickmode="array", tickvals=[1, 2, 3], ticktext=["Year 1", "Year 2", "Year 3"]),
        yaxis=dict(tickformat="$,.0f"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=50, b=40), height=400,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_revenue_composition(
    std: CohortScenario, ltv: CohortScenario, top: CohortScenario,
) -> None:
    """Stacked bar showing revenue mix by year for all three scenarios."""
    st.markdown("**Revenue Composition by Year**")

    categories = ["SaaS", "CC", "ACH", "Float", "Impl Fee", "TP SaaS", "TP Proc"]
    colors = ["#3498DB", "#1B6AC9", "#2980B9", "#1ABC9C", "#95A5A6", "#9B59B6", "#8E44AD"]

    def _year_vals(s: CohortScenario, y: int) -> list[float]:
        cy = s.cohort_yearly[y]
        return [cy.saas_revenue, cy.cc_revenue, cy.ach_revenue,
                cy.float_income, cy.impl_fee_revenue,
                cy.teampay_saas_revenue, cy.teampay_processing_revenue]

    x_labels = [
        "Std Y1", "LTV Y1", "Top Y1",
        "Std Y2", "LTV Y2", "Top Y2",
        "Std Y3", "LTV Y3", "Top Y3",
    ]

    all_vals: list[list[float]] = []
    for y in (1, 2, 3):
        all_vals.append(_year_vals(std, y))
        all_vals.append(_year_vals(ltv, y))
        all_vals.append(_year_vals(top, y))

    fig = go.Figure()
    for i, cat in enumerate(categories):
        y_vals = [bar[i] for bar in all_vals]
        texts = [f"${v:,.0f}" if v > 50_000 else "" for v in y_vals]
        fig.add_trace(go.Bar(
            x=x_labels, y=y_vals,
            name=cat, marker_color=colors[i],
            text=texts, textposition="inside",
            textfont=dict(color="white", size=11),
        ))

    fig.update_layout(
        barmode="stack",
        yaxis=dict(tickformat="$,.0f", tickfont=dict(size=14)),
        xaxis=dict(tickfont=dict(size=12)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=13)),
        margin=dict(t=50, b=40), height=650,
    )

    for x_pos in [2.5, 5.5]:
        fig.add_vline(x=x_pos, line_dash="dot", line_color="#ccc", line_width=1)

    st.plotly_chart(fig, use_container_width=True)


def render_insight_callouts(
    std: CohortScenario, ltv: CohortScenario, top: CohortScenario,
) -> None:
    """Key insight messages."""
    BOX = (
        '<div style="padding:12px 16px;background:#e8f4fd;border-left:4px solid #1B6AC9;'
        'border-radius:4px;margin-bottom:8px;color:#1B6AC9;font-size:0.95rem;">'
    )
    BOX_GREEN = (
        '<div style="padding:12px 16px;background:#e8f8ef;border-left:4px solid #2ECC71;'
        'border-radius:4px;margin-bottom:8px;color:#1a6e3a;font-size:0.95rem;">'
    )
    BOX_ORANGE = (
        '<div style="padding:12px 16px;background:#fef3e8;border-left:4px solid #E67E22;'
        'border-radius:4px;margin-bottom:8px;color:#a85d1a;font-size:0.95rem;">'
    )

    ltv_deal_delta = ltv.deals_won - std.deals_won
    top_deal_delta = top.deals_won - std.deals_won

    if ltv_deal_delta > 0 or top_deal_delta > 0:
        st.markdown(
            f'{BOX_GREEN}Optimized pricing wins <b>{ltv_deal_delta} more deals</b> (LTV) '
            f'/ <b>{top_deal_delta} more deals</b> (Top Line) '
            f'from the same pipeline ({std.deals_won} standard).</div>',
            unsafe_allow_html=True,
        )

    ltv_margin = ltv.three_year_margin - std.three_year_margin
    top_margin = top.three_year_margin - std.three_year_margin
    ltv_rev = ltv.three_year_revenue - std.three_year_revenue
    top_rev = top.three_year_revenue - std.three_year_revenue

    st.markdown(
        f'{BOX}3-year margin impact: LTV <b>${ltv_margin:+,.0f}</b> &nbsp;|&nbsp; '
        f'Top Line <b>${top_margin:+,.0f}</b></div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'{BOX_ORANGE}3-year revenue impact: LTV <b>${ltv_rev:+,.0f}</b> &nbsp;|&nbsp; '
        f'Top Line <b>${top_rev:+,.0f}</b></div>',
        unsafe_allow_html=True,
    )
