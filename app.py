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
        df.columns = df.columns.astype(str).str.lower().str.strip().str.replace(" ", "_")
        cols = pd.Series(df.columns)
        for dup in df.columns[df.columns.duplicated()].unique():
            mask = df.columns == dup
            df.columns[mask] = [dup + "_" + str(i) if i > 0 else dup 
                              for i in range(df.columns.tolist().count(dup))]
        return df
    except Exception as e:
        st.error("Failed to load " + sheet_name + ": " + str(e))
        return pd.DataFrame()

with st.sidebar:
    pwd = st.text_input("Admin Password", type="password")
    is_admin = pwd == st.secrets["admin_password"]

tab1, tab2, tab3, tab4 = st.tabs(["Maintenance", "Owners", "Expenses", "Collections"])

with tab1:
    df_owners = safe_read_gsheet("Owners")
    df_coll = safe_read_gsheet("Collections")
    
    if df_owners.empty:
        st.error("Owners sheet missing!")
        st.stop()
    
    col1, col2 = st.columns([2, 1])
    with col1:
        selected_flat = st.selectbox("Select Flat", sorted(df_owners['flat'].dropna().unique()))
    with col2:
        owner_row = df_owners[df_owners['flat'] == selected_flat].iloc[0]
        st.info("Owner: " + str(owner_row.get('owner', 'N/A')))
    
    today = datetime.now()
    total_months = (today.year - 2025) * 12 + today.month
    
    opening_due = 0.0
    flat_col = next((col for col in df_owners.columns if 'flat' in col.lower()), None)
    due_col = next((col for col in df_owners.columns if 'due' in col.lower()), None)
    if flat_col and due_col:
        row = df_owners[df_owners[flat_col].astype(str).str.upper() == selected_flat.upper()]
        if not row.empty:
            opening_due = float(str(row.iloc[0][due_col]).replace("Rs", "").replace(",", "").strip() or 0)
    
    total_paid = 0.0
    if not df_coll.empty:
        flat_col_c = next((col for col in df_coll.columns if 'flat' in col.lower()), 'flat')
        amt_col = next((col for col in df_coll.columns if any(x in col.lower() for x in ['amount_received', 'amount', 'received'])), 'amount_received')
        
        if flat_col_c in df_coll.columns:
            flat_key = str(selected_flat).strip().upper()
            payments = df_coll[df_coll[flat_col_c].astype(str).str.strip().str.upper() == flat_key]
            
            if payments.empty:
                payments = df_coll[df_coll[flat_col_c].astype(str).str.strip().str.upper().str.replace('-','') == flat_key.replace('-','')]
            
            if not payments.empty and amt_col in payments.columns:
                total_paid = float(pd.to_numeric(payments[amt_col], errors='coerce').sum())
    
    current_due = max(0, opening_due + (total_months * MONTHLY_MAINT) - total_paid)
    st.metric("Total Outstanding Due", "Rs" + str(int(current_due)))
    
    with st.expander("Calculation Breakdown"):
        st.write("Period: Jan 2025 to " + today.strftime('%b %Y') + " (" + str(total_months) + " months)")
        st.write("Opening Due: Rs" + str(int(opening_due)))
        st.write("Expected: Rs" + str(int(total_months * MONTHLY_MAINT)))
        st.write("Total Paid: Rs" + str(int(total_paid)))
    
    if is_admin:
        st.divider()
        with st.form("payment_form"):
            c1, c2 = st.columns(2)
            with c1:
                p_date = st.date_input("Payment Date", datetime.now())
                next_bill = 1001
                if 'bill_no' in df_coll.columns:
                    bills = pd.to_numeric(df_coll['bill_no'], errors='coerce').dropna()
                    if not bills.empty:
                        next_bill = int(bills.max()) + 1
                p_bill = st.number_input("Bill No", value=next_bill, min_value=1001)
            with c2:
                p_mode = st.selectbox("Mode", ["Cash", "Online", "Cheque"])
                months_list = [m.strftime('%b') + "-" + str(m.year) for m in pd.date_range("2025-01-01", periods=26, freq="MS")]
                p_months = st.multiselect("Months", months_list)
                p_amt = st.number_input("Amount", value=len(p_months)*MONTHLY_MAINT if p_months else MONTHLY_MAINT)
            
            if st.form_submit_button("Save Payment"):
                new_payment = pd.DataFrame([{
                    "date": p_date.strftime("%d-%m-%Y"),
                    "bill_no": p_bill,
                    "flat": selected_flat,
                    "owner": str(owner_row.get('owner', '')),
                    "months_paid": ", ".join(p_months),
                    "amount_received": p_amt,
                    "mode": p_mode
                }])
                updated_df = pd.concat([df_coll, new_payment], ignore_index=True)
                conn.update(worksheet="Collections", data=updated_df)
                st.success("Payment saved!")
                st.cache_data.clear()
                st.rerun()

with tab2:
    st.subheader("Owners")
    st.dataframe(safe_read_gsheet("Owners"), use_container_width=True)

with tab3:
    st.subheader("Expenses")
    df_exp = safe_read_gsheet("Expenses")
    st.dataframe(df_exp, use_container_width=True)
    
    if is_admin:
        st.divider()
        with st.form("expense_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                e_date = st.date_input("Date", datetime.now())
                e_head = st.selectbox("Category", ["Security", "Electricity", "Diesel", "Salary", "Misc"])
            with c2:
                e_amt = st.number_input("Amount", min_value=0.01)
            with c3:
                e_desc = st.text_input("Description")
            
            if st.form_submit_button("Save Expense"):
                new_exp = pd.DataFrame([{
                    "date": e_date.strftime("%d-%m-%Y"),
                    "head": e_head,
                    "description": e_desc,
                    "amount": e_amt,
                    "mode": "Cash"
                }])
                updated_exp = pd.concat([df_exp, new_exp], ignore_index=True)
                conn.update(worksheet="Expenses", data=updated_exp)
                st.success("Expense saved!")
                st.cache_data.clear()
                st.rerun()

with tab4:
    st.subheader("Collections") 
    st.dataframe(safe_read_gsheet("Collections"), use_container_width=True)
