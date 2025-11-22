from lib.auth import authenticate
import streamlit as st
import pandas as pd
from time import sleep
import datetime as dt

from lib.db import (
    get_budget_category_id,
    select_budget_year,
    get_members,
    fetch_categories,
    insert_working_capital_entry,
    load_working_capital,
    delete_working_capital_entry,
    update_working_capital_entry,
    update_working_capital_entry,
    get_budget_category_name
)
from lib.email_utils import send_amount_due_notification
from lib.backend_calculations import calculate_working_capital_metrics

authenticate()

st.set_page_config(page_title="Working capital — Investia", page_icon="📊", layout="wide")
st.title("Working capital")

# --- Year selection ---
selected_year = select_budget_year()
st.divider()

# --- Metrics ---
metrics = calculate_working_capital_metrics(selected_year)
m_col1, m_col2, m_col3, m_col4 = st.columns(4)

with m_col1:
    st.metric("Total AR", f"€ {metrics['total_ar']:,.2f}")
    st.caption(f"Member: € {metrics['total_ar_member']:,.2f} | Sponsor: € {metrics['total_ar_sponsor']:,.2f} | Other: € {metrics['total_ar_other']:,.2f}")

with m_col2:
    st.metric("Total AP", f"€ {metrics['total_ap']:,.2f}")

with m_col3:
    st.metric("Total Inventory", f"€ {metrics['total_inventory']:,.2f}")

with m_col4:
    st.metric("NWC (AR + Inventory - AP)", f"€ {metrics['nwc']:,.2f}", delta_color="normal")

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

            email_member = st.checkbox("Email member", value=True)

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

        if ar_kind_detail == "Member" and member_choice and email_member:
            email_sent = send_amount_due_notification(
                member_name=member_choice.get("name") or member_choice.get("username"),
                member_email=member_choice.get("email"),
                amount=ar_amount,
                category=ar_category,
                description=ar_description.strip() if ar_description else None
            )
            if email_sent:
                st.toast("Email sent to member!", icon="📧")
            else:
                st.error("Failed to send email.")

        st.success("Accounts receivable entry submitted.")
        sleep(1)
        st.rerun()

    st.markdown("### Open accounts receivable")

    receivables_df = load_working_capital(book_year_label=selected_year, kind="AR")

    if receivables_df.empty:
        st.info("No open accounts receivable for this book year yet.")
    else:
        # Map usernames to actual names
        member_list = get_members()
        member_name_map = {m.get("username"): (m.get("name") or m.get("username")) for m in member_list}
        member_email_map = {m.get("username"): m.get("email") for m in member_list}
        for label in ["Member", "Sponsor", "Other"]:
            group_df = receivables_df[receivables_df["kind_detail"] == label] if "kind_detail" in receivables_df.columns else pd.DataFrame()
            if group_df.empty:
                continue

            st.divider()
            st.markdown(f"#### {label}")

            for r in group_df.to_dict("records"):
                with st.container(border=True):
                    c1, c2, c3, c4, c5, c6 = st.columns([2, 1, 1, 1, 1, 1])

                    # Left: title + description
                    with c1:
                        if label == "Member":
                            uname = r.get("member_username")
                            title = member_name_map.get(uname, uname) or "Member receivable"
                        else:
                            title = r.get("kind_detail") or "Receivable"
                        st.markdown(f"**{title}**")
                        if r.get("description"): st.caption(r["description"])

                    # Amount
                    with c2:
                        amount = float(r.get("amount") or 0); st.write(f"€ {amount:.2f}")

                    # Entry date
                    with c3:
                        entry_date = r.get("entry_date")
                        if entry_date: st.write(f"Date: {entry_date}")

                    # Category / extra info placeholder
                    with c4:
                        cat_id = r.get("budget_category_id")
                        cat = get_budget_category_name(selected_year, cat_id) if cat_id else None
                        if cat: st.write(cat)

                    # Actions
                    with c5:
                        if label == "Member":
                            if st.button("Send reminder", key=f"remind_{r['id']}"):
                                uname = r.get("member_username")
                                email = member_email_map.get(uname)
                                if email:
                                    cat_id = r.get("budget_category_id")
                                    cat_name = get_budget_category_name(selected_year, cat_id) if cat_id else "Uncategorized"
                                    
                                    sent = send_amount_due_notification(
                                        member_name=member_name_map.get(uname, uname),
                                        member_email=email,
                                        amount=float(r.get("amount") or 0),
                                        category=cat_name,
                                        description=r.get("description")
                                    )
                                    if sent:
                                        st.toast("Reminder sent!", icon="📧")
                                    else:
                                        st.error("Failed to send reminder.")
                                else:
                                    st.error("No email found for this member.")
                    with c6:
                        if st.button("Mark fulfilled", key=f"fulfilled_{r['id']}", help="Mark this receivable as fulfilled (will delete it)."):
                            delete_working_capital_entry(r["id"]); st.success("Removed."); sleep(1); st.rerun()
                        
                    with st.expander("Edit"):
                        with st.form(f"edit_{r['id']}"):
                            new_amount = st.number_input("Amount (€)", min_value=0.00, step=0.01, value=float(r.get("amount") or 0.00))

                            # Parse entry date into a proper date object
                            entry_date_raw = r.get("entry_date")
                            if isinstance(entry_date_raw, dt.date):
                                entry_date_value = entry_date_raw
                            elif isinstance(entry_date_raw, str):
                                try: entry_date_value = dt.date.fromisoformat(entry_date_raw)
                                except ValueError: entry_date_value = dt.date.today()
                            else:
                                entry_date_value = dt.date.today()
                            new_date = st.date_input("Date", value=entry_date_value)

                            # Category selection (optional change)
                            category_options = [""] + fetch_categories(selected_year)
                            new_category_name = st.selectbox("Category", category_options)

                            new_description = st.text_area("Description", value=r.get("description") or "")
                            save_edit = st.form_submit_button("Save changes")

                            if save_edit:
                                kwargs = {
                                    "amount": float(new_amount),
                                    "description": new_description.strip(),
                                    "entry_date": new_date,
                                }
                                if new_category_name:
                                    kwargs["budget_category_id"] = get_budget_category_id(selected_year, new_category_name)

                                update_working_capital_entry(r["id"], **kwargs)
                                st.success("Updated."); sleep(1); st.rerun()

