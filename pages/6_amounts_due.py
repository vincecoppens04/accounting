import datetime as dt
from typing import List, Dict, Optional

import streamlit as st

from lib.auth import authenticate
from lib.db import (
    get_members,                 # () -> List[Dict[str, str]] with keys: username, name
    list_amounts_due,            # () -> List[Dict]
    create_amount_due,           # (member_username: str, amount: float, due_date: date, note: Optional[str]) -> None
    update_amount_due,           # (id: str, amount: float, due_date: date, note: Optional[str]) -> None
    delete_amount_due,           # (id: str) -> None
)

authenticate()

st.set_page_config(page_title="Amounts Due — Investia", page_icon="💶", layout="wide")
st.title("Amounts Due")
st.caption("Create and manage outstanding amounts for members.")

# --- Helpers ---
@st.cache_data(ttl=300)
def _load_members() -> List[Dict[str, str]]:
    return get_members()

@st.cache_data(ttl=30)
def _load_dues() -> List[Dict]:
    return list_amounts_due()


def _member_options():
    members = _load_members()
    # Show names in the UI, keep usernames for FK
    labels = [m.get('name') or m.get('username') for m in members]
    return members, labels


# --- New Amount form ---
with st.form("new_due_form"):
    st.subheader("Add a new amount")
    members, labels = _member_options()
    if not members:
        st.info("No members available yet.")
        member_choice = None
    else:
        # Add an empty placeholder option so nothing is preselected
        options = [None] + list(range(len(members)))
        idx = st.selectbox(
            "Member",
            options=options,
            format_func=lambda i: "" if i is None else labels[i],
        )
        member_choice = None if idx is None else members[idx]

    amount = st.number_input("Amount (€)", min_value=0.01, step=0.01, value=0.01)
    default_due = dt.date.today() + dt.timedelta(days=7)
    due_date = st.date_input("Due date", value=default_due)
    note = st.text_area("Note (optional)", placeholder="Context, event, etc.")

    submitted = st.form_submit_button("Save")

    if submitted:
        if not member_choice:
            st.error("Please select a member.")
        else:
            try:
                create_amount_due(
                    member_username=member_choice['username'],
                    amount=float(amount),
                    due_date=due_date,
                    note=note.strip() if note else None,
                )
                st.success("Saved.")
                _load_dues.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Could not save: {e}")

st.divider()

# --- Existing amounts ---
st.subheader("Open amounts")
rows = _load_dues()

if not rows:
    st.info("Nothing outstanding.")
else:
    # Simple filter
    member_filter = st.selectbox(
        "Filter by member",
        options=["All"] + sorted({r.get('member_name') for r in rows if r.get('member_name')}),
    )

    def _apply_filters(data):
        out = list(data)
        if member_filter != "All":
            out = [r for r in out if r.get('member_name') == member_filter]
        return out

    filtered = _apply_filters(rows)

    for r in filtered:
        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 1])
            with c1:
                st.markdown(f"**{r.get('member_name') or r.get('member_username')}**")
                if r.get('note'):
                    st.caption(r['note'])
            with c2:
                st.write(f"€ {r.get('amount'):.2f}")
            with c3:
                created_at = r.get('created_at')
                if created_at:
                    if isinstance(created_at, dt.datetime):
                        created_at = created_at.date()
                    st.write(f"Created: {created_at}")
            with c4:
                due = r.get('due_date')
                st.write(f"Due: {due}")
            with c5:
                del_clicked = st.button("Mark fulfilled", key=f"del_{r['id']}")
                if del_clicked:
                    try:
                        delete_amount_due(r['id'])
                        st.success("Removed.")
                        _load_dues.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not remove: {e}")

            with st.expander("Edit"):
                with st.form(f"edit_{r['id']}"):
                    new_amount = st.number_input("Amount (€)", min_value=0.01, step=0.01, value=float(r.get('amount', 0.01)))
                    new_due = st.date_input("Due date", value=r.get('due_date') or (dt.date.today() + dt.timedelta(days=7)))
                    new_note = st.text_area("Note", value=r.get('note') or "")
                    save_edit = st.form_submit_button("Save changes")
                    if save_edit:
                        try:
                            update_amount_due(r['id'], float(new_amount), new_due, new_note.strip())
                            st.success("Updated.")
                            _load_dues.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Could not update: {e}")