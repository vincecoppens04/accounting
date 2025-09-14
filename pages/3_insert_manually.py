from lib.auth import authenticate
authenticate()

import streamlit as st
from datetime import date
from lib.db import fetch_categories, insert_transaction

st.set_page_config(page_title="Transaction — Investia", layout="wide")
st.title("Insert Transaction")

with st.form("transaction_form"):
    tx_date = st.date_input("Date", value=date.today())
    categories = fetch_categories()
    category = st.selectbox("Category", categories)
    description = st.text_input("Description")
    amount = st.number_input("Amount", step=0.01, format="%.2f")
    tx_type = st.radio("Type", ["Expense", "Income"])
    currency = st.text_input("Currency", value="EUR")
    submitted = st.form_submit_button("Insert")

if submitted:
    time_label = tx_date.strftime("%Y-%m")
    data = {
        "txn_date": tx_date.isoformat(),
        "time_label": time_label,
        "category": category,
        "description": description,
        "amount": amount,
        "is_expense": tx_type == "Expense",
        "currency": currency,
    }
    ok, payload = insert_transaction(data)
    if ok:
        st.success(f"Transaction inserted for {time_label}.")
    else:
        st.error("Failed to insert transaction.")