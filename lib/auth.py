import streamlit as st

def authenticate():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    with st.form("login_form"):
        st.subheader("Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Submit")
        if submitted:
            from lib.db import validate_member_credentials
            status, member = validate_member_credentials(username.strip(), password)
            if status == "ok":
                st.session_state.authenticated = True
                st.session_state.username = member["username"]
                st.session_state.display_name = member.get("name")
                st.rerun()
            elif status == "no_priv":
                st.error("Your credentials are valid, but you do not have privileges to access this app.")
            else:
                st.error("Incorrect username or password.")
        st.stop()

def logout():
    st.session_state.authenticated = False
    st.rerun()