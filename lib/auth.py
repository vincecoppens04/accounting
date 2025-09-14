import streamlit as st
import base64
import hashlib
import hmac
from lib.db import fetch_settings

def pbkdf2_hash(password: str, salt_b64: str) -> str:
    """Return PBKDF2-HMAC-SHA256 hash using base64 salt."""
    salt = base64.b64decode(salt_b64)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return base64.b64encode(dk).decode("utf-8")

def authenticate():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    settings = fetch_settings()
    stored_hash = settings.get("app_password_hash")
    stored_salt = settings.get("app_password_salt")

    with st.form("login_form"):
        st.subheader("Login")
        password = st.text_input("Enter password", type="password")
        submitted = st.form_submit_button("Submit")
        if submitted:
            if stored_hash and stored_salt:
                derived_hash = pbkdf2_hash(password, stored_salt)
                if hmac.compare_digest(derived_hash, stored_hash):
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Incorrect password.")
            else:
                st.error("Password is not configured.")
        st.stop()