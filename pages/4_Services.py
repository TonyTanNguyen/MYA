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

st.title("🛎️ Services")
show_logo()
services_table = "Service Database"
main_table = "Main Travel Database"

conn = sqlite3.connect(DB_FILE)

try:
    # Load base tables
    df_services = pd.read_sql(f"SELECT * FROM {quote_ident(services_table)}", conn)
    df_main = pd.read_sql(f"SELECT * FROM {quote_ident(main_table)}", conn)

    # Ensure consistent key columns exist
    partner_id_col = "Partner ID"
    partner_name_col = "Partner Name"

    # Trim whitespace in join keys to avoid mismatches
    if partner_id_col in df_services.columns:
        df_services[partner_id_col] = df_services[partner_id_col].astype(str).str.strip()
    if partner_name_col in df_services.columns:
        df_services[partner_name_col] = df_services[partner_name_col].astype(str).str.strip()
    if partner_id_col in df_main.columns:
        df_main[partner_id_col] = df_main[partner_id_col].astype(str).str.strip()
    if partner_name_col in df_main.columns:
        df_main[partner_name_col] = df_main[partner_name_col].astype(str).str.strip()

    # Prepare slim lookup from main table
    main_lookup_cols = []
    for col in [partner_id_col, partner_name_col, "Country", "Location"]:
        if col in df_main.columns:
            main_lookup_cols.append(col)

    df_main_lookup = df_main[main_lookup_cols].drop_duplicates()

    # First join on Partner ID
    merged = pd.merge(
        df_services,
        df_main_lookup,
        on=partner_id_col,
        how="left",
        suffixes=("", "_main_by_id"),
    ) if partner_id_col in df_services.columns and partner_id_col in df_main_lookup.columns else df_services.copy()

    # If Country/Location still missing, fallback join by Partner Name
    if "Country" not in merged.columns:
        merged["Country"] = None
    if "Location" not in merged.columns:
        merged["Location"] = None

    needs_name_backfill = merged["Country"].isna() | (merged["Location"].isna())
    if needs_name_backfill.any() and partner_name_col in df_services.columns and partner_name_col in df_main_lookup.columns:
        df_main_by_name = df_main_lookup[[c for c in [partner_name_col, "Country", "Location"] if c in df_main_lookup.columns]].drop_duplicates()
        merged = merged.merge(
            df_main_by_name,
            on=partner_name_col,
            how="left",
            suffixes=("", "_from_name"),
        )

        # Prefer values from ID-join; fill missing from name-join
        if "Country_from_name" in merged.columns:
            merged["Country"] = merged["Country"].fillna(merged["Country_from_name"])  # type: ignore
        if "Location_from_name" in merged.columns:
            merged["Location"] = merged["Location"].fillna(merged["Location_from_name"])  # type: ignore

        # Drop helper columns
        drop_cols = [c for c in ["Country_from_name", "Location_from_name"] if c in merged.columns]
        if drop_cols:
            merged = merged.drop(columns=drop_cols)

    df_enriched = merged

    # Filters
    st.subheader("🔎 Filter Services")
    col1, col2 = st.columns(2)

    with col1:
        if "Country" in df_enriched.columns:
            country_options = ["All Countries"] + sorted(df_enriched["Country"].dropna().astype(str).unique().tolist())
            selected_country = st.selectbox("Filter by Country:", country_options, key="services_country")
        else:
            selected_country = "All Countries"

    with col2:
        if "Location" in df_enriched.columns:
            if selected_country != "All Countries":
                locs = df_enriched[df_enriched["Country"] == selected_country]["Location"].dropna().astype(str).unique().tolist()
                location_options = ["All Locations"] + sorted(locs)
            else:
                location_options = ["All Locations"] + sorted(df_enriched["Location"].dropna().astype(str).unique().tolist())
            selected_location = st.selectbox("Filter by Location:", location_options, key="services_location")
        else:
            selected_location = "All Locations"

    # Partner name search
    search_name = st.text_input(
        "Search Partner Name:",
        placeholder="Type to search by partner name...",
        key="services_search_name"
    )

    # Apply filters
    df_filtered = df_enriched.copy()
    if selected_country != "All Countries" and "Country" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["Country"] == selected_country]
    if selected_location != "All Locations" and "Location" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["Location"] == selected_location]

    # Apply partner name search
    if partner_name_col in df_filtered.columns and search_name:
        df_filtered = df_filtered[df_filtered[partner_name_col].astype(str).str.contains(search_name, case=False, na=False)]

    # Remove rows with null/empty Partner Name
    if partner_name_col in df_filtered.columns:
        df_filtered = df_filtered[df_filtered[partner_name_col].notna()]
        # Normalize and drop empty after trimming
        df_filtered[partner_name_col] = df_filtered[partner_name_col].astype(str).str.strip()
        df_filtered = df_filtered[df_filtered[partner_name_col] != ""]

    st.markdown("---")
    st.subheader("📋 Services")

    if df_filtered.empty:
        st.info("No services found for the selected filters.")
    else:
        # Group by partner (prefer Partner ID if present to avoid name collisions)
        group_cols = [c for c in [partner_id_col] if c in df_filtered.columns]
        if not group_cols:
            group_cols = [c for c in [partner_name_col] if c in df_filtered.columns]

        display_cols = [
            c for c in [
                "Type of service",
                "Details",
                "Date Quotation",
                "Price quoted",
                "Date of Service",
                "Price final",
            ] if c in df_filtered.columns
        ]

        # Try to sort within partner by Date of Service then Date Quotation (if present)
        def _coerce_dt(series: pd.Series) -> pd.Series:
            try:
                return pd.to_datetime(series, errors="coerce")
            except Exception:
                return series

        if "Date of Service" in df_filtered.columns:
            df_filtered["__dos"] = _coerce_dt(df_filtered["Date of Service"])  # type: ignore
        if "Date Quotation" in df_filtered.columns:
            df_filtered["__dq"] = _coerce_dt(df_filtered["Date Quotation"])  # type: ignore

        for _, grp in df_filtered.groupby(group_cols, dropna=False):
            partner_name = grp.get("Partner Name", pd.Series(["Unknown Partner"]))
            partner_name = str(partner_name.iloc[0]) if len(partner_name) > 0 else "Unknown Partner"
            country = str(grp.get("Country", pd.Series([""])).iloc[0]) if "Country" in grp.columns else ""
            location = str(grp.get("Location", pd.Series([""])).iloc[0]) if "Location" in grp.columns else ""

            # Sort rows inside group (most recent first when dates exist)
            if "__dos" in grp.columns or "__dq" in grp.columns:
                sort_cols = [c for c in ["__dos", "__dq"] if c in grp.columns]
                grp = grp.sort_values(sort_cols, ascending=False)

            with st.container(border=True):
                header_bits = [b for b in [partner_name, country, location] if b]
                header_text = " • ".join([str(b) for b in header_bits]) if header_bits else "Service"
                st.markdown(f"**{header_text}**")

                table = grp[display_cols].reset_index(drop=True)
                st.dataframe(table, use_container_width=True)

        # Cleanup temporary columns if they were added
        drop_tmp = [c for c in ["__dos", "__dq"] if c in df_filtered.columns]
        if drop_tmp:
            df_filtered = df_filtered.drop(columns=drop_tmp)

except Exception as e:
    st.error(f"Error loading services: {e}")
finally:
    conn.close()


