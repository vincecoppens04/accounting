from lib.auth import authenticate, logout
authenticate()

import base64
import os
import hashlib
from typing import Optional

import pandas as pd
import streamlit as st

from lib.db import fetch_settings, update_settings, fetch_categories, upsert_categories, delete_categories

# --- Page config ---
st.set_page_config(page_title="Settings — Investia", page_icon="⚙️", layout="wide")
st.title("Settings")

st.caption(
    "This page lets you maintain the categories and their monthly budgets, and set the start of the financial year. All data are stored in Supabase."
)

# =====================
# Categories & budgets
# =====================

st.subheader("Categories & monthly budgets")
st.caption("Add, rename or remove categories. Budgets are monthly. Names must be unique.")

cat_df = fetch_categories()
original_names = set(cat_df["name"].astype(str).str.strip()) if not isinstance(cat_df, list) else set(cat_df)
if isinstance(cat_df, list):
    cat_df = pd.DataFrame({"name": cat_df, "monthly_budget": 0})
elif cat_df.empty:
    # Initialise with one example row only
    cat_df = pd.DataFrame({"name": ["Income"], "monthly_budget": [0]})

edited = st.data_editor(
    cat_df,
    num_rows="dynamic",
    column_config={
        "name": st.column_config.TextColumn("Category"),
        "monthly_budget": st.column_config.NumberColumn("Monthly budget", step=0.01),
    },
    use_container_width=True,
    key="cat_editor",
)

if st.button("Save categories", type="primary"):
    edited_clean = edited.copy()
    edited_clean["name"] = edited_clean["name"].fillna("").astype(str).str.strip()
    edited_clean["monthly_budget"] = pd.to_numeric(edited_clean["monthly_budget"], errors="coerce").fillna(0.0)

    remaining = set(edited_clean["name"])
    original_set = set([n for n in original_names if n])
    to_delete = sorted(n for n in original_set - remaining if n)

    count = upsert_categories(edited_clean)
    deleted = 0
    if to_delete:
        try:
            deleted = delete_categories(to_delete)
        except Exception as e:
            st.warning("Some categories could not be deleted because they are still used in transactions. Please move or delete those transactions first.")
    
    st.success(f"Saved {count} categories. Deleted {deleted}.")

st.divider()

st.subheader("Financial year start")
st.caption("Choose the month and day your financial year begins (e.g. 1 September → month 9, day 1). This will be used by reporting later.")

_current = fetch_settings()
fy_month_val = int((_current or {}).get("fy_start_month") or 1)
fy_day_val = int((_current or {}).get("fy_start_day") or 1)

col_m, col_d = st.columns(2)
with col_m:
    fy_month_val = st.number_input("Month (1–12)", min_value=1, max_value=12, value=fy_month_val)
with col_d:
    fy_day_val = st.number_input("Day (1–31)", min_value=1, max_value=31, value=fy_day_val)

if st.button("Save financial year start", type="primary"):
    update_settings({
        "fy_start_month": int(fy_month_val),
        "fy_start_day": int(fy_day_val),
    })
    st.success("Financial year start saved.")

if st.session_state.get("authenticated"):
    if st.button("Logout"):
        logout()
