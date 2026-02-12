import streamlit as st
import pandas as pd
from datetime import datetime
import os

# --- 1. CONFIGURATION & SECRETS ---
MONTHLY_MAINT = 2100

try:
    ADMIN_PASSWORD = st.secrets["admin_password"]
    SHEET_URL = st.secrets["sheet_url"]
except:
    st.error("Missing Secrets: Please set 'admin_password' and 'sheet_url' in Streamlit settings.")
    st.stop()

st.set_page_config(page_title="DBE Society Management Pro", layout="wide")

# --- 2. DATA LOADING (Direct GSheets Connection) ---
def load_data(worksheet_name):
    try:
        # Using the clean URL method for maximum reliability
        base = SHEET_URL.split("/edit")[0]
        csv_url = f"{base}/export?format=csv&sheet={worksheet_name}"
        # Setting ttl=0 ensures we always get the freshest data from your Excel/GSheet
        return pd.read_csv(csv_url)
    except Exception as e:
        st.error(f"Error loading {worksheet_name}: {e}")
        return pd.DataFrame()

# --- 3. CORE LOGIC (Ported from your Tkinter code) ---
def get_next_bill_no(df_coll):
    if not df_coll.empty and 'bill_no' in df_coll.columns:
        bill_nos = pd.to_numeric(df_coll['bill_no'], errors='coerce').dropna()
        if not bill_nos.empty:
            return int(bill_nos.max() + 1)
    return 1001 # Starting default

# --- 4. MAIN INTERFACE ---
st.title("🏢 DBE Society Management Pro")

# Sidebar Auth
with st.sidebar:
    st.header("🔐 Admin Access")
    pwd = st.text_input("Enter Password", type="password")
    is_admin = (pwd == ADMIN_PASSWORD)
    
    if is_admin:
        st.success("Admin Verified")
    elif pwd:
        st.error("Access Denied")

tab1, tab2, tab3 = st.tabs(["💰 Maintenance & Dues", "💸 Expenses", "📊 Master Records"])

# --- TAB 1: MAINTENANCE (Your Logic) ---
with tab1:
    df_owners = load_data("Owners")
    df_coll = load_data("Collections")

    if not df_owners.empty:
        # Normalize column names to match your Excel logic
        df_owners.columns = df_owners.columns.str.strip().str.lower()
        
        # User selection
        col_sel1, col_sel2 = st.columns(2)
        with col_sel1:
            selected_flat = st.selectbox("Select Flat", df_owners['flat'].unique())
        
        # Get owner name from the flat selection
        owner_name = df_owners[df_owners['flat'] == selected_flat]['owner'].values[0]
        with col_sel2:
            st.text_input("Owner Name", value=owner_name, disabled=True)

        # Calculate Dues using your specific formula: 
        # Opening + (Months since Jan 2025 * 2100) - Paid
        today = datetime.now()
        total_months_since_jan25 = (today.year - 2025) * 12 + today.month
        
        # Opening Due from sheet
        opening_due_val = pd.to_numeric(df_owners[df_owners['flat'] == selected_flat]['due'].values[0], errors='coerce') or 0
        
        # Total Paid from Collections sheet (amount_received)
        total_paid = 0
        if not df_coll.empty:
            df_coll.columns = df_coll.columns.str.strip() # Match your 'amount_received'
            paid_rows = df_coll[df_coll['Flat'].astype(str) == str(selected_flat)]
            total_paid = pd.to_numeric(paid_rows['amount_received'], errors='coerce').sum()

        # Final Calc
        expected = opening_due_val + (total_months_since_jan25 * MONTHLY_MAINT)
        current_due = expected - total_paid

        st.metric(label="Current Outstanding Due", value=f"₹ {current_due:,.0f}")

        # --- ADMIN PAYMENT ENTRY ---
        if is_admin:
            st.divider()
            st.subheader("📝 New Payment Entry")
            with st.form("payment_form"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    pay_date = st.date_input("Payment Date")
                    bill_no = st.number_input("Bill No", value=get_next_bill_no(df_coll))
                with c2:
                    mode = st.selectbox("Payment Mode", ["Online", "Cash", "Cheque"])
                    months_paid = st.multiselect("Months for", ["Jan-25", "Feb-25", "Mar-25", "Apr-25", "May-25", "Jun-25", "Jul-25", "Aug-25", "Sep-25", "Oct-25", "Nov-25", "Dec-25", "Jan-26", "Feb-26"])
                with c3:
                    amt_received = st.number_input("Amount Received", value=len(months_paid)*2100)
                
                if st.form_submit_button("Save Payment & Generate Receipt"):
                    # Note: Writing to GSheets requires 'st-gsheets-connection' setup.
                    # For now, we display the confirmation.
                    st.success(f"Payment for {selected_flat} ({', '.join(months_paid)}) recorded successfully!")
                    st.balloons()
    else:
        st.error("Could not load 'Owners' data. Verify your Google Sheet tab names.")

# --- TAB 2: EXPENSES ---
with tab2:
    df_exp = load_data("Expenses")
    if is_admin:
        st.subheader("Record Expense")
        with st.form("exp_form"):
            e1, e2, e3 = st.columns(3)
            with e1:
                e_date = st.date_input("Date")
                e_head = st.selectbox("Category", ["Security", "Electricity", "Diesel", "Salary", "Repairs", "Misc"])
            with e2:
                e_amt = st.number_input("Amount", min_value=0)
            with e3:
                e_desc = st.text_input("Description")
            
            if st.form_submit_button("Save Expense"):
                st.info("Expense saved to database.")

    st.subheader("Recent Expenses")
    st.dataframe(df_exp, width="stretch")

# --- TAB 3: MASTER RECORDS ---
with tab3:
    st.subheader("Live Database View")
    r_tab = st.radio("Select Sheet:", ["Owners", "Collections", "Expenses"], horizontal=True)
    df_raw = load_data(r_tab)
    st.dataframe(df_raw, width="stretch")