# === Accounts payable interface ===
if kind_choice == "Accounts payable":
    st.subheader("Accounts payable")
    st.markdown(f"Add a new accounts payable entry for **{selected_year}**.")

    col_left, col_right = st.columns(2)
    with col_left:
        ap_category = st.selectbox("Category", [""] + fetch_categories(selected_year))
    with col_right:
        ap_amount = st.number_input("Amount", min_value=0.0, step=1.0, format="%.2f")
        ap_entry_date = st.date_input("Date")

    ap_description = st.text_area("Description (optional)", height=80)
    submitted_ap = st.button("Add accounts payable")

    if submitted_ap:
        insert_working_capital_entry(
            book_year_label=selected_year,
            kind="AP",
            kind_detail=None,
            member_username=None,
            amount=ap_amount,
            entry_date=ap_entry_date,
            description=ap_description.strip() if ap_description else None,
            budget_category_id=get_budget_category_id(selected_year, ap_category),
            number_of_pieces=None,
            inserted_by_username=st.session_state.username,
        )
        st.success("Accounts payable entry submitted.")
        sleep(1); st.rerun()

    st.markdown("### Open accounts payable")
    payable_df = load_working_capital(book_year_label=selected_year, kind="AP")

    if payable_df.empty:
        st.info("No open accounts payable yet.")
    else:
        for r in payable_df.to_dict("records"):
            with st.container(border=True):
                c1, c2, c3, c4, c5 = st.columns([2,1,1,1,1])

                with c1:
                    st.markdown("**Accounts payable**")
                    if r.get("description"): st.caption(r["description"])

                with c2:
                    amt = float(r.get("amount") or 0); st.write(f"€ {amt:.2f}")

                with c3:
                    d = r.get("entry_date")
                    if d: st.write(f"Date: {d}")

                with c4:
                    cat_id = r.get("budget_category_id")
                    cat = get_budget_category_name(selected_year, cat_id) if cat_id else None
                    if cat: st.write(cat)

                with c5:
                    if st.button("Mark fulfilled", key=f"ap_del_{r['id']}"):
                        delete_working_capital_entry(r["id"])
                        st.success("Removed."); sleep(1); st.rerun()
                        
                with st.expander("Edit"):
                    with st.form(f"ap_edit_{r['id']}"):
                        new_amount = st.number_input("Amount (€)", min_value=0.00, step=0.01, value=float(r.get("amount") or 0.00))

                        raw = r.get("entry_date")
                        if isinstance(raw, dt.date): dval = raw
                        elif isinstance(raw, str):
                            try: dval = dt.date.fromisoformat(raw)
                            except ValueError: dval = dt.date.today()
                        else: dval = dt.date.today()
                        new_date = st.date_input("Date", value=dval)

                        opts = [""] + fetch_categories(selected_year)
                        new_cat = st.selectbox("Category", opts)

                        new_desc = st.text_area("Description", value=r.get("description") or "")
                        save = st.form_submit_button("Save changes")

                        if save:
                            kwargs = {
                                "amount": float(new_amount),
                                "description": new_desc.strip(),
                                "entry_date": new_date,
                            }
                            if new_cat:
                                kwargs["budget_category_id"] = get_budget_category_id(selected_year, new_cat)

                            update_working_capital_entry(r["id"], **kwargs)
                            st.success("Updated."); sleep(1); st.rerun()

