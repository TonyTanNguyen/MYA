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
    # Clear any stored original dataframes when switching tables
    for key in list(st.session_state.keys()):
        if key.startswith("original_df_"):
            del st.session_state[key]

# --- Show table data ---
df = pd.read_sql(f"SELECT * FROM {quote_ident(selected_table)}", conn)
st.subheader(f"Data in “{selected_table}”")

# Store original dataframe in session state for reset functionality
original_df_key = f"original_df_{selected_table}"
if original_df_key not in st.session_state:
    st.session_state[original_df_key] = df.copy()

# Display editable dataframe
edited_df = st.data_editor(
    df,
    num_rows="dynamic",
    use_container_width=True,
    key=f"editor_{selected_table}"
)

# Check if data was modified
original_df = st.session_state[original_df_key]
if not original_df.equals(edited_df):
    # Count changes
    update_count = 0
    insert_count = 0
    
    # Count updates
    for index, row in edited_df.iterrows():
        if index < len(original_df):
            original_row = original_df.iloc[index]
            if not row.equals(original_row):
                update_count += 1
    
    # Count inserts
    if len(edited_df) > len(original_df):
        insert_count = len(edited_df) - len(original_df)
    
    # Show change summary
    change_summary = []
    if update_count > 0:
        change_summary.append(f"{update_count} row(s) to update")
    if insert_count > 0:
        change_summary.append(f"{insert_count} new row(s) to add")
    
    st.info(f"⚠️ Data has been modified: {', '.join(change_summary)}. Click 'Save Changes' to update the database.")
    
    # Save changes button
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("💾 Save Changes", type="primary"):
            try:
                cursor = conn.cursor()
                
                # Handle updates to existing rows
                for index, row in edited_df.iterrows():
                    if index < len(original_df):
                        # Check if this row was modified
                        original_row = original_df.iloc[index]
                        if not row.equals(original_row):
                            # Build UPDATE query
                            set_clause = ", ".join([
                                f"{quote_ident(col)} = ?" 
                                for col in edited_df.columns 
                                if col in df.columns
                            ])
                            
                            # Get primary key column
                            pk_info = get_table_columns(conn, selected_table)
                            pk_column = pk_info[pk_info['pk'] == 1]['name'].iloc[0] if any(pk_info['pk'] == 1) else edited_df.columns[0]
                            
                            # Build WHERE clause using primary key
                            where_clause = f"{quote_ident(pk_column)} = ?"
                            
                            # Prepare values for SET clause
                            set_values = [row[col] for col in edited_df.columns if col in df.columns]
                            
                            # Prepare value for WHERE clause
                            where_value = row[pk_column] if pk_column in row else row[edited_df.columns[0]]
                            
                            # Execute UPDATE
                            query = f"UPDATE {quote_ident(selected_table)} SET {set_clause} WHERE {where_clause}"
                            cursor.execute(query, set_values + [where_value])
                
                # Handle new rows (INSERT)
                if len(edited_df) > len(original_df):
                    # Get column information for INSERT
                    columns_info = get_table_columns(conn, selected_table)
                    pk_column = columns_info[columns_info['pk'] == 1]['name'].iloc[0] if any(columns_info['pk'] == 1) else None
                    
                    # Get new rows (rows beyond the original dataframe length)
                    new_rows = edited_df.iloc[len(original_df):]
                    
                    for _, row in new_rows.iterrows():
                        # Skip if primary key is None or empty
                        if pk_column and (pd.isna(row[pk_column]) or row[pk_column] == ""):
                            continue
                        
                        # Build INSERT query
                        columns = [col for col in edited_df.columns if col in df.columns]
                        placeholders = ", ".join(["?" for _ in columns])
                        columns_str = ", ".join([quote_ident(col) for col in columns])
                        
                        # Prepare values for INSERT
                        values = [row[col] for col in columns]
                        
                        # Execute INSERT
                        query = f"INSERT INTO {quote_ident(selected_table)} ({columns_str}) VALUES ({placeholders})"
                        cursor.execute(query, values)
                
                # Commit changes
                conn.commit()
                st.success("✅ Changes saved successfully!")
                
                # Update the original dataframe in session state to reflect the new state
                st.session_state[original_df_key] = edited_df.copy()
                
                # Refresh the dataframe
                df = pd.read_sql(f"SELECT * FROM {quote_ident(selected_table)}", conn)
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Error saving changes: {e}")
                conn.rollback()
    
    with col2:
        if st.button("🗑️ Discard Changes"):
            # Reset the data editor to original state
            editor_key = f"editor_{selected_table}"
            if editor_key in st.session_state:
                del st.session_state[editor_key]
            
            # Reset the original dataframe to current database state
            st.session_state[original_df_key] = df.copy()
            
            st.info("🔄 Changes discarded. Data reset to original state.")
            st.rerun()
    
    # Show a diff view
    st.subheader("📊 Changes Preview")
    st.write("**Modified rows:**")
    
    # Find modified rows
    for index, row in edited_df.iterrows():
        if index < len(original_df):
            original_row = original_df.iloc[index]
            if not row.equals(original_row):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Row {index + 1} - Original:**")
                    st.dataframe(pd.DataFrame([original_row]).T, use_container_width=True)
                with col2:
                    st.write(f"**Row {index + 1} - Modified:**")
                    st.dataframe(pd.DataFrame([row]).T, use_container_width=True)
                st.markdown("---")

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
            # Refresh the dataframe after adding new record
            df = pd.read_sql(f"SELECT * FROM {quote_ident(selected_table)}", conn)
            st.rerun()
        except Exception as e:
            st.error(f"Error adding record: {e}")
else:
    st.info("You have viewer access. Only admins can add records.")

conn.close()