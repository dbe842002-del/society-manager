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
        # 1. Get current month number (Feb = 2)
        current_month_no = datetime.now().month
        
        # 2. Process Collections to get total paid per flat
        if not df_coll.empty and "Flat" in df_coll.columns:
            # Sum up all amounts paid by each flat
            payments_sum = df_coll.groupby("Flat")["Amount"].sum().reset_index()
        else:
            payments_sum = pd.DataFrame(columns=["Flat", "Amount"])

        # 3. Calculate Live Due for each owner
        def calculate_live_due(row):
            opening_due = row.get("due", 0)  # Value from your Google Sheet
            total_accrued = (2100 * 12) + (2100 * current_month_no)
            
            # Find how much this specific flat has paid
            paid_row = payments_sum[payments_sum["Flat"] == row["flat"]]
            total_paid = paid_row["Amount"].values[0] if not paid_row.empty else 0
            
            return (opening_due + total_accrued) - total_paid

        # Apply the formula
        df_owners["Current_Balance"] = df_owners.apply(calculate_live_due, axis=1)

        # 4. Display Logic
        if is_admin:
            st.subheader("📝 Record New Payment")
            # ... (keep your existing payment entry code here) ...
            
            st.divider()
            st.subheader("📊 Live Outstanding Summary")
            st.dataframe(df_owners[["flat", "owner", "due", "Current_Balance"]], width="stretch")
        else:
            st.subheader("🏢 Society Outstanding List")
            st.dataframe(df_owners[["flat", "owner", "Current_Balance"]], width="stretch")

with tab3:
    st.subheader("📋 Master Records")
    view_choice = st.radio("Select Sheet", ["Owners", "Expenses", "Collections"], horizontal=True)
    df_view = load_data(view_choice)
    # Fixed the 'use_container_width' warning here too
    st.dataframe(df_view, width="stretch")



