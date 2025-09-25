from lib.auth import authenticate
authenticate()

import streamlit as st
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta
import altair as alt

from lib.db import fetch_transactions, fetch_settings, fetch_category_budgets

st.set_page_config(page_title="Dashboard — Investia", page_icon="📊", layout="wide")
st.title("Dashboard")

# ----------------- Helpers -----------------

def current_fy_window(fy_month: int, fy_day: int) -> tuple[date, date]:
    today = date.today()
    try:
        start_this_year = date(
            today.year,
            fy_month,
            min(fy_day, 28 if fy_month == 2 else 30 if fy_month in (4, 6, 9, 11) else 31),
        )
    except Exception:
        start_this_year = date(today.year, 1, 1)
    if today >= start_this_year:
        start = start_this_year
        end = date(
            today.year + 1,
            fy_month,
            min(fy_day, 28 if fy_month == 2 else 30 if fy_month in (4, 6, 9, 11) else 31),
        )
    else:
        start = date(
            today.year - 1,
            fy_month,
            min(fy_day, 28 if fy_month == 2 else 30 if fy_month in (4, 6, 9, 11) else 31),
        )
        end = start_this_year
    return start, end  # [start, end)


def months_in_range(d1: date, d2: date) -> int:
    if d2 <= d1:
        return 0
    p1 = pd.Period(d1.strftime("%Y-%m"), freq="M")
    p2 = pd.Period((d2 - relativedelta(days=1)).strftime("%Y-%m"), freq="M")
    try:
        return int((p2 - p1).n) + 1 if d2 > d1 else 0
    except Exception:
        return 0

# ----------------- Time window -----------------
settings = fetch_settings() or {}
fy_m = int(settings.get("fy_start_month") or 1)
fy_d = int(settings.get("fy_start_day") or 1)
start_default, end_default = current_fy_window(fy_m, fy_d)

with st.expander("Time window", expanded=True):
    c1, c2 = st.columns(2)
    with c1:
        start_date = st.date_input("From", value=start_default)
    with c2:
        end_date = st.date_input("To (exclusive)", value=end_default)
    st.caption(f"Default = current financial year from settings (start {fy_d:02d}-{fy_m:02d}).")

# ----------------- Data -----------------
rows = fetch_transactions() or []
if not rows:
    st.info("No transactions yet.")
    st.stop()

DF = pd.DataFrame(rows)
DF["txn_date"] = pd.to_datetime(DF["txn_date"], errors="coerce").dt.date
DF = DF[(DF["txn_date"] >= start_date) & (DF["txn_date"] < end_date)]
if DF.empty:
    st.info("No transactions in the selected period.")
    st.stop()

# Normalised fields
DF["amount"] = pd.to_numeric(DF["amount"], errors="coerce").fillna(0.0)
DF["is_expense"] = DF["is_expense"].astype(bool)
DF["expense"] = DF.apply(lambda r: float(r["amount"]) if r["is_expense"] else 0.0, axis=1)
DF["income"] = DF.apply(lambda r: float(r["amount"]) if not r["is_expense"] else 0.0, axis=1)

# ----------------- Charts: Expense / Income per category -----------------
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
cat_bud = fetch_category_budgets()
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
