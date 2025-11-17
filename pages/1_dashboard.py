from lib.auth import authenticate
authenticate()

import streamlit as st
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta
import altair as alt

from lib.db import select_budget_year, fetch_settings, fetch_categories_df, fetch_transactions_with_categories

st.set_page_config(page_title="Dashboard — Investia", page_icon="📊", layout="wide")
st.title("Dashboard")

# ----------------- Helpers -----------------
def months_in_range(d1: date, d2: date) -> int:
    if d2 <= d1:
        return 0
    p1 = pd.Period(d1.strftime("%Y-%m"), freq="M")
    p2 = pd.Period((d2 - relativedelta(days=1)).strftime("%Y-%m"), freq="M")
    try:
        return int((p2 - p1).n) + 1 if d2 > d1 else 0
    except Exception:
        return 0


def fy_window_from_label(year_label: str, fy_month: int, fy_day: int) -> tuple[date, date]:
    """
    Parse a year label like '2025-26' and compute the financial year range.
    Returns (start_date, end_date) where end_date is exclusive.
    E.g. '2025-26' with fy_month=10, fy_day=1 → (2025-10-01, 2026-09-30)
    """
    parts = year_label.split("-")
    start_year = int(parts[0])
    
    start = date(start_year, fy_month, fy_day)
    end = date(start_year+1, fy_month, fy_day)
    return start, end

# ----------------- Budget Year Selection -----------------
selected_year = select_budget_year()

# ----------------- Time window -----------------
settings = fetch_settings() or {}
fy_m = int(settings.get("fy_start_month") or 1)
fy_d = int(settings.get("fy_start_day") or 1)
start_default, end_default = fy_window_from_label(selected_year, fy_m, fy_d)

with st.expander("Time window", expanded=True):
    c1, c2 = st.columns(2)
    with c1:
        start_date = st.date_input("From", value=start_default)
    with c2:
        end_date = st.date_input("To (exclusive)", value=end_default)
    st.caption(f"Default = financial year from selected year (start {fy_d:02d}-{fy_m:02d}).")

# ----------------- Data -----------------
full_df = fetch_transactions_with_categories(selected_year)

if not full_df.size:
    st.info("No transactions yet.")
    st.stop()

# Filter by date range
DF = full_df[
    (pd.to_datetime(full_df["txn_date"], errors="coerce").dt.date >= start_date) &
    (pd.to_datetime(full_df["txn_date"], errors="coerce").dt.date < end_date)
].copy()

if DF.empty:
    st.info("No transactions in the selected date range.")
    st.stop()


DF["expense"] = DF.apply(lambda r: r["amount"] if r["is_expense"] else 0.0, axis=1)
DF["income"] = DF.apply(lambda r: r["amount"] if not r["is_expense"] else 0.0, axis=1)

# Compute expenses and income per category
exp_by_cat = DF.groupby("category", as_index=False)["expense"].sum().sort_values("expense", ascending=False)
inc_by_cat = DF.groupby("category", as_index=False)["income"].sum().sort_values("income", ascending=False)

c1, c2 = st.columns(2)
with c1:
    st.subheader("Expense per category")
    st.altair_chart(
        alt.Chart(exp_by_cat)
        .mark_bar(color="#00008B")
        .encode(
            x=alt.X("category:N", sort='-y'),
            y=alt.Y("expense:Q", title="Expense"),
            tooltip=["category", alt.Tooltip("expense:Q", format=",.2f")],
        ),
        use_container_width=True,
    )
with c2:
    st.subheader("Income per category")
    st.altair_chart(
        alt.Chart(inc_by_cat)
        .mark_bar(color="#ADD8E6")
        .encode(
            x=alt.X("category:N", sort='-y'),
            y=alt.Y("income:Q", title="Income"),
            tooltip=["category", alt.Tooltip("income:Q", format=",.2f")],
        ),
        use_container_width=True,
    )

# ----------------- Net spending vs budget (prorated) -----------------
# Fetch categories/budgets and normalise to the expected shape for merging.
# Expected columns: 'name' and 'monthly_budget'
cat_bud = fetch_categories_df(selected_year)
if cat_bud is None or (isinstance(cat_bud, pd.DataFrame) and cat_bud.empty):
    cat_bud = pd.DataFrame(columns=["name", "monthly_budget"])
