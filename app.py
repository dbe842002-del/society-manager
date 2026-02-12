import streamlit as st
import pandas as pd
from datetime import datetime

# --- 1. CONFIGURATION ---
try:
    ADMIN_PASSWORD = st.secrets["admin_password"]
    SHEET_URL = st.secrets["sheet_url"]
except Exception:
    st.error("Missing Secrets: Please check admin_password and sheet_url in Streamlit Settings.")
    st.stop()

st.set_page_config(page_title="DBE Society Management", layout="wide")

# --- 2. THE ULTIMATE LOAD DATA FUNCTION ---
def load_data(worksheet_name):
    try:
        # Step A: Clean the URL (Removing /edit and everything after)
        base_url = SHEET_URL.split("/edit")[0]
        # Step B: Construct a direct export URL for the specific tab
        # This bypasses the gsheets library's internal bugs
        csv_url = f"{base_url}/export?format=csv&sheet={worksheet_name}"
        
        df = pd.read_csv(csv_url)
        return df
    except Exception as e:
        st.error(f"⚠️ Connection Error for '{worksheet_name}': {e}")
        return pd.DataFrame()

# --- 3. AUTHENTICATION ---
st.sidebar.title("🔐 Admin Portal")
pwd = st.sidebar.text_input("Password", type="password")
is_admin = (pwd == ADMIN_PASSWORD)

if is_admin:
    st.sidebar.success("Logged in as Admin")
elif pwd:
    st.sidebar.error("Incorrect Password")

# --- 4. MAIN INTERFACE ---
st.title("🏢 DBE Society Management")

tab1, tab2, tab3 = st.tabs(["💰 Maintenance", "💸 Expenses", "📊 Logs & Audit"])

with tab1:
    df_owners = load_data("Owners")
    df_coll = load_data("Collections")
    
    if not df_owners.empty:
        # --- 1. THE MATH ENGINE ---
        today = datetime.now()
        # Calculates months since Jan 2025 (e.g., Feb 2026 = 14 months)
        total_months_since_2025 = (today.year - 2025) * 12 + today.month
        
        # Calculate total paid per flat from the Collections sheet
        if not df_coll.empty and "Flat" in df_coll.columns:
            payments_sum = df_coll.groupby("Flat")["Amount"].sum()
        else:
            payments_sum = pd.Series(dtype=float)

        # --- 2. APPLY FORMULA TO EACH ROW ---
        def calculate_balance(row):
            opening_due = row.get("due", 0)
            # Your Formula: Expected = Opening + (Months * 2100)
            expected_amount = opening_due + (total_months_since_2025 * MONTHLY_MAINT)
            
            # Subtract what they have actually paid
            total_paid = payments_sum.get(row["flat"], 0)
            return expected_amount - total_paid

        # Create the dynamic column
        df_owners["Total_Outstanding"] = df_owners.apply(calculate_balance, axis=1)

        # --- 3. DISPLAY ---
        if is_admin:
            st.subheader("📝 Record New Payment")
            # ... (Your existing Selectbox and Save Payment button code goes here) ...
            
            st.divider()
            st.subheader("📊 Live Financial Status")
            # Show the breakdown for Admin
            display_cols = ["flat", "owner", "due", "Total_Outstanding"]
            st.dataframe(df_owners[display_cols], width="stretch")
        else:
            st.subheader("🏢 Society Dues List")
            # Show simplified view for residents
            st.dataframe(df_owners[["flat", "owner", "Total_Outstanding"]], width="stretch")

with tab3:
    st.subheader("📋 Master Records")
    view_choice = st.radio("Select Sheet", ["Owners", "Expenses", "Collections"], horizontal=True)
    df_view = load_data(view_choice)
    # Fixed the 'use_container_width' warning here too
    st.dataframe(df_view, width="stretch")




