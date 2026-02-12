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
        # 1. Standardize Names (Force lowercase for Owners, Strip spaces)
        df_owners.columns = df_owners.columns.str.strip().str.lower()
        
        # 2. Setup Constants
        today = datetime.now()
        MONTHLY_MAINT = 2100
        # Formula: Jan 2025 to Feb 2026 = 14 months
        total_months_due = (today.year - 2025) * 12 + today.month

        # 3. Sum Payments from Collections
        payments_dict = {}
        if not df_coll.empty:
            df_coll.columns = df_coll.columns.str.strip() # Don't lowercase Collections yet
            if "Flat" in df_coll.columns and "Amount" in df_coll.columns:
                df_coll["Amount"] = pd.to_numeric(df_coll["Amount"], errors='coerce').fillna(0)
                # Key: UpperCase + No Spaces
                df_coll["Flat_Match"] = df_coll["Flat"].astype(str).str.strip().str.upper()
                payments_dict = df_coll.groupby("Flat_Match")["Amount"].sum().to_dict()

        # 4. Detailed Calculation
        def get_details(row):
            f_id = str(row.get("flat", "")).strip().upper()
            opening = pd.to_numeric(row.get("due", 0), errors='coerce') or 0
            
            # The Math
            expected_total = opening + (total_months_due * MONTHLY_MAINT)
            paid = payments_dict.get(f_id, 0)
            balance = expected_total - paid
            
            return pd.Series([opening, total_months_due, expected_total, paid, balance])

        # Create the breakdown columns
        df_owners[['Sheet_Due', 'Months_Count', 'Expected_Total', 'Total_Paid', 'Final_Balance']] = df_owners.apply(get_details, axis=1)

        # 5. The Display
        st.subheader("📊 Live Calculation Breakdown")
        st.write(f"**Current Calculation Date:** {today.strftime('%B %Y')} ({total_months_due} months since Jan 2025)")
        
        # We show exactly how the app arrived at the result
        debug_cols = ["flat", "owner", "Sheet_Due", "Expected_Total", "Total_Paid", "Final_Balance"]
        st.dataframe(df_owners[debug_cols], width="stretch")

        # --- TROUBLESHOOTING HELP ---
        with st.expander("🛠️ Why is the math wrong? Click to check"):
            st.write("### 1. Check for Name Mismatches")
            st.write("Names found in Collections (Payments):", list(payments_dict.keys()))
            st.write("Names found in Owners:", df_owners["flat"].astype(str).str.strip().str.upper().tolist())
            
            st.write("### 2. Check Your Formula")
            st.write(f"The app is adding {total_months_due} months of maintenance (Rs. {total_months_due * MONTHLY_MAINT}) to your 2025 Opening Due.")
            st.write("If the 'Expected_Total' is too high, we need to subtract months from the `total_months_due` variable.")

    else:
        st.error("Could not load Owners sheet.")
        
with tab3:
    st.subheader("📋 Master Records")
    view_choice = st.radio("Select Sheet", ["Owners", "Expenses", "Collections"], horizontal=True)
    df_view = load_data(view_choice)
    # Fixed the 'use_container_width' warning here too
    st.dataframe(df_view, width="stretch")








