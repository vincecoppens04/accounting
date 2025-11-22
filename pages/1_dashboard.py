import streamlit as st
import pandas as pd
import altair as alt
from lib.auth import authenticate
from lib.db import select_budget_year
from lib.backend_calculations import (
    calculate_budget_metrics,
    calculate_working_capital_metrics,
    calculate_dashboard_data,
    calculate_cash_flow_evolution,
    calculate_current_cash_position,
    calculate_cash_position_with_nwc
)

authenticate()

st.set_page_config(page_title="Dashboard — Investia", page_icon="📊", layout="wide")
st.title("Dashboard")

# ----------------- Year Selection -----------------
selected_year = select_budget_year()
st.divider()

# ----------------- Metrics Overview -----------------
# Fetch metrics
b_metrics = calculate_budget_metrics(selected_year)
wc_metrics = calculate_working_capital_metrics(selected_year)
current_cash = calculate_current_cash_position(selected_year)
cash_with_nwc = calculate_cash_position_with_nwc(selected_year)

st.markdown("### Key metrics")

# First row of metrics
m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)

with m_col1:
    st.metric("Cash Position (Beginning)", f"€ {b_metrics['opening_cash']:,.2f}")
with m_col2:
    st.metric("Total Expenses", f"€ {b_metrics['total_expenses_all']:,.2f}")
    st.caption(f"Sem 1: € {b_metrics['total_expenses_sem1']:,.2f} | Sem 2: € {b_metrics['total_expenses_sem2']:,.2f} | Year: € {b_metrics['total_expenses_year']:,.2f}")
with m_col3:
    st.metric("Current Cash Position", f"€ {current_cash:,.2f}")
with m_col4:
    st.metric("NWC", f"€ {wc_metrics['nwc']:,.2f}")
    st.caption(f"AR: € {wc_metrics['total_ar']:,.2f} | AP: € {wc_metrics['total_ap']:,.2f} | Inv: € {wc_metrics['total_inventory']:,.2f}")
with m_col5:
    st.metric("Cash Position with NWC", f"€ {cash_with_nwc:,.2f}")

# Second row of metrics
m_col6, m_col7, m_col8, m_col9, m_col10 = st.columns(5)

with m_col6:
    st.metric("Projected Savings", f"€ {b_metrics['savings']:,.2f}")
with m_col7:
    st.metric("Free Float", f"€ {b_metrics['free_float']:,.2f}")

st.divider()

# ----------------- Period Selection -----------------
st.markdown("### Budget vs Spending")

period_filter = st.radio(
    "Select period",
    ["Everything", "Sem 1", "Sem 2", "Year Expenses"],
    horizontal=True
)

# Fetch data based on selection
dashboard_df = calculate_dashboard_data(selected_year, period_filter)

if dashboard_df.empty:
    st.info("No budget data found for the selected period.")
else:
    # ----------------- Bullet Chart -----------------
    st.subheader("Spending overview")
    
    # Prepare data for Altair
    # We want a bar for Net Spending and a marker for Budget
    
    base = alt.Chart(dashboard_df).encode(
        x=alt.X("category:N", sort="-y", title="Category")
    )
    
    # Bar for Net Spending
    bars = base.mark_bar(color="#B0C4DE").encode(
        y=alt.Y("net_spending:Q", title="Amount (€)"),
        tooltip=["category", "net_spending", "budget", "remaining"]
    )
    
    # Tick for Budget
    ticks = base.mark_tick(color="black", thickness=2, width=20).encode(
        y=alt.Y("budget:Q")
    )
    
    chart = (bars + ticks).properties(height=400)
    st.altair_chart(chart, use_container_width=True)
    
    st.caption("Blue bars represent Net Spending. Black markers represent the Budget.")

    # ----------------- Budget Table -----------------
    st.subheader("Detailed budget table")
    
    # Color coding logic for 'Remaining'
    # We can use Pandas Styler or st.column_config
    # Let's use st.dataframe with column_config for a cleaner look
    
    # We want to highlight if remaining is negative (Over budget) -> Red?
    # Or if remaining is positive (Under budget) -> Green?
    # Usually for expenses: Remaining > 0 is Good (Green), Remaining < 0 is Bad (Red).
    
    # Prepare display dataframe
    display_df = dashboard_df[["category", "budget", "net_spending", "remaining"]].copy()
    
    # Apply color coding
    def color_remaining(val):
        color = '#ff4b4b' if val < 0 else '#3dd56d' # Red if negative, Green if positive
        return f'color: {color}'

    styled_df = display_df.style.map(color_remaining, subset=['remaining']).format("€ {:,.2f}", subset=["budget", "net_spending", "remaining"])

    st.dataframe(
        styled_df,
        use_container_width=True,
        column_config={
            "category": "Category",
            "budget": st.column_config.NumberColumn("Budget"),
            "net_spending": st.column_config.NumberColumn("Net Spending"),
            "remaining": st.column_config.NumberColumn(
                "Remaining",
                help="Budget - Net Spending"
            ),
        }
    )

st.divider()

# ----------------- Suggestions -----------------
st.markdown("### Cash flow evolution")

cash_flow_df = calculate_cash_flow_evolution(selected_year)

if cash_flow_df.empty:
    st.info("No transactions to show cash flow evolution.")
else:
    # Create line chart
    line_chart = alt.Chart(cash_flow_df).mark_line(point=True).encode(
        x=alt.X("date:T", title="Date"),
        y=alt.Y("balance:Q", title="Balance (€)"),
        tooltip=[alt.Tooltip("date:T", format="%Y-%m-%d"), alt.Tooltip("balance:Q", format=",.2f")]
    ).properties(height=400)
    
    st.altair_chart(line_chart, use_container_width=True)
