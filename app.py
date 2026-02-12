import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# ================= 1. CONFIGURATION =================
MONTHLY_MAINT = 2100
st.set_page_config(page_title="DBE Society Management Pro", layout="wide")

# Connection for WRITING data
conn = st.connection("gsheets", type=GSheetsConnection)

# ================= 2. DATA LOADING (FIXED) =================
def load_sheet(name):
    """Direct CSV method to bypass the GSheets Tab Mismatch bug"""
    try:
        base_url = st.secrets["connections"]["gsheets"]["spreadsheet"].split("/edit")[0]
        csv_url = f"{base_url}/export?format=csv&sheet={name}"
        df = pd.read_csv(csv_url)
        # Standardize: remove spaces and lowercase for calculation logic
        df.columns = df.columns.astype(str).str.strip()
        return df
    except Exception as e:
        st.error(f"Failed to load tab '{name}': {e}")
        return pd.DataFrame()

# ================= 3. AUTHENTICATION =================
with st.sidebar:
    st.header("🔐 Admin Panel")
    pwd = st.text_input("Enter Admin Password", type="password")
    is_admin = (pwd == st.secrets["admin_password"])
    if is_admin: st.success("Admin Access Granted")

# ================= 4. MAIN INTERFACE =================
st.title("🏢 DBE Society Management Pro v2.0")
tab1, tab2, tab3, tab4 = st.tabs(["💰 Maintenance", "💸 Expenses", "📋 Collections History", "📊 Summary Report"])

# --- LOAD ALL DATA ---
df_owners = load_sheet("Owners")
df_coll = load_sheet("Collections")
df_exp = load_sheet("Expenses")

# ================= TAB 1: MAINTENANCE =================
with tab1:
    if not df_owners.empty:
        # Standardize Owners columns for logic
        df_o = df_owners.copy()
        df_o.columns = df_o.columns.str.lower()
        
        c1, c2 = st.columns(2)
        with c1:
            selected_flat = st.selectbox("Select Flat", df_o['flat'].unique())
            owner_row = df_o[df_o['flat'] == selected_flat].iloc[0]
            st.write(f"**Owner Name:** {owner_row.get('owner', 'N/A')}")

        # --- DUES LOGIC ---
        today = datetime.now()
        total_months = (today.year - 2025) * 12 + today.month
        
        # Safe column finding for 'Due'
        due_col = next((c for c in df_o.columns if 'due' in c), None)
        opening_due = pd.to_numeric(owner_row[due_col], errors='coerce') if due_col else 0
        if pd.isna(opening_due): opening_due = 0

        # Safe column finding for 'Amount Received' in Collections
        paid_amt = 0
        if not df_coll.empty:
            df_c = df_coll.copy()
            df_c.columns = df_c.columns.str.lower()
            c_flat = next((c for c in df_c.columns if 'flat' in c), 'flat')
            c_amt = next((c for c in df_c.columns if 'received' in c or 'amount' in c), 'amount_received')
            
            paid_rows = df_c[df_c[c_flat].astype(str).str.upper() == str(selected_flat).upper()]
            paid_amt = pd.to_numeric(paid_rows[c_amt], errors='coerce').sum()

        current_due = (opening_due + (total_months * MONTHLY_MAINT)) - paid_amt
        st.metric("Total Outstanding Balance", f"₹ {current_due:,.0f}")

        if is_admin:
            st.divider()
            st.subheader("📝 Record Payment")
            with st.form("pay_form", clear_on_submit=True):
                col_a, col_b = st.columns(2)
                with col_a:
                    p_date = st.date_input("Date")
                    # Increment Bill No
                    next_bill = 1001
                    if not df_coll.empty:
                        # Logic to find bill_no column
                        bill_col = next((c for c in df_coll.columns if 'bill' in c.lower()), None)
                        if bill_col:
                            next_bill = int(pd.to_numeric(df_coll[bill_col], errors='coerce').max() + 1)
                    p_bill = st.number_input("Bill No", value=next_bill)
                with col_b:
                    p_mode = st.selectbox("Mode", ["Online", "Cash", "Cheque"])
                    p_months = st.multiselect("Months", ["Jan-25", "Feb-25", "Mar-25", "Apr-25", "May-25", "Jun-25", "Jul-25", "Aug-25", "Sep-25", "Oct-25", "Nov-25", "Dec-25", "Jan-26", "Feb-26"])
                
                p_amt = st.number_input("Amount", value=len(p_months)*2100 if p_months else 2100)
                
                if st.form_submit_button("Save Payment"):
                    # Use exact column names for your sheet
                    new_row = pd.DataFrame([{
                        "date": p_date.strftime("%d-%m-%Y"),
                        "flat": selected_flat,
                        "owner": owner_row.get('owner'),
                        "months_paid": ", ".join(p_months),
                        "amount_received": p_amt,
                        "mode": p_mode,
                        "bill_no": p_bill
                    }])
                    updated_df = pd.concat([df_coll, new_row], ignore_index=True)
                    conn.update(worksheet="Collections", data=updated_df)
                    st.success("Payment Saved!")
                    st.rerun()

# ================= TAB 2: EXPENSES =================
with tab2:
    if is_admin:
        st.subheader("🖋️ Record New Expense")
        with st.form("exp_form", clear_on_submit=True):
            e1, e2, e3 = st.columns(3)
            with e1:
                edate = st.date_input("Expense Date")
                ehead = st.selectbox("Category", ["Security", "Electricity", "Diesel", "Salary", "Repairs", "Misc"])
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
                st.success("Expense Recorded!")
                st.rerun()
    
    st.subheader("Expense Log")
    st.dataframe(df_exp, use_container_width=True)

# ================= TAB 3: COLLECTIONS =================
with tab3:
    st.subheader("All Collection Records")
    st.dataframe(df_coll, use_container_width=True)

# ================= TAB 4: SUMMARY =================
with tab4:
    st.subheader("Monthly Financial Summary")
    
    # Simple calculation for dashboard
    total_in = pd.to_numeric(df_coll[next((c for c in df_coll.columns if 'received' in c.lower() or 'amount' in c.lower()), df_coll.columns[0])], errors='coerce').sum() if not df_coll.empty else 0
    total_out = pd.to_numeric(df_exp[next((c for c in df_exp.columns if 'amount' in c.lower()), df_exp.columns[0])], errors='coerce').sum() if not df_exp.empty else 0
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Collections", f"₹ {total_in:,.0f}")
    m2.metric("Total Expenses", f"₹ {total_out:,.0f}")
    m3.metric("Net Surplus", f"₹ {(total_in - total_out):,.0f}", delta_color="normal")
