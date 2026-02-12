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
        today = datetime.now()
        MONTHLY_MAINT = 2100
        total_months_due = (today.year - 2025) * 12 + today.month

        # --- 1. CLEAN COLLECTIONS DATA ---
        payments_dict = {}
        if not df_coll.empty:
            # Clean column names (remove any accidental spaces)
            df_coll.columns = df_coll.columns.str.strip()
            
            if "Flat" in df_coll.columns and "Amount" in df_coll.columns:
                # Convert Amount to numbers
                df_coll["Amount"] = pd.to_numeric(df_coll["Amount"], errors='coerce').fillna(0)
                
                # CRITICAL: Clean the 'Flat' names so they match Owners exactly
                # This turns " 101 " into "101" and "A-101" into "A-101"
                df_coll["Flat_Clean"] = df_coll["Flat"].astype(str).str.strip().str.upper()
                
                payments_dict = df_coll.groupby("Flat_Clean")["Amount"].sum().to_dict()

        # --- 2. CALCULATION FUNCTION ---
        def calculate_balance(row):
            # Clean the owner flat name to match the collection flat name
            flat_id = str(row.get("flat", "")).strip().upper()
            
            # Get Opening Due from 2025
            opening_due = pd.to_numeric(row.get("due", 0), errors='coerce')
            if pd.isna(opening_due): opening_due = 0
            
            # Expected = Opening + (Months * 2100)
            expected = opening_due + (total_months_due * MONTHLY_MAINT)
            
            # Total Paid (Linked via the cleaned Flat name)
            total_paid = payments_dict.get(flat_id, 0)
            
            return expected - total_paid

        # Apply
        df_owners["Total_Paid"] = df_owners.apply(lambda r: payments_dict.get(str(r["flat"]).strip().upper(), 0), axis=1)
        df_owners["Total_Outstanding"] = df_owners.apply(calculate_balance, axis=1)

        # --- 3. DISPLAY ---
        st.subheader("📊 Society Financial Summary")
        
        # Displaying 'Total Paid' helps you debug if the payment is being counted
        cols_to_show = ["flat", "owner", "due", "Total_Paid", "Total_Outstanding"]
        st.dataframe(df_owners[cols_to_show], width="stretch")

    else:
        st.error("No data in Owners sheet.")

with tab3:
    st.subheader("📋 Master Records")
    view_choice = st.radio("Select Sheet", ["Owners", "Expenses", "Collections"], horizontal=True)
    df_view = load_data(view_choice)
    # Fixed the 'use_container_width' warning here too
    st.dataframe(df_view, width="stretch")






