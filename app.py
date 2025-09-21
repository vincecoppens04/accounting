import streamlit as st
from lib.auth import authenticate, logout
authenticate()

st.switch_page("pages/1_dashboard.py")

st.set_page_config(page_title="Investia – Finance", page_icon="💷", layout="wide")

st.title("Investia")
st.write("Use the navigation at the top of the sidebar to switch between pages.")

if st.session_state.get("authenticated"):
    if st.button("Logout"):
        logout()
