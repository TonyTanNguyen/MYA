import streamlit as st
import sqlite3
import pandas as pd
from utils import DB_FILE, quote_ident, init_session_state, require_login, show_logo

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
require_login()

st.title("✈️ Main Travel Database")
show_logo()
table_name = "Main Travel Database"
conn = sqlite3.connect(DB_FILE)

try:
    df_main = pd.read_sql(f"SELECT * FROM {quote_ident(table_name)}", conn)

    if "Partner Name" not in df_main.columns:
        st.error(f"Column 'Partner Name' not found in table '{table_name}'.")
    else:
        # Search functionality
        st.subheader("🔍 Search Partners")
        
        # Filters for Country, Location, and Status
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Country filter
            if "Country" in df_main.columns:
                countries = ["All Countries"] + sorted(df_main["Country"].dropna().unique().tolist())
                selected_country = st.selectbox("Filter by Country:", countries, key="country_filter")
            else:
                selected_country = "All Countries"
        
        with col2:
            # Location filter
            if "Location" in df_main.columns:
                # Filter locations based on selected country
                if selected_country != "All Countries":
                    country_locations = df_main[df_main["Country"] == selected_country]["Location"].dropna().unique()
                    locations = ["All Locations"] + sorted(country_locations.tolist())
                else:
                    locations = ["All Locations"] + sorted(df_main["Location"].dropna().unique().tolist())
                
                selected_location = st.selectbox("Filter by Location:", locations, key="location_filter")
            else:
                selected_location = "All Locations"
        
        with col3:
            # Status filter
            if "Status" in df_main.columns:
                statuses = ["All Statuses"] + sorted(df_main["Status"].dropna().unique().tolist())
                selected_status = st.selectbox("Filter by Status:", statuses, key="status_filter")
            else:
                selected_status = "All Statuses"
        
        st.markdown("---")
        
        # Search box
        search_keyword = st.text_input(
            "Enter keyword to search in Partner Name, Description, or Location:",
            placeholder="e.g., Hotel ABC, Beach, Luxury...",
            key="partner_search"
        )
        
        if search_keyword or selected_country != "All Countries" or selected_location != "All Locations" or selected_status != "All Statuses":
            # Apply filters
            df_filtered = df_main.copy()
            
            # Apply country filter
            if selected_country != "All Countries":
                df_filtered = df_filtered[df_filtered["Country"] == selected_country].reset_index(drop=True)
            
            # Apply location filter
            if selected_location != "All Locations":
                df_filtered = df_filtered[df_filtered["Location"] == selected_location].reset_index(drop=True)
            
            # Apply status filter
            if selected_status != "All Statuses":
                df_filtered = df_filtered[df_filtered["Status"] == selected_status].reset_index(drop=True)
            
            # Apply search keyword filter
            if search_keyword:
                # Search across multiple columns
                search_columns = ["Partner Name", "Description", "Location"]
                available_columns = [col for col in search_columns if col in df_filtered.columns]
                
                if available_columns:
                    # Create search mask across all available columns
                    search_mask = pd.Series([False] * len(df_filtered), index=df_filtered.index)
                    for col in available_columns:
                        col_mask = df_filtered[col].astype(str).str.contains(
                            search_keyword, 
                            case=False, 
                            na=False
                        )
                        search_mask |= col_mask
                    
                    df_filtered = df_filtered[search_mask].reset_index(drop=True)
                else:
                    # Fallback to Partner Name only if other columns don't exist
                    mask = df_filtered["Partner Name"].astype(str).str.contains(
                        search_keyword, 
                        case=False, 
                        na=False
                    )
                    df_filtered = df_filtered[mask].reset_index(drop=True)
            
            if not df_filtered.empty:
                # Show search results summary in one line
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Matches", len(df_filtered))
                with col2:
                    unique_partners = df_filtered["Partner Name"].nunique()
                    st.metric("Unique Partners", unique_partners)
                with col3:
                    # Count active filters
                    active_filters = []
                    if selected_country != "All Countries":
                        active_filters.append(f"Country: {selected_country}")
                    if selected_location != "All Locations":
                        active_filters.append(f"Location: {selected_location}")
                    if selected_status != "All Statuses":
                        active_filters.append(f"Status: {selected_status}")
                    if search_keyword:
                        active_filters.append(f"Search: {search_keyword}")
                    
                    st.metric("Active Filters", len(active_filters))
                with col4:
                    # Show filter summary
                    if active_filters:
                        filter_summary = " | ".join(active_filters)
                        st.caption(f"**Filters:** {filter_summary}")
                    else:
                        st.caption("**No filters applied**")
                
                st.markdown("---")
                # Create a descriptive results header
                if search_keyword:
                    st.subheader(f"🔍 Results for: '{search_keyword}'")
                else:
                    st.subheader("🔍 Filtered Results")
                
                # Show filter summary
                if active_filters:
                    filter_summary = " | ".join(active_filters)
                    st.caption(f"**Filters applied:** {filter_summary}")
                
                # Display filtered results
                for idx, row in df_filtered.iterrows():
                    partner_name = row.get("Partner Name", "Unknown Partner")
                    
                    with st.container():
                        # Get status for display in title
                        status = row.get("Status", "No status")
                        status_display = f" - {status}" if status and status != "No status" else ""
                        
                        with st.expander(f"📋 {partner_name}{status_display}", expanded=False):
                            # Row 1: Country, Location, Address
                            r1c1, r1c2, r1c3 = st.columns(3)
                            with r1c1:
                                st.markdown("**Country:**")
                                country = row.get("Country", "No country specified")
                                st.info(country)
                            with r1c2:
                                st.markdown("**Location:**")
                                location = row.get("Location", "No location specified")
                                st.success(location)
                            with r1c3:
                                st.markdown("**Address:**")
                                address = row.get("Address", "No address specified")
                                st.success(address)

                            # Row 2: Standard Type, Contact Person, Status
                            r2c1, r2c2, r2c3 = st.columns(3)
                            with r2c1:
                                st.markdown("**Standard Type:**")
                                standard_type = row.get("Standard_Type", "No standard type specified")
                                st.success(standard_type)
                            with r2c2:
                                st.markdown("**Contact Person:**")
                                contact_person = row.get("Contact Person", "No contact person specified")
                                st.info(contact_person)
                            with r2c3:
                                st.markdown("**Status:**")
                                status = row.get("Status", "No status specified")
                                st.info(status)

                            # Row 3: Full width Description
                            st.markdown("**Description:**")
                            description = row.get("Description", "No description available")
                            st.info(description)

                            # Show full partner data in a simple container
                            st.markdown("---")
                            st.markdown("**📊 Full Partner Data**")
                            st.dataframe(pd.DataFrame([row]).T, use_container_width=True)
                            
                            # Show feedback for this partner
                            partner_id = row.get("Partner ID", None)
                            if partner_id:
                                try:
                                    # Connect to feedback database
                                    feedback_conn = sqlite3.connect(DB_FILE)
                                    feedback_df = pd.read_sql(f"SELECT * FROM {quote_ident('Feedback Database')}", feedback_conn)
                                    
                                    # Filter feedback by Partner ID
                                    partner_feedback = feedback_df[feedback_df["Partner ID"] == partner_id]
                                    
                                    if not partner_feedback.empty:
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
                                        
                                        # Sort the feedback
                                        partner_feedback = partner_feedback.copy()
                                        partner_feedback['priority'] = partner_feedback['Feedback Type'].apply(get_feedback_priority)
                                        partner_feedback = partner_feedback.sort_values('priority')
                                        
                                        # Count feedback by type
                                        good_count = len(partner_feedback[partner_feedback['priority'] == 1])
                                        neutral_count = len(partner_feedback[partner_feedback['priority'] == 2])
                                        bad_count = len(partner_feedback[partner_feedback['priority'] == 3])
                                        
                                        st.markdown("---")
                                        st.markdown(f"**💬 Feedback ({len(partner_feedback)} entries) - ✅ Good: {good_count} | 💡 Neutral: {neutral_count} | ❌ Bad: {bad_count}**")
                                        
                                        # Display each feedback entry in containers instead of expanders
                                        for feedback_idx, feedback_row in partner_feedback.iterrows():
                                            feedback_msg = feedback_row.get("Feedback Message", "No feedback message")
                                            feedback_type = feedback_row.get("Feedback Type", "No type specified")
                                            what_was_done = feedback_row.get("What was done?", "No action taken")
                                            
                                            with st.container(border=True):
                                                # Feedback type badge with better styling
                                                if "positive" in str(feedback_type).lower() or "good" in str(feedback_type).lower() or "excellent" in str(feedback_type).lower():
                                                    st.markdown(f"<div style='background-color: #d4edda; color: #155724; padding: 8px 12px; border-radius: 6px; border: 1px solid #c3e6cb; font-weight: bold;'>✅ {feedback_type}</div>", unsafe_allow_html=True)
                                                elif "negative" in str(feedback_type).lower() or "bad" in str(feedback_type).lower() or "poor" in str(feedback_type).lower() or "complaint" in str(feedback_type).lower():
                                                    st.markdown(f"<div style='background-color: #f8d7da; color: #721c24; padding: 8px 12px; border-radius: 6px; border: 1px solid #f5c6cb; font-weight: bold;'>❌ {feedback_type}</div>", unsafe_allow_html=True)
                                                elif "neutral" in str(feedback_type).lower() or "suggestion" in str(feedback_type).lower() or "improvement" in str(feedback_type).lower():
                                                    st.markdown(f"<div style='background-color: #fff3cd; color: #856404; padding: 8px 12px; border-radius: 6px; border: 1px solid #ffeaa7; font-weight: bold;'>💡 {feedback_type}</div>", unsafe_allow_html=True)
                                                else:
                                                    st.markdown(f"<div style='background-color: #e2e3e5; color: #383d41; padding: 8px 12px; border-radius: 6px; border: 1px solid #d6d8db; font-weight: bold;'>📝 {feedback_type}</div>", unsafe_allow_html=True)
                                                
                                                st.markdown("")
                                                
                                                # Feedback message
                                                st.info(feedback_msg)
                                                
                                                # Action taken
                                                st.markdown("**✅ Action Taken:**")
                                                st.success(what_was_done)
                                        
                                        feedback_conn.close()
                                    else:
                                        st.info("💬 No feedback found for this partner")
                                        
                                except Exception as e:
                                    st.warning(f"⚠️ Could not load feedback data: {e}")
                            else:
                                st.info("💬 Partner ID not available - cannot search for feedback")
                
            else:
                st.warning(f"No partners found matching the applied filters")
                st.info("Try adjusting your filters or search criteria")
        
        else:
            # Show initial instructions
            st.info("👆 Use the filters above to search for partners by country, location, or partner name")
            
            # Show some statistics about the database
            with st.container(border=True):
                st.markdown("**📊 Database Overview**")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Records", len(df_main))
                with col2:
                    unique_partners = df_main["Partner Name"].nunique()
                    st.metric("Unique Partners", unique_partners)
                with col3:
                    if "Partner Type" in df_main.columns:
                        partner_types = df_main["Partner Type"].nunique()
                        st.metric("Partner Types", partner_types)
                    else:
                        st.metric("Columns", len(df_main.columns))

except Exception as e:
    st.error(f"Error loading main travel database: {e}")
finally:
    conn.close()
