from lib.auth import authenticate, logout
authenticate()

import streamlit as st

from lib.db import fetch_settings, update_settings, fetch_budget_year_labels
from lib.export_utils import generate_excel_export

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

st.divider()

# --- Export Data ---
st.subheader("Export Data")
st.caption("Download all financial data (Budget, Transactions, Working Capital) for a specific year as an Excel file.")

export_years = fetch_budget_year_labels()
if not export_years:
    st.info("No budget years available to export.")
else:
    col_ex_year, col_ex_btn_prep = st.columns([2, 1])
    with col_ex_year:
        selected_export_year = st.selectbox("Select Year", export_years, key="export_year_select")
    with col_ex_btn_prep:
        st.write("") # Spacer to align button with input box
        st.write("") 
        
        # We generate the file on click (or pre-generate if small enough, but on click is better for fresh data).
        # However, st.download_button requires the data upfront or a callback.
        # Generating on every render is expensive.
        # We can use a callback to generate data? No, download_button needs 'data' arg.
        # If data is small, we can generate it.
        # Let's generate it when the user selects a year? 
        # Actually, for this scale, generating it on render is probably fine, or we can use a "Prepare Download" button pattern.
        # But st.download_button is the standard way.
        # Let's try to generate it only if the user interacts? Streamlit re-runs on interaction.
        # So we generate it every time the page loads? That might be slow if data grows.
        # Optimization: cache the generation?
        # For now, let's just generate it. If it's slow, we can optimize.
        
        if st.button("Prepare Excel export", type="secondary"):
            with st.spinner("Preparing Excel export…"):
                try:
                    st.session_state["excel_export_data"] = generate_excel_export(selected_export_year)
                    st.session_state["excel_export_year"] = selected_export_year
                    st.success("Export prepared")
                except httpx.ReadError:
                    st.error("Could not read data from the backend (temporary error). Please try again.")
                except Exception as e:
                    st.error(f"Unexpected error while preparing export: {e}")

    # Show download button only if we have data
    excel_data = st.session_state.get("excel_export_data")
    excel_year = st.session_state.get("excel_export_year")
    if excel_data is not None:
        st.download_button(
            label=f"Download Excel ({excel_year})",
            data=excel_data,
            file_name=f"investia_export_{excel_year}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )

st.divider()

if st.session_state.get("authenticated"):
    if st.button("Logout"):
        logout()
