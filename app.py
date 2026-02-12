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
        # --- 1. SETUP VARIABLES ---
        today = datetime.now()
        MONTHLY_MAINT = 2100
        total_months_due = (today.year - 2025) * 12 + today.month

        # --- 2. SUM PAYMENTS ---
        # We create the dictionary BEFORE the function uses it
        payments_dict = {}
        if not df_coll.empty:
            # Ensure column names match your sheet (Capital 'Flat' and 'Amount')
            if "Flat" in df_coll.columns and "Amount" in df_coll.columns:
                df_coll["Amount"] = pd.to_numeric(df_coll["Amount"], errors='coerce').fillna(0)
                payments_dict = df_coll.groupby("Flat")["Amount"].sum().to_dict()

        # --- 3. DEFINE THE FUNCTION ---
        # This MUST be defined before the .apply() line below
        def calculate_balance(row):
            # Safe conversion of 'due' column
            opening_due = pd.to_numeric(row.get("due", 0), errors='coerce')
            if pd.isna(opening_due): 
                opening_due = 0
            
            expected = opening_due + (total_months_due * MONTHLY_MAINT)
            # Match 'flat' from Owners to 'Flat' in Collections
            paid = payments_dict.get(row["flat"], 0)
            return expected - paid

        # --- 4. APPLY THE FUNCTION ---
        df_owners["Total_Outstanding"] = df_owners.apply(calculate_balance, axis=1)

        # --- 5. DISPLAY ---
        st.subheader("📊 Society Financial Status")
        
        # Admin View vs Resident View
        if is_admin:
            st.dataframe(df_owners[["flat", "owner", "due", "Total_Outstanding"]], width="stretch")
            st.divider()
            st.subheader("📝 Record New Payment")
            
            # Form for adding payments
            col1, col2 = st.columns(2)
            with col1:
                flat_selection = st.selectbox("Select Flat", df_owners["flat"].tolist())
                amt_input = st.number_input("Amount", value=2100)
            with col2:
                mode = st.selectbox("Mode", ["Online", "Cash", "Cheque"])
                if st.button("Save Payment", type="primary"):
                    st.info("Saving...") # Add your update_db logic here
        else:
            st.dataframe(df_owners[["flat", "owner", "Total_Outstanding"]], width="stretch")
            
    else:
        st.error("Owners data is empty. Check your Google Sheet tab named 'Owners'.")

with tab3:
    st.subheader("📋 Master Records")
    view_choice = st.radio("Select Sheet", ["Owners", "Expenses", "Collections"], horizontal=True)
    df_view = load_data(view_choice)
    # Fixed the 'use_container_width' warning here too
    st.dataframe(df_view, width="stretch")





