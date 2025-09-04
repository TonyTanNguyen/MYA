import streamlit as st
from utils import require_login, init_session_state

# Add custom CSS for title fonts
st.markdown("""
<style>
h1, h2, h3, h4, h5, h6 {
    font-family: 'CormorantGaramond', serif !important;
    font-weight: 500 !important;
}
</style>
""", unsafe_allow_html=True)

init_session_state()
user = require_login()

st.title("📌 Welcome to MYA App")
st.write("Use the navigation menu to switch between:")
st.markdown("""
- **Table Manager** – View tables and add records  
- **Suppliers Feedback** – Search feedback by supplier name  
- **Main Travel** – Search for Partners  
""")