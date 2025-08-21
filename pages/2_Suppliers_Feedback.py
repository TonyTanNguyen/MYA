import streamlit as st
import sqlite3
import pandas as pd
from utils import DB_FILE, quote_ident, init_session_state, require_login

init_session_state()
require_login()

st.title("💬 Suppliers Feedback")

table_name = "Feedback Database"
conn = sqlite3.connect(DB_FILE)

def update_state():
    st.session_state.selected_supplier = st.session_state["supplier_selected"]

try:
    df_feedback = pd.read_sql(f"SELECT * FROM {quote_ident(table_name)}", conn)

    if "Partner Name" not in df_feedback.columns:
        st.error(f"Column 'Partner Name' not found in table '{table_name}'.")
    else:
        # Build stable options
        suppliers = (
            df_feedback["Partner Name"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )
        suppliers.sort()

        # Add filters for Partner Type, Country, and Region BEFORE supplier selection
        st.markdown("---")
        st.subheader("🔍 Filter Suppliers")
        
        # Connect to Main Travel Database to get partner details for filtering
        try:
            main_conn = sqlite3.connect(DB_FILE)
            df_main = pd.read_sql(f"SELECT * FROM {quote_ident('Main Travel Database')}", main_conn)
            
            # Partner Type filter
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if "Partner Type" in df_main.columns:
                    partner_types = ["All Types"] + sorted(df_main["Partner Type"].dropna().unique().tolist())
                    selected_partner_type = st.selectbox("Filter by Partner Type:", partner_types, key="partner_type_filter")
                else:
                    selected_partner_type = "All Types"
            
            with col2:
                if "Country" in df_main.columns:
                    countries = ["All Countries"] + sorted(df_main["Country"].dropna().unique().tolist())
                    selected_country = st.selectbox("Filter by Country:", countries, key="country_filter")
                else:
                    selected_country = "All Countries"
            
            with col3:
                if "Region" in df_main.columns:
                    # Filter regions based on selected country
                    if selected_country != "All Countries":
                        country_regions = df_main[df_main["Country"] == selected_country]["Region"].dropna().unique()
                        regions = ["All Regions"] + sorted(country_regions.tolist())
                    else:
                        regions = ["All Regions"] + sorted(df_main["Region"].dropna().unique().tolist())
                    
                    selected_region = st.selectbox("Filter by Region:", regions, key="region_filter")
                else:
                    selected_region = "All Regions"
            
            # Filter suppliers based on selected criteria
            if selected_partner_type != "All Types" or selected_country != "All Countries" or selected_region != "All Regions":
                # Create filter mask for Main Travel Database
                main_mask = pd.Series([True] * len(df_main))  # Start with all True
                
                if selected_partner_type != "All Types":
                    main_mask &= df_main["Partner Type"] == selected_partner_type
                
                if selected_country != "All Countries":
                    main_mask &= df_main["Country"] == selected_country
                
                if selected_region != "All Regions":
                    main_mask &= df_main["Region"] == selected_region
                
                # Get filtered partner names
                filtered_partners = df_main[main_mask]["Partner Name"].unique()
                
                # Filter suppliers to only show those that match the criteria AND have feedback
                suppliers = [s for s in suppliers if s in filtered_partners]
            
            main_conn.close()
            
        except Exception as e:
            st.warning(f"⚠️ Could not load partner details for filtering: {e}")
            selected_partner_type = "All Types"
            selected_country = "All Countries"
            selected_region = "All Regions"

        st.markdown("---")
        # st.subheader("👥 Select Supplier")
        
        # ✅ Compute default index from previous selection WITHOUT mutating session_state first
        prior = st.session_state.get("selected_supplier")
        default_index = suppliers.index(prior) if prior in suppliers and suppliers else 0

        # ✅ Render widget (no key, no mutation yet)
        supplier_selected = st.selectbox("Select Supplier", suppliers, index=default_index, key = "supplier_selected",on_change = update_state)

        # ✅ Save AFTER widget renders (prevents snap-back)
        if supplier_selected != prior:
            st.session_state.selected_supplier = supplier_selected

        # Show filtered data in Streamlit native format
        df_filtered = df_feedback[df_feedback["Partner Name"].astype(str) == supplier_selected]
        
        if not df_filtered.empty:
            # Get supplier details from Main Travel Database
            try:
                main_conn = sqlite3.connect(DB_FILE)
                df_main = pd.read_sql(f"SELECT * FROM {quote_ident('Main Travel Database')}", main_conn)
                
                # Get supplier details
                supplier_details = df_main[df_main["Partner Name"] == supplier_selected]
                
                if not supplier_details.empty:
                    # Display supplier information
                    with st.expander("🏢 Supplier Information", expanded=False):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown("**Standard Type:**")
                            standard_type = supplier_details.iloc[0].get("Standard_Type", "Not specified")
                            if standard_type is None:
                                standard_type = "Not specified"
                            st.info(standard_type)
                            
                            st.markdown("**Country:**")
                            country = supplier_details.iloc[0].get("Country", "Not specified")
                            if country is None:
                                country = "Not specified"
                            st.success(country)
                        
                        with col2:
                            st.markdown("**Location:**")
                            location = supplier_details.iloc[0].get("Location", "Not specified")
                            if location is None:
                                location = "Not specified"
                            st.success(location)
                            
                            st.markdown("**Description:**")
                            description = supplier_details.iloc[0].get("Description", "No description available")
                            # Handle None values and truncate description if too long
                            if description is None:
                                description = "No description available"
                            elif len(str(description)) > 100:
                                description = str(description)[:100] + "..."
                            st.info(description)
                    
                    main_conn.close()
                    
            except Exception as e:
                st.warning(f"⚠️ Could not load supplier details: {e}")
            
            # Sort feedback by priority: good first, then neutral, then bad
            def get_feedback_priority(feedback_type):
                feedback_lower = str(feedback_type).lower()
                if any(word in feedback_lower for word in ["positive", "good", "excellent", "great", "outstanding"]):
                    return 1  # Highest priority (good)
                elif any(word in feedback_lower for word in ["neutral", "suggestion", "improvement", "general"]):
                    return 2  # Medium priority (neutral)
                elif any(word in feedback_lower for word in ["negative", "bad", "poor", "complaint", "issue"]):
                    return 3  # Lowest priority (bad)
                else:
                    return 2  # Default to neutral priority
            
            # Sort the dataframe by priority
            df_filtered = df_filtered.copy()
            df_filtered['priority'] = df_filtered['Feedback Type'].apply(get_feedback_priority)
            df_filtered = df_filtered.sort_values('priority')
            
            # Show total count below dropdown in a nice container
            with st.container(border=True):
                # Create a nice summary section using Streamlit components
                st.markdown("**📊 Feedback Summary**")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Feedback", len(df_filtered))
                with col2:
                    # Count good feedback
                    good_count = len(df_filtered[df_filtered['priority'] == 1])
                    st.metric("✅ Good", good_count)
                with col3:
                    # Count neutral feedback
                    neutral_count = len(df_filtered[df_filtered['priority'] == 2])
                    st.metric("💡 Neutral", neutral_count)
                with col4:
                    # Count bad feedback
                    bad_count = len(df_filtered[df_filtered['priority'] == 3])
                    st.metric("❌ Bad", bad_count)
                
                # Show most common type below the metrics
                col1, col2 = st.columns(2)
                with col1:
                    type_counts = df_filtered["Feedback Type"].value_counts()
                    if not type_counts.empty:
                        st.metric("Most Common Type", type_counts.index[0])
                    else:
                        st.metric("Most Common Type", "N/A")
                with col2:
                    # Calculate percentage of good feedback
                    if len(df_filtered) > 0:
                        good_percentage = (good_count / len(df_filtered)) * 100
                        st.metric("Good Feedback %", f"{good_percentage:.1f}%")
                    else:
                        st.metric("Good Feedback %", "0%")
            
            # st.markdown("---")
            st.subheader(f"📋 Feedback for: {supplier_selected}")
            
            # Display each feedback entry using Streamlit components
            for idx, row in df_filtered.iterrows():
                # Get the relevant columns (adjust column names as needed)
                feedback_msg = row.get("Feedback Message", "No feedback message")
                feedback_type = row.get("Feedback Type", "No type specified")
                what_was_done = row.get("What was done?", "No action taken")
                
                # Create a container for each feedback entry with better visual separation
                with st.container():
                    # Use expander for better organization
                    # Truncate feedback message for title if too long
                    feedback_preview = feedback_msg[:50] + "..." if len(feedback_msg) > 50 else feedback_msg
                    
                    # Determine symbol for feedback type
                    if "positive" in feedback_type.lower() or "good" in feedback_type.lower() or "excellent" in feedback_type.lower():
                        feedback_symbol = "✅"
                    elif "negative" in feedback_type.lower() or "bad" in feedback_type.lower() or "poor" in feedback_type.lower() or "complaint" in feedback_type.lower():
                        feedback_symbol = "❌"
                    elif "neutral" in feedback_type.lower() or "suggestion" in feedback_type.lower() or "improvement" in feedback_type.lower():
                        feedback_symbol = "💡"
                    else:
                        feedback_symbol = "📝"
                    
                    with st.expander(f"{feedback_symbol} {feedback_type} | {feedback_preview}", expanded=False):
                        # Feedback type badge with better styling
                        if "positive" in feedback_type.lower() or "good" in feedback_type.lower() or "excellent" in feedback_type.lower():
                            st.markdown(f"<div style='background-color: #d4edda; color: #155724; padding: 8px 12px; border-radius: 6px; border: 1px solid #c3e6cb; font-weight: bold;'>✅ {feedback_type}</div>", unsafe_allow_html=True)
                        elif "negative" in feedback_type.lower() or "bad" in feedback_type.lower() or "poor" in feedback_type.lower() or "complaint" in feedback_type.lower():
                            st.markdown(f"<div style='background-color: #f8d7da; color: #721c24; padding: 8px 12px; border-radius: 6px; border: 1px solid #f5c6cb; font-weight: bold;'>❌ {feedback_type}</div>", unsafe_allow_html=True)
                        elif "neutral" in feedback_type.lower() or "suggestion" in feedback_type.lower() or "improvement" in feedback_type.lower():
                            st.markdown(f"<div style='background-color: #fff3cd; color: #856404; padding: 8px 12px; border-radius: 6px; border: 1px solid #ffeaa7; font-weight: bold;'>💡 {feedback_type}</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<div style='background-color: #e2e3e5; color: #383d41; padding: 8px 12px; border-radius: 6px; border: 1px solid #d6d8db; font-weight: bold;'>📝 {feedback_type}</div>", unsafe_allow_html=True)
                        
                        st.markdown("")
                        
                        # Feedback message
                        st.info(feedback_msg)
                        
                        # Action taken
                        st.markdown("**✅ Action Taken:**")
                        st.success(what_was_done)
                    
                    st.markdown("")
        else:
            st.info(f"No feedback found for {supplier_selected}")

except Exception as e:
    st.error(f"Error loading suppliers feedback: {e}")
finally:
    conn.close()

    