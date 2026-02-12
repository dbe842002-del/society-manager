import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURATION ---
MONTHLY_MAINT = 2100
st.set_page_config(page_title="DBE Society Management", layout="wide")

# Library used ONLY for writing/saving
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 2. RELIABLE DATA LOADER ---
def load_sheet(name):
    try:
        # Direct export link is the only way to avoid the "Tab Mismatch" bug
        base_url = st.secrets["connections"]["gsheets"]["spreadsheet"].split("/edit")[0]
        csv_url = f"{base_url}/export?format=csv&sheet={name}"
        df = pd.read_csv(csv_url)
        # Clean columns: remove spaces and make lowercase for logic
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Failed to load {name}: {e}")
        return pd.DataFrame()

# --- 3. ADMIN AUTH ---
with st.sidebar:
    pwd = st.text_input("Admin Password", type="password")
    is_admin = (pwd == st.secrets["admin_password"])

tab1, tab2 = st.tabs(["💰 Maintenance", "📊 Records"])

with tab1:
    df_owners = load_sheet("Owners")
    df_coll = load_sheet("Collections")

    if not df_owners.empty:
        # Standardize Owners columns for selection
        df_owners.columns = df_owners.columns.str.lower()
        
        col1, col2 = st.columns(2)
        with col1:
            selected_flat = st.selectbox("Select Flat", df_owners['flat'].unique())
            owner_row = df_owners[df_owners['flat'] == selected_flat].iloc[0]
            st.write(f"**Owner:** {owner_row['owner']}")

        # --- MATH ENGINE ---
        today = datetime.now()
        total_months = (today.year - 2025) * 12 + today.month
        
        # 1. Clean Owners columns for this calculation
        df_owners.columns = df_owners.columns.str.strip().str.lower()
        opening_due = pd.to_numeric(owner_row.get('opening due', 0), errors='coerce') or 0
        
        # 2. Clean Collections columns for this calculation
        paid_amt = 0
        if not df_coll.empty:
            # Force lowercase and strip spaces on Collections headers
            df_coll.columns = df_coll.columns.str.strip().str.lower()
            
            # Find the flat column and amount column regardless of slight name variations
            c_flat = next((c for c in df_coll.columns if 'flat' in c), None)
            c_amt = next((c for c in df_coll.columns if 'received' in c or 'amount' in c), None)

            if c_flat and c_amt:
                # Match flat exactly (case insensitive)
                paid_rows = df_coll[df_coll[c_flat].astype(str).str.upper() == str(selected_flat).upper()]
                paid_amt = pd.to_numeric(paid_rows[c_amt], errors='coerce').sum()
            else:
                st.error(f"Could not find required columns in Collections. Found: {list(df_coll.columns)}")

        # 3. Final Calculation
        current_due = (opening_due + (total_months * 2100)) - paid_amt

        # --- DISPLAY RESULTS ---
        st.metric("Total Outstanding Due", f"₹ {current_due:,.0f}")
        
        with st.expander("🔍 Calculation Breakdown"):
            st.write(f"Period: Jan 2025 to {today.strftime('%b %Y')} ({total_months} months)")
            st.write(f"Fixed Maintenance: {total_months} × ₹2100 = ₹{total_months*MONTHLY_MAINT:,.0f}")
            st.write(f"Opening Due (Jan 2025): ₹{opening_due:,.0f}")
            st.write(f"Total Amount Paid: ₹{paid_amt:,.0f}")

        # --- ADMIN PAYMENT ENTRY ---
        if is_admin:
            st.divider()
            st.subheader("📝 Record New Payment")
            with st.form("pay_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                with c1:
                    p_date = st.date_input("Payment Date", datetime.now())
                    # Auto-increment Bill No
                    next_bill = 1001
                    if not df_coll.empty and 'bill_no' in df_coll.columns:
                        next_bill = int(pd.to_numeric(df_coll['bill_no'], errors='coerce').max() + 1)
                    p_bill = st.number_input("Bill No", value=next_bill)
                with c2:
                    p_mode = st.selectbox("Mode", ["Cash", "Online", "Cheque"])
                    p_months = st.multiselect("Paying for Months", ["Jan-25", "Feb-25", "Mar-25", "Apr-25", "May-25", "Jun-25", "Jul-25", "Aug-25", "Sep-25", "Oct-25", "Nov-25", "Dec-25", "Jan-26", "Feb-26"])
                
                p_amt = st.number_input("Amount Received", value=len(p_months)*2100 if p_months else 2100)

                if st.form_submit_button("Save & Sync"):
                    new_data = pd.DataFrame([{
                        "date": p_date.strftime("%d-%m-%Y"),
                        "flat": selected_flat,
                        "owner": owner_row['owner'],
                        "months_paid": ", ".join(p_months),
                        "amount_received": p_amt,
                        "mode": p_mode,
                        "bill_no": p_bill
                    }])
                    # Write to GSheets
                    updated_df = pd.concat([df_coll, new_data], ignore_index=True)
                    conn.update(worksheet="Collections", data=updated_df)
                    st.success("Payment saved to Google Sheet!")
                    st.rerun()

with tab4:
    st.subheader("Payment History")
    st.dataframe(df_coll, use_container_width=True)

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










