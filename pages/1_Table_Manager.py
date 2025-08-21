import streamlit as st
import sqlite3
import pandas as pd
from utils import DB_FILE, quote_ident, get_table_names, get_table_columns, insert_row, init_session_state, require_login, is_admin

init_session_state()
require_login()

st.title("📊 Table Viewer & Data Entry")

# --- Connect to DB ---
conn = sqlite3.connect(DB_FILE)

def update_table_state():
    st.session_state.selected_table = st.session_state["table_selected"]

# --- Sidebar: Table selection ---
all_tables = get_table_names(conn)
tables = [t for t in all_tables if t.lower() != "users"]

if not tables:
    st.warning("No tables found in the database.")
    conn.close()
    st.stop()

# Compute default index without mutating session_state before widget render
prior_table = st.session_state.get("selected_table")
default_index = tables.index(prior_table) if prior_table in tables else 0

selected_table = st.selectbox(
    "Select a table",
    tables,
    index=default_index,
    key="table_selected",
    on_change=update_table_state
)

# Keep persisted state updated after widget renders
if selected_table != prior_table:
    st.session_state.selected_table = selected_table

# --- Show table data ---
df = pd.read_sql(f"SELECT * FROM {quote_ident(selected_table)}", conn)
st.subheader(f"Data in “{selected_table}”")
st.dataframe(df)

if is_admin():
    # --- Data Entry Form ---
    st.subheader("Add New Record")
    columns_info = get_table_columns(conn, selected_table)

    form_data = {}
    with st.form("data_entry_form"):
        for _, row in columns_info.iterrows():
            col_name = row["name"]
            col_type = (row["type"] or "").upper()
            is_pk = row["pk"] == 1
            if is_pk:
                continue

            if any(date_word in col_name.lower() for date_word in ["date", "created", "updated", "time", "timestamp"]):
                if "TIME" in col_type or "TIMESTAMP" in col_type:
                    value = st.datetime_input(col_name)
                else:
                    value = st.date_input(col_name)
            elif "partner type" in col_name.lower() or "standard_type" in col_name.lower():
                try:
                    existing_values = df[col_name].dropna().unique()
                    if len(existing_values) > 0:
                        options = ["Select..."] + sorted(existing_values.tolist())
                        value = st.selectbox(col_name, options, index=0)
                        if value == "Select...":
                            value = None
                    else:
                        value = st.text_input(col_name)
                except:
                    value = st.text_input(col_name)
            elif "country" in col_name.lower():
                try:
                    existing_values = df[col_name].dropna().unique()
                    if len(existing_values) > 0:
                        options = ["Select..."] + sorted(existing_values.tolist())
                        value = st.selectbox(col_name, options, index=0)
                        if value == "Select...":
                            value = None
                    else:
                        value = st.text_input(col_name)
                except:
                    value = st.text_input(col_name)
            elif "region" in col_name.lower() or "location" in col_name.lower():
                try:
                    existing_values = df[col_name].dropna().unique()
                    if len(existing_values) > 0:
                        options = ["Select..."] + sorted(existing_values.tolist())
                        value = st.selectbox(col_name, options, index=0)
                        if value == "Select...":
                            value = None
                    else:
                        value = st.text_input(col_name)
                except:
                    value = st.text_input(col_name)
            elif "feedback type" in col_name.lower():
                feedback_options = ["Select...", "Good", "Neutral", "Bad"]
                value = st.selectbox(col_name, feedback_options, index=0)
                if value == "Select...":
                    value = None
            elif "priority" in col_name.lower() or "rating" in col_name.lower() or "score" in col_name.lower():
                if "INT" in col_type:
                    value = st.selectbox(col_name, ["Select...", 1, 2, 3, 4, 5], index=0)
                    if value == "Select...":
                        value = None
                else:
                    value = st.number_input(col_name, min_value=1, max_value=5, step=1)
            elif "INT" in col_type:
                value = st.number_input(col_name, step=1)
            elif any(t in col_type for t in ("REAL", "FLOAT", "DOUBLE", "NUM")):
                value = st.number_input(col_name, format="%.4f")
            elif "TEXT" in col_type and len(col_name) > 50:
                value = st.text_area(col_name, height=100)
            else:
                value = st.text_input(col_name)

            form_data[col_name] = value

        submitted = st.form_submit_button("Add Record")

    if submitted:
        try:
            cleaned = {
                k: (v if not (isinstance(v, str) and v == "") else None)
                for k, v in form_data.items()
            }
            insert_row(conn, selected_table, cleaned)
            st.success(f"Record added to “{selected_table}” successfully!")
            df = pd.read_sql(f"SELECT * FROM {quote_ident(selected_table)}", conn)
            st.dataframe(df)
        except Exception as e:
            st.error(f"Error adding record: {e}")
else:
    st.info("You have viewer access. Only admins can add records.")

conn.close()