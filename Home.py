import streamlit as st
from utils import require_login, init_session_state

init_session_state()
user = require_login()

st.title("📌 Welcome to MYA App")
st.write("Use the navigation menu to switch between:")
st.markdown("""
- **Table Manager** – View tables and add records  
- **Suppliers Feedback** – Search feedback by supplier name  
- **Main Travel** – Search for Partners  
""")