# === Inventory interface ===
if kind_choice == "Inventory":
    st.subheader("Inventory")
    st.markdown("Edit your inventory below. Changes are saved when you press **Save inventory**. Make sure that the green banner appears to confirm saving, otherwise press once more on save. Inventory does not depend on the bookyear.")

    # Load all inventory entries, independent of book year
    inv_df = load_working_capital(kind="INVENTORY")
    if inv_df.empty:
        inv_df = pd.DataFrame()

    # Ensure the needed columns exist
    for col in ["description", "amount", "number_of_pieces"]:
        if col not in inv_df.columns:
            inv_df[col] = None

    # Keep ids so we can map back after editing
    ids = inv_df["id"] if "id" in inv_df.columns else pd.Series([None] * len(inv_df))
    display_df = inv_df[["description", "amount", "number_of_pieces"]].copy()

    edited_df = st.data_editor(
        display_df,
        num_rows="dynamic",
        key="inventory_editor",
        column_config={
            "description": st.column_config.TextColumn("Description"),
            "amount": st.column_config.NumberColumn("Amount (€)", step=1.0, format="%.2f"),
            "number_of_pieces": st.column_config.NumberColumn("Pieces", step=1),
        },
    )

    if st.button("Save inventory"):
        # Attach ids back to edited rows (index is preserved by data_editor)
        edited_df["id"] = ids

        # Drop completely empty rows
        def _row_empty(row):
            desc = (str(row["description"]).strip() if row["description"] is not None else "")
            desc_empty = (desc == "" or desc.lower() == "nan")
            amount_empty = pd.isna(row["amount"]) or float(row["amount"]) == 0
            pieces_empty = pd.isna(row["number_of_pieces"]) or int(row["number_of_pieces"] or 0) == 0
            return desc_empty and amount_empty and pieces_empty

        # Keep rows with a valid id OR truly new non-empty rows
        cleaned = edited_df[
            (edited_df["id"].notna() & (edited_df["id"].astype(str).str.strip() != ""))
            | (~edited_df.apply(_row_empty, axis=1))
        ].reset_index(drop=True)

        existing_ids = set(inv_df["id"].dropna().astype(str)) if "id" in inv_df.columns else set()
        cleaned_ids = set(cleaned["id"].dropna().astype(str))

        # Deletions: rows that existed before but are now gone
        for del_id in existing_ids - cleaned_ids:
            delete_working_capital_entry(del_id)

        # Inserts / updates
        for _, row in cleaned.iterrows():
            desc = str(row["description"]).strip() if row["description"] is not None else None
            amt = float(row["amount"]) if not pd.isna(row["amount"]) else 0.0
            pieces = int(row["number_of_pieces"]) if not pd.isna(row["number_of_pieces"]) else None

            rid = row.get("id")

            # Update only if id exists and is valid
            if pd.notna(rid) and str(rid).strip() != "":
                update_working_capital_entry(
                    str(rid),
                    description=desc,
                    amount=amt,
                    number_of_pieces=pieces,
                )
            else:
                # New row
                insert_working_capital_entry(
                    book_year_label=selected_year,
                    kind="INVENTORY",
                    kind_detail=None,
                    member_username=None,
                    amount=amt,
                    entry_date=dt.date.today(),
                    description=desc,
                    budget_category_id=None,
                    number_of_pieces=pieces,
                    inserted_by_username=st.session_state.username,
                )

        st.success("Inventory saved."); sleep(1); st.rerun()