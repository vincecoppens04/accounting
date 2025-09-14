from lib.auth import authenticate
authenticate()

import base64
import os
import hmac
import hashlib
from typing import Optional

import pandas as pd
import streamlit as st

from lib.db import fetch_settings, update_settings, fetch_categories, upsert_categories, delete_categories

# --- Page config ---
st.set_page_config(page_title="Settings — Investia", page_icon="⚙️", layout="wide")
st.title("Settings")

st.caption(
    "This page lets you maintain two things: (1) categories with their monthly budgets; (2) the site password.\n"
    "All data are stored in Supabase. The password is never stored in cleartext — only a PBKDF2 hash + salt."
)

# --- Minimal helpers: password hashing (PBKDF2-SHA256) ---
# We store two columns in the single-row `settings` table (id=1):
#   app_password_hash (base64 PBKDF2 digest)
#   app_password_salt (base64 random salt)

def pbkdf2_hash(password: str, salt_b64: Optional[str] = None) -> tuple[str, str]:
    """Return (hash_b64, salt_b64) using PBKDF2-HMAC-SHA256 with 200k iterations."""
    salt = os.urandom(16) if not salt_b64 else base64.b64decode(salt_b64)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return base64.b64encode(dk).decode("utf-8"), base64.b64encode(salt).decode("utf-8")

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
    # Clean and process edited categories
    edited_clean = edited.copy()
    edited_clean["name"] = edited_clean["name"].fillna("").astype(str).str.strip()
    edited_clean["monthly_budget"] = pd.to_numeric(edited_clean["monthly_budget"], errors="coerce").fillna(0.0)

    remaining = set(edited_clean["name"])
    to_delete = sorted(n for n in original_names - remaining if n)

    count = upsert_categories(edited_clean)
    deleted = 0
    if to_delete:
        try:
            deleted = delete_categories(to_delete)
        except Exception as e:
            st.warning(f"Some categories could not be deleted because they are still used in transactions. Please move or delete those transactions first.")
    st.success(f"Saved {count} categories. Deleted {deleted}.")

st.divider()

# ===============
# Password change
# ===============

st.subheader("Password")
st.caption(
    "Set a new password for accessing the app. Since you’re on this page, we assume you’re already authenticated.\n"
    "When you save, we store only a PBKDF2 hash plus a random salt — never the cleartext password."
)

with st.form("pwd_form"):
    new = st.text_input("New password", type="password")
    confirm = st.text_input("Confirm new password", type="password")
    submitted_pwd = st.form_submit_button("Update password")

if submitted_pwd:
    if new != confirm:
        st.error("New passwords do not match.")
    elif len(new or "") < 8:
        st.error("Choose at least 8 characters.")
    else:
        new_hash, new_salt = pbkdf2_hash(new)
        update_settings({"app_password_hash": new_hash, "app_password_salt": new_salt})
        st.success("Password updated.")
        with st.expander("How hashing works (for curiosity)", expanded=False):
            st.markdown(
                """
                **PBKDF2-SHA256** derives a key from your password using many iterations. We store:
                - `app_password_hash`: base64 of the derived key; and
                - `app_password_salt`: base64 of a random 16‑byte salt.

                On login, we recompute PBKDF2 with the stored salt and compare hashes using constant‑time comparison.
                This means the real password is never stored or retrievable from the database.
                """
            )

# ==========================
# Financial year start (M/D)
# ==========================

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

# Note: We intentionally omit Reporting Window / Fiscal Year UI here to keep the page minimal.
# You can still keep `date_start` / `date_end` / `fy_*` columns in the DB for future use.