else:
    # Rename common category name columns to 'name'
    if "name" not in cat_bud.columns:
        if "category_name" in cat_bud.columns:
            cat_bud = cat_bud.rename(columns={"category_name": "name"})
        elif "category" in cat_bud.columns:
            cat_bud = cat_bud.rename(columns={"category": "name"})

    # Create/normalise 'monthly_budget' from 'budget' if present.
    if "monthly_budget" not in cat_bud.columns:
        if "budget" in cat_bud.columns:
            cat_bud["monthly_budget"] = pd.to_numeric(cat_bud["budget"], errors="coerce").fillna(0.0)
        else:
            cat_bud["monthly_budget"] = 0.0

    # Keep only the two columns we need for merging (preserve order)
    cat_bud = cat_bud[["name", "monthly_budget"]].copy()

months = months_in_range(start_date, end_date)
grouped = DF.groupby("category", as_index=False).agg({
    "expense": "sum",
    "income": "sum"
})
grouped["net_spending"] = grouped["expense"] - grouped["income"]

merged = grouped.merge(cat_bud.rename(columns={"name": "category"}), on="category", how="left")
merged["monthly_budget"] = pd.to_numeric(merged["monthly_budget"], errors="coerce").fillna(0.0)

st.subheader("Net spending vs budget")
merged["net_spending"] = merged["net_spending"].fillna(0.0)
merged["monthly_budget"] = merged["monthly_budget"].fillna(0.0)

# Generate flat row: each column is Budget <category> or Net Spending <category>
data_dict = {}

for _, row in merged.iterrows():
    cat = row["category"]
    data_dict[cat + " (Budget)"] = row["monthly_budget"]
    data_dict[cat + " (Spending)"] = row["net_spending"]

chart_df = pd.DataFrame([data_dict])

# Melt into long form for Altair
long_df = pd.DataFrame([data_dict]).melt(var_name="Metric", value_name="Amount")

# Extract category and type
long_df["Category"] = long_df["Metric"].str.extract(r"^(.*?) \(")
long_df["Type"] = long_df["Metric"].str.extract(r"\((.*?)\)")

# Draw a single unified bar chart with custom colours
color_scale = alt.Scale(domain=["Budget", "Spending"], range=["#ADD8E6", "#00008B"])

st.altair_chart(
    alt.Chart(long_df)
    .mark_bar()
    .encode(
        x=alt.X("Category:N", sort=None, title="Category"),
        xOffset="Type:N",
        y=alt.Y("Amount:Q", title="Amount"),
        color=alt.Color("Type:N", scale=color_scale, legend=alt.Legend(title="Type")),
        tooltip=["Category", "Type", alt.Tooltip("Amount:Q", format=",.2f")],
    )
    .properties(height=400),
    use_container_width=True,
)

# ----------------- Drilldown -----------------
st.subheader("Overview by category")

overview_df = merged[["category", "expense", "income", "net_spending", "monthly_budget"]].copy()
overview_df = overview_df.rename(columns={
    "category": "Category",
    "expense": "Total Expense",
    "income": "Total Income",
    "net_spending": "Net Spending",
    "monthly_budget": "Budget"
})
st.dataframe(overview_df, use_container_width=True)
st.subheader("Top 3 costs and incomes")

all_categories = sorted(DF["category"].dropna().unique().tolist())
sel = st.selectbox("Category", options=all_categories)
sub = DF[DF["category"] == sel].copy()

# Top 3 costs and incomes
top_exp = sub[sub["expense"] > 0].sort_values("expense", ascending=False).head(3)
top_inc = sub[sub["income"] > 0].sort_values("income", ascending=False).head(3)

c3, c4 = st.columns(2)
with c3:
    st.markdown("**Top 3 costs**")
    if top_exp.empty:
        st.write("–")
    else:
        st.dataframe(
            top_exp[["txn_date", "description", "expense"]].rename(columns={"txn_date": "Date", "expense": "Amount"}),
            use_container_width=True,
        )
with c4:
    st.markdown("**Top 3 incomes**")
    if top_inc.empty:
        st.write("–")
    else:
        st.dataframe(
            top_inc[["txn_date", "description", "income"]].rename(columns={"txn_date": "Date", "income": "Amount"}),
            use_container_width=True,
        )
