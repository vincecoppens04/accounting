import streamlit as st
from lib.auth import authenticate
from lib.db import fetch_scanner_context, update_scanner_context, fetch_categories, insert_transaction
from lib.scanner_logic import classify_transactions
import pandas as pd
from datetime import datetime, date


# Enforce login
authenticate()

# Page title and explainer
st.set_page_config(page_title="Scanner — Investia", layout="wide")
st.title("Bank Statement Scanner")
st.markdown("Upload your **KBC PDF bank statement** and use the context below to help classify the transactions. The system will extract and classify the data for you.")

# Upload box
uploaded_pdf = st.file_uploader("Upload KBC PDF", type=["pdf"])


# Context editor (linked to Supabase settings)
st.subheader("Context for classification")

if "scanner_context" not in st.session_state:
    st.session_state.scanner_context = fetch_scanner_context()

context_text = st.text_area("Update the context used by the scanner", value=st.session_state.scanner_context, height=150)

if st.button("Save context to settings"):
    update_scanner_context(context_text)
    st.session_state.scanner_context = context_text
    st.success("Context saved.")

# Run button
go_button = st.button("Go", type="primary")

# Placeholder for loading indicator and results
status_placeholder = st.empty()
results_placeholder = st.container()

if go_button and uploaded_pdf:
    with status_placeholder:
        with st.spinner("Scanning and classifying transactions..."):
            import time
            time.sleep(1)
            classified_df = classify_transactions(uploaded_pdf)
            st.session_state.classified_df = classified_df
            st.session_state.uploaded_pdf = uploaded_pdf

classified_df = st.session_state.get("classified_df")
if classified_df is None and "uploaded_pdf" in st.session_state:
    classified_df = classify_transactions(st.session_state.uploaded_pdf)
    st.session_state.classified_df = classified_df

if classified_df is not None:

    st.subheader("Scanned Transactions")

    with st.form("all_transactions_form"):

        category_options_df = fetch_categories()
        category_options = category_options_df["name"].tolist()

        transactions_to_save = []

        for i, row in classified_df.iterrows():
            if st.session_state.get(f"saved_{i}", False):
                continue

            st.markdown(f"**Transaction {i + 1}**")

            default_date = pd.to_datetime(row["date"]).date() if pd.notnull(row["date"]) else date.today()
            proposed_category = row["category"] if row["category"] in category_options else None

            tx_date = st.date_input(f"Date_{i}", value=default_date, key=f"date_{i}")
            if proposed_category:
                category = st.selectbox(f"Category_{i}", category_options, index=category_options.index(proposed_category), key=f"cat_{i}")
            else:
                st.markdown(f"**Proposed category:** {row['category']}")
                category = st.selectbox(f"Category_{i}", category_options, key=f"cat_{i}")
            description = st.text_input(f"Description_{i}", row.get("message", ""), key=f"desc_{i}")
            amount = st.number_input(f"Amount_{i}", value=row["amount_eur"], step=0.01, format="%.2f", key=f"amt_{i}")
            is_expense = st.radio(f"Type_{i}", ["Expense", "Income"], index=0 if row["direction"] == "expense" else 1, key=f"type_{i}") == "Expense"
            currency = st.text_input(f"Currency_{i}", value="EUR", key=f"cur_{i}")
            include = st.checkbox(f"Include transaction {i + 1}?", value=True, key=f"checkbox_{i}")

            if include:
                tx_data = {
                    "txn_date": tx_date.isoformat(),
                    "category": category,
                    "description": description,
                    "amount": amount,
                    "is_expense": is_expense,
                    "time_label": tx_date.strftime("%Y-%m"),
                    "currency": currency
                }
                transactions_to_save.append((i, tx_data))
            st.markdown("---")

        if st.form_submit_button("Save All"):
            with st.spinner("Saving transactions..."):
                saved_count = 0
                for i, tx_data in transactions_to_save:
                    ok, res = insert_transaction(tx_data)
                    if ok:
                        st.session_state[f"saved_{i}"] = True
                        saved_count += 1
                st.success(f"Saved {saved_count} transactions.")