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
        # --- 1. CLEAN COLUMN NAMES (Removes accidental spaces/caps) ---
        df_owners.columns = df_owners.columns.str.strip().str.lower()
        if not df_coll.empty:
            df_coll.columns = df_coll.columns.str.strip() # Collections usually uses caps

        # --- 2. DYNAMIC MATH SETUP ---
        today = datetime.now()
        MONTHLY_MAINT = 2100
        # Months since Jan 1st, 2025
        total_months_due = (today.year - 2025) * 12 + today.month

        # --- 3. LINK COLLECTIONS ---
        payments_dict = {}
        if not df_coll.empty and "Flat" in df_coll.columns and "Amount" in df_coll.columns:
            df_coll["Amount"] = pd.to_numeric(df_coll["Amount"], errors='coerce').fillna(0)
            df_coll["Flat_Key"] = df_coll["Flat"].astype(str).str.strip().str.upper()
            payments_dict = df_coll.groupby("Flat_Key")["Amount"].sum().to_dict()

        # --- 4. CALCULATE BALANCE ---
        def calculate_balance(row):
            # Use .get() to avoid KeyErrors if a column is missing
            flat_id = str(row.get("flat", "")).strip().upper()
            # Try 'due' or 'opening_due' or default to 0
            opening_due = pd.to_numeric(row.get("due", 0), errors='coerce')
            if pd.isna(opening_due): opening_due = 0
            
            expected = opening_due + (total_months_due * MONTHLY_MAINT)
            paid = payments_dict.get(flat_id, 0)
            return expected - paid

        # Apply calculations
        df_owners["total_paid"] = df_owners.apply(lambda r: payments_dict.get(str(r.get("flat", "")).strip().upper(), 0), axis=1)
        df_owners["total_outstanding"] = df_owners.apply(calculate_balance, axis=1)

        # --- 5. SAFE DISPLAY ---
        st.subheader("📊 Society Financial Summary")
        
        # We only show columns that actually exist to prevent the KeyError
        existing_cols = [c for c in ["flat", "owner", "due", "total_paid", "total_outstanding"] if c in df_owners.columns]
        st.dataframe(df_owners[existing_cols], width="stretch")

        if is_admin:
            st.divider()
            st.subheader("📝 Record New Payment")
            if "flat" in df_owners.columns:
                flat_selection = st.selectbox("Select Flat", df_owners["flat"].unique())
                if st.button("Save Record", type="primary"):
                    st.info("Recording functionality logic goes here.")
    else:
        st.error("The 'Owners' sheet is empty or could not be loaded.")
with tab3:
    st.subheader("📋 Master Records")
    view_choice = st.radio("Select Sheet", ["Owners", "Expenses", "Collections"], horizontal=True)
    df_view = load_data(view_choice)
    # Fixed the 'use_container_width' warning here too
    st.dataframe(df_view, width="stretch")







