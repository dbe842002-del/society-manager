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
        # Porting your Desktop Logic: Calc Dues
        col1, col2 = st.columns(2)
        with col1:
            # Clean column names for safety
            df_owners.columns = df_owners.columns.str.strip().str.lower()
            selected_flat = st.selectbox("Select Flat", df_owners['flat'].unique())
            owner_row = df_owners[df_owners['flat'] == selected_flat].iloc[0]
            st.write(f"**Owner:** {owner_row['owner']}")

        # Calculation Engine (From your Excel code)
        today = datetime.now()
        total_months = (today.year - 2025) * 12 + today.month
        opening_due = pd.to_numeric(owner_row['due'], errors='coerce') or 0
        
        # Get Paid from Collections
        paid_amt = 0
        if not df_coll.empty:
            df_coll.columns = df_coll.columns.str.strip()
            paid_amt = pd.to_numeric(df_coll[df_coll['Flat'].astype(str) == str(selected_flat)]['amount_received'], errors='coerce').sum()

        current_due = (opening_due + (total_months * MONTHLY_MAINT)) - paid_amt
        st.metric("Outstanding Balance", f"₹ {current_due:,.0f}")

        if is_admin:
            st.divider()
            st.subheader("📝 Record New Payment")
            with st.form("pay_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                with c1:
                    bill_date = st.date_input("Date", datetime.now())
                    # Get next bill number logic
                    next_bill = 1001
                    if not df_coll.empty and 'bill_no' in df_coll.columns:
                        next_bill = int(pd.to_numeric(df_coll['bill_no'], errors='coerce').max() + 1)
                    
                    bill_no = st.number_input("Bill No", value=next_bill)
                with c2:
                    mode = st.selectbox("Mode", ["Online", "Cash", "Cheque"])
                    amt = st.number_input("Amount Received", value=2100)
                
                months = st.multiselect("Paying for Months", ["Jan-25", "Feb-25", "Mar-25", "Apr-25", "May-25", "Jun-25", "Jul-25", "Aug-25", "Sep-25", "Oct-25", "Nov-25", "Dec-25", "Jan-26", "Feb-26"])
                
                if st.form_submit_button("Submit Payment"):
                    new_payment = pd.DataFrame([{
                        "date": bill_date.strftime("%d-%m-%Y"),
                        "bill_no": bill_no,
                        "Flat": selected_flat,
                        "owner": owner_row['owner'],
                        "months_paid": ", ".join(months),
                        "amount_received": amt,
                        "mode": mode
                    }])
                    updated_df = pd.concat([df_coll, new_payment], ignore_index=True)
                    conn.update(worksheet="Collections", data=updated_df)
                    st.success("Payment Recorded!")
                    st.rerun()

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


