from lib.auth import authenticate
authenticate()

import streamlit as st
import pandas as pd
from lib.db import fetch_transactions, upsert_transactions, delete_transactions

st.set_page_config(page_title="Transactions — Investia", page_icon="🗃️", layout="wide")
st.title("Transactions")

# Load full rows (including id)
rows = fetch_transactions()
if not rows:
    st.info("No transactions yet.")
    st.stop()

full_df = pd.DataFrame(rows)

# Preserve ids separately (we'll reattach on save so updates don't duplicate)
id_series = full_df["id"] if "id" in full_df.columns else pd.Series(dtype=object)
original_ids = set(id_series.dropna().astype(str)) if not id_series.empty else set()

# Build the view dataframe (drop id, time_label, created_at)
keep_cols = ["description", "amount", "txn_date", "category", "is_expense", "currency"]
view_df = full_df[[c for c in keep_cols if c in full_df.columns]].copy()

# Derive friendly Type and a small coloured indicator from is_expense
if "is_expense" in view_df.columns:
    view_df["type"] = view_df["is_expense"].apply(lambda x: "Cost" if bool(x) else "Income")
    view_df["indicator"] = view_df["is_expense"].apply(lambda x: "🔴" if bool(x) else "🟢")

# Reorder columns: indicator first for scan, then Description, Amount, Date, Category, Type, Currency
column_order = [col for col in ["indicator", "description", "amount", "txn_date", "category", "type", "currency"] if col in view_df.columns]
view_df = view_df[column_order]

view_df.index = id_series

st.caption("Edit cells directly. Click Save to persist changes. (Add new transactions using the Insert pages)")
st.caption("Type controls Cost/Income. Date is view-only here.")

# Ensure txn_date is a real date for editable DateColumn
view_df["txn_date"] = pd.to_datetime(view_df["txn_date"], errors="coerce").dt.date

edited = st.data_editor(
    view_df,
    num_rows="dynamic",
    use_container_width=True,
    key="tx_editor",
    column_config={
        "txn_date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
        "description": st.column_config.TextColumn("Description"),
        "amount": st.column_config.NumberColumn("Amount", step=0.01),
        "type": st.column_config.SelectboxColumn("Type", options=["Cost", "Income"]),
        "currency": st.column_config.TextColumn("Currency"),
        "category": st.column_config.TextColumn("Category"),
        "indicator": st.column_config.TextColumn(" ", disabled=True),
    },
    column_order=column_order,
    hide_index=True,
)

if st.button("Save changes", type="primary"):
    # Prepare to save: map Type -> is_expense; drop helper columns
    to_save = edited.copy()
    if "type" in to_save.columns:
        to_save["is_expense"] = to_save["type"].apply(lambda v: True if v == "Cost" else False)
    to_save = to_save.drop(columns=["type", "indicator"], errors="ignore")

    # The editor preserves the index; existing rows keep their UUID id as index; new rows have NaN or a new index
    edited_ids = set(str(i) for i in to_save.index if pd.notna(i))
    to_delete = sorted(i for i in original_ids - edited_ids if i)

    # Reattach id column for upsert/insert
    to_save["id"] = [i if pd.notna(i) else None for i in to_save.index]

    deleted = 0
    if to_delete:
        try:
            deleted = delete_transactions(to_delete)
        except Exception:
            st.warning("Some rows could not be deleted.")

    # Convert txn_date to string (ISO 8601) so it's JSON serialisable
    if "txn_date" in to_save.columns:
        to_save["txn_date"] = to_save["txn_date"].apply(lambda d: d.isoformat() if pd.notna(d) else None)

    updated, inserted = upsert_transactions(to_save)

    st.success(f"Saved. Updated {updated}, inserted {inserted}, deleted {deleted}.")