import streamlit as st
from lib.auth import authenticate, logout
from lib.ui import render_footer
authenticate()

st.set_page_config(page_title="Investia – Finance", page_icon="💷", layout="wide")

st.title("Investia Finance Management System")

st.markdown("""
### ⚠️ Important Notice & Terms of Use

This platform was designed and developed by **Vince Coppens** and remains exclusively his **intellectual property**.

---

- **Ownership & Rights:** All intellectual property rights are strictly reserved by Vince Coppens. No rights, licenses, or ownership are granted or transferred to any third-party users.
- **Authorized Use:** Any access or use of this application is strictly subject to the prior explicit approval of Vince Coppens.
- **No Guarantees / "As-Is" Basis:** No warranties, service guarantees, or commitments are made or lent to any user other than the owner.
- **Infrastructure & Scope:** The platform and its database are hosted entirely on personal GitHub and cloud database accounts, originally architected and built for short-term use.
- **Complimentary Access:** The platform is currently maintained and kept live at the owner's sole discretion and personal expense without charging users.

---

*Use the sidebar to navigate to the application modules.*
""")

if st.session_state.get("authenticated"):
    st.divider()
    if st.button("Logout"):
        logout()

render_footer()
