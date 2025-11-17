from lib.auth import authenticate
authenticate()

import streamlit as st
from datetime import date
from time import sleep
from lib.db import fetch_categories, insert_transaction, select_budget_year, get_budget_category_id

st.set_page_config(page_title="Transaction — Investia", layout="wide")
st.title("Insert Transaction")

 
tx_date = st.date_input("Date", value=date.today())

# ----------------- Budget Year Selection -----------------
year_label = select_budget_year()

categories = fetch_categories(year_label)
category = st.selectbox("Category", categories)

description = st.text_input("Description")
amount = st.number_input("Amount", step=0.01, format="%.2f")
tx_type = st.radio("Type", ["Expense", "Income"])
submitted = st.button("Insert")

if submitted:
    time_label = tx_date.strftime("%Y-%m")

    budget_category_id = get_budget_category_id(year_label, category)
    if not budget_category_id:
        st.error("No matching budget category for this year. Please check the budget setup.")
    else:
        data = {
            "txn_date": tx_date.isoformat(),
            "time_label": time_label,
            "category": category,
            "budget_category_id": budget_category_id,
            "description": description,
            "amount": amount,
            "is_expense": tx_type == "Expense",
            "currency": 'EUR',
            "year_label": year_label,
        }
        ok, payload = insert_transaction(data)
        if ok:
            st.success(f"Transaction inserted for {time_label}.")
            st.rerun()
            sleep(1)
        else:
            st.error("Failed to insert transaction.")