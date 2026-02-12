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
        # 1. Setup Variables
        today = datetime.now()
        MONTHLY_MAINT = 2100
        # Months since Jan 1st, 2025 (Feb 2026 = 14 months)
        total_months_due = (today.year - 2025) * 12 + today.month

        # 2. Process Collections (The "Paid" side)
        payments_dict = {}
        if not df_coll.empty:
            # Clean column names to handle spaces or hidden characters
            df_coll.columns = df_coll.columns.str.strip()
            
            # Use your specific column name: 'amount_received'
            # We also check for 'Flat' (adjust to 'flat' if it's lowercase in that sheet too)
            flat_col = "Flat" if "Flat" in df_coll.columns else "flat"
            
            if "amount_received" in df_coll.columns:
                # Convert to numeric, replace empty/text with 0
                df_coll["amount_received"] = pd.to_numeric(df_coll["amount_received"], errors='coerce').fillna(0)
                
                # Group payments by Flat
                # We normalize the flat name to UPPERCASE to ensure a perfect match
                df_coll["match_key"] = df_coll[flat_col].astype(str).str.strip().str.upper()
                payments_dict = df_coll.groupby("match_key")["amount_received"].sum().to_dict()

        # 3. Calculation Function for Owners
        def calculate_balance(row):
            # Normalize owner flat name
            f_id = str(row.get("flat", "")).strip().upper()
            
            # Get Opening Due (from your 'due' column)
            opening_due = pd.to_numeric(row.get("due", 0), errors='coerce')
            if pd.isna(opening_due): opening_due = 0
            
            # Expected = Opening + (Months * 2100)
            expected = opening_due + (total_months_due * MONTHLY_MAINT)
            
            # Get Paid amount from our dictionary
            paid = payments_dict.get(f_id, 0)
            
            return pd.Series([paid, expected - paid])

        # 4. Apply and Display
        # We ensure the Owners column names are clean
        df_owners.columns = df_owners.columns.str.strip().str.lower()
        
        # Apply the calculation
        df_owners[["Total_Paid", "Total_Outstanding"]] = df_owners.apply(calculate_balance, axis=1)

        st.subheader("📊 Society Financial Summary")
        st.write(f"**Period:** Jan 2025 to {today.strftime('%b %Y')} ({total_months_due} months)")
        
        # Display results
        view_cols = ["flat", "owner", "due", "Total_Paid", "Total_Outstanding"]
        # Filter to only show columns that actually exist
        final_cols = [c for c in view_cols if c in df_owners.columns]
        st.dataframe(df_owners[final_cols], width="stretch")

    else:
        st.error("Could not load Owners data. Please check your 'Owners' tab.")
        
with tab3:
    st.subheader("📋 Master Records")
    view_choice = st.radio("Select Sheet", ["Owners", "Expenses", "Collections"], horizontal=True)
    df_view = load_data(view_choice)
    # Fixed the 'use_container_width' warning here too
    st.dataframe(df_view, width="stretch")









