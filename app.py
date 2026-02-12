import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- 1. CONFIGURATION ---
MONTHLY_MAINT = 2100
st.set_page_config(page_title="DBE Society Management", layout="wide")

# --- 2. CONNECTION SETUP ---
# This uses the 'sheet_url' from your Secrets automatically
conn = st.connection("gsheets", type=GSheetsConnection)

def load_sheet(name):
    try:
        # Attempt 1: Standard library read
        df = conn.read(worksheet=name, ttl=0)
        return df
    except Exception:
        try:
            # Attempt 2: Fallback to the working CSV method
            base_url = st.secrets["connections"]["gsheets"]["spreadsheet"].split("/edit")[0]
            csv_url = f"{base_url}/export?format=csv&sheet={name}"
            return pd.read_csv(csv_url)
        except Exception as e:
            st.error(f"Error: {e}")
            return pd.DataFrame()

# --- 3. AUTHENTICATION ---
with st.sidebar:
    st.header("🔐 Admin Access")
    pwd = st.text_input("Password", type="password")
    is_admin = (pwd == st.secrets["admin_password"])

# --- 4. MAIN INTERFACE ---
st.title("🏢 DBE Society Management Pro")
tab1, tab2, tab3 = st.tabs(["💰 Maintenance", "💸 Expenses", "📊 Master Records"])

# --- TAB 1: MAINTENANCE & PAYMENTS ---
with tab1:
    df_owners = load_sheet("Owners")
    df_coll = load_sheet("Collections")

    if not df_owners.empty:
        # 1. Clean column names
        df_owners.columns = df_owners.columns.str.strip().str.lower()
        
        # 2. Selection UI
        selected_flat = st.selectbox("Select Flat", df_owners['flat'].unique())
        owner_row = df_owners[df_owners['flat'] == selected_flat].iloc[0]
        
        st.write(f"**Owner:** {owner_row.get('owner', 'N/A')}")

        # --- 3. SAFE CALCULATION ENGINE ---
        today = datetime.now()
        total_months = (today.year - 2025) * 12 + today.month
        
        # FIX: Find the 'due' column even if it's named 'due' or 'opening due'
        # We look for any column that contains the word 'due'
        due_col = next((c for c in df_owners.columns if 'due' in c), None)
        
        if due_col:
            opening_due = pd.to_numeric(owner_row[due_col], errors='coerce') or 0
        else:
            st.error("Column 'due' not found in Owners sheet!")
            opening_due = 0
        
        # Get Paid amount from Collections
        paid_amt = 0
        if not df_coll.empty:
            # Normalize Collections columns
            df_coll.columns = df_coll.columns.str.strip()
            # Find the 'Flat' and 'amount_received' columns regardless of case
            c_flat_col = next((c for c in df_coll.columns if c.lower() == 'flat'), 'Flat')
            c_amt_col = next((c for c in df_coll.columns if 'received' in c.lower()), 'amount_received')
            
            # Filter and Sum
            paid_rows = df_coll[df_coll[c_flat_col].astype(str).str.upper() == str(selected_flat).upper()]
            paid_amt = pd.to_numeric(paid_rows[c_amt_col], errors='coerce').sum()

        # Final Formula
        current_due = (opening_due + (total_months * MONTHLY_MAINT)) - paid_amt
        
        st.metric("Outstanding Balance", f"₹ {current_due:,.0f}")
        st.caption(f"Calculation: {opening_due} (Opening) + {total_months} months - {paid_amt} (Paid)")
                    

# --- TAB 2: EXPENSES ---
with tab2:
    df_exp = load_sheet("Expenses")
    if is_admin:
        with st.form("exp_form", clear_on_submit=True):
            st.subheader("Add Expense")
            e1, e2, e3 = st.columns(3)
            with e1:
                edate = st.date_input("Date")
                ehead = st.selectbox("Category", ["Security", "Electricity", "Diesel", "Salary", "Misc"])
            with e2:
                eamt = st.number_input("Amount", min_value=0)
            with e3:
                edesc = st.text_input("Description")
            
            if st.form_submit_button("Save Expense"):
                new_exp = pd.DataFrame([{
                    "date": edate.strftime("%d-%m-%Y"),
                    "head": ehead,
                    "description": edesc,
                    "amount": eamt,
                    "mode": "Cash"
                }])
                updated_exp = pd.concat([df_exp, new_exp], ignore_index=True)
                conn.update(worksheet="Expenses", data=updated_exp)
                st.success("Expense Saved!")
                st.rerun()
    st.dataframe(df_exp, width="stretch")

# --- TAB 3: RECORDS ---
with tab3:
    st.dataframe(load_sheet("Collections"), width="stretch")



