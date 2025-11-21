from lib.auth import authenticate
import streamlit as st
import pandas as pd
from time import sleep

from lib.db import (
    fetch_budget_year_labels,
    get_opening_cash,
    update_opening_cash,
    fetch_budget_entries,
    fetch_budget_entries_for_type,
    add_budget_category,
    delete_budget_category,
    update_budget_category,
    select_budget_year
)

authenticate()

st.set_page_config(page_title="Budget — Investia", page_icon="📊", layout="wide")
st.title("Budget")

# --- Year selection ---
years = fetch_budget_year_labels()
if not years:
    st.info("No budget years available.")
    st.stop()

col_year_select, _ = st.columns([2, 1])
with col_year_select:
    # ----------------- Budget Year Selection -----------------
    current_year = select_budget_year()

# --- Constants ---
CATEGORY_TYPES = ["income", "year", "semester1", "semester2"]

st.subheader("Manage categories")

# --- Add new category ---
st.markdown("#### Add new category")
with st.form(f"add_category_{current_year}"):
    new_name = st.text_input("Category name")
    new_type = st.selectbox("Category type", CATEGORY_TYPES)
    new_year = st.selectbox("Year", years, index=years.index(current_year))
    new_amount = st.number_input("Initial amount", value=0.0)
    add_ok = st.form_submit_button("Add category")

    if add_ok:
        name_clean = new_name.strip()
        if not name_clean:
            st.warning("Please enter a name.")
        else:
            add_budget_category(new_year, name_clean, new_type, new_amount)
            st.success(f"Added '{name_clean}' to {new_year}.")

# --- Edit / delete category for current year ---
st.markdown("#### Edit or delete category for current year")
entries = fetch_budget_entries(current_year)
if entries.empty:
    st.info("No categories yet for this year.")
else:
    names = entries["category_name"].drop_duplicates().tolist()

    # Select which category to edit
    selected_name = st.selectbox(
        "Select category",
        names,
        key=f"edit_select_{current_year}",
    )

    # Pull current data for that category
    subset = entries[entries["category_name"] == selected_name]
    original_type = subset.iloc[0]["budget_type"]
    original_amount = float(subset.iloc[0]["budget"])

    # Use keys that depend on the selected category so widgets reset when selection changes
    edit_name = st.text_input(
        "New name",
        value=selected_name,
        key=f"edit_name_{current_year}_{selected_name}",
    )
    edit_type = st.selectbox(
        "New type",
        CATEGORY_TYPES,
        index=CATEGORY_TYPES.index(original_type),
        key=f"edit_type_{current_year}_{selected_name}",
    )
    edit_amount = st.number_input(
        "Amount",
        value=original_amount,
        key=f"edit_amount_{current_year}_{selected_name}",
    )

    col_edit, col_delete = st.columns(2)
    with col_edit:
        do_edit = st.button(
            "Save changes",
            key=f"save_category_{current_year}_{selected_name}",
        )
    with col_delete:
        do_delete = st.button(
            "Delete category",
            key=f"delete_category_{current_year}_{selected_name}",
        )

    if do_edit:
        new_name_clean = edit_name.strip()
        if not new_name_clean:
            st.warning("Name cannot be empty.")
        else:
            update_budget_category(
                current_year,
                selected_name,
                new_name_clean,
                original_type,
                edit_type,
                edit_amount,
            )
            st.success("Category updated.")
            sleep(1)
            st.rerun()

    if do_delete:
        try:
            delete_budget_category(current_year, selected_name)
        except Exception as e:
            # Try to extract an error code (e.g. Postgres 23503 for FK violation)
            err_code = None
            # Some clients put details on the exception object
            if hasattr(e, "code"):
                err_code = getattr(e, "code", None)
            # Others put the payload in args[0] as a dict
            if err_code is None and e.args:
                first_arg = e.args[0]
                if isinstance(first_arg, dict):
                    err_code = first_arg.get("code")

            if err_code == "23503":
                st.warning(
                    "You cannot delete this category because there are still "
                    "transactions linked to it. Please delete those transactions "
                    "first and then try again."
                )
            else:
                st.error(f"Error while deleting category: {e}")
        else:
            st.success("Category deleted.")
            sleep(1)
            st.rerun()

st.markdown("---")

# --- Opening cash ---
st.subheader("Opening cash position")
current_opening = get_opening_cash(current_year)
col_cash_input, col_cash_save = st.columns([2,1])
with col_cash_input:
    cash_val = st.number_input("Opening cash", value=float(current_opening), step=100.0)
with col_cash_save:
    if st.button("Save", key=f"save_opening_{current_year}"):
        update_opening_cash(current_year, float(cash_val))
        st.success("Saved")
        sleep(1)
        st.rerun()

st.markdown("---")

# --- Render section ---

def section(title: str, btype: str) -> None:
    st.subheader(title)
    df = fetch_budget_entries_for_type(current_year, btype)
    # Only show the requested columns (keep order). If none are present,
    # show an empty frame with the expected column headers.
    desired_cols = ["category_name", "budget", "budget_type", "year_label"]
    if df is None:
        df = pd.DataFrame(columns=desired_cols)
    else:
        cols_present = [c for c in desired_cols if c in df.columns]
        if cols_present:
            df = df[cols_present]
        else:
            df = pd.DataFrame(columns=desired_cols)

    st.dataframe(df)
    st.markdown("---")


# --- Sections ---
section("Income", "income")
section("Full year", "year")
section("Semester 1", "semester1")
section("Semester 2", "semester2")