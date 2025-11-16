from lib.auth import authenticate, logout
authenticate()

import streamlit as st

from lib.db import fetch_settings, update_settings

# --- Page config ---
st.set_page_config(page_title="Settings — Investia", page_icon="⚙️", layout="wide")
st.title("Settings")

st.caption(
    "This page lets you set the start of the financial year. All data are stored in Supabase."
)

st.divider()

st.subheader("Financial year start")
st.caption("Choose the month and day your financial year (e.g. 2025-26) begins (e.g. 1 September → month 9, day 1). This will be used by reporting later. According to the Investia statutes, the financial year starts on 1 October.")

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
