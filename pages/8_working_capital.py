from lib.auth import authenticate
import streamlit as st
import pandas as pd
from time import sleep

from lib.db import (
    get_budget_category_id,
    select_budget_year,
    get_members,
    fetch_categories,
    insert_working_capital_entry,
    load_working_capital,
    delete_working_capital_entry,
    update_working_capital_entry,
)

authenticate()

st.set_page_config(page_title="Working capital — Investia", page_icon="📊", layout="wide")
st.title("Working capital")

# --- Year selection ---
selected_year = select_budget_year()
st.divider()

# --- Working capital kind selection ---
kind_choice = st.radio(
    "Working capital type",
    ["Accounts receivable", "Accounts payable", "Inventory"],
    horizontal=True,
)

# === Accounts receivable interface ===
if kind_choice == "Accounts receivable":
    st.subheader("Accounts receivable")

    st.markdown(
        "Use the form below to add a new accounts receivable entry for the "
        f"book year **{selected_year}**. Once saved, it will appear in the "
        "tables by type further down the page."
    )

    # Top form to create a new accounts receivable entry
    col_left, col_right = st.columns(2)

    with col_left:
        ar_kind_detail = st.selectbox(
            "Type",
            ["Member", "Sponsor", "Other"],
        )
        member_choice = None
        if ar_kind_detail == "Member":
            members = get_members()
            labels = [m.get("name") or m.get("username") for m in members]
            options = [None] + list(range(len(members)))
            idx = st.selectbox(
                "Member",
                options=options,
                format_func=lambda i: "" if i is None else labels[i],
            )
            member_choice = None if idx is None else members[idx]

        ar_category = st.selectbox(
            "Category",
            [""] + fetch_categories(selected_year),
        )

    with col_right:
        ar_amount = st.number_input(
            "Amount",
            min_value=0.0,
            step=1.0,
            format="%.2f")
        ar_entry_date = st.date_input(
            "Date",
        )

    ar_description = st.text_area(
        "Description (optional)",
        height=80,
    )

    submitted = st.button("Add accounts receivable")

    if submitted:
        insert_working_capital_entry(
            book_year_label=selected_year,
            kind="AR",
            kind_detail=ar_kind_detail,
            member_username=(
                member_choice.get("username") if member_choice else None
            ) if ar_kind_detail == "Member" else None,
            amount=ar_amount,
            entry_date=ar_entry_date,
            description=ar_description.strip() if ar_description else None,
            budget_category_id=get_budget_category_id(selected_year, ar_category),
            number_of_pieces=None,
            inserted_by_username=st.session_state.username,
        )
        st.success("Accounts receivable entry submitted.")
        sleep(1)
        st.rerun()

    st.markdown("### Open accounts receivable")

    # This returns a dataframe with all the working capital filtered on selected year and AR kind
    receivables_df = load_working_capital(book_year_label=selected_year, kind="AR")

    if receivables_df.empty:
        st.info("No open accounts receivable for this book year yet.")
    else:
        for r in receivables_df.to_dict("records"):
            with st.container(border=True):
                c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 1])

                # Left: name and description
                with c1:
                    st.markdown(f"**{'testing'}**")
                    if r.get("description"):
                        st.caption(r["description"])

                # Amount
                with c2:
                    amount = float(r.get("amount") or 0)
                    st.write(f"€ {amount:.2f}")

                # Entry date
                with c3:
                    entry_date = r.get("entry_date")
                    if entry_date:
                        st.write(f"Created: {entry_date}")

                # Detail: e.g. member/sponsor/other
                with c4:
                    kind_detail = r.get("kind_detail")
                    if kind_detail:
                        st.write(f"Type: {kind_detail}")

                # Actions
                with c5:
                    mark_fulfilled = st.button(
                        "Mark fulfilled",
                        key=f"fulfilled_{r['id']}",
                        help="Mark this receivable as fulfilled (will delete it).",
                    )
                    if mark_fulfilled:
                        delete_working_capital_entry(r["id"])
                        st.success("Removed.")
                        sleep(1)
                        st.rerun()

                with st.expander("Edit"):
                    with st.form(f"edit_{r['id']}"):
                        new_amount = st.number_input(
                            "Amount (€)",
                            min_value=0.00,
                            step=0.01,
                            value=float(r.get("amount") or 0.00),
                        )
                        new_description = st.text_area(
                            "Description",
                            value=r.get("description") or "",
                        )
                        save_edit = st.form_submit_button("Save changes")
                        if save_edit:
                            update_working_capital_entry(
                                r["id"],
                                amount=float(new_amount),
                                description=new_description.strip(),
                            )
                            st.success("Updated.")
                            sleep(1)
                            st.rerun()