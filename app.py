import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

MONTHLY_MAINT = 2100
st.set_page_config(page_title="DBE Society Management", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=300)
def safe_read_gsheet(sheet_name):
    try:
        base_url = st.secrets["connections"]["gsheets"]["spreadsheet"].split("/edit")[0]
        csv_url = base_url + "/export?format=csv&sheet=" + sheet_name
        df = pd.read_csv(csv_url)
        # Clean columns: lowercase, strip, and replace spaces with underscores
        df.columns = df.columns.astype(str).str.lower().str.strip().str.replace(" ", "_")
        return df
    except Exception as e:
        st.error(f"Failed to load {sheet_name}: {e}")
        return pd.DataFrame()

# --- AUTH ---
with st.sidebar:
    pwd = st.text_input("Admin Password", type="password")
    is_admin = pwd == st.secrets.get("admin_password", "")

tab1, tab2, tab3, tab4 = st.tabs(["Maintenance", "Owners", "Expenses", "Collections"])

# --- TAB 1: MAINTENANCE ---
with tab1:
    df_owners = safe_read_gsheet("Owners")
    df_coll = safe_read_gsheet("Collections")
    
    if df_owners.empty:
        st.error("Owners sheet missing or empty!")
        st.stop()
    
    col1, col2 = st.columns([2, 1])
    with col1:
        # Find the flat column (usually 'flat')
        flat_col = next((c for c in df_owners.columns if 'flat' in c), df_owners.columns[0])
        flats = sorted(df_owners[flat_col].dropna().unique())
        selected_flat = st.selectbox("Select Flat", flats)
    
    with col2:
        owner_row = df_owners[df_owners[flat_col] == selected_flat].iloc[0]
        # Find owner name column
        name_col = next((c for c in df_owners.columns if 'owner' in c or 'name' in c), None)
        st.info(f"**Owner:** {owner_row.get(name_col, 'N/A')}")

    # === DUES CALCULATION ENGINE ===
    today = datetime.now()
    # Months from Jan 2025 to Feb 2026 = 14 months
    total_months = (today.year - 2025) * 12 + today.month

    # 1. Get Opening Due (Safe lookup)
    due_col = next((c for c in df_owners.columns if 'due' in c or 'opening' in c), None)
    opening_due = pd.to_numeric(owner_row.get(due_col, 0), errors='coerce')
    if pd.isna(opening_due): opening_due = 0

    # 2. Get Total Paid (Safe lookup)
    total_paid = 0.0
    if not df_coll.empty:
        # Standardize collection columns
        c_flat_col = next((c for c in df_coll.columns if 'flat' in c), None)
        c_amt_col = next((c for c in df_coll.columns if 'received' in c or 'amount' in c), None)
        
        if c_flat_col and c_amt_col:
            # Clean matching for flat names
            flat_key = str(selected_flat).strip().upper()
            payments = df_coll[df_coll[c_flat_col].astype(str).str.strip().str.upper() == flat_key]
            total_paid = pd.to_numeric(payments[c_amt_col], errors='coerce').sum()

    # 3. Final Math
    current_due = (opening_due + (total_months * MONTHLY_MAINT)) - total_paid

    # --- DISPLAY METRIC ---
    st.metric("Total Outstanding Due", f"₹ {int(current_due):,}")
    
    with st.expander("🔍 Calculation Breakdown"):
        st.write(f"**Period:** Jan 2025 to {today.strftime('%b %Y')} ({total_months} months)")
        st.write(f"**Opening Balance (Jan 25):** ₹{int(opening_due):,}")
        st.write(f"**Maintenance Accrued:** {total_months} × ₹2,100 = ₹{int(total_months*MONTHLY_MAINT):,}")
        st.write(f"**Total Paid to Date:** ₹{int(total_paid):,}")

    # --- ADMIN PAYMENT FORM ---
    if is_admin:
        st.divider()
        with st.form("payment_form", clear_on_submit=True):
            st.subheader("Record New Payment")
            c1, c2 = st.columns(2)
            with c1:
                p_date = st.date_input("Payment Date", today)
                # Next Bill Logic
                next_bill = 1001
                if not df_coll.empty:
                    bill_col = next((c for c in df_coll.columns if 'bill' in c), None)
                    if bill_col:
                        bills = pd.to_numeric(df_coll[bill_col], errors='coerce').dropna()
                        if not bills.empty: next_bill = int(bills.max()) + 1
                p_bill = st.number_input("Bill No", value=next_bill)
            with c2:
                p_mode = st.selectbox("Mode", ["Online", "Cash", "Cheque"])
                months_list = [(datetime(2025, 1, 1) + pd.DateOffset(months=i)).strftime('%b-%Y') for i in range(24)]
                p_months = st.multiselect("Paying for Months", months_list)
                p_amt = st.number_input("Amount Received", value=len(p_months)*MONTHLY_MAINT if p_months else MONTHLY_MAINT)
            
            if st.form_submit_button("Save & Sync to Cloud"):
                new_payment = pd.DataFrame([{
                    "date": p_date.strftime("%d-%m-%Y"),
                    "bill_no": p_bill,
                    "flat": selected_flat,
                    "owner": str(owner_row.get(name_col, '')),
                    "months_paid": ", ".join(p_months),
                    "amount_received": p_amt,
                    "mode": p_mode
                }])
                updated_df = pd.concat([df_coll, new_payment], ignore_index=True)
                conn.update(worksheet="Collections", data=updated_df)
                st.success("✅ Payment saved and synced!")
                st.cache_data.clear()
                st.rerun()

# --- TABS 2, 3, 4 (Reports) ---
with tab2:
    st.subheader("Owners Records")
    st.dataframe(df_owners, use_container_width=True)

with tab3:
    st.subheader("Expense Log")
    df_exp = safe_read_gsheet("Expenses")
    st.dataframe(df_exp, use_container_width=True)
    if is_admin:
        with st.form("exp_form"):
            e1, e2, e3 = st.columns(3)
            with e1:
                edate = st.date_input("Date")
                ehead = st.selectbox("Category", ["Security", "Electricity", "Diesel", "Salary", "Misc"])
            with e2:
                eamt = st.number_input("Amount", min_value=0.0)
            with e3:
                edesc = st.text_input("Description")
            if st.form_submit_button("Save Expense"):
                new_exp = pd.DataFrame([{"date": edate.strftime("%d-%m-%Y"), "head": ehead, "description": edesc, "amount": eamt, "mode": "Cash"}])
                updated_exp = pd.concat([df_exp, new_exp], ignore_index=True)
                conn.update(worksheet="Expenses", data=updated_exp)
                st.cache_data.clear()
                st.rerun()

with tab4:
    st.subheader("Collection History")
    st.dataframe(df_coll, use_container_width=True)
