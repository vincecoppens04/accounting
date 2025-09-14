import streamlit as st
from lib.auth import authenticate
authenticate()

st.set_page_config(page_title="Investia – Finance", page_icon="💷", layout="wide")

st.title("Investia")
st.write("Use the navigation at the top of the sidebar to switch between pages.")

st.info(
    "This is the home page."
)