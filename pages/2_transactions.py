from lib.auth import authenticate
authenticate()

from time import sleep
import streamlit as st
import pandas as pd
from lib.db import (
    upsert_transactions,
    delete_transactions,
    fetch_budget_year_labels,
    fetch_transactions_with_categories
)

st.set_page_config(page_title="Transactions — Investia", page_icon="🗃️", layout="wide")
st.title("Transactions")

year_labels = fetch_budget_year_labels()
selected_year = st.selectbox("Budget year", year_labels, index=0)

if selected_year == "":
    st.warning("Please select a budget year.")
    st.stop()

 # Load full rows (including id) and live category names joined from the budget table

full_df = fetch_transactions_with_categories(selected_year)

# -------------------------
# Filters Section
# -------------------------
st.markdown("### Filters")

filter_df = full_df.copy()

# Build month options based on txn_date (YYYY-MM)
if "txn_date" in filter_df.columns:
    month_series = pd.to_datetime(filter_df["txn_date"], errors="coerce").dt.to_period("M").astype(str)
    filter_df["_month"] = month_series
    month_options = sorted(m for m in month_series.dropna().unique())
else:
    filter_df["_month"] = None
    month_options = []

selected_months = st.multiselect("Month", month_options)

# Build category options
category_options = sorted(c for c in filter_df["category"].dropna().unique()) if "category" in filter_df.columns else []
selected_categories = st.multiselect("Category", category_options)

# Apply filters
if selected_months:
    filter_df = filter_df[filter_df["_month"].isin(selected_months)]
if selected_categories:
    filter_df = filter_df[filter_df["category"].isin(selected_categories)]

# Drop helper column before editing
if "_month" in filter_df.columns:
    filter_df = filter_df.drop(columns=["_month"])

st.write("You can edit the transactions directly in the table below. To delete a transaction, remove its row and click 'Save changes.', If you want to change the category, delete the transaction and re-insert it with the correct category using the 'Insert Transaction' page. Don't forget to save your changes!")

# Make a copy for editing (after filters)
edit_df = filter_df.copy()

# Convert txn_date to proper date for Streamlit
if "txn_date" in edit_df.columns:
    edit_df["txn_date"] = pd.to_datetime(edit_df["txn_date"], errors="coerce").dt.date

edited = st.data_editor(
    edit_df,
    use_container_width=True,
    num_rows="dynamic",
    column_order=["id", "txn_date", "category", "description", "amount", "is_expense", "year_label"],
    column_config={
        "id": st.column_config.NumberColumn("ID", disabled=True),
        "txn_date": st.column_config.DateColumn("Date"),
        "category": st.column_config.TextColumn("Category", disabled=True),
        "description": st.column_config.TextColumn("Description"),
        "amount": st.column_config.NumberColumn("Amount", format="%.2f"),
        "is_expense": st.column_config.CheckboxColumn("Expense?"),
        "year_label": st.column_config.TextColumn("Year", disabled=True),
    },
    hide_index=True,
)
if st.button("Save changes"):
    # Determine deleted rows
    original_ids = set(full_df["id"].astype(str).tolist())
    edited_ids = set(edited["id"].astype(str).dropna().tolist())
    deleted_ids = list(original_ids - edited_ids)

    if deleted_ids:
        delete_transactions(deleted_ids)
        st.success(f"Deleted {len(deleted_ids)} transactions.")
        sleep(1)

    # Upsert edited and new rows directly from the edited DataFrame
    updated, inserted = upsert_transactions(edited)
    if updated or inserted:
        st.success(f"Upserted {updated} existing and inserted {inserted} transactions.")
        sleep(1)
    st.rerun()

    # --Apply filters--
    